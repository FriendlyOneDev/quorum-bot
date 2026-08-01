from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def game_list_keyboard(games, prefix):
    """Build a keyboard listing games. callback_data = {prefix}:{game_id}"""
    buttons = [
        [InlineKeyboardButton(g["title"], callback_data=f"{prefix}:{g['game_id']}")]
        for g in games
    ]
    buttons.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def join_leave_keyboard(game_id):
    """Signup toggle (row 1) + Interested (row 2) for a posted game message."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Записатись / Відписатись", callback_data=f"signup:{game_id}")],
        [InlineKeyboardButton("Зацікавлений", callback_data=f"interested:{game_id}")],
    ])


def edit_field_keyboard():
    """Field selection keyboard for /edit."""
    fields = [
        ("Назва", "title"),
        ("Опис", "description"),
        ("Макс. гравців", "max_players"),
        ("Місце", "location"),
        ("Дата", "game_date"),
        ("Тон", "tone"),
        ("Протяжність", "duration"),
    ]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"edit_field:{field}")]
        for label, field in fields
    ]
    buttons.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def date_picker_keyboard(prefix="cal"):
    """14-day date picker, 2 buttons per row."""
    today = date.today()
    buttons = []
    for i in range(0, 14, 2):
        row = []
        for offset in (i, i + 1):
            d = today + timedelta(days=offset)
            label = f"{DAY_NAMES[d.weekday()]} {d.strftime('%d.%m')}"
            row.append(
                InlineKeyboardButton(label, callback_data=f"{prefix}:{d.isoformat()}")
            )
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Пропустити", callback_data=f"{prefix}:skip")])
    return InlineKeyboardMarkup(buttons)


def time_picker_keyboard(prefix="time"):
    """Time picker with common slots, 2 per row."""
    hours = ["11:00", "12:00", "13:00", "14:00", "15:00", "16:00",
             "17:00", "18:00", "19:00", "20:00"]
    buttons = [
        [
            InlineKeyboardButton(hours[i], callback_data=f"{prefix}:{hours[i]}"),
            InlineKeyboardButton(hours[i + 1], callback_data=f"{prefix}:{hours[i + 1]}"),
        ]
        for i in range(0, len(hours), 2)
    ]
    buttons.append([InlineKeyboardButton("Пропустити", callback_data=f"{prefix}:skip")])
    return InlineKeyboardMarkup(buttons)


def player_list_keyboard(player_ids, player_names):
    """One button per player + a 'kick all' row. Handles both kick_player:{id} and kick_all."""
    buttons = [
        [InlineKeyboardButton(player_names.get(pid, str(pid)), callback_data=f"kick_player:{pid}")]
        for pid in player_ids
    ]
    buttons.append([InlineKeyboardButton("🧹 Зняти всіх гравців", callback_data="kick_all")])
    buttons.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def confirm_kick_all_keyboard():
    """Yes/No confirmation for bulk kick."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, зняти всіх", callback_data="kick_all_yes"),
            InlineKeyboardButton("Ні", callback_data="kick_all_no"),
        ]
    ])


def confirm_delete_keyboard(game_id):
    """Yes/No confirmation for deletion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, видалити", callback_data=f"del_yes:{game_id}"),
            InlineKeyboardButton("Ні, скасувати", callback_data="del_no"),
        ]
    ])


def confirm_cancel_keyboard(game_id):
    """Yes/No confirmation for soft-cancellation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, скасувати гру", callback_data=f"cancel_yes:{game_id}"),
            InlineKeyboardButton("Ні, не скасовувати", callback_data="cancel_no"),
        ]
    ])


def channel_picker_keyboard(channels, selected, repost):
    """Picker used at publish time. `channels` is the list from bot.config.CHANNELS.
    `selected[key]` is True/False for unposted channels (checkbox state).
    `repost[key]` is True for already-posted channels marked for delete+repost.

    Each channel button shows its current state; tapping toggles/prompts."""
    rows = []
    for ch in channels:
        if not ch.get("chat_id"):
            continue
        key = ch["key"]
        if repost.get(key):
            label = f"🔄 {ch['name']} (перепублікувати)"
            data = f"pubch:rp_cancel:{key}"
        elif key in selected:
            check = "✅" if selected[key] else "☐"
            label = f"{check} {ch['name']}"
            data = f"pubch:toggle:{key}"
        else:
            # already posted, not marked for repost
            label = f"📌 {ch['name']} (вже опубліковано)"
            data = f"pubch:repost:{key}"
        rows.append([InlineKeyboardButton(label, callback_data=data)])
    rows.append([
        InlineKeyboardButton("Публікувати", callback_data="pubch:go"),
        InlineKeyboardButton("Скасувати", callback_data="pubch:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


def confirm_repost_keyboard(channel_key):
    """Confirm dialog before marking an already-posted channel for delete+repost."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, перепублікувати", callback_data=f"pubch:rp_yes:{channel_key}"),
            InlineKeyboardButton("Ні", callback_data=f"pubch:rp_no:{channel_key}"),
        ]
    ])
