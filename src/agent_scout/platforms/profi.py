"""Скрапер Profi.ru — заглушка."""

from agent_scout.platforms.base import BasePlatform, ListingData, SellerData, MessageData


class ProfiPlatform(BasePlatform):
    """Скрапер для Profi.ru. TODO: реализовать."""

    platform_name = "profi"

    async def search_listings(
        self, query: str, category: str, location: str, limit: int = 20
    ) -> list[ListingData]:
        raise NotImplementedError("Profi.ru скрапер ещё не реализован")

    async def get_seller_profile(self, seller_url: str) -> SellerData:
        raise NotImplementedError("Profi.ru скрапер ещё не реализован")

    async def send_message(self, seller_url: str, message: str) -> bool:
        raise NotImplementedError("Profi.ru скрапер ещё не реализован")

    async def read_messages(self, conversation_url: str) -> list[MessageData]:
        raise NotImplementedError("Profi.ru скрапер ещё не реализован")
