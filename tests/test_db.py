import os
import pytest
from src.db import (
    init_db,
    save_keywords,
    get_active_keywords,
    is_tweet_seen,
    save_tweet_lead,
    get_lead_by_id,
)

TEST_DB = "data/test_leads.db"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_db_initialization_and_keywords():
    init_db(TEST_DB)
    save_keywords(12345, ["ai automation", "n8n", "make.com"], TEST_DB)
    keywords = get_active_keywords(TEST_DB)
    assert keywords == ["ai automation", "n8n", "make.com"]

def test_tweet_deduplication():
    init_db(TEST_DB)
    assert not is_tweet_seen("tweet_100", TEST_DB)
    lead_info = {
        "tweet_id": "tweet_100",
        "author_handle": "testuser",
        "created_at": "2026-09-17T10:00:00Z",
        "text": "Need help setting up AI workflow",
        "is_lead": True,
        "reason": "Asks for AI workflow setup",
        "suggested_comment": "I can help build that workflow for you!"
    }
    save_tweet_lead(lead_info, TEST_DB)
    assert is_tweet_seen("tweet_100", TEST_DB)
    fetched = get_lead_by_id("tweet_100", TEST_DB)
    assert fetched is not None
    assert fetched["author_handle"] == "testuser"
    assert fetched["suggested_comment"] == "I can help build that workflow for you!"
