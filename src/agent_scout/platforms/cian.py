"""Скрапер ЦИАН — заглушка."""

from agent_scout.platforms.base import BasePlatform, ListingData, SellerData, MessageData


class CianPlatform(BasePlatform):
    """Скрапер для ЦИАН. TODO: реализовать."""

    platform_name = "cian"

    async def search_listings(
        self, query: str, category: str, location: str, limit: int = 20
    ) -> list[ListingData]:
        raise NotImplementedError("ЦИАН скрапер ещё не реализован")

    async def get_seller_profile(self, seller_url: str) -> SellerData:
        raise NotImplementedError("ЦИАН скрапер ещё не реализован")

    async def send_message(self, seller_url: str, message: str) -> bool:
        raise NotImplementedError("ЦИАН скрапер ещё не реализован")

    async def read_messages(self, conversation_url: str) -> list[MessageData]:
        raise NotImplementedError("ЦИАН скрапер ещё не реализован")
