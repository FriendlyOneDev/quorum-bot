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
    await query.answer()

    game_id = query.data.split(":", 1)[1]
    game = data_utils.get_game(game_id)
    if not game:
        await query.edit_message_text("Гру не знайдено.")
        return

    keyboard = join_leave_keyboard(game_id)
    text = format_game(game)

    if game.get("photo_id"):
        sent = await query.message.chat.send_photo(
            photo=game["photo_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        sent = await query.message.chat.send_message(
            text, parse_mode="HTML", reply_markup=keyboard,
        )
    data_utils.update_game(game_id, {"message_id": sent.message_id})
    await query.edit_message_text("Гру опубліковано!")


# ---------------------------------------------------------------------------
# Join / Leave callbacks
# ---------------------------------------------------------------------------

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
                "У вас немає слотів для запису. Попросіть GM дати вам слот!",
                show_alert=True,
            )
            return
        data_utils.consume_slot(player_id)

    data_utils.add_player(game_id, player_id)
    game = data_utils.get_game(game_id)
    await query.answer("Ви записались!")
    await _update_posted_message(query, game, game_id)


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

    mentions = " ".join(
        f'<a href="tg://user?id={pid}">гравець</a>' for pid in players
    )
    await query.edit_message_text(
        f"Перекличка для <b>{game['title']}</b>:\n\n{mentions}",
        parse_mode="HTML",
    )
