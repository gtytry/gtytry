import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from ai.client import SalesQAAnalyzer
from app.logging_config import configure_logging
from bot.telegram_bot import BotContext, create_bot, create_dispatcher, feed_webhook_update
from config.settings import get_settings
from database.session import create_engine, create_session_factory, init_db
from ocr.service import OCRService
from services.analysis_service import AnalysisService
from services.image_store import ImageStore
from services.rate_limiter import InMemoryRateLimiter
from services.sessions import SessionManager

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

engine: AsyncEngine = create_engine(settings)
session_factory = create_session_factory(engine)
bot = create_bot(settings)
analysis_service = AnalysisService(OCRService(settings), SalesQAAnalyzer(settings))
bot_context = BotContext(
    settings=settings,
    session_factory=session_factory,
    analysis_service=analysis_service,
    sessions=SessionManager(settings.session_ttl_minutes, settings.max_images_per_session),
    image_store=ImageStore(settings),
    rate_limiter=InMemoryRateLimiter(settings.rate_limit_per_minute),
    album_tasks={},
)
dispatcher = create_dispatcher(bot_context)

app = FastAPI(title="AI Sales QA Agent", version="1.0.0")
polling_task: asyncio.Task | None = None


@app.on_event("startup")
async def on_startup() -> None:
    global polling_task
    await init_db(engine)
    if settings.bot_mode == "webhook":
        await bot.set_webhook(settings.webhook_url, secret_token=settings.webhook_secret)
        logger.info("Telegram webhook configured: %s", settings.webhook_url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        polling_task = asyncio.create_task(dispatcher.start_polling(bot))
        logger.info("Telegram polling started")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if polling_task:
        polling_task.cancel()
    await bot.session.close()
    await engine.dispose()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request) -> dict[str, bool]:
    if settings.bot_mode != "webhook":
        raise HTTPException(status_code=404, detail="Webhook mode is disabled")
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.webhook_secret or header_secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    payload = await request.json()
    await feed_webhook_update(dispatcher, bot, payload)
    return {"ok": True}
