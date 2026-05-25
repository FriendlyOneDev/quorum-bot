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
    """One button per player. callback_data = kick_player:{user_id}"""
    buttons = [
        [InlineKeyboardButton(player_names.get(pid, str(pid)), callback_data=f"kick_player:{pid}")]
        for pid in player_ids
    ]
    buttons.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(game_id):
    """Yes/No confirmation for deletion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, видалити", callback_data=f"del_yes:{game_id}"),
            InlineKeyboardButton("Ні, скасувати", callback_data="del_no"),
        ]
    ])
