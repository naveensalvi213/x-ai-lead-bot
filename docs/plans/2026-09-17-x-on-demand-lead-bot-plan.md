# On-Demand X AI Lead Generation Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the X Lead Bot pipeline so that when a Telegram user sends comma-separated keywords, it immediately searches X for 20 Top posts + 20 Latest posts per keyword, evaluates lead intent with Gemini 2.5 Flash Lite, and streams real-time lead cards with personalized comments directly to Telegram.

**Architecture:** A FastAPI service hosting a Telegram bot polling listener and Telegram Mini App UI. When a message is received, `src/bot.py` triggers an instant pipeline in `src/scheduler.py` that fetches 20 Top + 20 Latest tweets per keyword using `twikit`, filters duplicates via SQLite, evaluates lead fit using `google-genai` (`gemini-2.5-flash-lite`), and sends real-time lead cards and a final summary back to Telegram.

**Tech Stack:** Python 3.11+, FastAPI, python-telegram-bot, twikit, google-genai, SQLite3, pytest.

## Global Constraints

- **Python Version**: Python 3.11+
- **Tweets per Keyword**: Exactly 20 Top + 20 Latest per keyword
- **Gemini Model**: `gemini-2.5-flash-lite` via `google-genai` package
- **Database**: SQLite3 (`data/leads.db`)

---

### Task 1: Update Scraper Engine for 20 Top + 20 Latest per Keyword (`src/scraper.py`)

**Files:**
- Modify: `src/scraper.py`
- Modify: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `keywords: list[str]`, `ct0: str`, `auth_token: str`, `max_tweets_per_section: int = 20`
- Produces: `async fetch_candidate_tweets(keywords: list[str], ct0: str, auth_token: str, max_tweets_per_section: int = 20) -> list[dict]`

- [ ] **Step 1: Update `tests/test_scraper.py` to verify 20 Top + 20 Latest per keyword**

```python
# tests/test_scraper.py snippet
@pytest.mark.asyncio
async def test_fetch_candidate_tweets_top_and_latest():
    mock_tweet_top = MagicMock()
    mock_tweet_top.id = "top_1"
    mock_tweet_top.user.screen_name = "user_top"
    mock_tweet_top.text = "Need AI automation workflow"

    mock_tweet_latest = MagicMock()
    mock_tweet_latest.id = "latest_1"
    mock_tweet_latest.user.screen_name = "user_latest"
    mock_tweet_latest.text = "Looking for Make.com developer"

    mock_client = AsyncMock()
    mock_client.search_tweet.side_effect = [[mock_tweet_top], [mock_tweet_latest]]

    with patch("src.scraper.get_twikit_client", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            results = await fetch_candidate_tweets(["ai automation"], ct0="mock_ct0", auth_token="mock_token", max_tweets_per_section=20)
            assert len(results) == 2
            assert results[0]["tweet_id"] == "top_1"
            assert results[1]["tweet_id"] == "latest_1"
            # Verify Top and Latest were called with count=20
            assert mock_client.search_tweet.call_count == 2
            mock_client.search_tweet.assert_any_call("ai automation", product="Top", count=20)
            mock_client.search_tweet.assert_any_call("ai automation", product="Latest", count=20)
```

- [ ] **Step 2: Run test to verify it passes/fails**

Run: `pytest tests/test_scraper.py -v`

- [ ] **Step 3: Update `src/scraper.py`**

Ensure `fetch_candidate_tweets` takes `max_tweets_per_section: int = 20` and passes `count=max_tweets_per_section` to `client.search_tweet(keyword, product=product_type, count=max_tweets_per_section)` for both `'Top'` and `'Latest'`.

```python
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
                for t in tweets:
                    created_at = getattr(t, 'created_at_datetime', None) or datetime.now(timezone.utc)
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
                    logger.warning("X Rate Limit hit (HTTP 429). Pausing search...")
                    break
            
            # Anti-ban human delay (3 to 7 seconds)
            await asyncio.sleep(random.uniform(3.0, 7.0))

    return candidates
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scraper.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "feat: update scraper to fetch 20 Top and 20 Latest posts per keyword"
```

---

