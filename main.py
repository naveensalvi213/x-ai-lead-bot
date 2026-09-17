# main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.db import init_db, get_lead_by_id, get_active_keywords
from src.scheduler import run_lead_generation_cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = os.getenv("DB_PATH", "data/leads.db")
    init_db(db_path=db_path)
    
    # Start APScheduler
    interval_hours = int(os.getenv("SCAN_INTERVAL_HOURS", "24"))
    scheduler.add_job(run_lead_generation_cycle, 'interval', hours=interval_hours, kwargs={"db_path": db_path})
    scheduler.start()
    logger.info(f"APScheduler started. Scanning every {interval_hours} hours.")

    # Start Telegram Bot Polling
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_app = None
    if bot_token:
        from src.bot import build_telegram_app
        tg_app = build_telegram_app(bot_token, db_path=db_path)
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling()
        logger.info("Telegram Bot polling started successfully.")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN missing. Telegram Bot polling skipped.")

    yield

    if tg_app:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        logger.info("Telegram Bot shut down cleanly.")

    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health_check():
    db_path = os.getenv("DB_PATH", "data/leads.db")
    return {
        "status": "ok",
        "active_keywords": get_active_keywords(db_path=db_path),
        "service": "X AI Lead Generation Bot"
    }

@app.get("/webapp", response_class=HTMLResponse)
def serve_webapp():
    file_path = os.path.join(os.path.dirname(__file__), "webapp", "index.html")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="webapp/index.html not found")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/lead/{lead_id}")
def get_lead_api(lead_id: str):
    db_path = os.getenv("DB_PATH", "data/leads.db")
    lead = get_lead_by_id(lead_id, db_path=db_path)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return JSONResponse(content=dict(lead))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
