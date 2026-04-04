"""Управление браузером с anti-detection через playwright-stealth."""

import json
from pathlib import Path
from typing import Optional

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from agent_scout.browser.humanizer import HumanBehavior
from agent_scout.browser.proxy import ProxyManager
from agent_scout.config import AppConfig

logger = structlog.get_logger()


class BrowserManager:
    """Управление браузером Playwright с anti-detection.

    - Сохраняет cookies/storage state между запусками
    - Первый запуск: headful для ручного логина
    - Последующие: headless с сохранённой сессией
    - Фиксированный viewport (мы один и тот же "человек")
    """

    def __init__(self, config: AppConfig, proxy_manager: Optional[ProxyManager] = None):
        self._config = config
        self._proxy = proxy_manager or ProxyManager()
        self.human = HumanBehavior()
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._sessions_dir = Path(config.database.sessions_dir)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, platform: str) -> Path:
        """Путь к файлу сессии для площадки."""
        return self._sessions_dir / f"{platform}.json"

    def _has_session(self, platform: str) -> bool:
        """Есть ли сохранённая сессия для площадки."""
        return self._session_path(platform).exists()

    async def start(self, platform: str, headless: Optional[bool] = None) -> Page:
        """Запустить браузер и вернуть страницу.

        Если сессия для площадки не найдена — запускает в headful режиме
        для ручного логина. Иначе — headless с сохранённой сессией.
        """
        from playwright_stealth import stealth_async

        has_session = self._has_session(platform)

        if headless is None:
            headless = has_session and self._config.browser.headless

        self._playwright = await async_playwright().start()

        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }

        proxy_config = self._proxy.get_playwright_proxy()
        if proxy_config:
            launch_args["proxy"] = proxy_config

        self._browser = await self._playwright.chromium.launch(**launch_args)

        # Контекст браузера с настройками fingerprint
        context_args = {
            "viewport": {
                "width": self._config.browser.viewport_width,
                "height": self._config.browser.viewport_height,
            },
            "locale": self._config.browser.locale,
            "timezone_id": self._config.browser.timezone,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        # Загрузить сохранённую сессию если есть
        session_path = self._session_path(platform)
        if has_session:
            context_args["storage_state"] = str(session_path)
            logger.info("session_loaded", platform=platform)

        self._context = await self._browser.new_context(**context_args)
        page = await self._context.new_page()

        # Применить stealth
        await stealth_async(page)

        if not has_session:
            logger.info(
                "no_session_found",
                platform=platform,
                message="Браузер открыт в headful режиме. Залогиньтесь вручную.",
            )

        return page

    async def save_session(self, platform: str) -> None:
        """Сохранить текущую сессию (cookies, localStorage)."""
        if self._context:
            session_path = self._session_path(platform)
            state = await self._context.storage_state()
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info("session_saved", platform=platform, path=str(session_path))

    async def close(self) -> None:
        """Закрыть браузер и освободить ресурсы."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("browser_closed")

    async def new_page(self) -> Page:
        """Открыть новую вкладку в текущем контексте."""
        from playwright_stealth import stealth_async

        if not self._context:
            raise RuntimeError("Браузер не запущен. Вызовите start() сначала.")
        page = await self._context.new_page()
        await stealth_async(page)
        return page
