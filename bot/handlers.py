from telegram import Update
from telegram.ext import ContextTypes


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")


async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("create_event")


async def view_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("view_events")


async def edit_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("edit_event")


async def delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("delete_event")


async def rollcall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("rollcall")
