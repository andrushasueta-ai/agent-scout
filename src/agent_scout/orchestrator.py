"""Оркестратор — координация всех задач с имитацией поведения живого человека."""

import asyncio
import random
from datetime import datetime, time as dtime
from enum import Enum
from typing import Optional

import structlog

from agent_scout.config import AppConfig
from agent_scout.database.repository import Repository
from agent_scout.browser.manager import BrowserManager
from agent_scout.browser.proxy import ProxyManager
from agent_scout.messenger.chat_ai import ChatAI
from agent_scout.messenger.conversation import ConversationManager
from agent_scout.platforms.avito import AvitoPlatform
from agent_scout.platforms.base import BasePlatform

logger = structlog.get_logger()


class ActivityType(Enum):
    """Тип активности в расписании дня."""

    SCRAPE = "scrape"
    MESSAGE = "message"
    CHECK_REPLIES = "check_replies"
    BREAK = "break"


class DaySchedule:
    """Генератор расписания на день с рандомизацией.

    Модель "живого человека":
    - 9:00-11:00 — скрапинг
    - 11:00-14:00 — переписка
    - 14:00-15:30 — перерыв
    - 15:30-18:00 — переписка + новые объявления
    - 18:00-19:00 — перерыв
    - 19:00-22:00 — проверка ответов
    """

    def __init__(self, is_weekend: bool = False, reduction: float = 0.4):
        self._is_weekend = is_weekend
        self._reduction = reduction

    def generate(self) -> list[tuple[dtime, dtime, ActivityType]]:
        """Генерировать расписание на день с рандомом."""
        schedule = [
            (dtime(9, self._jitter(0, 30)), dtime(11, self._jitter(0, 30)), ActivityType.SCRAPE),
            (dtime(11, self._jitter(0, 20)), dtime(14, self._jitter(0, 30)), ActivityType.MESSAGE),
            (dtime(14, 0), dtime(15, 30), ActivityType.BREAK),
            (dtime(15, 30 + self._jitter(0, 20)), dtime(18, self._jitter(0, 30)), ActivityType.MESSAGE),
            (dtime(18, 0), dtime(19, 0), ActivityType.BREAK),
            (dtime(19, self._jitter(0, 20)), dtime(22, self._jitter(0, 0)), ActivityType.CHECK_REPLIES),
        ]

        if self._is_weekend:
            # Убираем часть блоков на выходных
            keep_count = max(2, int(len(schedule) * (1 - self._reduction)))
            schedule = random.sample(
                [s for s in schedule if s[2] != ActivityType.BREAK], keep_count
            )

        return schedule

    @staticmethod
    def _jitter(min_m: int, max_m: int) -> int:
        return random.randint(min_m, max_m)


