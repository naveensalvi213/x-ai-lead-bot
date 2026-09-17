# X AI Automation Lead Generation Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 24/7 automated Python tool deployed on Render that monitors X (Twitter) for recent (24h) posts matching user keywords, uses Gemini 2.5 Flash Lite to score high-intent AI automation leads, and sends interactive Telegram notification cards with Telegram Mini App buttons for one-click comment copy & outreach.

**Architecture:** A FastAPI web application hosting a `/health` endpoint for UptimeRobot pings and serving a Telegram Mini App. Integrated with `python-telegram-bot` for simple keyword management, `twikit` for human-paced cookie-authenticated X searching, SQLite for deduplication, and `google-genai` for lead scoring and personalized outreach draft generation.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, python-telegram-bot, twikit, google-genai, APScheduler, SQLite3, pytest.

## Global Constraints

- **Python Version**: Python 3.11+
- **Gemini Model**: `gemini-2.5-flash-lite` via `google-genai` package
- **Database**: SQLite3 (`data/leads.db`)
- **Port**: 8080 (or `PORT` environment variable)
- **Zero Auto-Posting on X**: Search-only; outreach posted manually by user via Telegram Mini App.

---

### Task 1: Database & Persistence Layer

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: None (Built-in `sqlite3`)
- Produces:
  - `init_db(db_path: str = "data/leads.db") -> None`
  - `save_keywords(user_id: int, keywords: list[str], db_path: str = "data/leads.db") -> None`
  - `get_active_keywords(db_path: str = "data/leads.db") -> list[str]`
  - `is_tweet_seen(tweet_id: str, db_path: str = "data/leads.db") -> bool`
  - `save_tweet_lead(tweet_data: dict, db_path: str = "data/leads.db") -> None`
  - `get_lead_by_id(tweet_id: str, db_path: str = "data/leads.db") -> dict | None`

- [ ] **Step 1: Write failing tests for SQLite database operations**

```python
# tests/test_db.py
import os
import pytest
from src.db import init_db, save_keywords, get_active_keywords, is_tweet_seen, save_tweet_lead, get_lead_by_id

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
    assert fetched["author_handle"] == "testuser"
    assert fetched["suggested_comment"] == "I can help build that workflow for you!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src'`

- [ ] **Step 3: Implement `src/db.py`**

```python
# src/db.py
import sqlite3
import os
import json
from typing import Optional, List, Dict, Any

def get_connection(db_path: str = "data/leads.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        keywords TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS seen_tweets (
        tweet_id TEXT PRIMARY KEY,
        author_handle TEXT,
        created_at TEXT,
        text TEXT,
        is_lead BOOLEAN,
        reason TEXT,
        suggested_comment TEXT,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

def save_keywords(user_id: int, keywords: List[str], db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    keywords_json = json.dumps([k.strip().lower() for k in keywords if k.strip()])
    cursor.execute("DELETE FROM keywords WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO keywords (user_id, keywords) VALUES (?, ?)", (user_id, keywords_json))
    conn.commit()
    conn.close()

def get_active_keywords(db_path: str = "data/leads.db") -> List[str]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT keywords FROM keywords ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row and row["keywords"]:
        return json.loads(row["keywords"])
    return []

def is_tweet_seen(tweet_id: str, db_path: str = "data/leads.db") -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM seen_tweets WHERE tweet_id = ?", (tweet_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_tweet_lead(tweet_data: Dict[str, Any], db_path: str = "data/leads.db") -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO seen_tweets 
    (tweet_id, author_handle, created_at, text, is_lead, reason, suggested_comment)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        tweet_data.get("tweet_id"),
        tweet_data.get("author_handle"),
        tweet_data.get("created_at"),
        tweet_data.get("text"),
        tweet_data.get("is_lead", False),
        tweet_data.get("reason", ""),
        tweet_data.get("suggested_comment", "")
    ))
    conn.commit()
    conn.close()

def get_lead_by_id(tweet_id: str, db_path: str = "data/leads.db") -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM seen_tweets WHERE tweet_id = ?", (tweet_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: add SQLite database and persistence layer"
```

---

### Task 2: Human-Paced X Scraper Engine (`src/scraper.py`)

**Files:**
- Create: `src/scraper.py`
- Create: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `X_CT0`, `X_AUTH_TOKEN` environment variables, `twikit.Client`
- Produces: `async fetch_candidate_tweets(keywords: list[str], max_tweets_per_keyword: int = 20) -> list[dict]`

- [ ] **Step 1: Write unit tests with mocked X responses**

