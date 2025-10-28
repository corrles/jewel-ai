from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from ..core.agent import Agent
from ..memory.sqlite_store import SqliteStore
from ..config import settings
from ..logging_setup import logger

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi, I'm Jewel. Talk to me.")

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: Agent = context.application.bot_data["agent"]
    reply = agent.ask(update.message.text)
    await update.message.reply_text(reply)

async def run_telegram():
    store = SqliteStore(settings.db_path)
    agent = Agent(store)

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["agent"] = agent
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))

    logger.info("[telegram] polling…")
    await app.run_polling()