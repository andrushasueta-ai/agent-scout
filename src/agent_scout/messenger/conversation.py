"""Управление диалогами с продавцами."""

import asyncio
import random
from typing import Optional

import structlog

from agent_scout.database.repository import Repository
from agent_scout.messenger.chat_ai import ChatAI
from agent_scout.platforms.base import BasePlatform

logger = structlog.get_logger()


class ConversationManager:
    """Менеджер диалогов: инициация, ответы, завершение.

    Координирует AI-генерацию сообщений, отправку через платформу
    и хранение в БД.
    """

    def __init__(
        self,
        repo: Repository,
        chat_ai: ChatAI,
        platform: BasePlatform,
        reply_delay_range: tuple[int, int] = (3, 20),
    ):
        self._repo = repo
        self._ai = chat_ai
        self._platform = platform
        self._reply_delay_range = reply_delay_range

    async def start_conversation(
        self,
        seller_id: int,
        seller_url: str,
        platform_name: str,
        goal: str = "Узнать цены на мех. штукатурку ~40м2 стен, ЖК Парксайд, Москва",
    ) -> Optional[int]:
        """Начать новый диалог с продавцом.

        Returns:
            ID созданного диалога или None если уже есть диалог.
        """
        # Не писать дважды одному продавцу
        if await self._repo.has_conversation_with_seller(seller_id):
            logger.info("conversation_exists", seller_id=seller_id)
            return None

        # Генерируем первое сообщение
        message = await self._ai.generate_first_message(goal)
        logger.info("first_message_generated", message=message[:50])

        # Отправляем через платформу
        sent = await self._platform.send_message(seller_url, message)
        if not sent:
            logger.warning("message_send_failed", seller_url=seller_url)
            return None

        # Сохраняем в БД
        conv = await self._repo.create_conversation(
            seller_id=seller_id,
            platform=platform_name,
            goal=goal,
        )
        await self._repo.update_conversation_status(conv.id, "active")
        await self._repo.add_message(conv.id, "out", message)

        logger.info("conversation_started", conversation_id=conv.id, seller_id=seller_id)
        return conv.id

    async def check_and_reply(self, conversation_id: int, conversation_url: str) -> bool:
        """Проверить новые сообщения и ответить если нужно.

        Returns:
            True если был отправлен ответ.
        """
        # Читаем сообщения с площадки
        platform_messages = await self._platform.read_messages(conversation_url)
        if not platform_messages:
            return False

        # Получаем сохранённые сообщения
        db_messages = await self._repo.get_conversation_messages(conversation_id)
        db_count = len(db_messages)

        # Если новых сообщений нет — пропускаем
        if len(platform_messages) <= db_count:
            return False

        # Сохраняем новые входящие сообщения
        for msg in platform_messages[db_count:]:
            if msg.direction == "in":
                await self._repo.add_message(conversation_id, "in", msg.text)

        # Получаем обновлённый контекст
        all_messages = await self._repo.get_conversation_messages(conversation_id)

        # Проверяем, нужно ли ещё отвечать
        # Получаем goal из БД
        active_convs = await self._repo.get_active_conversations()
        goal = "Узнать цены на мех. штукатурку ~40м2 стен, ЖК Парксайд, Москва"
        for c in active_convs:
            if c.id == conversation_id:
                goal = c.goal or goal
                break

        should_continue = await self._ai.should_continue_conversation(all_messages, goal)

        if not should_continue:
            await self._repo.update_conversation_status(conversation_id, "completed")
            logger.info("conversation_completed", conversation_id=conversation_id)
            return False

        # Задержка перед ответом (3-20 минут)
        delay_minutes = random.randint(*self._reply_delay_range)
        logger.info(
            "reply_delay",
            conversation_id=conversation_id,
            delay_minutes=delay_minutes,
        )
        await asyncio.sleep(delay_minutes * 60)

        # Генерируем и отправляем ответ
        reply = await self._ai.generate_reply(all_messages, goal)

        # Для ответа нужен URL продавца — берём из последнего сообщения
        sent = await self._platform.send_message(conversation_url, reply)
        if sent:
            await self._repo.add_message(conversation_id, "out", reply)
            logger.info("reply_sent", conversation_id=conversation_id, reply=reply[:50])
            return True

        return False

    async def get_pending_replies_count(self) -> int:
        """Количество диалогов, ожидающих ответа."""
        active = await self._repo.get_active_conversations()
        count = 0
        for conv in active:
            messages = await self._repo.get_conversation_messages(conv.id)
            if messages and messages[-1].direction == "in":
                count += 1
        return count