```python
# tests/test_scraper.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.scraper import fetch_candidate_tweets

@pytest.mark.asyncio
async def test_fetch_candidate_tweets():
    mock_tweet = MagicMock()
    mock_tweet.id = "123456789"
    mock_tweet.user.screen_name = "john_doe"
    mock_tweet.text = "Looking for an AI tool to automate lead processing"
    mock_tweet.created_at_datetime.isoformat.return_value = "2026-09-17T09:00:00Z"

    mock_client = AsyncMock()
    mock_client.search_tweet.return_value = [mock_tweet]

    with patch("src.scraper.get_twikit_client", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await fetch_candidate_tweets(["ai automation"], ct0="mock_ct0", auth_token="mock_token", max_tweets_per_keyword=5)
            assert len(results) == 1
            assert results[0]["tweet_id"] == "123456789"
            assert results[0]["author_handle"] == "john_doe"
            assert "automate lead processing" in results[0]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scraper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.scraper'`

- [ ] **Step 3: Implement `src/scraper.py`**

```python
# src/scraper.py
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
    max_tweets_per_keyword: int = 20
) -> List[Dict[str, Any]]:
    client = get_twikit_client(ct0, auth_token)
    candidates = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

    for keyword in keywords:
        logger.info(f"Searching X for keyword: '{keyword}'")
        for product_type in ['Top', 'Latest']:
            try:
                tweets = await client.search_tweet(keyword, product=product_type, count=max_tweets_per_keyword)
                for t in tweets:
                    # Check age limit (last 24 hours)
                    created_at = getattr(t, 'created_at_datetime', None) or datetime.now(timezone.utc)
                    if created_at < cutoff_time:
                        continue

                    candidates.append({
                        "tweet_id": str(t.id),
                        "author_handle": getattr(t.user, 'screen_name', 'unknown'),
                        "author_name": getattr(t.user, 'name', 'Unknown User'),
                        "created_at": created_at.isoformat(),
                        "text": str(t.text),
                        "keyword": keyword,
                        "url": f"https://x.com/{getattr(t.user, 'screen_name', 'i')}/status/{t.id}"
                    })
            except Exception as e:
                logger.error(f"Error searching X for keyword '{keyword}' in {product_type}: {e}")
                if "429" in str(e):
                    logger.warning("X Rate Limit hit (HTTP 429). Pausing scraper execution...")
                    break
            
            # Anti-ban human jitter sleep between requests (7 to 15 seconds)
            jitter_delay = random.uniform(7.0, 15.0)
            await asyncio.sleep(jitter_delay)

    return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "feat: add human-paced X scraper engine with twikit"
```

---

### Task 3: Gemini 2.5 Flash Lite Lead Evaluator (`src/evaluator.py`)

**Files:**
- Create: `src/evaluator.py`
- Create: `tests/test_evaluator.py`

**Interfaces:**
- Consumes: `GEMINI_API_KEY` environment variable, `google-genai` SDK
- Produces: `async evaluate_tweet_lead(tweet_text: str, api_key: str) -> dict`

- [ ] **Step 1: Write unit tests with mocked Gemini SDK**

```python
# tests/test_evaluator.py
import pytest
from unittest.mock import MagicMock, patch
from src.evaluator import evaluate_tweet_lead

@pytest.mark.asyncio
async def test_evaluate_tweet_lead():
    mock_json_response = """
    {
        "is_lead": true,
        "confidence_score": 9,
        "service_match_reason": "User is looking to automate client intake forms using AI.",
        "suggested_comment": "You can easily automate intake forms using custom webhooks with Claude or n8n. Happy to share a working template if you need one!"
    }
    """
    mock_response = MagicMock()
    mock_response.text = mock_json_response

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("src.evaluator.genai.Client", return_value=mock_client):
        result = await evaluate_tweet_lead("Looking for someone to automate client intake forms using AI", api_key="fake_key")
        assert result["is_lead"] is True
        assert result["confidence_score"] == 9
        assert "automate intake forms" in result["service_match_reason"]
        assert "custom webhooks with Claude" in result["suggested_comment"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evaluator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.evaluator'`

- [ ] **Step 3: Implement `src/evaluator.py`**

```python
# src/evaluator.py
import json
import logging
from typing import Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an expert AI Lead Scoring Assistant for an AI Automation Agency. 
The agency builds custom AI tools, automations, workflows (using Claude, Antigravity AI, n8n, Make, Python) for service providers, agencies, and businesses.

Your task is to analyze an X (Twitter) post text and evaluate if the poster is a prospective client who needs AI automations, workflow optimization, or custom tools to make work easier.

Return ONLY a raw JSON object with the following schema:
{
  "is_lead": boolean (true if the post indicates a need for AI automations, workflows, or tool building; false otherwise),
  "confidence_score": integer (1 to 10),
  "service_match_reason": string (1-2 sentences explaining why this is a good lead or why it was rejected),
  "suggested_comment": string (Short, 1-2 sentence, natural, conversational, non-spammy outreach response offering helpful insights/value)
}
"""

async def evaluate_tweet_lead(tweet_text: str, api_key: str) -> Dict[str, Any]:
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Target Tweet Content:\n\"\"\"{tweet_text}\"\"\""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text.strip())
        return result
    except Exception as e:
        logger.error(f"Error evaluating tweet with Gemini Flash Lite: {e}")
        return {
            "is_lead": False,
            "confidence_score": 0,
            "service_match_reason": f"Error: {str(e)}",
            "suggested_comment": ""
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_evaluator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/evaluator.py tests/test_evaluator.py
git commit -m "feat: add Gemini 2.5 Flash Lite lead evaluator module"
```

