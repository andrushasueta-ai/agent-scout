"""SQLAlchemy 2.0 модели базы данных."""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, Float, Integer, DateTime, JSON
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Seller(Base):
    """Продавец/конкурент на площадке."""

    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    registration_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    listings_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="seller")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="seller")


class Listing(Base):
    """Объявление на площадке."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"))
    platform: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    photos_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    seller: Mapped["Seller"] = relationship(back_populates="listings")


class Conversation(Base):
    """Диалог с продавцом."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"))
    platform: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="new")  # new/active/completed
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    seller: Mapped["Seller"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    """Сообщение в диалоге."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    direction: Mapped[str] = mapped_column(String(10))  # in/out
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


def get_engine(db_path: str = "data/agent_scout.db"):
    """Создать async engine для SQLite."""
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


def get_session_factory(engine):
    """Создать фабрику async-сессий."""
    return async_sessionmaker(engine, expire_on_commit=False)
