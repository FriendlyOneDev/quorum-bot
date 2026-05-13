import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.config import ANNOUNCEMENTS_CHAT, ANNOUNCEMENTS_TOPIC
from bot.handlers.common import format_game, resolve_player_names, build_announcement_link_html
from bot.handlers.decorators import ensure_user, require_private, require_gm
from bot.keyboards import game_list_keyboard, join_leave_keyboard

logger = logging.getLogger(__name__)


def _is_game_started(game):
    """Check if the game's scheduled time has passed."""
    game_date = game.get("game_date")
    if not game_date:
        return False
    try:
        dt = datetime.strptime(game_date, "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=data_utils.TIMEZONE)
        return datetime.now(data_utils.TIMEZONE) >= dt
    except ValueError:
        return False


def _keyboard_for(game, game_id):
    """Return join/leave keyboard if game hasn't started, else None to hide buttons."""
    if _is_game_started(game):
        return None
    return join_leave_keyboard(game_id)


# ---------------------------------------------------------------------------
# /post (DM only, GM+) — posts to announcements channel
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if data_utils.is_admin(user_id):
        games = data_utils.get_all_games()
    else:
        games = data_utils.get_games_by_creator(user_id)

    if not games:
        await update.message.reply_text("У вас немає ігор для публікації.")
        return

    await update.message.reply_text(
        "Оберіть гру для публікації:",
        reply_markup=game_list_keyboard(games, "post"),
    )


@ensure_user
async def post_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    if not data_utils.has_gm_permission(user_id):
        await query.answer("Ця дія доступна лише для GM.", show_alert=True)
        return

    await query.answer()
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return

    text_msg, photo_msg = await _post_game_to_announcements(context.bot, game)
    if text_msg:
        updates = {"message_id": text_msg.message_id}
        if photo_msg:
            updates["photo_message_id"] = photo_msg.message_id
        data_utils.update_game(game_id, updates)
        await query.edit_message_text("Гру опубліковано!")
    else:
        await query.edit_message_text("Не вдалося опублікувати. Перевірте налаштування каналу.")


CAPTION_LIMIT = 1024


async def _post_game_to_announcements(bot, game):
    """Post a game to the configured announcements channel.

    Returns a tuple (text_msg, photo_msg) where photo_msg is None if media is in caption.
    Returns (None, None) on failure.
    """
    if not ANNOUNCEMENTS_CHAT:
        return None, None

    player_names = await resolve_player_names(bot, ANNOUNCEMENTS_CHAT, game.get("players", []))
    text = format_game(game, player_names)
    keyboard = _keyboard_for(game, game["game_id"])
    logger.info(
        "POST game=%s players=%d/%d started=%s",
        game["game_id"], len(game.get("players", [])),
        game["max_players"], _is_game_started(game),
    )

    has_media = bool(game.get("photo_id"))
    is_animation = game.get("media_type") == "animation"
    needs_split = has_media and len(text) > CAPTION_LIMIT

    try:
        if not has_media:
            sent = await bot.send_message(
                chat_id=ANNOUNCEMENTS_CHAT,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
            return sent, None

        if needs_split:
            # Send photo first (no caption, no buttons), then text with buttons
            send_media = bot.send_animation if is_animation else bot.send_photo
            media_arg = "animation" if is_animation else "photo"
            photo_msg = await send_media(
                chat_id=ANNOUNCEMENTS_CHAT,
                **{media_arg: game["photo_id"]},
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
            text_msg = await bot.send_message(
                chat_id=ANNOUNCEMENTS_CHAT,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
            return text_msg, photo_msg

        # Caption fits — single message
        if is_animation:
            sent = await bot.send_animation(
                chat_id=ANNOUNCEMENTS_CHAT,
                animation=game["photo_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
        else:
            sent = await bot.send_photo(
                chat_id=ANNOUNCEMENTS_CHAT,
                photo=game["photo_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
        return sent, None
    except Exception as e:
        logger.error("POST failed game=%s: %s", game["game_id"], e, exc_info=True)
        await _notify_admin_post_failure(bot, game, e)
        return None, None


async def _notify_admin_post_failure(bot, game, err):
    import os
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        return
    try:
        await bot.send_message(
            chat_id=int(admin_id),
            text=f"Failed to post game {game.get('game_id')}: {type(err).__name__}: {err}",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Publish prompt after /create
# ---------------------------------------------------------------------------

@ensure_user
async def publish_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return

    text_msg, photo_msg = await _post_game_to_announcements(context.bot, game)
    if text_msg:
        updates = {"message_id": text_msg.message_id}
        if photo_msg:
            updates["photo_message_id"] = photo_msg.message_id
        data_utils.update_game(game_id, updates)
        await query.edit_message_text("Гру опубліковано!")
    else:
        await query.edit_message_text("Не вдалося опублікувати. Перевірте налаштування каналу.")


@ensure_user
async def publish_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Можете опублікувати пізніше через /post.")


# ---------------------------------------------------------------------------
# Update posted message (used after join/leave/edit)
# ---------------------------------------------------------------------------

async def update_posted_message(bot, game, game_id):
    """Update the posted game message in announcements channel."""
    msg_id = game.get("message_id")
    if not msg_id or not ANNOUNCEMENTS_CHAT:
        return

    player_names = await resolve_player_names(bot, ANNOUNCEMENTS_CHAT, game.get("players", []))
    text = format_game(game, player_names)
    keyboard = _keyboard_for(game, game_id)
    logger.info(
        "UPDATE game=%s msg_id=%s players=%d/%d started=%s",
        game_id, msg_id, len(game.get("players", [])),
        game["max_players"], _is_game_started(game),
    )

    # If photo is in a separate message, the main msg_id is plain text → use edit_message_text.
    # Otherwise, caption is part of the photo message → use edit_message_caption.
    is_caption = bool(game.get("photo_id")) and not game.get("photo_message_id")

    try:
        if is_caption:
            await bot.edit_message_caption(
                chat_id=ANNOUNCEMENTS_CHAT,
                message_id=msg_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            await bot.edit_message_text(
                chat_id=ANNOUNCEMENTS_CHAT,
                message_id=msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        # "Message is not modified" is benign — caused by no actual change
        if "not modified" not in str(e).lower():
            logger.warning("UPDATE failed game=%s msg_id=%s: %s", game_id, msg_id, e)


# ---------------------------------------------------------------------------
# Delete posted message (used on game delete)
# ---------------------------------------------------------------------------

async def delete_posted_message(bot, game):
    """Delete the posted game message(s) from announcements channel."""
    if not ANNOUNCEMENTS_CHAT:
        return
    for msg_id in (game.get("message_id"), game.get("photo_message_id")):
        if not msg_id:
            continue
        try:
            await bot.delete_message(chat_id=ANNOUNCEMENTS_CHAT, message_id=msg_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Notify creator
# ---------------------------------------------------------------------------

async def _resolve_user_display(bot, user):
    """Resolve a user mention string. Adds character tag/title in parens if available."""
    display = f"@{user.username or user.full_name}"
    if ANNOUNCEMENTS_CHAT:
        try:
            member = await bot.get_chat_member(ANNOUNCEMENTS_CHAT, user.id)
            char_name = getattr(member, "tag", None) or getattr(member, "custom_title", None)
            if char_name:
                display = f"@{user.username or user.full_name}({char_name})"
        except Exception:
            pass
    return f'<a href="tg://user?id={user.id}">{display}</a>'


def _title_link(game):
    title = game["title"]
    msg_id = game.get("message_id")
    if msg_id and ANNOUNCEMENTS_CHAT:
        return build_announcement_link_html(msg_id, title)
    return f"<b>{title}</b>"


async def _notify_creator(context, game, user, action):
    """Send a DM to the game creator about a join/leave action."""
    creator_id = game.get("creator_id")
    if not creator_id:
        return

    user_mention = await _resolve_user_display(context.bot, user)
    players = game.get("players", [])
    max_players = game["max_players"]
    title_link = _title_link(game)

    text = (
        f"{user_mention} {action} {title_link}\n"
        f"<b>Поточна заповненість:</b> {len(players)}/{max_players}"
    )

    try:
        await context.bot.send_message(
            chat_id=creator_id, text=text, parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        pass


async def _notify_creator_interested(context, game, user):
    """DM the GM that someone marked themselves interested in the game."""
    creator_id = game.get("creator_id")
    if not creator_id:
        return

    user_mention = await _resolve_user_display(context.bot, user)
    title_link = _title_link(game)
    interested_count = len(game.get("interested", []))

    text = (
        f"{user_mention} зацікавився(-лась) грою {title_link}\n"
        f"<b>Зацікавлених:</b> {interested_count}"
    )

    try:
        await context.bot.send_message(
            chat_id=creator_id, text=text, parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        pass


async def _notify_interested_for_free_signup(bot, game):
    """DM every interested user (who hasn't opted out) that signup is now free."""
    title_link = _title_link(game)
    text = (
        f"Гра {title_link} починається менш ніж за 24 години. "
        f"Реєстрація тепер безкоштовна (слот не списується)."
    )

    sent = 0
    for uid in data_utils.get_interested_users(game["game_id"]):
        user = data_utils.get_user(uid)
        if not user or not user.get("notify_interested", True):
            continue
        try:
            await bot.send_message(
                chat_id=uid, text=text, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception:
            pass
    logger.info("24H_NOTIFY game=%s sent=%d", game["game_id"], sent)


async def maybe_fire_24h_notifications(bot, game):
    """If the game just crossed the 24h boundary, fire one-shot DMs to interested users."""
    if game.get("interested_notified"):
        return
    if _is_game_started(game):
        return
    if not data_utils.is_within_24h(game):
        return
    # Atomic flip — only the call that flips actually sends DMs.
    if not data_utils.mark_interested_notified(game["game_id"]):
        return
    await _notify_interested_for_free_signup(bot, game)


# ---------------------------------------------------------------------------
# Signup toggle (merged join/leave) + Interested
# ---------------------------------------------------------------------------

@ensure_user
async def signup_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Single handler for both join and leave — dispatches on current DB state."""
    query = update.callback_query
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if not game:
        await query.answer("Ця гра більше не існує.", show_alert=True)
        return

    if _is_game_started(game):
        await query.answer("Гра вже розпочалась.", show_alert=True)
        return

    player_id = update.effective_user.id

    if player_id in game["players"]:
        await _do_leave(update, context, game, player_id)
    else:
        await _do_join(update, context, game, player_id)


async def _do_join(update, context, game, player_id):
    query = update.callback_query
    game_id = game["game_id"]

    if len(game["players"]) >= game["max_players"]:
        await query.answer("Гра заповнена!", show_alert=True)
        return

    used_slot = False
    if data_utils.needs_slot(game, player_id):
        slots = data_utils.get_slots(player_id)
        if slots <= 0:
            await query.answer("У вас немає слотів для запису.", show_alert=True)
            return
        data_utils.consume_slot(player_id)
        used_slot = True

    data_utils.add_player(game_id, player_id, used_slot=used_slot)
    game = data_utils.get_game(game_id)
    logger.info(
        "JOIN game=%s user=%s used_slot=%s players=%d/%d",
        game_id, player_id, used_slot,
        len(game["players"]), game["max_players"],
    )
    await query.answer("Ви записались!")
    await update_posted_message(context.bot, game, game_id)
    await _notify_creator(context, game, update.effective_user, "записався на")


async def _do_leave(update, context, game, player_id):
    query = update.callback_query
    game_id = game["game_id"]

    players_info = data_utils.get_players_with_slots(game_id)
    player_used_slot = any(
        p["user_id"] == player_id and p["used_slot"] for p in players_info
    )

    data_utils.remove_player(game_id, player_id)
    if player_used_slot:
        data_utils.add_slots(player_id, 1)

    game = data_utils.get_game(game_id)
    logger.info(
        "LEAVE game=%s user=%s refunded=%s players=%d/%d",
        game_id, player_id, player_used_slot,
        len(game["players"]), game["max_players"],
    )
    await query.answer("Ви відписались.")
    await update_posted_message(context.bot, game, game_id)
    await _notify_creator(context, game, update.effective_user, "відписався від")


# Back-compat: old posted messages still carry join:/leave: callbacks.
# Both delegate to the new merged toggle.
join_game = signup_toggle
leave_game = signup_toggle


@ensure_user
async def interested_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle the user's interest in a game."""
    query = update.callback_query
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if not game:
        await query.answer("Ця гра більше не існує.", show_alert=True)
        return

    if _is_game_started(game):
        await query.answer("Гра вже розпочалась.", show_alert=True)
        return

    user_id = update.effective_user.id

    if user_id in game.get("players", []):
        await query.answer("Ви вже записані — кнопка «Зацікавлений» вам не потрібна.", show_alert=True)
        return

    if data_utils.is_interested(game_id, user_id):
        data_utils.remove_interested(game_id, user_id)
        logger.info("INTERESTED_REMOVE game=%s user=%s", game_id, user_id)
        await query.answer("Прибрано з зацікавлених.")
        notify_gm = False
    else:
        data_utils.add_interested(game_id, user_id)
        logger.info("INTERESTED_ADD game=%s user=%s", game_id, user_id)
        await query.answer("Додано до зацікавлених.")
        notify_gm = True

    game = data_utils.get_game(game_id)
    await update_posted_message(context.bot, game, game_id)
    if notify_gm:
        await _notify_creator_interested(context, game, update.effective_user)


# ---------------------------------------------------------------------------
# /rollcall (group only, GM+)
# ---------------------------------------------------------------------------

@ensure_user
@require_gm
async def rollcall_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if data_utils.is_admin(user_id):
        games = data_utils.get_all_games()
    else:
        games = data_utils.get_games_by_creator(user_id)

    if not games:
        await update.message.reply_text("У вас немає ігор.")
        return

    await update.message.reply_text(
        "Оберіть гру для переклички:",
        reply_markup=game_list_keyboard(games, "rollcall"),
    )


@ensure_user
async def rollcall_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    if not data_utils.has_gm_permission(user_id):
        await query.answer("Ця дія доступна лише для GM.", show_alert=True)
        return

    await query.answer()
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return

    players = game.get("players", [])
    if not players:
        await query.edit_message_text(
            f"Ніхто не записався на <b>{game['title']}</b>.",
            parse_mode="HTML",
        )
        return

    # Build mentions: prefer @username (triggers notifications), fallback to text_mention
    name_chat = ANNOUNCEMENTS_CHAT or query.message.chat.id
    player_names = await resolve_player_names(context.bot, name_chat, players)

    mention_parts = []
    for pid in players:
        user = data_utils.get_user(pid)
        username = user.get("username") if user else None
        display = player_names.get(pid, str(pid))
        if username:
            mention_parts.append(f"@{username}")
        else:
            mention_parts.append(f'<a href="tg://user?id={pid}">{display}</a>')
    mentions = " ".join(mention_parts)

    target_chat = query.message.chat
    thread_id = query.message.message_thread_id

    await query.message.delete()
    await context.bot.send_message(
        chat_id=target_chat.id,
        text=f"Перекличка для <b>{game['title']}</b>:\n\n{mentions}",
        parse_mode="HTML",
        message_thread_id=thread_id,
    )
