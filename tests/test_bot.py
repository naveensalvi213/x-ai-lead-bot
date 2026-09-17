import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import InlineKeyboardMarkup, WebAppInfo
from src.db import init_db, get_active_keywords
from src.bot import create_lead_notification, handle_message

TEST_DB = "data/test_bot_leads.db"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_create_lead_notification():
    lead = {
        "tweet_id": "987654321",
        "author_handle": "ai_founder",
        "text": "Looking for someone to automate lead generation using AI and Telegram bot",
        "reason": "Explicitly requests AI lead generation bot build",
        "suggested_comment": "I built an automated lead bot pipeline that does exactly this!"
    }
    webapp_base_url = "https://my-lead-bot.onrender.com"

    text, keyboard = create_lead_notification(lead, webapp_base_url)

    assert "@ai_founder" in text
    assert "Looking for someone to automate lead generation" in text
    assert "Explicitly requests AI lead generation bot build" in text
    
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert len(keyboard.inline_keyboard) == 2
    
    # Check WebApp button
    webapp_btn = keyboard.inline_keyboard[0][0]
    assert webapp_btn.text == "📱 Open Lead in WebApp"
    assert webapp_btn.web_app.url == "https://my-lead-bot.onrender.com/webapp?id=987654321"
    
    # Check Tweet link button
    tweet_btn = keyboard.inline_keyboard[1][0]
    assert tweet_btn.text == "🔗 Open Tweet on X"
    assert tweet_btn.url == "https://x.com/ai_founder/status/987654321"

@pytest.mark.asyncio
async def test_handle_message_saves_keywords():
    mock_user = MagicMock()
    mock_user.id = 55555

    mock_chat = MagicMock()
    mock_chat.id = 77777

    mock_message = AsyncMock()
    mock_message.text = "ai automation, n8n, make.com, python bot"

    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat

    mock_context = MagicMock()

    from unittest.mock import patch
    def close_coro(coro):
        coro.close()
    with patch("asyncio.create_task", side_effect=close_coro) as mock_create_task:
        await handle_message(mock_update, mock_context, db_path=TEST_DB)
        mock_create_task.assert_called_once()

    saved_keywords = get_active_keywords(TEST_DB)
    assert saved_keywords == ["ai automation", "n8n", "make.com", "python bot"]

    mock_message.reply_text.assert_called_once()
    reply_arg = mock_message.reply_text.call_args[0][0]
    assert "Keywords Received" in reply_arg
    assert "ai automation, n8n, make.com, python bot" in reply_arg
    assert "20 Top" in reply_arg

@pytest.mark.asyncio
async def test_handle_message_empty():
    mock_update = MagicMock()
    mock_update.message = None
    mock_context = MagicMock()

    await handle_message(mock_update, mock_context, db_path=TEST_DB)
    # Should complete without error
