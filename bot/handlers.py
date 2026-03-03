from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import event_utils
from bot.keyboards import (
    event_list_keyboard,
    join_leave_keyboard,
    edit_field_keyboard,
    confirm_delete_keyboard,
    date_picker_keyboard,
    time_picker_keyboard,
)

# Conversation states
CREATE_TITLE, CREATE_DESC, CREATE_MAX, CREATE_DATE, CREATE_TIME, CREATE_IMAGE = range(6)
EDIT_SELECT, EDIT_FIELD, EDIT_VALUE = range(6, 9)
DELETE_SELECT, DELETE_CONFIRM = range(9, 11)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_private(update):
    return update.effective_chat.type == "private"


def is_group(update):
    return update.effective_chat.type in ("group", "supergroup")


def get_user_events(user_id):
    return [e for e in event_utils.get_all_events() if e["creator_id"] == user_id]


def format_event(event):
    players = event.get("players", [])
    lines = [
        f"<b>{event['title']}</b>",
        event["description"],
        f"Players: {len(players)}/{event['max_players']}",
    ]
    if event.get("event_date"):
        lines.append(f"Date: {event['event_date']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cancel (shared fallback)
# ---------------------------------------------------------------------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Cancelled.")
    else:
        await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /ping
# ---------------------------------------------------------------------------

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")


# ---------------------------------------------------------------------------
# /create conversation (private only)
# ---------------------------------------------------------------------------

async def create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private(update):
        await update.message.reply_text("This command only works in private chat. DM me!")
        return ConversationHandler.END
    await update.message.reply_text("Enter event title:")
    return CREATE_TITLE


async def create_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_title"] = update.message.text
    await update.message.reply_text("Enter description:")
    return CREATE_DESC


async def create_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["create_desc"] = update.message.text
    await update.message.reply_text("Enter max players (number):")
    return CREATE_MAX


async def create_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        max_players = int(text)
        if max_players < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a positive number:")
        return CREATE_MAX

    context.user_data["create_max"] = max_players
    await update.message.reply_text(
        "Pick a date:", reply_markup=date_picker_keyboard("cal"),
    )
    return CREATE_DATE


async def create_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    picked = query.data.split(":", 1)[1]
    if picked == "skip":
        context.user_data["create_event_date"] = None
    else:
        context.user_data["create_date"] = picked
        await query.edit_message_text(
            f"Date: {picked}\n\nPick a time:",
            reply_markup=time_picker_keyboard("time"),
        )
        return CREATE_TIME

    await query.edit_message_text("Send a photo for the event or /skip:")
    return CREATE_IMAGE


async def create_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    picked = query.data.split(":", 1)[1]
    picked_date = context.user_data["create_date"]

    if picked == "skip":
        context.user_data["create_event_date"] = picked_date
    else:
        context.user_data["create_event_date"] = f"{picked_date} {picked}"

    await query.edit_message_text("Send a photo for the event or /skip:")
    return CREATE_IMAGE


async def create_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["create_photo_id"] = update.message.photo[-1].file_id
    return await _finish_create(update.message, context)


async def _finish_create(reply_target, context):
    """Create the event and send confirmation."""
    photo_id = context.user_data.get("create_photo_id")
    event = event_utils.create_event(
        creator_id=context._user_id,
        title=context.user_data["create_title"],
        description=context.user_data["create_desc"],
        max_players=context.user_data["create_max"],
        event_date=context.user_data.get("create_event_date"),
    )
    if photo_id:
        event_utils.update_event(event["event_id"], {"photo_id": photo_id})
    context.user_data.clear()

    await reply_target.reply_text(
        f"Event created!\n\n{format_event(event)}", parse_mode="HTML"
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /view (private only)
# ---------------------------------------------------------------------------

async def view_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private(update):
        await update.message.reply_text("This command only works in private chat. DM me!")
        return

    events = get_user_events(update.effective_user.id)
    if not events:
        await update.message.reply_text("You have no events.")
        return

    text = "\n\n".join(format_event(e) for e in events)
    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /edit conversation (private only)
# ---------------------------------------------------------------------------

async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private(update):
        await update.message.reply_text("This command only works in private chat. DM me!")
        return ConversationHandler.END

    events = get_user_events(update.effective_user.id)
    if not events:
        await update.message.reply_text("You have no events to edit.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Select an event to edit:",
        reply_markup=event_list_keyboard(events, "edit_sel"),
    )
    return EDIT_SELECT


async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.")
        return ConversationHandler.END

    context.user_data["edit_event_id"] = event_id
    await query.edit_message_text(
        f"Editing: <b>{event['title']}</b>\n\nSelect a field to edit:",
        parse_mode="HTML",
        reply_markup=edit_field_keyboard(),
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    field = query.data.split(":", 1)[1]
    context.user_data["edit_field"] = field

    labels = {
        "title": "title",
        "description": "description",
        "max_players": "max players",
        "event_date": "event date (YYYY-MM-DD HH:MM)",
    }
    await query.edit_message_text(f"Enter new {labels[field]}:")
    return EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data["edit_field"]
    event_id = context.user_data["edit_event_id"]
    text = update.message.text
    value = text

    if field == "max_players":
        try:
            value = int(text)
            if value < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Please enter a positive number:")
            return EDIT_VALUE

    if field == "event_date":
        try:
            datetime.strptime(text, "%Y-%m-%d %H:%M")
        except ValueError:
            await update.message.reply_text("Invalid format. Use YYYY-MM-DD HH:MM:")
            return EDIT_VALUE

    event_utils.update_event(event_id, {field: value})
    context.user_data.clear()

    event = event_utils.get_event(event_id)
    await update.message.reply_text(
        f"Event updated!\n\n{format_event(event)}", parse_mode="HTML"
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /delete conversation (private only)
# ---------------------------------------------------------------------------

async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private(update):
        await update.message.reply_text("This command only works in private chat. DM me!")
        return ConversationHandler.END

    events = get_user_events(update.effective_user.id)
    if not events:
        await update.message.reply_text("You have no events to delete.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Select an event to delete:",
        reply_markup=event_list_keyboard(events, "del_sel"),
    )
    return DELETE_SELECT


async def delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"Delete <b>{event['title']}</b>?\n\n{format_event(event)}",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard(event_id),
    )
    return DELETE_CONFIRM


async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("del_no"):
        await query.edit_message_text("Deletion cancelled.")
        return ConversationHandler.END

    event_id = query.data.split(":", 1)[1]
    event_utils.delete_event(event_id)
    await query.edit_message_text("Event deleted.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /post (group only) + join/leave callbacks
# ---------------------------------------------------------------------------

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("This command only works in group chats.")
        return

    events = get_user_events(update.effective_user.id)
    if not events:
        await update.message.reply_text("You have no events to post.")
        return

    await update.message.reply_text(
        "Select an event to post:",
        reply_markup=event_list_keyboard(events, "post"),
    )


async def post_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)
    if not event:
        await query.edit_message_text("Event not found.")
        return

    keyboard = join_leave_keyboard(event_id)
    text = format_event(event)

    if event.get("photo_id"):
        sent = await query.message.chat.send_photo(
            photo=event["photo_id"],
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    else:
        sent = await query.message.chat.send_message(
            text, parse_mode="HTML", reply_markup=keyboard,
        )
    event_utils.update_event(event_id, {"message_id": sent.message_id})
    await query.edit_message_text("Event posted!")


async def _update_posted_message(query, event, event_id):
    """Update the posted event message (handles both text and photo posts)."""
    text = format_event(event)
    keyboard = join_leave_keyboard(event_id)
    if query.message.photo:
        await query.edit_message_caption(
            caption=text, parse_mode="HTML", reply_markup=keyboard,
        )
    else:
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=keyboard,
        )


async def join_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)

    if not event:
        await query.answer("This event no longer exists.", show_alert=True)
        return

    player_id = update.effective_user.id

    if player_id in event["players"]:
        await query.answer("You've already joined.")
        return

    if len(event["players"]) >= event["max_players"]:
        await query.answer("Event is full!", show_alert=True)
        return

    event_utils.add_player(event_id, player_id)
    event = event_utils.get_event(event_id)
    await query.answer("You joined!")
    await _update_posted_message(query, event, event_id)


async def leave_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)

    if not event:
        await query.answer("This event no longer exists.", show_alert=True)
        return

    player_id = update.effective_user.id

    if player_id not in event["players"]:
        await query.answer("You're not in this event.")
        return

    event_utils.remove_player(event_id, player_id)
    event = event_utils.get_event(event_id)
    await query.answer("You left.")
    await _update_posted_message(query, event, event_id)


# ---------------------------------------------------------------------------
# /rollcall (group only)
# ---------------------------------------------------------------------------

async def rollcall_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("This command only works in group chats.")
        return

    events = get_user_events(update.effective_user.id)
    if not events:
        await update.message.reply_text("You have no events.")
        return

    await update.message.reply_text(
        "Select an event for rollcall:",
        reply_markup=event_list_keyboard(events, "rollcall"),
    )


async def rollcall_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    event_id = query.data.split(":", 1)[1]
    event = event_utils.get_event(event_id)

    if not event:
        await query.edit_message_text("Event not found.")
        return

    players = event.get("players", [])
    if not players:
        await query.edit_message_text(
            f"No players signed up for <b>{event['title']}</b>.",
            parse_mode="HTML",
        )
        return

    mentions = " ".join(
        f'<a href="tg://user?id={pid}">player</a>' for pid in players
    )
    await query.edit_message_text(
        f"Rollcall for <b>{event['title']}</b>:\n\n{mentions}",
        parse_mode="HTML",
    )
