import asyncio
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from twikit import Client

logger = logging.getLogger(__name__)

_client_instance: Optional[Client] = None

def get_twikit_client(ct0: str, auth_token: str) -> Client:
    global _client_instance
    if _client_instance is None:
        client = Client('en-US')
        client.set_cookies({
            'ct0': ct0,
            'auth_token': auth_token
        })
        _client_instance = client
    return _client_instance

async def fetch_candidate_tweets(
    keywords: List[str],
    ct0: str,
    auth_token: str,
    max_tweets_per_section: int = 20
) -> List[Dict[str, Any]]:
    client = get_twikit_client(ct0, auth_token)
    candidates = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

    for keyword in keywords:
        logger.info(f"Searching X for keyword: '{keyword}' (20 Top + 20 Latest)")
        for product_type in ['Top', 'Latest']:
            try:
                tweets = await client.search_tweet(keyword, product=product_type, count=max_tweets_per_section)
                if not tweets:
                    logger.warning(f"No tweets returned by X for keyword '{keyword}' in {product_type}")
                    continue

                for t in tweets:
                    created_at = getattr(t, 'created_at_datetime', None)
                    if not created_at:
                        created_at = datetime.now(timezone.utc)
                    elif created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    # For Latest, filter posts older than 48 hours to account for timezone skew.
                    # For Top, allow top-ranking posts from the past 7 days.
                    max_hours = 48 if product_type == 'Latest' else 168
                    if created_at < datetime.now(timezone.utc) - timedelta(hours=max_hours):
                        continue

                    screen_name = getattr(t.user, 'screen_name', 'unknown') if hasattr(t, 'user') and t.user else 'unknown'
                    name = getattr(t.user, 'name', 'Unknown User') if hasattr(t, 'user') and t.user else 'Unknown User'

                    candidates.append({
                        "tweet_id": str(t.id),
                        "author_handle": screen_name,
                        "author_name": name,
                        "created_at": created_at.isoformat(),
                        "text": str(t.text),
                        "keyword": keyword,
                        "url": f"https://x.com/{screen_name}/status/{t.id}"
                    })
            except Exception as e:
                logger.error(f"Error searching X for keyword '{keyword}' in {product_type}: {e}", exc_info=True)
                if "429" in str(e):
                    logger.warning("X Rate Limit hit (HTTP 429). Pausing scraper execution...")
                    break


            # Anti-ban human jitter sleep between requests (3 to 7 seconds)
            jitter_delay = random.uniform(3.0, 7.0)
            await asyncio.sleep(jitter_delay)

    return candidates
