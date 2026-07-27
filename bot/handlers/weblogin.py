"""Bot-side hooks for the web frontend's magic-link auth.

Issues a signed short-lived token URL via `/login` or via the
`/start weblogin` deep link. The web verifies the token and sets a session
cookie. Signing secret and base URL come from env vars shared with the
web process.
"""
import logging
import os
from urllib.parse import quote

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import help_cmd
from bot.handlers.decorators import ensure_user
from web.auth import issue_token

logger = logging.getLogger(__name__)


async def _send_login_link(update: Update):
    base_url = os.getenv("WEB_BASE_URL")
    if not base_url:
        await update.message.reply_text(
            "Веб-інтерфейс не налаштований (немає WEB_BASE_URL). Скажіть адміну."
        )
        return
    try:
        token = issue_token(update.effective_user.id)
    except RuntimeError as e:
        logger.warning("WEBLOGIN issue_token failed: %s", e)
        await update.message.reply_text(
            "Веб-інтерфейс не налаштований (немає WEB_SECRET_KEY). Скажіть адміну."
        )
        return

    url = f"{base_url.rstrip('/')}/auth?token={quote(token)}"
    await update.message.reply_text(
        f"Ось ваше посилання для входу (діє 10 хвилин):\n{url}",
        disable_web_page_preview=True,
    )
    logger.info("WEBLOGIN issued token user=%s", update.effective_user.id)


@ensure_user
async def login_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/login — DMs a magic-link URL to the caller."""
    await _send_login_link(update)


@ensure_user
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — if payload is `weblogin`, issue a login link; else fall back to /help."""
    if context.args and context.args[0] == "weblogin":
        await _send_login_link(update)
        return
    await help_cmd(update, context)
