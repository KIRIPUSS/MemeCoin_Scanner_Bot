import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from scanner import run_full_pipeline 


# Enable logging (optional but recommended)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ThreadPoolExecutor for running blocking scan without freezing bot
executor = ThreadPoolExecutor(max_workers=1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Starting scan, please wait... This might take a moment.")

    # Run the blocking scanning function in separate thread to not block the event loop
    loop = asyncio.get_event_loop()
    safe_tokens = await loop.run_in_executor(executor, run_full_pipeline, 50, 5)

    if not safe_tokens:
        await update.message.reply_text("❌ No safe tokens found.")
        return

    # Build the result message
    result_msg = "✅ Scan finished! Here are the safe tokens found:\n\n"
    for i, token in enumerate(safe_tokens, 1):
        result_msg += f"#{i} {token['token']}\n{token['report']}\n{'-'*40}\n"

    # Send the full result (you can chunk if too long)
    await update.message.reply_text(result_msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /start to run the token scan.")


def main():
    # Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your bot token string
    app = ApplicationBuilder().token("7643316985:AAFYQbYZS9gvQ0pQGyVLIBFgQ7qyidwlOAs").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    print("Bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
