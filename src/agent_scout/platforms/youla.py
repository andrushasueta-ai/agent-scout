"""Скрапер Юла — заглушка."""

from agent_scout.platforms.base import BasePlatform, ListingData, SellerData, MessageData


class YoulaPlatform(BasePlatform):
    """Скрапер для Юла. TODO: реализовать."""

    platform_name = "youla"

    async def search_listings(
        self, query: str, category: str, location: str, limit: int = 20
    ) -> list[ListingData]:
        raise NotImplementedError("Юла скрапер ещё не реализован")

    async def get_seller_profile(self, seller_url: str) -> SellerData:
        raise NotImplementedError("Юла скрапер ещё не реализован")

    async def send_message(self, seller_url: str, message: str) -> bool:
        raise NotImplementedError("Юла скрапер ещё не реализован")

    async def read_messages(self, conversation_url: str) -> list[MessageData]:
        raise NotImplementedError("Юла скрапер ещё не реализован")
