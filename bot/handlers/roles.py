from telegram import Update
from telegram.ext import ContextTypes

import data_utils
from bot.handlers.decorators import ensure_user, require_private, require_admin, require_gm
from bot.handlers.post import update_posted_message


# ---------------------------------------------------------------------------
# /setrole @username gm|user
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_admin
async def setrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Використання: /setrole @username gm|user"
        )
        return

    username = args[0]
    role = args[1].lower()

    if role not in ("gm", "user"):
        await update.message.reply_text("Роль має бути 'gm' або 'user'.")
        return

    user = data_utils.get_user_by_username(username)
    if not user:
        await update.message.reply_text(
            f"Користувача {username} не знайдено. "
            "Він має спочатку зареєструватися через бота."
        )
        return

    data_utils.set_role(user["user_id"], role)
    role_label = {"gm": "GM (Майстер)", "user": "Гравець"}[role]
    name = user.get("display_name") or user.get("username") or str(user["user_id"])
    await update.message.reply_text(
        f"Роль {name} змінено на {role_label}."
    )


# ---------------------------------------------------------------------------
# /setname — GM sets their custom display name
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_gm
async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Використання: /setname Ваше ім'я")
        return

    name = " ".join(args)
    data_utils.update_user(update.effective_user.id, {"custom_name": name})
    await update.message.reply_text(f"Ваше ім'я ГМ змінено на: {name}")

    # Update all posted games by this GM
    games = data_utils.get_games_by_creator(update.effective_user.id)
    for game in games:
        if game.get("message_id"):
            try:
                await update_posted_message(context.bot, game, game["game_id"])
            except Exception:
                pass


# ---------------------------------------------------------------------------
# /whoami
# ---------------------------------------------------------------------------

@ensure_user
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = data_utils.get_role(user_id)
    slots = data_utils.get_slots(user_id)

    role_labels = {
        "admin": "Адміністратор",
        "gm": "GM (Майстер)",
        "user": "Гравець",
    }
    role_label = role_labels.get(role, role)

    await update.message.reply_text(
        f"Роль: {role_label}\nСлоти: {slots}"
    )


# ---------------------------------------------------------------------------
# /users (admin only)
# ---------------------------------------------------------------------------

@ensure_user
@require_private
@require_admin
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = data_utils.get_all_users()
    if not users:
        await update.message.reply_text("Немає зареєстрованих користувачів.")
        return

    role_labels = {
        "admin": "Адмін",
        "gm": "GM",
        "user": "Гравець",
    }

    lines = ["<b>Користувачі:</b>\n"]
    for user in users:
        name = user.get("display_name") or user.get("username") or str(user["user_id"])
        uname = f"@{user['username']}" if user.get("username") else ""
        role = role_labels.get(user["role"], user["role"])
        slots = data_utils.get_slots(user["user_id"])
        lines.append(f"• {name} {uname} — {role}, слотів: {slots}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
