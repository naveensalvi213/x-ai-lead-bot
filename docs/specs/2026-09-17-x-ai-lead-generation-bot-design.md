# Technical Design Specification: X (Twitter) AI Lead Generation Bot

## 1. Overview
The **X AI Automation Lead Generation Bot** is an automated 24/7 web service deployed on Render. It scans X (Twitter) for recent (past 24h) posts matching user-defined keywords, evaluates whether the author needs AI automation/workflow services using **Gemini 2.5 Flash Lite**, and sends high-intent leads alongside personalized outreach comment suggestions directly to a Telegram user via a Telegram Bot.

---

## 2. Core Architecture & Workflow

### 2.1 Component Architecture
```
┌──────────────────┐
│  Telegram User   │
└────────┬─────────┘
         │ 1. Send comma-separated keywords (e.g. "ai automation, n8n")
         ▼
┌────────────────────────────────────────────────────────┐
│ Telegram Bot Listener & Command Handler (python-telegram-bot) │
└────────┬───────────────────────────────────────────────┘
         │ 2. Save active keywords to SQLite & trigger search job
         ▼
┌────────────────────────────────────────────────────────┐
│  X Scraper Engine (twikit Async Client with Cookie Auth) │
└────────┬───────────────────────────────────────────────┘
         │ 3. Search "Top" & "Latest" tweets past 24h (Human delays)
         ▼
┌────────────────────────────────────────────────────────┐
│ Deduplication & Filtering Layer                        │
│ - Skip already evaluated tweet IDs (SQLite seen_tweets) │
│ - Filter created_at >= 24h ago                          │
└────────┬───────────────────────────────────────────────┘
         │ 4. Send new candidate tweets
         ▼
┌────────────────────────────────────────────────────────┐
│ AI Lead Evaluator (Gemini 2.5 Flash Lite via google-genai) │
│ - Evaluates AI automation fit & business pain points    │
│ - Crafts non-spammy, high-converting outreach comment   │
└────────┬───────────────────────────────────────────────┘
         │ 5. Return JSON: is_lead, confidence, reason, comment
         ▼
┌────────────────────────────────────────────────────────┐
│ Telegram Lead Notifier                                 │
│ - Send Markdown Lead Alert card with direct tweet link  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1 Telegram Bot & Mini WebApp (`bot.py` & `webapp/`)
- **Framework**: `python-telegram-bot` (v20+ async) + HTML/JS Telegram Mini App.
- **Behavior**:
  - Accepts any text message containing comma-separated keywords (e.g., `ai automation, make.com, n8n, chatbot`).
  - Stores the latest keyword list into SQLite database (`leads.db`).
  - Immediately launches an asynchronous search scan task in the background.
  - Commands: `/start`, `/help`, `/keywords` (shows saved keywords), `/status` (shows bot status & last run info).
  - **Telegram WebApp Button**: Each lead notification contains an Inline Keyboard Button: `📱 Open Lead in WebApp` alongside `🔗 Open Tweet on X`.
  - Clicking `📱 Open Lead in WebApp` opens an interactive Telegram Mini App modal inside Telegram displaying:
    - Target Tweet snippet & Author info
    - High-intent pain point analysis
    - One-click **"Copy Comment"** button
    - One-click **"Open & Reply on X"** button

### 3.2 X Scraper Engine (`scraper.py`)
- **Library**: `twikit` (Python async library for X cookie-based authentication).
- **Authentication**: `auth_token` and `ct0` cookies provided via environment variables.
- **Search Logic**:
  - Loops over active keywords.
  - Queries both `Top` and `Latest` sections.
  - Enforces `created_at` timestamp check (must be within last 24 hours).
- **Anti-Ban & Human Behavior Controls**:
  - **Random Delays**: 7s to 18s randomized sleep between keyword queries.
  - **Batch Cap**: Maximum 25 tweets retrieved per keyword per search cycle.
  - **Rate Limit Protection**: Catches HTTP `429` / `Too Many Requests`. On trigger, pauses scraping for 20 minutes and alerts user on Telegram.
  - **Read-Only**: Zero automated posting/replying on X directly.

### 3.3 Gemini Lead Evaluator (`evaluator.py`)
- **SDK**: `google-genai` Python SDK
- **Model**: `gemini-2.5-flash-lite` (or `gemini-2.0-flash-lite`)
- **System Prompt Focus**:
  - Target audience: Business owners, service providers, agency owners, creators asking for workflow automation, custom AI tools, CRM integrations, Claude/Antigravity AI tools, or manual task elimination.
  - Output Schema:
    ```json
    {
      "is_lead": true,
      "confidence_score": 8,
      "service_match_reason": "User is asking how to automate client onboarding using AI.",
      "suggested_comment": "You can set up an automated webhook workflow with Claude to process client intakes automatically. Built a similar flow recently—happy to share how!"
    }
    ```

### 3.4 Storage & Deduplication (`db.py`)
- **Database**: SQLite3 (`data/leads.db`).
- **Tables**:
  - `keywords`: `id`, `user_id`, `keyword_list`, `updated_at`.
  - `seen_tweets`: `tweet_id` (PRIMARY KEY), `author_handle`, `created_at`, `is_lead`, `evaluated_at`, `suggested_comment`, `reason`.

### 3.5 Web Server, WebApp Host & Uptime (`main.py` & `scheduler.py`)
- **Web Framework**: `FastAPI` + `uvicorn`
- **Port**: 8080 (or process `PORT` environment variable for Render)
- **Endpoints**:
  - `GET /health` -> Returns `{"status": "ok", "timestamp": "...", "keywords": [...]}`
  - `GET /webapp/lead/{lead_id}` -> Serves the interactive Telegram Mini App web page for viewing and copying the lead comment.
- **Scheduler**: `APScheduler` or async background loop running daily automated scans (every 24 hours).

---

## 4. Environment Variables Specification

| Variable Name | Description | Example / Required |
|---------------|-------------|--------------------|
| `TELEGRAM_BOT_TOKEN` | Token from Telegram BotFather | Required |
| `TELEGRAM_CHAT_ID` | Your Telegram Chat ID | Required |
| `GEMINI_API_KEY` | Google Gemini API Key | Required |
| `X_CT0` | X Cookie `ct0` token | Required |
| `X_AUTH_TOKEN` | X Cookie `auth_token` secret | Required |
| `SCAN_INTERVAL_HOURS` | Frequency of auto scans in hours | Default: `24` |
| `PORT` | Web server port | Default: `8080` |

---

## 5. Deployment Configuration (`render.yaml`)

- **Platform**: Render Web Service (Free Tier compatible)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Health Check Path**: `/health`
- **Uptime Monitoring**: UptimeRobot configured to ping `https://<render-app-name>.onrender.com/health` every 5 minutes.
