from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def event_list_keyboard(events, prefix):
    """Build a keyboard listing events. callback_data = {prefix}:{event_id}"""
    buttons = [
        [InlineKeyboardButton(e["title"], callback_data=f"{prefix}:{e['event_id']}")]
        for e in events
    ]
    buttons.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


def join_leave_keyboard(event_id):
    """Join/Leave buttons for a posted event message."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Join", callback_data=f"join:{event_id}"),
            InlineKeyboardButton("Leave", callback_data=f"leave:{event_id}"),
        ]
    ])


def edit_field_keyboard():
    """Field selection keyboard for /edit."""
    fields = [
        ("Title", "title"),
        ("Description", "description"),
        ("Max Players", "max_players"),
        ("Date", "event_date"),
    ]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"edit_field:{field}")]
        for label, field in fields
    ]
    buttons.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
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
    buttons.append([InlineKeyboardButton("Skip", callback_data=f"{prefix}:skip")])
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
    buttons.append([InlineKeyboardButton("Skip", callback_data=f"{prefix}:skip")])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(event_id):
    """Yes/No confirmation for deletion."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, delete", callback_data=f"del_yes:{event_id}"),
            InlineKeyboardButton("No, cancel", callback_data="del_no"),
        ]
    ])
