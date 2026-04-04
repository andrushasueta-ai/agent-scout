"""Async CRUD операции для всех моделей."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_scout.database.models import (
    Base,
    Seller,
    Listing,
    Conversation,
    Message,
    get_engine,
    get_session_factory,
)


class Repository:
    """Единый репозиторий для работы с БД."""

    def __init__(self, db_path: str = "data/agent_scout.db"):
        self._engine = get_engine(db_path)
        self._session_factory = get_session_factory(self._engine)

    async def init_db(self) -> None:
        """Создать все таблицы."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Закрыть соединение с БД."""
        await self._engine.dispose()

    def _session(self) -> AsyncSession:
        return self._session_factory()

    # --- Sellers ---

    async def create_seller(
        self,
        platform: str,
        external_id: str,
        name: str,
        profile_url: str,
        rating: Optional[float] = None,
        reviews_count: Optional[int] = None,
        registration_date: Optional[str] = None,
        listings_count: Optional[int] = None,
    ) -> Seller:
        """Создать или обновить продавца (upsert по platform + external_id)."""
        async with self._session() as session:
            stmt = select(Seller).where(
                Seller.platform == platform, Seller.external_id == external_id
            )
            result = await session.execute(stmt)
            seller = result.scalar_one_or_none()

            if seller:
                seller.name = name
                seller.profile_url = profile_url
                seller.rating = rating if rating is not None else seller.rating
                seller.reviews_count = (
                    reviews_count if reviews_count is not None else seller.reviews_count
                )
                seller.registration_date = (
                    registration_date
                    if registration_date is not None
                    else seller.registration_date
                )
                seller.listings_count = (
                    listings_count
                    if listings_count is not None
                    else seller.listings_count
                )
                seller.updated_at = datetime.utcnow()
            else:
                seller = Seller(
                    platform=platform,
                    external_id=external_id,
                    name=name,
                    profile_url=profile_url,
                    rating=rating,
                    reviews_count=reviews_count,
                    registration_date=registration_date,
                    listings_count=listings_count,
                )
                session.add(seller)

            await session.commit()
            await session.refresh(seller)
            return seller

    async def get_seller(self, seller_id: int) -> Optional[Seller]:
        """Получить продавца по ID."""
        async with self._session() as session:
            return await session.get(Seller, seller_id)

    async def get_seller_by_external(
        self, platform: str, external_id: str
    ) -> Optional[Seller]:
        """Найти продавца по platform + external_id."""
        async with self._session() as session:
            stmt = select(Seller).where(
                Seller.platform == platform, Seller.external_id == external_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_sellers(self, platform: Optional[str] = None) -> list[Seller]:
        """Получить список продавцов."""
        async with self._session() as session:
            stmt = select(Seller)
            if platform:
                stmt = stmt.where(Seller.platform == platform)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # --- Listings ---

    async def create_listing(
        self,
        seller_id: int,
        platform: str,
        title: str,
        url: str,
        description: Optional[str] = None,
        price: Optional[str] = None,
        category: Optional[str] = None,
        location: Optional[str] = None,
        photos_json: Optional[dict] = None,
    ) -> Listing:
        """Создать объявление."""
        async with self._session() as session:
            listing = Listing(
                seller_id=seller_id,
                platform=platform,
                title=title,
                url=url,
                description=description,
                price=price,
                category=category,
                location=location,
                photos_json=photos_json,
            )
            session.add(listing)
            await session.commit()
            await session.refresh(listing)
            return listing

    async def list_listings(
        self,
        platform: Optional[str] = None,
        seller_id: Optional[int] = None,
    ) -> list[Listing]:
        """Получить список объявлений."""
        async with self._session() as session:
            stmt = select(Listing)
            if platform:
                stmt = stmt.where(Listing.platform == platform)
            if seller_id:
                stmt = stmt.where(Listing.seller_id == seller_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # --- Conversations ---

    async def create_conversation(
        self,
        seller_id: int,
        platform: str,
        goal: Optional[str] = None,
    ) -> Conversation:
        """Создать диалог."""
        async with self._session() as session:
            conv = Conversation(
                seller_id=seller_id,
                platform=platform,
                goal=goal,
                status="new",
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
            return conv

    async def update_conversation_status(
        self, conversation_id: int, status: str
    ) -> None:
        """Обновить статус диалога."""
        async with self._session() as session:
            stmt = (
                update(Conversation)
                .where(Conversation.id == conversation_id)
                .values(status=status)
            )
            await session.execute(stmt)
            await session.commit()

    async def get_active_conversations(
        self, platform: Optional[str] = None
    ) -> list[Conversation]:
        """Получить активные диалоги."""
        async with self._session() as session:
            stmt = select(Conversation).where(
                Conversation.status.in_(["new", "active"])
            )
            if platform:
                stmt = stmt.where(Conversation.platform == platform)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def has_conversation_with_seller(
        self, seller_id: int
    ) -> bool:
        """Проверить, есть ли уже диалог с продавцом."""
        async with self._session() as session:
            stmt = select(Conversation).where(Conversation.seller_id == seller_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    # --- Messages ---

    async def add_message(
        self,
        conversation_id: int,
        direction: str,
        text: str,
    ) -> Message:
        """Добавить сообщение в диалог."""
        async with self._session() as session:
            msg = Message(
                conversation_id=conversation_id,
                direction=direction,
                text=text,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return msg

    async def get_conversation_messages(
        self, conversation_id: int
    ) -> list[Message]:
        """Получить все сообщения диалога."""
        async with self._session() as session:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.sent_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
