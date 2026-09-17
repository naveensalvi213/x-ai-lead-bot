import logging
from typing import Dict, Any, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes
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
