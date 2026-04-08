from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.config import ANNOUNCEMENTS_CHAT, ANNOUNCEMENTS_TOPIC
from bot.handlers.common import format_game, resolve_player_names
from bot.handlers.decorators import ensure_user, require_private, require_gm
from bot.keyboards import game_list_keyboard, join_leave_keyboard


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

    sent = await _post_game_to_announcements(context.bot, game)
    if sent:
        data_utils.update_game(game_id, {"message_id": sent.message_id})
        await query.edit_message_text("Гру опубліковано!")
    else:
        await query.edit_message_text("Не вдалося опублікувати. Перевірте налаштування каналу.")


async def _post_game_to_announcements(bot, game):
    """Post a game to the configured announcements channel. Returns the sent message."""
    if not ANNOUNCEMENTS_CHAT:
        return None

    player_names = await resolve_player_names(bot, ANNOUNCEMENTS_CHAT, game.get("players", []))
    text = format_game(game, player_names)
    keyboard = join_leave_keyboard(game["game_id"])

    try:
        if game.get("photo_id"):
            return await bot.send_photo(
                chat_id=ANNOUNCEMENTS_CHAT,
                photo=game["photo_id"],
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
        else:
            return await bot.send_message(
                chat_id=ANNOUNCEMENTS_CHAT,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
    except Exception:
        return None


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

    sent = await _post_game_to_announcements(context.bot, game)
    if sent:
        data_utils.update_game(game_id, {"message_id": sent.message_id})
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
    keyboard = join_leave_keyboard(game_id)

    try:
        if game.get("photo_id"):
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
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Delete posted message (used on game delete)
# ---------------------------------------------------------------------------

async def delete_posted_message(bot, game):
    """Delete the posted game message from announcements channel."""
    msg_id = game.get("message_id")
    if not msg_id or not ANNOUNCEMENTS_CHAT:
        return
    try:
        await bot.delete_message(chat_id=ANNOUNCEMENTS_CHAT, message_id=msg_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Notify creator
# ---------------------------------------------------------------------------

async def _notify_creator(context, game, user, action):
    """Send a DM to the game creator about a join/leave action."""
    creator_id = game.get("creator_id")
    if not creator_id:
        return

    # Resolve custom_title for the user
    display = f"@{user.username or user.full_name}"
    if ANNOUNCEMENTS_CHAT:
        try:
            member = await context.bot.get_chat_member(ANNOUNCEMENTS_CHAT, user.id)
            ct = getattr(member, "custom_title", None)
            if ct:
                display = f"@{user.username or user.full_name}({ct})"
        except Exception:
            pass
    user_mention = f'<a href="tg://user?id={user.id}">{display}</a>'

    players = game.get("players", [])
    max_players = game["max_players"]

    title = game["title"]
    msg_id = game.get("message_id")
    if msg_id and ANNOUNCEMENTS_CHAT:
        # Build link based on announcements chat config
        chat_str = str(ANNOUNCEMENTS_CHAT)
        if chat_str.startswith("@"):
            # Public group — use username
            if ANNOUNCEMENTS_TOPIC:
                title_link = f'<a href="https://t.me/{chat_str[1:]}/{ANNOUNCEMENTS_TOPIC}/{msg_id}">{title}</a>'
            else:
                title_link = f'<a href="https://t.me/{chat_str[1:]}/{msg_id}">{title}</a>'
        else:
            # Numeric chat ID
            link_id = chat_str.lstrip("-")
            if link_id.startswith("100"):
                link_id = link_id[3:]
            if ANNOUNCEMENTS_TOPIC:
                title_link = f'<a href="https://t.me/c/{link_id}/{ANNOUNCEMENTS_TOPIC}/{msg_id}">{title}</a>'
            else:
                title_link = f'<a href="https://t.me/c/{link_id}/{msg_id}">{title}</a>'
    else:
        title_link = f"<b>{title}</b>"

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


# ---------------------------------------------------------------------------
# Join / Leave callbacks
# ---------------------------------------------------------------------------

@ensure_user
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if not game:
        await query.answer("Ця гра більше не існує.", show_alert=True)
        return

    player_id = update.effective_user.id

    if player_id in game["players"]:
        await query.answer("Ви вже записані.")
        return

    if len(game["players"]) >= game["max_players"]:
        await query.answer("Гра заповнена!", show_alert=True)
        return

    # Slot check
    used_slot = False
    if data_utils.needs_slot(game, player_id):
        slots = data_utils.get_slots(player_id)
        if slots <= 0:
            await query.answer(
                "У вас немає слотів для запису.",
                show_alert=True,
            )
            return
        data_utils.consume_slot(player_id)
        used_slot = True

    data_utils.add_player(game_id, player_id, used_slot=used_slot)
    game = data_utils.get_game(game_id)
    await query.answer("Ви записались!")
    await update_posted_message(context.bot, game, game_id)
    await _notify_creator(context, game, update.effective_user, "записався на")


@ensure_user
async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)

    if not game:
        await query.answer("Ця гра більше не існує.", show_alert=True)
        return

    player_id = update.effective_user.id

    if player_id not in game["players"]:
        await query.answer("Ви не записані на цю гру.")
        return

    # Check if player used a slot before removing
    players_info = data_utils.get_players_with_slots(game_id)
    player_used_slot = any(
        p["user_id"] == player_id and p["used_slot"] for p in players_info
    )

    data_utils.remove_player(game_id, player_id)

    if player_used_slot:
        data_utils.add_slots(player_id, 1)

    game = data_utils.get_game(game_id)
    await query.answer("Ви відписались.")
    await update_posted_message(context.bot, game, game_id)
    await _notify_creator(context, game, update.effective_user, "відписався від")


# ---------------------------------------------------------------------------
# /rollcall (group only, GM+)
# ---------------------------------------------------------------------------

@ensure_user
@require_private
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

    chat_id = ANNOUNCEMENTS_CHAT or query.message.chat.id
    player_names = await resolve_player_names(context.bot, chat_id, players)
    mention_parts = [
        f'<a href="tg://user?id={pid}">{player_names.get(pid, str(pid))}</a>'
        for pid in players
    ]
    mentions = " ".join(mention_parts)

    if ANNOUNCEMENTS_CHAT:
        # Send rollcall to announcements channel
        await query.edit_message_text("Перекличку надіслано!")
        try:
            await context.bot.send_message(
                chat_id=ANNOUNCEMENTS_CHAT,
                text=f"Перекличка для <b>{game['title']}</b>:\n\n{mentions}",
                parse_mode="HTML",
                message_thread_id=ANNOUNCEMENTS_TOPIC,
            )
        except Exception:
            pass
    else:
        await query.message.delete()
        await query.message.chat.send_message(
            f"Перекличка для <b>{game['title']}</b>:\n\n{mentions}",
            parse_mode="HTML",
        )
