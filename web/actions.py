"""Sync wrappers around join/leave/interested that mirror the bot's behavior.

Each action:
  1. Validates the game (exists, not cancelled, not already started, etc.)
  2. Mutates the DB via data_utils (add_player / remove_player / etc.)
  3. Fires the Telegram side-effects (update posted message, DM the GM)
     using a standalone `telegram.Bot` instance, driven by asyncio.run().

Failures on the Telegram side are logged but never fail the request — the DB
mutation is the source of truth.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from telegram import Bot

import data_utils

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    ok: bool
    message: str
    category: str = "info"  # "success" | "info" | "warning" | "error"


_bot_instance = None


def _get_bot() -> Bot:
    global _bot_instance
    if _bot_instance is None:
        token = os.getenv("TELEGRAM_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_TOKEN environment variable is not set")
        _bot_instance = Bot(token=token)
    return _bot_instance


def _user_shim(user_row):
    """Build a telegram.User-like object from a DB users row."""
    display = user_row.get("custom_name") or user_row.get("display_name") or ""
    return SimpleNamespace(
        id=user_row["user_id"],
        username=user_row.get("username"),
        full_name=display or (user_row.get("username") or str(user_row["user_id"])),
    )


def _is_game_started(game) -> bool:
    game_date = game.get("game_date")
    if not game_date:
        return False
    try:
        dt = datetime.strptime(game_date, "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=data_utils.TIMEZONE)
        return datetime.now(data_utils.TIMEZONE) >= dt
    except ValueError:
        return False


async def _sync_telegram_after_join(game, game_id, user_shim):
    from bot.handlers.post import update_posted_message, _notify_creator
    bot = _get_bot()
    try:
        await update_posted_message(bot, game, game_id)
    except Exception as e:
        logger.warning("WEB update_posted_message failed game=%s: %s", game_id, e)
    try:
        await _notify_creator(bot, game, user_shim, "записався на")
    except Exception as e:
        logger.warning("WEB _notify_creator (join) failed game=%s: %s", game_id, e)


async def _sync_telegram_after_leave(game, game_id, user_shim):
    from bot.handlers.post import update_posted_message, _notify_creator
    bot = _get_bot()
    try:
        await update_posted_message(bot, game, game_id)
    except Exception as e:
        logger.warning("WEB update_posted_message failed game=%s: %s", game_id, e)
    try:
        await _notify_creator(bot, game, user_shim, "відписався від")
    except Exception as e:
        logger.warning("WEB _notify_creator (leave) failed game=%s: %s", game_id, e)


async def _sync_telegram_after_interested(game, game_id, user_shim, notify_gm: bool):
    from bot.handlers.post import update_posted_message, _notify_creator_interested
    bot = _get_bot()
    try:
        await update_posted_message(bot, game, game_id)
    except Exception as e:
        logger.warning("WEB update_posted_message failed game=%s: %s", game_id, e)
    if notify_gm:
        try:
            await _notify_creator_interested(bot, game, user_shim)
        except Exception as e:
            logger.warning("WEB _notify_creator_interested failed game=%s: %s", game_id, e)


def join_game(game_id: str, user_id: int) -> ActionResult:
    game = data_utils.get_game(game_id)
    if not game:
        return ActionResult(False, "Ця гра більше не існує.", "error")
    if game.get("cancelled"):
        return ActionResult(False, "Ця гра скасована.", "warning")
    if _is_game_started(game):
        return ActionResult(False, "Гра вже розпочалась.", "warning")
    if user_id in game.get("players", []):
        return ActionResult(False, "Ви вже записані.", "info")
    if len(game.get("players", [])) >= game["max_players"]:
        return ActionResult(False, "Гра заповнена.", "warning")

    used_slot = False
    if data_utils.needs_slot(game, user_id):
        slots = data_utils.get_slots(user_id)
        if slots <= 0:
            return ActionResult(False, "У вас немає слотів для запису.", "warning")
        data_utils.consume_slot(user_id)
        used_slot = True

    data_utils.add_player(game_id, user_id, used_slot=used_slot)
    logger.info("WEB JOIN game=%s user=%s used_slot=%s", game_id, user_id, used_slot)

    game = data_utils.get_game(game_id)
    user_row = data_utils.get_user(user_id)
    if user_row:
        asyncio.run(_sync_telegram_after_join(game, game_id, _user_shim(user_row)))
    return ActionResult(True, "Ви записались!", "success")


def leave_game(game_id: str, user_id: int) -> ActionResult:
    game = data_utils.get_game(game_id)
    if not game:
        return ActionResult(False, "Ця гра більше не існує.", "error")
    if user_id not in game.get("players", []):
        return ActionResult(False, "Ви не були записані.", "info")

    players_info = data_utils.get_players_with_slots(game_id)
    player_used_slot = any(
        p["user_id"] == user_id and p["used_slot"] for p in players_info
    )

    data_utils.remove_player(game_id, user_id)
    if player_used_slot:
        data_utils.add_slots(user_id, 1)
    logger.info("WEB LEAVE game=%s user=%s refunded=%s", game_id, user_id, player_used_slot)

    game = data_utils.get_game(game_id)
    user_row = data_utils.get_user(user_id)
    if user_row:
        asyncio.run(_sync_telegram_after_leave(game, game_id, _user_shim(user_row)))
    return ActionResult(True, "Ви відписались.", "success")


def toggle_interested(game_id: str, user_id: int) -> ActionResult:
    game = data_utils.get_game(game_id)
    if not game:
        return ActionResult(False, "Ця гра більше не існує.", "error")
    if game.get("cancelled"):
        return ActionResult(False, "Ця гра скасована.", "warning")
    if _is_game_started(game):
        return ActionResult(False, "Гра вже розпочалась.", "warning")
    if user_id in game.get("players", []):
        return ActionResult(False, "Ви вже записані — «Зацікавлений» непотрібний.", "info")

    if data_utils.is_interested(game_id, user_id):
        data_utils.remove_interested(game_id, user_id)
        msg = "Прибрано з зацікавлених."
        notify_gm = False
    else:
        data_utils.add_interested(game_id, user_id)
        msg = "Додано до зацікавлених."
        notify_gm = True
    logger.info("WEB INTERESTED_TOGGLE game=%s user=%s notify=%s", game_id, user_id, notify_gm)

    game = data_utils.get_game(game_id)
    user_row = data_utils.get_user(user_id)
    if user_row:
        asyncio.run(
            _sync_telegram_after_interested(game, game_id, _user_shim(user_row), notify_gm)
        )
    return ActionResult(True, msg, "success")
