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

async def run_lead_generation_cycle(db_path: str = "data/leads.db") -> None:
    """
    Fetches active keywords from SQLite database, searches X for candidate tweets,
    filters unseen tweets, evaluates lead quality using Gemini 2.5 Flash Lite,
    saves evaluated leads to SQLite, and sends Telegram notifications for positive leads.
    """
    logger.info("Executing scheduled X lead generation cycle...")
    
    keywords = get_active_keywords(db_path=db_path)
    if not keywords:
        logger.info("No active keywords set. Skipping cycle.")
        return

    ct0 = os.getenv("X_CT0", "")
    auth_token = os.getenv("X_AUTH_TOKEN", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    webapp_url = os.getenv("WEBAPP_URL", "https://localhost:8080")

    if not all([ct0, auth_token, gemini_key, bot_token, chat_id]):
        logger.error("Missing required environment variables for lead generation cycle.")
        return

    bot = Bot(token=bot_token)
    candidates = await fetch_candidate_tweets(keywords, ct0=ct0, auth_token=auth_token)

    for tweet in candidates:
        tweet_id = tweet["tweet_id"]
        if is_tweet_seen(tweet_id, db_path=db_path):
            continue

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
            msg_text, keyboard = create_lead_notification(lead_data, webapp_url)
            await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
