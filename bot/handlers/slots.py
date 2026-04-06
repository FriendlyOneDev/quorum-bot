from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.handlers.decorators import ensure_user, require_gm


# ---------------------------------------------------------------------------
# /giveslot — GM gives slot(s) to a user
# In private: /giveslot @username [N]
# In group: reply to a message with /giveslot [N]
# ---------------------------------------------------------------------------

@ensure_user
@require_gm
async def giveslot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []

    target_user = None
    count = 1

    # Method 1: Reply-to in group
    if update.message.reply_to_message:
        reply_user = update.message.reply_to_message.from_user
        if reply_user:
            target_user = data_utils.get_or_create_user(
                reply_user.id, reply_user.username, reply_user.full_name
            )
        if args:
            try:
                count = int(args[0])
                if count == 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Кількість має бути ненульовим числом.")
                return
    # Method 2: @username in private/group
    elif args:
        username = args[0]
        if not username.startswith("@"):
            await update.message.reply_text(
                "Використання:\n"
                "• Відповідь на повідомлення: /giveslot [кількість]\n"
                "• За юзернеймом: /giveslot @username [кількість]"
            )
            return
        target_user = data_utils.get_user_by_username(username)
        if not target_user:
            await update.message.reply_text(
                f"Користувача {username} не знайдено. "
                "Він має спочатку зареєструватися через бота."
            )
            return
        if len(args) > 1:
            try:
                count = int(args[1])
                if count == 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Кількість має бути ненульовим числом.")
                return
    else:
        await update.message.reply_text(
            "Використання:\n"
            "• Відповідь на повідомлення: /giveslot [кількість]\n"
            "• За юзернеймом: /giveslot @username [кількість]"
        )
        return

    data_utils.add_slots(target_user["user_id"], count)
    new_total = data_utils.get_slots(target_user["user_id"])
    name = target_user.get("display_name") or target_user.get("username") or str(target_user["user_id"])

    word = _slot_word(count)
    await update.message.reply_text(
        f"Видано {count} {word} гравцю {name}. Всього: {new_total}."
    )


# ---------------------------------------------------------------------------
# /giveslots — GM gives 1 slot to all known regular users
# ---------------------------------------------------------------------------

@ensure_user
@require_gm
async def giveslots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    amount = 1
    if args:
        try:
            amount = int(args[0])
            if amount == 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Кількість має бути ненульовим числом.")
            return

    users = data_utils.get_all_users()
    count = 0
    for user in users:
        if user["role"] == "user":
            data_utils.add_slots(user["user_id"], amount)
            count += 1

    word = _slot_word(amount)
    await update.message.reply_text(
        f"Видано по {amount} {word} {count} гравцям."
    )


# ---------------------------------------------------------------------------
# /myslots — check own slot balance
# ---------------------------------------------------------------------------

@ensure_user
async def myslots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    slots = data_utils.get_slots(user_id)
    word = _slot_word(slots)
    await update.message.reply_text(f"У вас {slots} {word}.")


def _slot_word(n: int) -> str:
    """Ukrainian plural form for 'слот'."""
    if 11 <= n % 100 <= 19:
        return "слотів"
    last = n % 10
    if last == 1:
        return "слот"
    if 2 <= last <= 4:
        return "слоти"
    return "слотів"
