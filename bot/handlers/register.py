from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import data_utils
from bot.handlers.decorators import ensure_user, require_group, require_gm


@ensure_user
@require_group
@require_gm
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Зареєструватися", callback_data="register_me")]
    ])
    await update.message.reply_text(
        "Натисніть кнопку нижче, щоб зареєструватися та отримати слот:",
        reply_markup=keyboard,
    )


@ensure_user
async def register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    existing = data_utils.get_user(user.id)
    if existing:
        slots = data_utils.get_slots(user.id)
        await query.answer(f"Ви вже зареєстровані. Слотів: {slots}.")
        return

    # New user — get_or_create_user gives 1 welcome slot via ensure_user decorator
    # (already called above), so user is already created. Just confirm.
    new_user = data_utils.get_user(user.id)
    slots = data_utils.get_slots(user.id)
    await query.answer(f"Вас зареєстровано! Слотів: {slots}.", show_alert=True)
