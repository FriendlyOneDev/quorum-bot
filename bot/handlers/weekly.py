"""Admin-only pause/resume for the weekly pinned schedule."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.handlers.decorators import ensure_user, require_admin

logger = logging.getLogger(__name__)


@ensure_user
@require_admin
async def pause_weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if data_utils.get_weekly_paused():
        await update.message.reply_text("Тижневий розклад вже призупинено.")
        return
    data_utils.set_weekly_paused(True)
    logger.info("WEEKLY_PAUSE by user=%s", update.effective_user.id)
    await update.message.reply_text(
        "Тижневий розклад призупинено. Наявні закріплення не змінено — /resume_weekly щоб відновити."
    )


@ensure_user
@require_admin
async def resume_weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data_utils.get_weekly_paused():
        await update.message.reply_text("Тижневий розклад вже активний.")
        return
    data_utils.set_weekly_paused(False)
    logger.info("WEEKLY_RESUME by user=%s", update.effective_user.id)
    await update.message.reply_text(
        "Тижневий розклад відновлено. Оновиться протягом наступного циклу оновлення."
    )
