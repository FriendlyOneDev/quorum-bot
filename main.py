from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
from datetime import datetime
import os


# Load environment variables
load_dotenv()
api_key = os.getenv("TELEGRAM_TOKEN")
admin_id = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None


# Function to send error messages to the admin
async def send_error_message(context: ContextTypes.DEFAULT_TYPE, matches, error_msg=""):
    # error_message = (
    #     "The following links could not be processed:\n"
    #     + "\n".join(matches)
    #     + "\n"
    #     + error_msg
    # )
    # await context.bot.send_message(chat_id=admin_id, text=error_message)
    pass

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

async def on_startup(app):
    if admin_id:
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await app.bot.send_message(
            chat_id=admin_id,
            text=f"Bot started successfully at {start_time}"
        )

if __name__ == "__main__":
    # Bot setup and start polling
    request = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=60.0,
        write_timeout=60.0,
        pool_timeout=10.0,
        media_write_timeout=60.0,
    )

    app = (ApplicationBuilder()
           .token(api_key)
           .request(request)
           .post_init(on_startup)
           .build())

    app.add_handler(CommandHandler("ping", ping))

    app.run_polling()
