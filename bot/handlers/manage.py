import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import data_utils
from bot.config import MAIN_CHANNEL
from bot.handlers.common import (
    format_game, build_announcement_link_html, _DAY_NAMES_UK, resolve_player_names,
)
from bot.handlers.decorators import ensure_user, require_private, require_gm
from bot.handlers.post import update_posted_message, delete_posted_message

logger = logging.getLogger(__name__)
from bot.handlers.post import notify_cancellation
from bot.keyboards import (
    game_list_keyboard, edit_field_keyboard, confirm_delete_keyboard, player_list_keyboard,
    confirm_cancel_keyboard,
)

# Conversation states
EDIT_SELECT, EDIT_FIELD, EDIT_VALUE = range(6, 9)
DELETE_SELECT, DELETE_CONFIRM = range(9, 11)
KICK_SELECT_GAME, KICK_SELECT_PLAYER = range(11, 13)
CANCEL_SELECT, CANCEL_CONFIRM = range(13, 15)
UNCANCEL_SELECT = 15


def _get_manageable_games(user_id):
    """Get games the user can manage: own games for GM, all games for admin."""
    if data_utils.is_admin(user_id):
        return data_utils.get_all_games()
    return data_utils.get_games_by_creator(user_id)


def _get_cancellable_games(user_id):
    """Manageable games that are NOT currently cancelled."""
    return [g for g in _get_manageable_games(user_id) if not g.get("cancelled")]


def _get_cancelled_games(user_id):
    """Manageable games that ARE currently cancelled."""
    return [g for g in _get_manageable_games(user_id) if g.get("cancelled")]


# ---------------------------------------------------------------------------
# /view
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def view_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    games = _get_manageable_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає ігор.")
        return

    text = "\n\n".join(format_game(g) for g in games)
    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /edit conversation
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    games = _get_manageable_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає ігор для редагування.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Оберіть гру для редагування:",
        reply_markup=game_list_keyboard(games, "edit_sel"),
    )
    return EDIT_SELECT


@ensure_user
async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END

    context.user_data["edit_game_id"] = game_id
    await query.edit_message_text(
        f"Редагування: <b>{game['title']}</b>\n\nОберіть поле:",
        parse_mode="HTML",
        reply_markup=edit_field_keyboard(),
    )
    return EDIT_FIELD


@ensure_user
async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    field = query.data.split(":", 1)[1]
    context.user_data["edit_field"] = field

    labels = {
        "title": "назву",
        "description": "опис",
        "max_players": "макс. гравців",
        "location": "місце проведення",
        "tone": "тон гри",
        "duration": "протяжність",
        "game_date": "дату (РРРР-ММ-ДД ГГ:ХХ)",
    }
    await query.edit_message_text(f"Введіть нове значення для {labels[field]}:")
    return EDIT_VALUE


@ensure_user
async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("edit_field")
    game_id = context.user_data.get("edit_game_id")
    if not field or not game_id:
        # State was wiped (e.g. another conversation cleared user_data).
        context.user_data.clear()
        await update.message.reply_text("Сесія редагування скинулась. Почніть знову з /edit.")
        return ConversationHandler.END
    text = update.message.text
    value = text

    if field == "max_players":
        try:
            value = int(text)
            if value < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Будь ласка, введіть додатнє число:")
            return EDIT_VALUE

    if field == "game_date":
        try:
            datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text("Невірний формат. Використовуйте РРРР-ММ-ДД ГГ:ХХ:")
            return EDIT_VALUE

    data_utils.update_game(game_id, {field: value})
    logger.info("EDIT game=%s field=%s by user=%s", game_id, field, update.effective_user.id)
    context.user_data.clear()

    game = data_utils.get_game(game_id)
    await update.message.reply_text(
        f"Гру оновлено!\n\n{format_game(game)}", parse_mode="HTML"
    )

    # Auto-sync posted message in announcements
    if game.get("message_id"):
        await update_posted_message(context.bot, game, game_id)

    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /delete conversation
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    games = _get_manageable_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає ігор для видалення.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Оберіть гру для видалення:",
        reply_markup=game_list_keyboard(games, "del_sel"),
    )
    return DELETE_SELECT


@ensure_user
async def delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"Видалити <b>{game['title']}</b>?\n\n{format_game(game)}",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard(game_id),
    )
    return DELETE_CONFIRM


