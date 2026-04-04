"""Скрапер Авито — поиск объявлений и парсинг профилей продавцов."""

import re
from typing import Optional
from urllib.parse import quote_plus

import structlog

from agent_scout.browser.manager import BrowserManager
from agent_scout.platforms.base import BasePlatform, ListingData, SellerData, MessageData

logger = structlog.get_logger()


class AvitoPlatform(BasePlatform):
    """Скрапер для Авито."""

    platform_name = "avito"
    BASE_URL = "https://www.avito.ru"

    def __init__(self, browser_manager: BrowserManager):
        self._browser = browser_manager
        self._human = browser_manager.human

    async def search_listings(
        self, query: str, category: str, location: str, limit: int = 20
    ) -> list[ListingData]:
        """Поиск объявлений на Авито.

        Переходит на страницу поиска, скроллит, парсит карточки.
        """
        page = await self._browser.start(self.platform_name)
        listings: list[ListingData] = []

        try:
            # Формируем URL поиска
            location_slug = self._location_to_slug(location)
            search_url = (
                f"{self.BASE_URL}/{location_slug}/uslugi"
                f"?q={quote_plus(query)}"
            )
            logger.info("search_start", url=search_url, query=query, location=location)

            await page.goto(search_url, wait_until="domcontentloaded")
            await self._human.random_delay(2.0, 4.0)

            # Скроллим для загрузки контента
            await self._human.human_scroll(page, scroll_count=5)
            await self._human.random_delay(1.0, 2.0)

            # Парсим карточки объявлений
            cards = await page.query_selector_all('[data-marker="item"]')
            logger.info("cards_found", count=len(cards))

            for card in cards[:limit]:
                try:
                    listing = await self._parse_listing_card(card)
                    if listing:
                        listings.append(listing)
                        await self._human.random_delay(0.2, 0.5)
                except Exception as e:
                    logger.warning("card_parse_error", error=str(e))
                    continue

            logger.info("search_done", listings_count=len(listings))

        finally:
            await self._browser.save_session(self.platform_name)

        return listings

    async def get_seller_profile(self, seller_url: str) -> SellerData:
        """Получить профиль продавца с его страницы."""
        page = await self._browser.start(self.platform_name)

        try:
            await page.goto(seller_url, wait_until="domcontentloaded")
            await self._human.random_delay(2.0, 4.0)
            await self._human.random_page_interaction(page)

            # Имя продавца
            name_el = await page.query_selector('[data-marker="seller-info/name"]')
            name = await name_el.inner_text() if name_el else "Неизвестно"

            # Рейтинг
            rating = None
            rating_el = await page.query_selector('[data-marker="seller-info/score"]')
            if rating_el:
                rating_text = await rating_el.inner_text()
                try:
                    rating = float(rating_text.replace(",", "."))
                except ValueError:
                    pass

            # Количество отзывов
            reviews_count = None
            reviews_el = await page.query_selector(
                '[data-marker="seller-info/summary"] span'
            )
            if reviews_el:
                reviews_text = await reviews_el.inner_text()
                numbers = re.findall(r"\d+", reviews_text)
                if numbers:
                    reviews_count = int(numbers[0])

            # Дата регистрации
            reg_date = None
            reg_el = await page.query_selector('[data-marker="seller-info/start-date"]')
            if reg_el:
                reg_date = await reg_el.inner_text()

            # Количество активных объявлений
            listings_count = None
            count_el = await page.query_selector(
                '[data-marker="seller-info/items-count"]'
            )
            if count_el:
                count_text = await count_el.inner_text()
                numbers = re.findall(r"\d+", count_text)
                if numbers:
                    listings_count = int(numbers[0])

            # Извлекаем external_id из URL
            external_id = self._extract_seller_id(seller_url)

            seller = SellerData(
                external_id=external_id,
                name=name.strip(),
                profile_url=seller_url,
                rating=rating,
                reviews_count=reviews_count,
                registration_date=reg_date,
                listings_count=listings_count,
            )
            logger.info("seller_parsed", name=seller.name, rating=seller.rating)

            await self._browser.save_session(self.platform_name)
            return seller

        except Exception as e:
            logger.error("seller_profile_error", url=seller_url, error=str(e))
            raise

    async def send_message(self, seller_url: str, message: str) -> bool:
        """Отправить сообщение продавцу через форму на Авито."""
        page = await self._browser.start(self.platform_name)

        try:
            await page.goto(seller_url, wait_until="domcontentloaded")
            await self._human.random_delay(2.0, 4.0)

            # Ищем кнопку "Написать сообщение"
            write_btn = await page.query_selector(
                '[data-marker="messenger-button"], '
                'button:has-text("Написать"), '
                'a:has-text("Написать сообщение")'
            )
            if not write_btn:
                logger.warning("message_button_not_found", url=seller_url)
                return False

            await self._human.human_mouse_move(page, '[data-marker="messenger-button"]')
            await write_btn.click()
            await self._human.random_delay(2.0, 4.0)

            # Ввод сообщения
            textarea = await page.query_selector(
                'textarea[data-marker="messenger-input"], '
                'div[contenteditable="true"]'
            )
            if not textarea:
                logger.warning("message_textarea_not_found")
                return False

            await self._human.human_type(page, "textarea", message)
            await self._human.random_delay(0.5, 1.5)

            # Отправка
            send_btn = await page.query_selector(
                'button[data-marker="messenger-send"], '
                'button:has-text("Отправить")'
            )
            if send_btn:
                await send_btn.click()
                await self._human.random_delay(1.0, 2.0)
                logger.info("message_sent", url=seller_url)
                await self._browser.save_session(self.platform_name)
                return True

            logger.warning("send_button_not_found")
            return False

        except Exception as e:
            logger.error("send_message_error", url=seller_url, error=str(e))
            return False

    async def read_messages(self, conversation_url: str) -> list[MessageData]:
        """Прочитать сообщения в диалоге на Авито."""
        page = await self._browser.start(self.platform_name)
        messages: list[MessageData] = []

        try:
            await page.goto(conversation_url, wait_until="domcontentloaded")
            await self._human.random_delay(2.0, 4.0)

            # Парсим сообщения в чате
            msg_elements = await page.query_selector_all(
                '[data-marker*="message"]'
            )

            for msg_el in msg_elements:
                try:
                    text_el = await msg_el.query_selector('[data-marker*="text"]')
                    if not text_el:
                        continue
                    text = await text_el.inner_text()

                    # Определяем направление по CSS-классам
                    classes = await msg_el.get_attribute("class") or ""
                    direction = "out" if "sent" in classes or "own" in classes else "in"

                    messages.append(MessageData(text=text.strip(), direction=direction))
                except Exception:
                    continue

            logger.info("messages_read", count=len(messages), url=conversation_url)
            await self._browser.save_session(self.platform_name)

        except Exception as e:
            logger.error("read_messages_error", url=conversation_url, error=str(e))

        return messages

    # --- Вспомогательные методы ---

    async def _parse_listing_card(self, card) -> Optional[ListingData]:
        """Парсинг одной карточки объявления."""
        # Заголовок и ссылка
        title_el = await card.query_selector('[itemprop="name"]')
        if not title_el:
            title_el = await card.query_selector("h3")
        if not title_el:
            return None

        title = await title_el.inner_text()

        link_el = await card.query_selector("a[href]")
        url = ""
        if link_el:
            href = await link_el.get_attribute("href")
            url = f"{self.BASE_URL}{href}" if href and href.startswith("/") else href or ""

        # Цена
        price = None
        price_el = await card.query_selector('[itemprop="price"]')
        if not price_el:
            price_el = await card.query_selector('[data-marker="item-price"]')
        if price_el:
            price_val = await price_el.get_attribute("content")
            if price_val:
                price = price_val
            else:
                price = await price_el.inner_text()

        # Описание (краткое из карточки)
        description = None
        desc_el = await card.query_selector('[class*="description"], [class*="snippet"]')
        if desc_el:
            description = await desc_el.inner_text()

        # Локация
        location = None
        loc_el = await card.query_selector('[class*="geo"], [data-marker*="address"]')
        if loc_el:
            location = await loc_el.inner_text()

        # Фото
        photos = []
        img_el = await card.query_selector("img[src]")
        if img_el:
            src = await img_el.get_attribute("src")
            if src:
                photos.append(src)

        # Ссылка на продавца
        seller_url = None
        seller_el = await card.query_selector('a[href*="/user/"]')
        if seller_el:
            href = await seller_el.get_attribute("href")
            seller_url = f"{self.BASE_URL}{href}" if href and href.startswith("/") else href

        return ListingData(
            title=title.strip(),
            url=url,
            price=price,
            description=description.strip() if description else None,
            location=location.strip() if location else None,
            photos=photos,
            seller_url=seller_url,
        )

    @staticmethod
    def _location_to_slug(location: str) -> str:
        """Преобразовать название города в slug для URL Авито."""
        slugs = {
            "москва": "moskva",
            "санкт-петербург": "sankt-peterburg",
            "новосибирск": "novosibirsk",
            "екатеринбург": "ekaterinburg",
            "казань": "kazan",
            "нижний новгород": "nizhniy_novgorod",
            "челябинск": "chelyabinsk",
            "самара": "samara",
            "уфа": "ufa",
            "ростов-на-дону": "rostov-na-donu",
            "краснодар": "krasnodar",
            "воронеж": "voronezh",
            "пермь": "perm",
            "волгоград": "volgograd",
        }
        return slugs.get(location.lower(), location.lower().replace(" ", "_"))

    @staticmethod
    def _extract_seller_id(url: str) -> str:
        """Извлечь ID продавца из URL."""
        match = re.search(r"/user/([a-f0-9]+)", url)
        if match:
            return match.group(1)
        # Fallback: последний сегмент пути
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else "unknown"
