from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import data_utils
from bot.handlers.decorators import ensure_user


def format_game(game):
    players = game.get("players", [])
    lines = [
        f"<b>{game['title']}</b>",
        game["description"],
        f"Гравці: {len(players)}/{game['max_players']}",
    ]
    if game.get("game_date"):
        lines.append(f"Дата: {game['game_date']}")
    return "\n".join(lines)


@ensure_user
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Скасовано.")
    else:
        await update.message.reply_text("Скасовано.")
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
