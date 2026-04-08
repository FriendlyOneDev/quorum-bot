from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import data_utils
from bot.handlers.common import format_game
from bot.handlers.decorators import ensure_user, require_private, require_gm
from bot.keyboards import date_picker_keyboard, time_picker_keyboard

# Conversation states
CREATE_TITLE, CREATE_DESC, CREATE_MAX, CREATE_LOCATION, CREATE_DATE, CREATE_TIME, CREATE_TONE, CREATE_IMAGE = range(8)


@ensure_user
@require_private
@require_gm
async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть назву гри:")
    return CREATE_TITLE


@ensure_user
async def create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_title"] = update.message.text
    await update.message.reply_text("Введіть опис:")
    return CREATE_DESC


@ensure_user
async def create_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_desc"] = update.message.text_html
    await update.message.reply_text("Введіть максимальну кількість гравців:")
    return CREATE_MAX


@ensure_user
async def create_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        max_players = int(text)
        if max_players < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть додатнє число:")
        return CREATE_MAX

    context.user_data["create_max"] = max_players
    await update.message.reply_text("Місце проведення, онлайн/офлайн?")
    return CREATE_LOCATION


@ensure_user
async def create_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_location"] = update.message.text
    await update.message.reply_text(
        "Оберіть дату:", reply_markup=date_picker_keyboard("cal"),
    )
    return CREATE_DATE


@ensure_user
async def create_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    picked = query.data.split(":", 1)[1]
    if picked == "skip":
        context.user_data["create_game_date"] = None
    else:
        context.user_data["create_date"] = picked
        await query.edit_message_text(
            f"Дата: {picked}\n\nОберіть час:",
            reply_markup=time_picker_keyboard("time"),
        )
        return CREATE_TIME

    await query.edit_message_text("Тон гри:")
    return CREATE_TONE


@ensure_user
async def create_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    picked = query.data.split(":", 1)[1]
    picked_date = context.user_data["create_date"]

    if picked == "skip":
        context.user_data["create_game_date"] = picked_date
    else:
        context.user_data["create_game_date"] = f"{picked_date} {picked}"

    await query.edit_message_text("Тон гри:")
    return CREATE_TONE


@ensure_user
async def create_tone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_tone"] = update.message.text
    await update.message.reply_text("Надішліть фото або GIF для гри, або /skip:")
    return CREATE_IMAGE


@ensure_user
async def create_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["create_photo_id"] = update.message.photo[-1].file_id
        context.user_data["create_media_type"] = "photo"
    elif update.message.animation:
        context.user_data["create_photo_id"] = update.message.animation.file_id
        context.user_data["create_media_type"] = "animation"
    return await _finish_create(update.message, context)


async def _finish_create(reply_target, context):
    photo_id = context.user_data.get("create_photo_id")
    media_type = context.user_data.get("create_media_type")
    game = data_utils.create_game(
        creator_id=context._user_id,
        title=context.user_data["create_title"],
        description=context.user_data["create_desc"],
        max_players=context.user_data["create_max"],
        game_date=context.user_data.get("create_game_date"),
        location=context.user_data.get("create_location"),
        tone=context.user_data.get("create_tone"),
    )
    if photo_id:
        data_utils.update_game(game["game_id"], {"photo_id": photo_id, "media_type": media_type})
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так", callback_data=f"publish_now:{game['game_id']}"),
            InlineKeyboardButton("Ні", callback_data="publish_skip"),
        ]
    ])
    await reply_target.reply_text(
        f"Гру створено!\n\n{format_game(game)}\n\nОпублікувати зараз?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return ConversationHandler.END
