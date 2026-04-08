from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import data_utils
from bot.handlers.decorators import ensure_user

_DAY_NAMES_UK = {
    0: "Понеділок", 1: "Вівторок", 2: "Середа", 3: "Четвер",
    4: "П'ятниця", 5: "Субота", 6: "Неділя",
}


def _format_game_date(game_date_str: str) -> str:
    """Format 'YYYY-MM-DD HH:MM' into 'Неділя(01.01), 18:00'."""
    try:
        dt = datetime.strptime(game_date_str, "%Y-%m-%d %H:%M")
        day_name = _DAY_NAMES_UK[dt.weekday()]
        return f"{day_name}({dt.strftime('%d.%m')}), {dt.strftime('%H:%M')}"
    except ValueError:
        return game_date_str


def format_game(game, player_names=None):
    players = game.get("players", [])
    lines = [
        f"<b>{game['title']}</b>",
        game["description"],
    ]
    if game.get("location"):
        lines.append(f"<b>Місце:</b> {game['location']}")
    if game.get("game_date"):
        lines.append(f"<b>Дата:</b> {_format_game_date(game['game_date'])}")
    if game.get("tone"):
        lines.append(f"<b>Тон:</b> {game['tone']}")

    if player_names and players:
        names = ", ".join(player_names.get(pid, "?") for pid in players)
        lines.append(f"<b>Гравці ({len(players)}/{game['max_players']}):</b> {names}")
    else:
        lines.append(f"<b>Гравці:</b> {len(players)}/{game['max_players']}")

    return "\n".join(lines)


async def resolve_player_names(bot, chat_id, player_ids):
    """Resolve player display names: tag → display_name from DB."""
    names = {}
    for pid in player_ids:
        name = None
        # Try to get custom_title (character name) from chat member
        try:
            member = await bot.get_chat_member(chat_id, pid)
            title = getattr(member, "custom_title", None)
            if title:
                name = title
        except Exception:
            pass
        # Fallback to DB display name
        if not name:
            user = data_utils.get_user(pid)
            if user:
                name = user.get("display_name") or user.get("username") or str(pid)
            else:
                name = str(pid)
        names[pid] = name
    return names


@ensure_user
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        # In groups, only GM+ can dismiss selection menus
        if update.effective_chat.type in ("group", "supergroup"):
            if not data_utils.has_gm_permission(update.effective_user.id):
                await update.callback_query.answer(
                    "Ця дія доступна лише для GM.", show_alert=True
                )
                return ConversationHandler.END
        await update.callback_query.answer()
        await update.callback_query.message.delete()
    else:
        await update.message.reply_text("Скасовано.")
    context.user_data.clear()
    return ConversationHandler.END


@ensure_user
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")


@ensure_user
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = data_utils.get_role(user_id)

    lines = ["<b>Доступні команди:</b>\n"]

    # Everyone
    lines.append("/myslots — Перевірити свої слоти")
    lines.append("/whoami — Ваша роль та слоти")
    lines.append("/help — Показати цю довідку")
    lines.append("/ping — Перевірка зв'язку")

    if data_utils.has_gm_permission(user_id):
        lines.append("\n<b>Команди GM:</b>")
        lines.append("/create — Створити гру")
        lines.append("/view — Переглянути свої ігри")
        lines.append("/edit — Редагувати гру")
        lines.append("/delete — Видалити гру")
        lines.append("/post — Опублікувати гру в групі")
        lines.append("/rollcall — Перекличка гравців")
        lines.append("/giveslot — Дати слот гравцю")
        lines.append("/giveslots — Дати слот всім гравцям")
        lines.append("/register — Кнопка реєстрації в групі")

    if data_utils.is_admin(user_id):
        lines.append("\n<b>Команди адміна:</b>")
        lines.append("/setrole — Змінити роль користувача")
        lines.append("/users — Список користувачів")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
