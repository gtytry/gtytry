import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Document, Message, Update
from sqlalchemy.ext.asyncio import async_sessionmaker

from config.settings import Settings
from database.repositories import AnalysisRepository, ManagerRepository
from services.analysis_service import AnalysisService
from services.formatting import format_analysis, format_stats
from services.image_store import ImageStore
from services.rate_limiter import InMemoryRateLimiter
from services.sessions import AnalysisSession, SessionManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BotContext:
    settings: Settings
    session_factory: async_sessionmaker
    analysis_service: AnalysisService
    sessions: SessionManager
    image_store: ImageStore
    rate_limiter: InMemoryRateLimiter
    album_tasks: dict[str, asyncio.Task]
    analysis_tasks: set[asyncio.Task]


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(context: BotContext) -> Dispatcher:
    router = Router()

    @router.message(Command("start", "help"))
    async def start(message: Message) -> None:
        await message.answer(
            "👋 Отправьте один или несколько скриншотов переписки.\n\n"
            "Команды:\n"
            "• /new — начать новую ручную сессию\n"
            "• /done — запустить анализ накопленных скринов\n"
            "• /cancel — сбросить текущую сессию\n"
            "• /stats — статистика для админов\n\n"
            "Альбом фото я сгруппирую автоматически."
        )

    @router.message(Command("new"))
    async def new_session(message: Message) -> None:
        context.sessions.start(message.from_user.id)
        await message.answer("🧩 Новая сессия начата. Присылайте скриншоты, затем нажмите /done.")

    @router.message(Command("cancel"))
    async def cancel(message: Message) -> None:
        session = context.sessions.cancel(message.from_user.id)
        if session:
            delete_images(session.image_paths)
        await message.answer("Сессия сброшена." if session else "Активной сессии нет.")

    @router.message(Command("done"))
    async def done(message: Message) -> None:
        session = context.sessions.pop(message.from_user.id) or context.sessions.pop_album_for_user(message.from_user.id)
        if not session or not session.image_paths:
            await message.answer("Пока нет скриншотов для анализа. Отправьте фото или альбом.")
            return
        await enqueue_analysis(message, session, context)

    @router.message(Command("stats"))
    async def stats(message: Message) -> None:
        if context.settings.admin_user_ids and message.from_user.id not in context.settings.admin_user_ids:
            await message.answer("⛔️ Эта команда доступна только админам.")
            return
        async with context.session_factory() as db:
            snapshot = await AnalysisRepository(db).stats()
        await message.answer(format_stats(snapshot))

    @router.message(F.photo)
    async def photo(message: Message, bot: Bot) -> None:
        await handle_image_message(message, bot, context, file_id=message.photo[-1].file_id, filename="photo.jpg")

    @router.message(F.document)
    async def document(message: Message, bot: Bot) -> None:
        document: Document = message.document
        if document.mime_type not in {"image/png", "image/jpeg"}:
            await message.answer("Поддерживаются только PNG/JPG/JPEG изображения.")
            return
        await handle_image_message(message, bot, context, file_id=document.file_id, filename=document.file_name)

    dp = Dispatcher()
    dp.include_router(router)
    return dp


async def handle_image_message(
    message: Message,
    bot: Bot,
    context: BotContext,
    file_id: str,
    filename: str | None,
) -> None:
    if not context.rate_limiter.allow(message.from_user.id):
        await message.answer("⏳ Слишком много запросов. Попробуйте чуть позже.")
        return

    path = context.image_store.new_path(filename)
    telegram_file = await bot.get_file(file_id)
    await bot.download_file(telegram_file.file_path, destination=path)

    try:
        context.image_store.validate(path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        await message.answer(f"Не могу принять файл: {exc}")
        return

    if message.media_group_id:
        session = context.sessions.get_album_or_create(message.from_user.id, message.media_group_id)
        try:
            context.sessions.add_image(session, path)
        except ValueError as exc:
            path.unlink(missing_ok=True)
            await message.answer(str(exc))
            return
        if len(session.image_paths) == 1:
            await message.answer("✅ Альбом получен. Я соберу все скриншоты и сам запущу анализ через пару секунд.")
        schedule_album_analysis(message, context)
        return

    session = context.sessions.get_or_create(message.from_user.id)
    try:
        context.sessions.add_image(session, path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        await message.answer(str(exc))
        return

    await message.answer(
        f"✅ Скриншот добавлен ({len(session.image_paths)}/{context.settings.max_images_per_session}). "
        "Пришлите еще или отправьте /done."
    )


def schedule_album_analysis(message: Message, context: BotContext) -> None:
    media_group_id = message.media_group_id
    old_task = context.album_tasks.pop(media_group_id, None)
    if old_task:
        old_task.cancel()
    context.album_tasks[media_group_id] = asyncio.create_task(
        delayed_album_analysis(message, media_group_id, context)
    )


async def delayed_album_analysis(message: Message, media_group_id: str, context: BotContext) -> None:
    try:
        await asyncio.sleep(context.settings.album_debounce_seconds)
        session = context.sessions.pop_album(media_group_id)
        if session and session.image_paths:
            await enqueue_analysis(message, session, context)
    except asyncio.CancelledError:
        return
    finally:
        context.album_tasks.pop(media_group_id, None)


async def enqueue_analysis(message: Message, session: AnalysisSession, context: BotContext) -> None:
    await message.answer(f"🔎 Анализирую {len(session.image_paths)} скриншот(ов). Это может занять до минуты.")
    task = asyncio.create_task(analyze_session(message, session, context))
    context.analysis_tasks.add(task)
    task.add_done_callback(context.analysis_tasks.discard)


async def analyze_session(message: Message, session: AnalysisSession, context: BotContext) -> None:
    user = message.from_user
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part) or None

    try:
        async with context.session_factory() as db:
            result = await context.analysis_service.analyze_and_save(
                image_paths=session.image_paths,
                session_id=session.id,
                telegram_user_id=user.id,
                username=user.username,
                full_name=full_name,
                manager_repo=ManagerRepository(db),
                analysis_repo=AnalysisRepository(db),
            )
            await db.commit()
    except Exception:
        logger.exception("Analysis failed for session %s", session.id)
        await message.answer("❌ Не удалось выполнить анализ. Ошибка уже записана в лог, попробуйте позже.")
        if context.settings.delete_images_after_analysis:
            delete_images(session.image_paths)
        return

    await message.answer(format_analysis(result), disable_web_page_preview=True)
    if context.settings.delete_images_after_analysis:
        delete_images(session.image_paths)


def delete_images(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete image %s", path)


async def feed_webhook_update(dispatcher: Dispatcher, bot: Bot, payload: dict) -> None:
    update = Update.model_validate(payload, context={"bot": bot})
    await dispatcher.feed_update(bot, update)
