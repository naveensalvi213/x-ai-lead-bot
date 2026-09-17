# Technical Design Specification: On-Demand X AI Lead Generation Bot

## 1. Overview
The **On-Demand X AI Lead Generation Bot** is a real-time Telegram-triggered tool. Upon receiving comma-separated keywords from a Telegram user, it searches X (Twitter) for **20 Top posts** and **20 Latest posts** per keyword, evaluates lead intent using **Gemini 2.5 Flash Lite**, and streams qualified leads alongside personalized outreach comments directly to the user's Telegram chat.

---

## 2. System Architecture & Workflow

```
┌──────────────────┐
│  Telegram User   │
└────────┬─────────┘
         │ 1. Send comma-separated keywords (e.g. "ai automation, n8n, make.com")
         ▼
┌────────────────────────────────────────────────────────┐
│ Telegram Bot Listener & Command Handler (src/bot.py)  │
└────────┬───────────────────────────────────────────────┘
         │ 2. Reply: "🔎 Searching 3 keywords..."
         ▼
┌────────────────────────────────────────────────────────┐
│  X Scraper Engine (src/scraper.py via twikit client)   │
└────────┬───────────────────────────────────────────────┘
         │ 3. Fetch 20 Top + 20 Latest tweets per keyword (Human delays)
         ▼
┌────────────────────────────────────────────────────────┐
│ Deduplication & Filtering Layer (src/db.py)            │
│ - Skip already evaluated tweet IDs (SQLite seen_tweets) │
└────────┬───────────────────────────────────────────────┘
         │ 4. Send new candidate tweets
         ▼
┌────────────────────────────────────────────────────────┐
│ AI Lead Evaluator (src/evaluator.py via Gemini 2.5)    │
│ - Evaluates AI automation fit & business pain points    │
│ - Crafts non-spammy, high-converting outreach comment   │
└────────┬───────────────────────────────────────────────┘
         │ 5. Return JSON: is_lead, confidence, reason, comment
         ▼
┌────────────────────────────────────────────────────────┐
│ Telegram Lead Notifier (src/bot.py)                    │
│ - Stream Markdown Lead Alert cards with direct links   │
└────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1 Telegram Bot (`src/bot.py`)
- **Framework**: `python-telegram-bot` (v20+ async)
- **Behavior**:
  - Listens for text messages containing comma-separated keywords.
  - Sends immediate status response: *"🔎 Starting scan for N keywords... Fetching 20 Top + 20 Latest tweets for each keyword."*
  - As soon as Gemini identifies a qualified lead, streams a Telegram Lead Card:
    - 🎯 **AI Lead Found**
    - 👤 **Author**: `@author_handle`
    - 📝 **Tweet**: Original tweet text + direct link `https://x.com/handle/status/id`
    - 💡 **Service Fit**: Pain point or workflow automation request
    - 💬 **Suggested Comment**: Pre-written outreach comment
  - Sends a final summary message when all keywords finish.

### 3.2 X Scraper Engine (`src/scraper.py`)
- **Library**: `twikit` (Python async library for X cookie authentication).
- **Authentication**: `X_CT0` and `X_AUTH_TOKEN` cookies.
- **Search Logic**:
  - For each keyword in the list:
    - Query **Top** section for 20 tweets.
    - Query **Latest** section for 20 tweets.
  - Apply random delay (3 to 7 seconds) between keyword requests for human pacing and account safety.

### 3.3 Gemini Lead Evaluator (`src/evaluator.py`)
- **SDK**: `google-genai` Python SDK
- **Model**: `gemini-2.5-flash-lite` (or `gemini-2.0-flash-lite`)
- **Execution**: Non-blocking `asyncio.to_thread` execution to prevent event loop lag.
- **Output Schema**:
  ```json
  {
    "is_lead": true,
    "confidence_score": 9,
    "service_match_reason": "User is asking how to automate client onboarding using AI.",
    "suggested_comment": "You can set up an automated webhook workflow with Claude to process client intakes automatically. Built a similar flow recently—happy to share how!"
  }
  ```

### 3.4 Storage & Deduplication (`src/db.py`)
- **Database**: SQLite3 (`data/leads.db`).
- **Tables**:
  - `keywords`: `id`, `user_id`, `keywords`, `updated_at`.
  - `seen_tweets`: `tweet_id` (PRIMARY KEY), `author_handle`, `created_at`, `text`, `is_lead`, `reason`, `suggested_comment`, `evaluated_at`.

### 3.5 Web Application & Server (`main.py`)
- **Web Server**: `FastAPI` + `uvicorn`
- **Port**: 8080 (or process `PORT` environment variable)
- **Endpoints**:
  - `GET /health` -> Returns `{"status": "ok", "active_keywords": [...], "service": "X AI Lead Generation Bot"}`
  - `GET /webapp` -> Serves Telegram Mini App HTML UI.
- **Background Tasks**:
  - Telegram Bot polling listener started in lifespan.
  - Internal 4-minute self-ping keep-alive loop to prevent Render free tier from sleeping.
