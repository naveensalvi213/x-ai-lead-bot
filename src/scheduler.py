# src/scheduler.py
import os
import logging
from typing import Optional
from telegram import Bot
from src.db import get_active_keywords, is_tweet_seen, save_tweet_lead
from src.scraper import fetch_candidate_tweets
from src.evaluator import evaluate_tweet_lead
from src.bot import create_lead_notification

logger = logging.getLogger(__name__)

async def run_lead_generation_cycle(
    target_keywords: Optional[list[str]] = None,
    target_chat_id: Optional[str] = None,
    db_path: str = "data/leads.db"
) -> None:
    """
    Fetches active keywords from SQLite database (or target_keywords), searches X for candidate tweets,
    filters unseen tweets, evaluates lead quality using Gemini 2.5 Flash Lite,
    saves evaluated leads to SQLite, streams lead notifications to Telegram in real-time,
    and sends a final scan summary message.
    """
    logger.info("Executing X lead generation cycle...")
    
    keywords = target_keywords or get_active_keywords(db_path=db_path)
    if not keywords:
        logger.info("No active keywords set. Skipping cycle.")
        return

    ct0 = os.getenv("X_CT0", "")
    auth_token = os.getenv("X_AUTH_TOKEN", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    raw_chat_ids = target_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    chat_ids = [cid.strip() for cid in raw_chat_ids.split(",") if cid.strip()]
    webapp_url = os.getenv("WEBAPP_URL", "https://localhost:8080")

    bot = Bot(token=bot_token)

    from src.scraper import verify_x_credentials
    valid_cookies = await verify_x_credentials(ct0, auth_token)
    if not valid_cookies:
        alert_msg = (
            "⚠️ *X Session Cookies Expired\\!*\n\n"
            "Your X `auth_token` or `ct0` session cookies have expired or were logged out by X\\. "
            "Please log into X in your browser, copy your new `auth_token` and `ct0` cookies, and update your bot configuration\\."
        )
        for cid in chat_ids:
            try:
                await bot.send_message(chat_id=cid, text=alert_msg, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Error sending cookie alert to chat {cid}: {e}")
        return

    candidates = await fetch_candidate_tweets(keywords, ct0=ct0, auth_token=auth_token, max_tweets_per_section=20)

    evaluated_count = 0
    leads_found = 0

    for tweet in candidates:
        tweet_id = tweet["tweet_id"]
        if is_tweet_seen(tweet_id, db_path=db_path):
            continue

        evaluated_count += 1
        eval_res = await evaluate_tweet_lead(tweet["text"], gemini_key)
        
        lead_data = {
            "tweet_id": tweet_id,
            "author_handle": tweet["author_handle"],
            "created_at": tweet["created_at"],
            "text": tweet["text"],
            "is_lead": eval_res.get("is_lead", False),
            "reason": eval_res.get("service_match_reason", ""),
            "suggested_comment": eval_res.get("suggested_comment", "")
        }
        
        save_tweet_lead(lead_data, db_path=db_path)

        if lead_data["is_lead"]:
            leads_found += 1
            msg_text, keyboard = create_lead_notification(lead_data, webapp_url)
            for cid in chat_ids:
                try:
                    await bot.send_message(
                        chat_id=cid,
                        text=msg_text,
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Error sending lead card to chat {cid}: {e}")

    # Send final summary
    summary_text = (
        f"✅ *Scan Complete\\!*\n\n"
        f"🔍 *Keywords Scanned:* {len(keywords)}\n"
        f"📊 *New Posts Evaluated:* {evaluated_count}\n"
        f"🎯 *Qualified Leads Found:* {leads_found}"
    )
    for cid in chat_ids:
        try:
            await bot.send_message(chat_id=cid, text=summary_text, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Error sending summary to chat {cid}: {e}")