@ensure_user
async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("del_no"):
        await query.edit_message_text("Видалення скасовано.")
        return ConversationHandler.END

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if game:
        # Delete posted message from announcements
        await delete_posted_message(context.bot, game)

        # Refund slots to players who used one
        players_info = data_utils.get_players_with_slots(game_id)
        refunded = 0
        for p in players_info:
            if p["used_slot"]:
                data_utils.add_slots(p["user_id"], 1)
                refunded += 1

        data_utils.delete_game(game_id)
        logger.info(
            "DELETE game=%s by user=%s refunded=%d",
            game_id, update.effective_user.id, refunded,
        )

        msg = "Гру видалено."
        if refunded > 0:
            msg += f" Повернуто слоти {refunded} гравцям."
        await query.edit_message_text(msg)
    else:
        await query.edit_message_text("Гру не знайдено.")

    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /games + /mygames — browse upcoming games
# ---------------------------------------------------------------------------

def _filter_and_sort_upcoming(games):
    now = datetime.now(data_utils.TIMEZONE)
    upcoming = []
    for g in games:
        if g.get("cancelled"):
            continue
        if not g.get("message_id") or not g.get("game_date"):
            continue
        try:
            dt = datetime.strptime(g["game_date"], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        dt = dt.replace(tzinfo=data_utils.TIMEZONE)
        if dt < now:
            continue
        upcoming.append((dt, g))
    upcoming.sort(key=lambda x: x[0])
    return upcoming


def _format_browse_list(upcoming):
    if not upcoming:
        return None
    lines = []
    current_date = None
    for dt, g in upcoming:
        d = dt.date()
        if d != current_date:
            if lines:
                lines.append("")
            day_name = _DAY_NAMES_UK[dt.weekday()]
            lines.append(f"<b>{day_name}, {dt.strftime('%d.%m')}</b>")
            current_date = d
        title = build_announcement_link_html(g["message_id"], g["title"])
        time = dt.strftime("%H:%M")
        location = g.get("location") or "—"
        count = f"{len(g.get('players', []))}/{g['max_players']}"
        interested_n = len(g.get("interested", []))
        if interested_n:
            count = f"{count} +{interested_n}"
        lines.append(f"• {title} · {time} · {location} · {count}")
    return "\n".join(lines)


@ensure_user
@require_private
async def available_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upcoming = _filter_and_sort_upcoming(data_utils.get_all_games())
    text = _format_browse_list(upcoming) or "Найближчих ігор немає."
    await update.message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True,
    )


@ensure_user
@require_private
async def my_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upcoming = _filter_and_sort_upcoming(
        data_utils.get_games_by_player(update.effective_user.id)
    )
    text = _format_browse_list(upcoming) or "Ви не записані на жодну з найближчих ігор."
    await update.message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
# /kick — GM removes a player from a game
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def kick_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    games = _get_manageable_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає ігор.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Оберіть гру:",
        reply_markup=game_list_keyboard(games, "kick_game"),
    )
    return KICK_SELECT_GAME


@ensure_user
async def kick_select_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END
    if not game.get("players"):
        await query.edit_message_text("На цю гру ніхто не записаний.")
        return ConversationHandler.END

    context.user_data["kick_game_id"] = game_id
    player_names = await resolve_player_names(
        context.bot, MAIN_CHANNEL["chat_id"], game["players"],
    )
    await query.edit_message_text(
        f"Кого зняти з <b>{game['title']}</b>?",
        parse_mode="HTML",
        reply_markup=player_list_keyboard(game["players"], player_names),
    )
    return KICK_SELECT_PLAYER