class Orchestrator:
    """Центральный оркестратор всех задач."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._repo = Repository(config.database.path)
        self._proxy = ProxyManager(config.proxies or None)
        self._browser = BrowserManager(config, self._proxy)
        self._platforms: dict[str, BasePlatform] = {}
        self._chat_ai = ChatAI(
            model=config.messaging.claude_model,
        )
        self._messages_sent_today = 0
        self._pages_viewed_this_hour = 0

        # Инициализация платформ
        for name, platform_config in config.platforms.items():
            if platform_config.enabled:
                if name == "avito":
                    self._platforms[name] = AvitoPlatform(self._browser)

    async def init(self) -> None:
        """Инициализация БД и ресурсов."""
        await self._repo.init_db()
        logger.info("orchestrator_initialized")

    async def close(self) -> None:
        """Закрытие всех ресурсов."""
        await self._browser.close()
        await self._repo.close()
        logger.info("orchestrator_closed")

    # --- Публичные команды ---

    async def scrape(
        self,
        platform_name: str,
        niche: str,
        location: str,
        limit: int = 20,
    ) -> int:
        """Скрапить объявления и сохранить в БД.

        Returns:
            Количество сохранённых объявлений.
        """
        platform = self._get_platform(platform_name)
        logger.info("scrape_start", platform=platform_name, niche=niche, location=location)

        listings = await platform.search_listings(
            query=niche, category="Строительство", location=location, limit=limit
        )

        saved = 0
        for listing in listings:
            # Проверяем rate limit
            if self._pages_viewed_this_hour >= self._config.platforms[platform_name].rate_limit:
                logger.warning("rate_limit_reached", platform=platform_name)
                break

            # Создаём/обновляем продавца
            seller_external_id = listing.seller_external_id or "unknown"
            seller = await self._repo.create_seller(
                platform=platform_name,
                external_id=seller_external_id,
                name=listing.seller_name or "Неизвестно",
                profile_url=listing.seller_url or "",
            )

            # Сохраняем объявление
            await self._repo.create_listing(
                seller_id=seller.id,
                platform=platform_name,
                title=listing.title,
                url=listing.url,
                description=listing.description,
                price=listing.price,
                category=listing.category,
                location=listing.location,
                photos_json={"photos": listing.photos} if listing.photos else None,
            )
            saved += 1
            self._pages_viewed_this_hour += 1

        logger.info("scrape_done", saved=saved)
        return saved

    async def enrich_profiles(self, platform_name: str, limit: int = 10) -> int:
        """Обогатить профили продавцов — получить рейтинги, отзывы и т.д."""
        platform = self._get_platform(platform_name)
        sellers = await self._repo.list_sellers(platform=platform_name)

        enriched = 0
        for seller in sellers[:limit]:
            if seller.rating is not None:
                continue  # Уже обогащён

            if not seller.profile_url:
                continue

            try:
                profile = await platform.get_seller_profile(seller.profile_url)
                await self._repo.create_seller(
                    platform=platform_name,
                    external_id=seller.external_id,
                    name=profile.name,
                    profile_url=profile.profile_url,
                    rating=profile.rating,
                    reviews_count=profile.reviews_count,
                    registration_date=profile.registration_date,
                    listings_count=profile.listings_count,
                )
                enriched += 1

                # Пауза между запросами профилей
                await asyncio.sleep(random.uniform(5, 15))

            except Exception as e:
                logger.warning("enrich_error", seller_id=seller.id, error=str(e))
                continue

        logger.info("enrich_done", enriched=enriched)
        return enriched

    async def send_messages(
        self,
        platform_name: str,
        goal: str = "Узнать цены на мех. штукатурку ~40м2 стен, ЖК Парксайд, Москва",
        limit: Optional[int] = None,
    ) -> int:
        """Отправить первые сообщения продавцам.

        Ограничено лимитом из конфига (8-15 в день).
        """
        if not self._config.messaging.enabled:
            logger.info("messaging_disabled")
            return 0

        max_per_day = self._config.messaging.max_conversations_per_day
        if limit:
            max_per_day = min(limit, max_per_day)

        remaining = max_per_day - self._messages_sent_today
        if remaining <= 0:
            logger.info("daily_message_limit_reached")
            return 0

        platform = self._get_platform(platform_name)
        conv_manager = ConversationManager(
            repo=self._repo,
            chat_ai=self._chat_ai,
            platform=platform,
            reply_delay_range=tuple(self._config.messaging.reply_delay_minutes),
        )

        sellers = await self._repo.list_sellers(platform=platform_name)
        sent = 0

        for seller in sellers:
            if sent >= remaining:
                break

            conv_id = await conv_manager.start_conversation(
                seller_id=seller.id,
                seller_url=seller.profile_url,
                platform_name=platform_name,
                goal=goal,
            )
            if conv_id:
                sent += 1
                self._messages_sent_today += 1
                # Пауза между сообщениями (2-8 минут)
                await asyncio.sleep(random.uniform(120, 480))

        logger.info("messages_sent", count=sent)
        return sent

    async def check_replies(self, platform_name: str) -> int:
        """Проверить ответы и ответить через AI."""
        platform = self._get_platform(platform_name)
        conv_manager = ConversationManager(
            repo=self._repo,
            chat_ai=self._chat_ai,
            platform=platform,
            reply_delay_range=tuple(self._config.messaging.reply_delay_minutes),
        )

        active = await self._repo.get_active_conversations(platform=platform_name)
        replied = 0

        for conv in active:
            messages = await self._repo.get_conversation_messages(conv.id)
            if messages and messages[-1].direction == "in":
                # Есть непрочитанный ответ
                # TODO: нужен URL диалога, пока используем profile_url продавца
                seller = await self._repo.get_seller(conv.seller_id)
                if seller:
                    success = await conv_manager.check_and_reply(
                        conv.id, seller.profile_url
                    )
                    if success:
                        replied += 1

        logger.info("replies_sent", count=replied)
        return replied

    async def run_auto(self) -> None:
        """Полный автоматический цикл с расписанием "живого человека"."""
        await self.init()

        try:
            now = datetime.now()
            is_weekend = now.weekday() >= 5
            schedule = DaySchedule(
                is_weekend=is_weekend,
                reduction=self._config.schedule.weekend_activity_reduction,
            ).generate()

            logger.info(
                "auto_run_start",
                is_weekend=is_weekend,
                activities=len(schedule),
            )

            for start_time, end_time, activity in schedule:
                # Ждём начала блока
                now = datetime.now()
                block_start = now.replace(
                    hour=start_time.hour, minute=start_time.minute, second=0
                )
                if now < block_start:
                    wait = (block_start - now).total_seconds()
                    logger.info("waiting_for_block", activity=activity.value, wait_s=wait)
                    await asyncio.sleep(wait)
                elif now.time() > end_time:
                    continue  # Блок уже прошёл

                if activity == ActivityType.BREAK:
                    logger.info("break_time")
                    continue

                # Работаем сессиями: 15-40 мин активности, потом перерыв
                session_min, session_max = self._config.schedule.session_duration_minutes
                break_min, break_max = self._config.schedule.break_duration_minutes

                while datetime.now().time() < end_time:
                    session_duration = random.randint(session_min, session_max) * 60

                    logger.info("session_start", activity=activity.value)
                    await self._run_activity_session(activity, session_duration)

                    if datetime.now().time() >= end_time:
                        break

                    break_duration = random.randint(break_min, break_max) * 60
                    logger.info("session_break", break_s=break_duration)
                    await asyncio.sleep(break_duration)

        finally:
            await self.close()

    async def _run_activity_session(
        self, activity: ActivityType, duration_seconds: int
    ) -> None:
        """Запустить сессию активности определённого типа."""
        for niche in self._config.niches:
            for location in niche.locations:
                for platform_name in self._platforms:
                    if activity == ActivityType.SCRAPE:
                        await self.scrape(platform_name, niche.name, location, limit=10)
                        await self.enrich_profiles(platform_name, limit=5)

                    elif activity == ActivityType.MESSAGE:
                        await self.send_messages(platform_name)

                    elif activity == ActivityType.CHECK_REPLIES:
                        await self.check_replies(platform_name)

    def _get_platform(self, name: str) -> BasePlatform:
        """Получить платформу по имени."""
        if name not in self._platforms:
            raise ValueError(
                f"Платформа '{name}' не найдена или не включена. "
                f"Доступные: {list(self._platforms.keys())}"
            )
        return self._platforms[name]
