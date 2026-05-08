import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import data_utils
from bot.handlers.common import format_game, build_announcement_link_html, _DAY_NAMES_UK
from bot.handlers.decorators import ensure_user, require_private, require_gm
from bot.handlers.post import update_posted_message, delete_posted_message

logger = logging.getLogger(__name__)
from bot.keyboards import game_list_keyboard, edit_field_keyboard, confirm_delete_keyboard

# Conversation states
EDIT_SELECT, EDIT_FIELD, EDIT_VALUE = range(6, 9)
DELETE_SELECT, DELETE_CONFIRM = range(9, 11)


def _get_manageable_games(user_id):
    """Get games the user can manage: own games for GM, all games for admin."""
    if data_utils.is_admin(user_id):
        return data_utils.get_all_games()
    return data_utils.get_games_by_creator(user_id)


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
        "game_date": "дату (РРРР-ММ-ДД ГГ:ХХ)",
    }
    await query.edit_message_text(f"Введіть нове значення для {labels[field]}:")
    return EDIT_VALUE


@ensure_user
async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data["edit_field"]
    game_id = context.user_data["edit_game_id"]
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
