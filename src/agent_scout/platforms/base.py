"""Абстрактный базовый класс для всех платформ."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ListingData:
    """Данные объявления, спарсенные со страницы."""

    title: str
    url: str
    price: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    photos: list[str] = field(default_factory=list)
    seller_url: Optional[str] = None
    seller_name: Optional[str] = None
    seller_external_id: Optional[str] = None


@dataclass
class SellerData:
    """Данные профиля продавца."""

    external_id: str
    name: str
    profile_url: str
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    registration_date: Optional[str] = None
    listings_count: Optional[int] = None


@dataclass
class MessageData:
    """Данные сообщения."""

    text: str
    direction: str  # "in" или "out"
    timestamp: Optional[str] = None


class BasePlatform(ABC):
    """Абстрактный интерфейс для скраперов площадок."""

    platform_name: str = "unknown"

    @abstractmethod
    async def search_listings(
        self, query: str, category: str, location: str, limit: int = 20
    ) -> list[ListingData]:
        """Поиск объявлений по запросу."""
        ...

    @abstractmethod
    async def get_seller_profile(self, seller_url: str) -> SellerData:
        """Получить полный профиль продавца."""
        ...

    @abstractmethod
    async def send_message(self, seller_url: str, message: str) -> bool:
        """Отправить сообщение продавцу."""
        ...

    @abstractmethod
    async def read_messages(self, conversation_url: str) -> list[MessageData]:
        """Прочитать сообщения в диалоге."""
        ...
