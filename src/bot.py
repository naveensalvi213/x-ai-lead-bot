import logging
from typing import Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, Application
from src.db import save_keywords

logger = logging.getLogger(__name__)

def create_lead_notification(lead: Dict[str, Any], webapp_base_url: str) -> Tuple[str, InlineKeyboardMarkup]:
    text = (
        f"🎯 *New AI Lead Found\\!*\n\n"
        f"👤 *Author:* @{lead['author_handle']}\n"
        f"📝 *Tweet:* {lead['text'][:180]}...\n\n"
        f"💡 *Opportunity:* {lead['reason']}\n"
    )
    
    base_url = webapp_base_url.rstrip("/")
    webapp_url = f"{base_url}/webapp?id={lead['tweet_id']}"
    tweet_url = f"https://x.com/{lead['author_handle']}/status/{lead['tweet_id']}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Open Lead in WebApp", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("🔗 Open Tweet on X", url=tweet_url)]
    ])
    
    return text, keyboard

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "👋 *Welcome to X AI Lead Generation Bot\\!*\n\n"
            "Send me any comma\\-separated keywords you want to monitor on X \\(e\\.g\\., `ai automation, n8n, make.com`\\)\\.\n\n"
            "Commands:\n"
            "• `/keywords` \\- Show active keywords\n"
            "• `/status` \\- Check bot status",
            parse_mode="MarkdownV2"
        )

async def handle_keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    from src.db import get_active_keywords
    if update.message:
        active = get_active_keywords(db_path=db_path)
        if active:
            kw_str = ", ".join(active)
            await update.message.reply_text(f"🔍 *Active Keywords:* `{kw_str}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ No active keywords set. Send me a message with comma-separated keywords to set them!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    if not update or not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    
    if not update.effective_user:
        return
        
    user_id = update.effective_user.id

    if keywords:
        save_keywords(user_id, keywords, db_path=db_path)
        kw_str = ", ".join(keywords)
        await update.message.reply_text(
            f"✅ Keywords saved!\n🔍 *Active Keywords:* `{kw_str}`\n\nStarting immediate scan of X for leads...",
            parse_mode="Markdown"
        )
        
        # Trigger immediate async background scan
        from src.scheduler import run_lead_generation_cycle
        import asyncio
        asyncio.create_task(run_lead_generation_cycle(db_path=db_path))

def build_telegram_app(token: str, db_path: str = "data/leads.db") -> Application:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    
    app = ApplicationBuilder().token(token).build()

    async def msg_wrapper(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await handle_message(u, c, db_path=db_path)

    async def keywords_wrapper(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await handle_keywords_cmd(u, c, db_path=db_path)

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("keywords", keywords_wrapper))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_wrapper))
    return app

