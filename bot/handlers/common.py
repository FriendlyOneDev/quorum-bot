import random
import time
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


def build_announcement_link_html(message_id, label: str) -> str:
    """HTML <a> tag pointing at the MAIN channel's post for this game.
    Returns the bare label (no link) if message_id or the main channel is missing."""
    from bot.config import MAIN_CHANNEL
    chat_id = MAIN_CHANNEL["chat_id"]
    topic_id = MAIN_CHANNEL["topic_id"]
    if not (message_id and chat_id):
        return label
    chat_str = str(chat_id)
    if chat_str.startswith("@"):
        base = f"https://t.me/{chat_str[1:]}"
    else:
        link_id = chat_str.lstrip("-")
        if link_id.startswith("100"):
            link_id = link_id[3:]
        base = f"https://t.me/c/{link_id}"
    if topic_id:
        url = f"{base}/{topic_id}/{message_id}"
    else:
        url = f"{base}/{message_id}"
    return f'<a href="{url}">{label}</a>'


def _get_gm_display_name(creator_id):
    """Get GM display name: custom_name → display_name → username."""
    user = data_utils.get_user(creator_id)
    if not user:
        return None
    return user.get("custom_name") or user.get("display_name") or user.get("username")


def format_game(game, player_names=None):
    players = game.get("players", [])
    gm_name = _get_gm_display_name(game.get("creator_id"))
    lines = []
    if game.get("cancelled"):
        lines.append("<b>Гру скасовано</b>")
        lines.append("")
    lines.extend([
        f"<b>{game['title']}</b>",
        game["description"],
        "",
    ])
    if gm_name:
        lines.append(f"<b>ГМ:</b> {gm_name}")
    if game.get("location"):
        lines.append(f"<b>Місце:</b> {game['location']}")
    if game.get("game_date"):
        lines.append(f"<b>Дата:</b> {_format_game_date(game['game_date'])}")
    if game.get("tone"):
        lines.append(f"<b>Тон:</b> {game['tone']}")
    if game.get("duration"):
        lines.append(f"<b>Протяжність:</b> {game['duration']}")

    if player_names and players:
        names = ", ".join(player_names.get(pid, "?") for pid in players)
        lines.append(f"<b>Гравці ({len(players)}/{game['max_players']}):</b> {names}")
    else:
        lines.append(f"<b>Гравці:</b> {len(players)}/{game['max_players']}")

    interested = game.get("interested", [])
    if interested:
        lines.append(f"<b>Зацікавлені:</b> {len(interested)}")

    return "\n".join(lines)


# get_chat_member carries the channel chat_id, so AIORateLimiter throttles it
# with the group bucket: 20/60s, i.e. 3 seconds per call. Resolving 138 players
# each refresh cycle cost ~7 minutes and blocked every user action behind it.
# Character tags change rarely, so cache them.
NAME_CACHE_TTL = 86400  # tags are character names; a day stale is fine
_name_cache: dict = {}


def _name_cache_expiry(now):
    """Jittered so entries don't all lapse on the same refresh cycle and
    re-create the stall this cache exists to prevent."""
    return now + NAME_CACHE_TTL * (0.5 + random.random())


async def resolve_player_names(bot, chat_id, player_ids):
    """Resolve player display names: tag → display_name from DB. Cached for
    NAME_CACHE_TTL seconds, keyed by (chat_id, user_id)."""
    names = {}
    now = time.monotonic()
    for pid in player_ids:
        cached = _name_cache.get((chat_id, pid))
        if cached and now < cached[0]:
            names[pid] = cached[1]
            continue
        name = None
        # Try to get tag (regular members) or custom_title (admins)
        try:
            member = await bot.get_chat_member(chat_id, pid)
            name = getattr(member, "tag", None) or getattr(member, "custom_title", None)
        except Exception:
            pass
        # Fallback to DB display name
        if not name:
            user = data_utils.get_user(pid)
            if user:
                name = user.get("display_name") or user.get("username") or str(pid)
            else:
                name = str(pid)
        _name_cache[(chat_id, pid)] = (_name_cache_expiry(now), name)
        names[pid] = name
    return names


def clear_flow(context, prefix):
    """Drop only one conversation's keys. user_data is shared by every
    conversation, so a blanket clear() in one flow wipes another still-live
    one (e.g. /edit mid-/create -> KeyError: 'create_title')."""
    for key in [k for k in context.user_data if k.startswith(prefix)]:
        del context.user_data[key]


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
    lines.append("/games — Список найближчих ігор")
    lines.append("/mygames — Ігри, на які ви записані")
    lines.append("/myslots — Перевірити свої слоти")
    lines.append("/whoami — Ваша роль та слоти")
    lines.append("/togglenotify — Увімкнути/вимкнути сповіщення про 24h")
    lines.append("/help — Показати цю довідку")
    lines.append("/ping — Перевірка зв'язку")

    if data_utils.has_gm_permission(user_id):
        lines.append("\n<b>Команди GM:</b>")
        lines.append("/create — Створити гру")
        lines.append("/view — Переглянути свої ігри")
        lines.append("/edit — Редагувати гру")
        lines.append("/delete — Видалити гру")
        lines.append("/cancel — Скасувати гру (зберігає оголошення)")
        lines.append("/uncancel — Відновити скасовану гру")
        lines.append("/kick — Зняти гравця з гри")
        lines.append("/post — Опублікувати гру в групі")
        lines.append("/rollcall — Перекличка гравців")
        lines.append("/giveslot — Дати слот гравцю")
        lines.append("/giveslots — Дати слот всім гравцям")
        lines.append("/register — Кнопка реєстрації в групі")
        lines.append("/setname — Змінити своє ім'я ГМ")

    if data_utils.is_admin(user_id):
        lines.append("\n<b>Команди адміна:</b>")
        lines.append("/setrole — Змінити роль користувача")
        lines.append("/users — Список користувачів")
        lines.append("/togglebypass — Увімкнути/вимкнути обхід слотів для себе")
        lines.append("/pause_weekly — Призупинити тижневий закріплений розклад")
        lines.append("/resume_weekly — Відновити тижневий закріплений розклад")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
