import asyncio
import random
import logging
import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from twikit import Client

from twikit.x_client_transaction.transaction import ClientTransaction

logger = logging.getLogger(__name__)

# Monkey-patch twikit ClientTransaction.get_indices to prevent KEY_BYTE indices errors on X frontend changes
_original_get_indices = ClientTransaction.get_indices

async def _patched_get_indices(self, home_page_response, session, headers):
    try:
        return await _original_get_indices(self, home_page_response, session, headers)
    except Exception as e:
        logger.warning(f"Twikit get_indices fallback triggered: {e}")
        return 3, [12, 14, 7]

ClientTransaction.get_indices = _patched_get_indices

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

async def verify_x_credentials(ct0: str, auth_token: str) -> bool:
    """Verifies if the provided X ct0 and auth_token cookies are active and valid."""
    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnv1FZZRewM25D69s%2FZyGQ8VkiVw%3D9AnNwIzUejRydW",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "cookie": f"ct0={ct0}; auth_token={auth_token}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as http:
        try:
            res = await http.get("https://x.com/i/api/1.1/account/verify_credentials.json")
            if res.status_code == 200:
                logger.info("X credentials verified successfully.")
                return True
            else:
                logger.error(f"X cookie verification failed: HTTP {res.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error verifying X cookies: {e}")
            return False

async def fetch_candidate_tweets(
    keywords: List[str],
    ct0: str,
    auth_token: str,
    max_tweets_per_section: int = 20
) -> List[Dict[str, Any]]:
    client = get_twikit_client(ct0, auth_token)
    candidates = []

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
                logger.error(f"Error searching X for keyword '{keyword}' in {product_type}: {e}")
                if "429" in str(e):
                    logger.warning("X Rate Limit hit (HTTP 429). Pausing search...")
                    break
                elif "401" in str(e) or "403" in str(e) or "Unauthorized" in str(e):
                    logger.error("X Authentication failed (HTTP 401/403). Cookies have expired!")
                    break

            await asyncio.sleep(random.uniform(3.0, 7.0))

    return candidates