@ensure_user
async def kick_select_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = context.user_data.get("kick_game_id")
    if not game_id:
        context.user_data.clear()
        await query.edit_message_text("Сесія скинулась. Почніть знову з /kick.")
        return ConversationHandler.END

    player_id = int(query.data.split(":", 1)[1])
    game = data_utils.get_game(game_id)
    if not game or player_id not in game.get("players", []):
        await query.edit_message_text("Гравця вже немає в цій грі.")
        context.user_data.clear()
        return ConversationHandler.END

    # Refund slot if it was used.
    players_info = data_utils.get_players_with_slots(game_id)
    used_slot = any(p["user_id"] == player_id and p["used_slot"] for p in players_info)
    data_utils.remove_player(game_id, player_id)
    if used_slot:
        data_utils.add_slots(player_id, 1)

    game = data_utils.get_game(game_id)
    logger.info(
        "KICK game=%s user=%s by=%s refunded=%s",
        game_id, player_id, update.effective_user.id, used_slot,
    )

    # Refresh the announcement post.
    if game.get("message_id"):
        await update_posted_message(context.bot, game, game_id)

    # DM the kicked player.
    msg_id = game.get("message_id")
    title_link = (
        build_announcement_link_html(msg_id, game["title"])
        if msg_id else f"<b>{game['title']}</b>"
    )
    try:
        await context.bot.send_message(
            chat_id=player_id,
            text=f"Ви були зняті з гри {title_link}.",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        pass

    # Confirm to the GM.
    target_user = data_utils.get_user(player_id) or {}
    name = (
        target_user.get("display_name")
        or target_user.get("username")
        or str(player_id)
    )
    await query.edit_message_text(
        f"Гравця {name} знято з гри <b>{game['title']}</b>.",
        parse_mode="HTML",
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /cancel — soft-cancel a game (keeps the announcement, disables signup)
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def cancel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    games = _get_cancellable_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає активних ігор для скасування.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Оберіть гру для скасування:",
        reply_markup=game_list_keyboard(games, "cancel_sel"),
    )
    return CANCEL_SELECT


@ensure_user
async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END
    if game.get("cancelled"):
        await query.edit_message_text("Гру вже скасовано.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"Скасувати гру <b>{game['title']}</b>? "
        f"Це поверне слоти, надішле сповіщення гравцям і зробить оголошення неактивним.",
        parse_mode="HTML",
        reply_markup=confirm_cancel_keyboard(game_id),
    )
    return CANCEL_CONFIRM


@ensure_user
async def cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("cancel_no"):
        await query.edit_message_text("Скасування відкладено.")
        return ConversationHandler.END

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END

    # Capture the affected sets before clearing them.
    players_info = data_utils.get_players_with_slots(game_id)
    player_ids = [p["user_id"] for p in players_info]
    interested_ids = data_utils.get_interested_users(game_id)

    if not data_utils.cancel_game(game_id):
        await query.edit_message_text("Гру вже скасовано.")
        return ConversationHandler.END

    # Refund slots for players who paid.
    refunded = 0
    for p in players_info:
        if p["used_slot"]:
            data_utils.add_slots(p["user_id"], 1)
            refunded += 1

    # Re-fetch with cancelled=True for the post update.
    game = data_utils.get_game(game_id)

    # Refresh the channel post (banner appears, buttons disappear).
    if game.get("message_id"):
        try:
            await update_posted_message(context.bot, game, game_id)
        except Exception as e:
            logger.warning("CANCEL refresh failed game=%s: %s", game_id, e)

    # DM the affected users.
    notified_players = await notify_cancellation(context.bot, game, player_ids)
    notified_interested = await notify_cancellation(context.bot, game, interested_ids)
    notified = notified_players + notified_interested

    # Clear the now-stale signup state.
    data_utils.clear_players(game_id)
    data_utils.clear_interested(game_id)

    logger.info(
        "CANCEL game=%s by user=%s refunded=%d notified=%d",
        game_id, update.effective_user.id, refunded, notified,
    )
    await query.edit_message_text(
        f"Гру скасовано. Повернуто {refunded} слотів, надіслано {notified} сповіщень."
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /uncancel — restore a previously cancelled game
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def uncancel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    games = _get_cancelled_games(update.effective_user.id)
    if not games:
        await update.message.reply_text("У вас немає скасованих ігор.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Оберіть гру для відновлення:",
        reply_markup=game_list_keyboard(games, "uncancel_sel"),
    )
    return UNCANCEL_SELECT


@ensure_user
async def uncancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return ConversationHandler.END
    if not game.get("cancelled"):
        await query.edit_message_text("Ця гра вже активна.")
        return ConversationHandler.END

    if not data_utils.uncancel_game(game_id):
        await query.edit_message_text("Ця гра вже активна.")
        return ConversationHandler.END

    game = data_utils.get_game(game_id)
    if game.get("message_id"):
        try:
            await update_posted_message(context.bot, game, game_id)
        except Exception as e:
            logger.warning("UNCANCEL refresh failed game=%s: %s", game_id, e)

    logger.info("UNCANCEL game=%s by user=%s", game_id, update.effective_user.id)
    await query.edit_message_text(
        "Гру відновлено. Сповіщення гравцям не надсилались — оголосіть у каналі за бажанням."
    )
    return ConversationHandler.END