### Task 2: Real-Time Stream Pipeline & Telegram Progress Reporting (`src/scheduler.py` & `src/bot.py`)

**Files:**
- Modify: `src/scheduler.py`
- Modify: `src/bot.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_bot.py`

**Interfaces:**
- Consumes: `run_lead_generation_cycle(keywords: list[str], chat_id: str, db_path: str)`
- Produces: Streams individual lead notifications directly to Telegram and sends a final summary report upon completion.

- [ ] **Step 1: Update `src/scheduler.py` for stream pipeline**

```python
async def run_lead_generation_cycle(
    target_keywords: Optional[List[str]] = None,
    target_chat_id: Optional[str] = None,
    db_path: str = "data/leads.db"
) -> None:
    logger.info("Executing X lead generation cycle...")
    
    keywords = target_keywords or get_active_keywords(db_path=db_path)
    if not keywords:
        logger.info("No active keywords set. Skipping cycle.")
        return

    ct0 = os.getenv("X_CT0", "")
    auth_token = os.getenv("X_AUTH_TOKEN", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = target_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    webapp_url = os.getenv("WEBAPP_URL", "https://localhost:8080")

    if not all([ct0, auth_token, gemini_key, bot_token, chat_id]):
        logger.error("Missing required environment variables for lead generation cycle.")
        return

    bot = Bot(token=bot_token)
    candidates = await fetch_candidate_tweets(keywords, ct0=ct0, auth_token=auth_token, max_tweets_per_section=20)

    evaluated_count = 0
    leads_found = 0

    for tweet in candidates:
        tweet_id = tweet["tweet_id"]
        if is_tweet_seen(tweet_id, db_path=db_path):
            continue

        evaluated_count += 1
        eval_res = await evaluate_tweet_lead(tweet["text"], gemini_key)
        
        lead_data = {
            "tweet_id": tweet_id,
            "author_handle": tweet["author_handle"],
            "created_at": tweet["created_at"],
            "text": tweet["text"],
            "is_lead": eval_res.get("is_lead", False),
            "reason": eval_res.get("service_match_reason", ""),
            "suggested_comment": eval_res.get("suggested_comment", "")
        }
        
        save_tweet_lead(lead_data, db_path=db_path)

        if lead_data["is_lead"]:
            leads_found += 1
            msg_text, keyboard = create_lead_notification(lead_data, webapp_url)
            await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

    # Send final summary
    summary_text = (
        f"✅ *Scan Complete\\!*\n\n"
        f"🔍 *Keywords Scanned:* {len(keywords)}\n"
        f"📊 *New Posts Evaluated:* {evaluated_count}\n"
        f"🎯 *Qualified Leads Found:* {leads_found}"
    )
    await bot.send_message(chat_id=chat_id, text=summary_text, parse_mode="MarkdownV2")
```

- [ ] **Step 2: Update `src/bot.py` `handle_message` to pass user keywords to `run_lead_generation_cycle`**

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db_path: str = "data/leads.db") -> None:
    if not update or not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    keywords = [k.strip() for k in text.split(",") if k.strip()]
    
    if not update.effective_user:
        return
        
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)

    if keywords:
        save_keywords(user_id, keywords, db_path=db_path)
        kw_str = ", ".join(keywords)
        await update.message.reply_text(
            f"✅ *Keywords Received\\!*\n\n"
            f"🔍 *Active Keywords:* `{kw_str}`\n"
            f"⚡ *Starting instant search on X \\(20 Top \\+ 20 Latest per keyword\\)\\.\\.\\.*",
            parse_mode="MarkdownV2"
        )
        
        # Trigger immediate search pipeline for these keywords
        from src.scheduler import run_lead_generation_cycle
        import asyncio
        asyncio.create_task(run_lead_generation_cycle(target_keywords=keywords, target_chat_id=chat_id, db_path=db_path))
```

- [ ] **Step 3: Run all unit tests**

Run: `pytest`
Expected: 17/17 passed cleanly.

- [ ] **Step 4: Commit and push**

```bash
git add .
git commit -m "feat: implement instant on-demand X lead search pipeline and real-time Telegram streaming"
git push origin main
```
