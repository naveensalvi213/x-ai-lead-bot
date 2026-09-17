# tests/test_main.py
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

TEST_DB = "data/test_main_leads.db"

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    monkeypatch.setenv("DB_PATH", TEST_DB)
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    from src.db import init_db
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_health_check(monkeypatch):
    from src.db import save_keywords
    save_keywords(12345, ["ai automation", "n8n"], TEST_DB)
    
    from main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "X AI Lead Generation Bot"
    assert data["active_keywords"] == ["ai automation", "n8n"]

def test_serve_webapp():
    from main import app
    client = TestClient(app)
    response = client.get("/webapp")
    assert response.status_code == 200
    assert "<title>AI Automation Lead Details</title>" in response.text
    assert "https://telegram.org/js/telegram-web-app.js" in response.text

def test_get_lead_api_success():
    from src.db import save_tweet_lead
    lead_info = {
        "tweet_id": "tweet_555",
        "author_handle": "leaduser",
        "created_at": "2026-09-17T11:00:00Z",
        "text": "Need AI workflow automation for agency intake",
        "is_lead": True,
        "reason": "Explicit ask for AI automation",
        "suggested_comment": "We can build this custom intake workflow for you."
    }
    save_tweet_lead(lead_info, TEST_DB)

    from main import app
    client = TestClient(app)
    response = client.get("/api/lead/tweet_555")
    assert response.status_code == 200
    data = response.json()
    assert data["tweet_id"] == "tweet_555"
    assert data["author_handle"] == "leaduser"
    assert data["is_lead"] == 1 or data["is_lead"] is True
    assert data["reason"] == "Explicit ask for AI automation"

def test_get_lead_api_not_found():
    from main import app
    client = TestClient(app)
    response = client.get("/api/lead/nonexistent_id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Lead not found"

@pytest.mark.asyncio
async def test_scheduler_cycle(monkeypatch):
    from src.db import save_keywords, is_tweet_seen, get_lead_by_id
    save_keywords(123, ["n8n"], TEST_DB)

    monkeypatch.setenv("X_CT0", "test_ct0")
    monkeypatch.setenv("X_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")
    monkeypatch.setenv("WEBAPP_URL", "https://testbot.com")

    candidate = {
        "tweet_id": "scheduled_tweet_1",
        "author_handle": "sched_author",
        "created_at": "2026-09-17T12:00:00Z",
        "text": "Looking for n8n expert to build workflow",
        "keyword": "n8n",
        "url": "https://x.com/sched_author/status/scheduled_tweet_1"
    }

    eval_result = {
        "is_lead": True,
        "confidence_score": 9,
        "service_match_reason": "Needs n8n workflow expert",
        "suggested_comment": "I am an n8n automation expert!"
    }

    mock_bot = AsyncMock()
    
    with patch("src.scheduler.fetch_candidate_tweets", new_callable=AsyncMock, return_value=[candidate]) as mock_fetch, \
         patch("src.scheduler.evaluate_tweet_lead", new_callable=AsyncMock, return_value=eval_result), \
         patch("src.scheduler.Bot", return_value=mock_bot):
        
        from src.scheduler import run_lead_generation_cycle
        await run_lead_generation_cycle(target_keywords=["n8n"], target_chat_id="654321", db_path=TEST_DB)

        assert is_tweet_seen("scheduled_tweet_1", TEST_DB)
        saved = get_lead_by_id("scheduled_tweet_1", TEST_DB)
        assert saved["reason"] == "Needs n8n workflow expert"
        assert mock_bot.send_message.call_count == 2
        lead_msg_call = mock_bot.send_message.call_args_list[0]
        summary_msg_call = mock_bot.send_message.call_args_list[1]
        assert lead_msg_call.kwargs["chat_id"] == "654321"
        assert summary_msg_call.kwargs["chat_id"] == "654321"
        assert "Scan Complete" in summary_msg_call.kwargs["text"]
        assert "*Qualified Leads Found:* 1" in summary_msg_call.kwargs["text"]
        mock_fetch.assert_called_once_with(["n8n"], ct0="test_ct0", auth_token="test_token", max_tweets_per_section=20)