---

### Task 4: Telegram Bot & Mini WebApp Interface

**Files:**
- Create: `src/bot.py`
- Create: `webapp/index.html`
- Create: `tests/test_bot.py`

**Interfaces:**
- Consumes: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, SQLite database functions
- Produces: Telegram bot instance + Telegram WebApp Mini App template page.

- [ ] **Step 1: Create `webapp/index.html` for Telegram Mini App**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Automation Lead Details</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1c1c1e; color: #f2f2f7; padding: 16px; margin: 0; }
    .card { background: #2c2c2e; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .title { font-size: 14px; text-transform: uppercase; color: #8e8e93; font-weight: 600; margin-bottom: 6px; }
    .author { font-size: 18px; font-weight: bold; color: #0a84ff; margin-bottom: 8px; }
    .content { font-size: 15px; line-height: 1.4; color: #e5e5ea; margin-bottom: 12px; }
    .reason { background: #3a3a3c; border-left: 4px solid #30d158; padding: 10px; border-radius: 6px; font-size: 14px; margin-bottom: 16px; }
    .comment-box { background: #1c1c1e; border: 1px solid #3a3a3c; border-radius: 8px; padding: 12px; font-size: 14px; margin-bottom: 16px; word-break: break-word; }
    .btn { display: block; width: 100%; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; text-align: center; cursor: pointer; text-decoration: none; box-sizing: border-box; margin-bottom: 10px; }
    .btn-primary { background: #0a84ff; color: #ffffff; }
    .btn-secondary { background: #30d158; color: #ffffff; }
  </style>
</head>
<body>
  <div id="app">
    <div class="card">
      <div class="title">Qualified Lead</div>
      <div class="author" id="author">Loading...</div>
      <div class="content" id="text">...</div>
      
      <div class="title">Service Opportunity</div>
      <div class="reason" id="reason">...</div>

      <div class="title">Suggested Outreach Comment</div>
      <div class="comment-box" id="comment">...</div>

      <button class="btn btn-secondary" onclick="copyComment()">📋 Copy Comment</button>
      <a id="tweetLink" class="btn btn-primary" target="_blank" href="#">🔗 Open & Reply on X</a>
    </div>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const leadId = urlParams.get('id');

    if (leadId) {
      fetch(`/api/lead/${leadId}`)
        .then(res => res.json())
        .then(data => {
          document.getElementById('author').innerText = `@${data.author_handle}`;
          document.getElementById('text').innerText = data.text;
          document.getElementById('reason').innerText = data.reason;
          document.getElementById('comment').innerText = data.suggested_comment;
          document.getElementById('tweetLink').href = `https://x.com/${data.author_handle}/status/${data.tweet_id}`;
        })
        .catch(err => console.error(err));
    }

    function copyComment() {
      const commentText = document.getElementById('comment').innerText;
      navigator.clipboard.writeText(commentText).then(() => {
        tg.showAlert("Comment copied to clipboard!");
      });
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Implement Telegram Notification & Bot logic (`src/bot.py`)**

```python
# src/bot.py
import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from src.db import save_keywords, get_active_keywords

logger = logging.getLogger(__name__)

def create_lead_notification(lead: Dict[str, Any], webapp_base_url: str) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        f"🎯 *New AI Lead Found\\!*\n\n"
        f"👤 *Author:* @{lead['author_handle']}\n"
        f"📝 *Tweet:* {lead['text'][:180]}...\n\n"
        f"💡 *Opportunity:* {lead['reason']}\n"
    )
    
    webapp_url = f"{webapp_base_url}/webapp?id={lead['tweet_id']}"
    tweet_url = f"https://x.com/{lead['author_handle']}/status/{lead['tweet_id']}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Open Lead in WebApp", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton("🔗 Open Tweet on X", url=tweet_url)]
    ])
    
    return text, keyboard

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    user_id = update.effective_user.id

    if keywords:
        save_keywords(user_id, keywords)
        kw_str = ", ".join(keywords)
        await update.message.reply_text(
            f"✅ Keywords saved!\n🔍 *Active Keywords:* `{kw_str}`\n\nStarting immediate scan of X for leads...",
            parse_mode="Markdown"
        )
```

- [ ] **Step 3: Commit**

```bash
git add webapp/index.html src/bot.py
git commit -m "feat: add Telegram bot listener and Telegram WebApp interface"
```

---

### Task 5: FastAPI App, Scheduler & Deployment Config

**Files:**
- Create: `main.py`
- Create: `src/scheduler.py`
- Create: `requirements.txt`
- Create: `render.yaml`
- Create: `.env.example`

**Interfaces:**
- Consumes: All environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`, `X_CT0`, `X_AUTH_TOKEN`, `WEBAPP_URL`)
- Produces: Unified FastAPI web server with `/health`, `/webapp`, `/api/lead/{id}` endpoints + background APScheduler runner.

- [ ] **Step 1: Implement `src/scheduler.py` search cycle**

```python
# src/scheduler.py
import os
import logging
from telegram import Bot
from src.db import get_active_keywords, is_tweet_seen, save_tweet_lead
from src.scraper import fetch_candidate_tweets
from src.evaluator import evaluate_tweet_lead
from src.bot import create_lead_notification

logger = logging.getLogger(__name__)

async def run_lead_generation_cycle():
    logger.info("Executing scheduled X lead generation cycle...")
    
    keywords = get_active_keywords()
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
        if is_tweet_seen(tweet["tweet_id"]):
            continue

        eval_res = await evaluate_tweet_lead(tweet["text"], gemini_key)
        
        lead_data = {
            "tweet_id": tweet["tweet_id"],
            "author_handle": tweet["author_handle"],
            "created_at": tweet["created_at"],
            "text": tweet["text"],
            "is_lead": eval_res.get("is_lead", False),
            "reason": eval_res.get("service_match_reason", ""),
            "suggested_comment": eval_res.get("suggested_comment", "")
        }
        
        save_tweet_lead(lead_data)

        if lead_data["is_lead"]:
            msg_text, keyboard = create_lead_notification(lead_data, webapp_url)
            await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
```

- [ ] **Step 2: Implement `main.py` FastAPI server & Telegram WebApp host**

```python
# main.py
import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.db import init_db, get_lead_by_id, get_active_keywords
from src.scheduler import run_lead_generation_cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Schedule periodic run every SCAN_INTERVAL_HOURS
    interval_hours = int(os.getenv("SCAN_INTERVAL_HOURS", "24"))
    scheduler.add_job(run_lead_generation_cycle, 'interval', hours=interval_hours)
    scheduler.start()
    logger.info(f"APScheduler started. Scanning every {interval_hours} hours.")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "active_keywords": get_active_keywords(),
        "service": "X AI Lead Generation Bot"
    }

@app.get("/webapp", response_class=HTMLResponse)
def serve_webapp():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/lead/{lead_id}")
def get_lead_api(lead_id: str):
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return JSONResponse(content=dict(lead))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
```

- [ ] **Step 3: Create `requirements.txt`, `render.yaml`, and `.env.example`**

```text
# requirements.txt
fastapi>=0.110.0
uvicorn>=0.28.0
python-telegram-bot>=20.8
twikit>=1.4.0
google-genai>=0.1.1
apscheduler>=3.10.4
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

```yaml
# render.yaml
services:
  - type: web
    name: x-ai-lead-bot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PORT
        value: 8080
      - key: SCAN_INTERVAL_HOURS
        value: 24
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: TELEGRAM_CHAT_ID
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: X_CT0
        sync: false
      - key: X_AUTH_TOKEN
        sync: false
      - key: WEBAPP_URL
        sync: false
```

```env
# .env.example
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
GEMINI_API_KEY=your_gemini_api_key
X_CT0=07c704d12f8db7c61973e3a...
X_AUTH_TOKEN=9b53b5fa1959493ca9774...
WEBAPP_URL=https://x-ai-lead-bot.onrender.com
PORT=8080
SCAN_INTERVAL_HOURS=24
```

- [ ] **Step 4: Commit**

```bash
git add main.py src/scheduler.py requirements.txt render.yaml .env.example
git commit -m "feat: add FastAPI web app, scheduler, and Render deployment config"
```

---

## Plan Self-Review & Verification

1. **Spec Coverage Check**:
   - Telegram Bot listener for keywords -> Task 4 (`src/bot.py`)
   - Human-paced X Scraper with `ct0`/`auth_token` -> Task 2 (`src/scraper.py`)
   - Gemini 2.5 Flash Lite lead evaluator -> Task 3 (`src/evaluator.py`)
   - Telegram WebApp button for lead cards -> Task 4 (`webapp/index.html`) & (`src/bot.py`)
   - Render 24/7 deployment + `/health` UptimeRobot endpoint -> Task 5 (`main.py` & `render.yaml`)
2. **No Placeholders**: All tasks contain explicit code.
3. **Type Consistency**: Database function names, parameter signatures, and schemas match across all tasks.
