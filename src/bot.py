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
            "• `/id` \\- Show Chat / Group ID\n"
            "• `/search <keywords>` \\- Search keywords in group or chat",
            parse_mode="MarkdownV2"
        )

async def handle_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.effective_chat:
        chat_id = update.effective_chat.id
        chat_title = update.effective_chat.title or update.effective_chat.username or "Private Chat"
        await update.message.reply_text(
            f"🆔 *Chat Information*\n\n"
            f"• *Name:* `{chat_title}`\n"
            f"• *Chat ID:* `{chat_id}`",
            parse_mode="Markdown"
        )

async def handle_search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    if not update.message or not update.effective_chat:
        return
    text = " ".join(context.args) if context.args else ""
    if not text and update.message.text:
        text = update.message.text.replace("/search", "").strip()
    
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    if not keywords:
        await update.message.reply_text("❌ Please specify keywords! Example: `/search ai automation, n8n`", parse_mode="Markdown")
        return

    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id if update.effective_user else 0

    save_keywords(user_id, keywords, db_path=db_path)
    kw_str = ", ".join(keywords)
    await update.message.reply_text(
        f"✅ *Keywords Received\\!*\n\n"
        f"🔍 *Active Keywords:* `{kw_str}`\n"
        f"⚡ *Starting instant search on X \\(20 Top \\+ 20 Latest per keyword\\)\\.\\.\\.*",
        parse_mode="MarkdownV2"
    )
    
    from src.scheduler import run_lead_generation_cycle
    import asyncio
    asyncio.create_task(run_lead_generation_cycle(target_keywords=keywords, target_chat_id=chat_id, db_path=db_path))

async def handle_keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    from src.db import get_active_keywords
    if update.message:
        active = get_active_keywords(db_path=db_path)
        if active:
            kw_str = ", ".join(active)
            await update.message.reply_text(f"🔍 *Active Keywords:* `{kw_str}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ No active keywords set. Send me a message or use `/search keyword1, keyword2`!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    if not update or not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    
    if not update.effective_chat:
        return
        
    user_id = update.effective_user.id if update.effective_user else 0
    chat_id = str(update.effective_chat.id)

    if keywords:
        save_keywords(user_id, keywords, db_path=db_path)
        kw_str = ", ".join(keywords)
        await update.message.reply_text(
            f"✅ *Keywords Received\\!*\n\n"
            f"🔍 *Active Keywords:* `{kw_str}`\n"
            f"⚡ *Starting instant search on X \\(20 Top \\+ 20 Latest per keyword\\)\\.\\.\\.*",
            parse_mode="MarkdownV2"
        )
        
        # Trigger immediate search pipeline for these keywords
        from src.scheduler import run_lead_generation_cycle
        import asyncio
        asyncio.create_task(run_lead_generation_cycle(target_keywords=keywords, target_chat_id=chat_id, db_path=db_path))

def build_telegram_app(token: str, db_path: str = "data/leads.db") -> Application:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    
    app = ApplicationBuilder().token(token).build()

    async def msg_wrapper(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await handle_message(u, c, db_path=db_path)

    async def keywords_wrapper(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await handle_keywords_cmd(u, c, db_path=db_path)

    async def search_wrapper(u: Update, c: ContextTypes.DEFAULT_TYPE):
        await handle_search_cmd(u, c, db_path=db_path)

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("id", handle_id_cmd))
    app.add_handler(CommandHandler("keywords", keywords_wrapper))
    app.add_handler(CommandHandler("search", search_wrapper))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_wrapper))
    return app


