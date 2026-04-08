from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import data_utils


async def _reply(update, text):
    """Reply via message or callback query alert, whichever is available."""
    if update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    elif update.message:
        await update.message.reply_text(text)


def ensure_user(func):
    """Auto-register the calling user on every handler invocation."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user:
            data_utils.get_or_create_user(
                user_id=user.id,
                username=user.username,
                display_name=user.full_name,
            )
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_private(func):
    """Reject if not in a private chat."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type != "private":
            await _reply(update, "Ця команда працює лише в особистих повідомленнях. Напишіть мені в ЛС!")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_group(func):
    """Reject if not in a group/supergroup."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.type not in ("group", "supergroup"):
            await _reply(update, "Ця команда працює лише в групових чатах.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_gm(func):
    """Reject if user is not GM or Admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not data_utils.has_gm_permission(user_id):
            await _reply(update, "Ця команда доступна лише для Майстрів (GM).")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper


def require_admin(func):
    """Reject if user is not Admin."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not data_utils.is_admin(user_id):
            await _reply(update, "Ця команда доступна лише для адміністраторів.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper
