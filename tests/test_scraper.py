import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from src.scraper import fetch_candidate_tweets, get_twikit_client

@pytest.mark.asyncio
async def test_get_twikit_client():
    with patch("src.scraper.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        
        # Reset cached instance if any
        import src.scraper
        src.scraper._client_instance = None
        
        client = get_twikit_client(ct0="test_ct0", auth_token="test_token")
        
        mock_client_cls.assert_called_once_with('en-US')
        mock_instance.set_cookies.assert_called_once_with({
            'ct0': 'test_ct0',
            'auth_token': 'test_token'
        })
        assert client == mock_instance

@pytest.mark.asyncio
async def test_fetch_candidate_tweets_success_and_filtering():
    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(hours=2)
    old_time = now - timedelta(hours=26)

    recent_tweet = MagicMock()
    recent_tweet.id = "recent_123"
    recent_tweet.user.screen_name = "recent_user"
    recent_tweet.user.name = "Recent User"
    recent_tweet.text = "Looking for AI automation software!"
    recent_tweet.created_at_datetime = recent_time

    old_tweet = MagicMock()
    old_tweet.id = "old_456"
    old_tweet.user.screen_name = "old_user"
    old_tweet.user.name = "Old User"
    old_tweet.text = "Looking for AI automation software old post"
    old_tweet.created_at_datetime = old_time

    mock_client = AsyncMock()
    # Return recent_tweet for 'Top' and old_tweet for 'Latest'
    mock_client.search_tweet.side_effect = [
        [recent_tweet],
        [old_tweet]
    ]

    with patch("src.scraper.get_twikit_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        import src.scraper
        src.scraper._client_instance = mock_client

        results = await fetch_candidate_tweets(
            keywords=["ai automation"],
            ct0="mock_ct0",
            auth_token="mock_token",
            max_tweets_per_section=20
        )

        assert len(results) == 1
        assert results[0]["tweet_id"] == "recent_123"
        assert results[0]["author_handle"] == "recent_user"
        assert results[0]["keyword"] == "ai automation"
        assert results[0]["url"] == "https://x.com/recent_user/status/recent_123"

        # Check that search_tweet was called for both Top and Latest
        assert mock_client.search_tweet.call_count == 2
        mock_client.search_tweet.assert_any_call("ai automation", product="Top", count=20)
        mock_client.search_tweet.assert_any_call("ai automation", product="Latest", count=20)

        # Check that asyncio.sleep was called with human delay (3 to 7 s)
        assert mock_sleep.call_count == 2
        for call_args in mock_sleep.call_args_list:
            delay = call_args[0][0]
            assert 3.0 <= delay <= 7.0

@pytest.mark.asyncio
async def test_fetch_candidate_tweets_rate_limit_handling():
    mock_client = AsyncMock()
    mock_client.search_tweet.side_effect = Exception("HTTP 429 Too Many Requests")

    with patch("src.scraper.get_twikit_client", return_value=mock_client), \
         patch("asyncio.sleep", new_callable=AsyncMock):

        results = await fetch_candidate_tweets(
            keywords=["rate_limited_kw"],
            ct0="mock_ct0",
            auth_token="mock_token"
        )

        assert results == []
