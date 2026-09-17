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
                for t in tweets:
                    # Check age limit (last 24 hours)
                    created_at = getattr(t, 'created_at_datetime', None) or datetime.now(timezone.utc)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    
                    if created_at < cutoff_time:
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
                logger.error(f"Error searching X for keyword '{keyword}' in {product_type}: {e}")
                if "429" in str(e):
                    logger.warning("X Rate Limit hit (HTTP 429). Pausing scraper execution...")
                    break

            # Anti-ban human jitter sleep between requests (3 to 7 seconds)
            jitter_delay = random.uniform(3.0, 7.0)
            await asyncio.sleep(jitter_delay)

    return candidates
