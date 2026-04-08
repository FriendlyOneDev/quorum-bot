from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.handlers.common import format_game
from bot.handlers.decorators import ensure_user, require_group, require_gm
from bot.keyboards import game_list_keyboard, join_leave_keyboard


# ---------------------------------------------------------------------------
# /post (group only, GM+)
# ---------------------------------------------------------------------------

@ensure_user
@require_group
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

    keyboard = join_leave_keyboard(game_id)
    text = format_game(game)
    thread_id = query.message.message_thread_id

    if game.get("photo_id"):
        sent = await query.message.chat.send_photo(
            photo=game["photo_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            message_thread_id=thread_id,
        )
    else:
        sent = await query.message.chat.send_message(
            text, parse_mode="HTML", reply_markup=keyboard,
            message_thread_id=thread_id,
        )
    data_utils.update_game(game_id, {"message_id": sent.message_id})
    await query.message.delete()


# ---------------------------------------------------------------------------
# Join / Leave callbacks
# ---------------------------------------------------------------------------

async def _notify_creator(context, game, user, action, chat, thread_id=None):
    """Send a DM to the game creator about a join/leave action."""
    creator_id = game.get("creator_id")
    if not creator_id:
        return

    user_mention = f'<a href="tg://user?id={user.id}">@{user.username or user.full_name}</a>'
    players = game.get("players", [])
    max_players = game["max_players"]

    title = game["title"]
    msg_id = game.get("message_id")
    if msg_id and chat:
        if chat.username:
            # Public group/channel — with optional topic
            if thread_id:
                title_link = f'<a href="https://t.me/{chat.username}/{thread_id}/{msg_id}">{title}</a>'
            else:
                title_link = f'<a href="https://t.me/{chat.username}/{msg_id}">{title}</a>'
        elif str(chat.id).startswith("-100"):
            # Private supergroup — with optional topic
            link_chat_id = str(chat.id)[4:]
            if thread_id:
                title_link = f'<a href="https://t.me/c/{link_chat_id}/{thread_id}/{msg_id}">{title}</a>'
            else:
                title_link = f'<a href="https://t.me/c/{link_chat_id}/{msg_id}">{title}</a>'
        else:
            title_link = f"<b>{title}</b>"
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


async def _update_posted_message(query, game, game_id):
    text = format_game(game)
    keyboard = join_leave_keyboard(game_id)
    if query.message.photo:
        await query.edit_message_caption(
            caption=text, parse_mode="HTML", reply_markup=keyboard,
        )
    else:
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=keyboard,
        )


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
    if data_utils.needs_slot(game, player_id):
        slots = data_utils.get_slots(player_id)
        if slots <= 0:
            await query.answer(
                "У вас немає слотів для запису.",
                show_alert=True,
            )
            return
        data_utils.consume_slot(player_id)

    data_utils.add_player(game_id, player_id)
    game = data_utils.get_game(game_id)
    await query.answer("Ви записались!")
    await _update_posted_message(query, game, game_id)
    await _notify_creator(context, game, update.effective_user, "записався на", query.message.chat, query.message.message_thread_id)


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

    data_utils.remove_player(game_id, player_id)

    # Refund slot if the user needed one to join
    if data_utils.needs_slot(game, player_id):
        data_utils.add_slots(player_id, 1)

    game = data_utils.get_game(game_id)
    await query.answer("Ви відписались.")
    await _update_posted_message(query, game, game_id)
    await _notify_creator(context, game, update.effective_user, "відписався від", query.message.chat, query.message.message_thread_id)


# ---------------------------------------------------------------------------
# /rollcall (group only, GM+)
# ---------------------------------------------------------------------------

@ensure_user
@require_group
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

    mention_parts = []
    for pid in players:
        user = data_utils.get_user(pid)
        name = (user.get("display_name") or user.get("username") or str(pid)) if user else str(pid)
        mention_parts.append(f'<a href="tg://user?id={pid}">{name}</a>')
    mentions = " ".join(mention_parts)

    await query.message.delete()
    await query.message.chat.send_message(
        f"Перекличка для <b>{game['title']}</b>:\n\n{mentions}",
        parse_mode="HTML",
    )
