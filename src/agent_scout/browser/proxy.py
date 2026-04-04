"""Опциональная поддержка прокси для защиты IP."""

from typing import Optional

import structlog

from agent_scout.config import ProxyConfig

logger = structlog.get_logger()


class ProxyManager:
    """Управление прокси-соединением.

    Прокси используется опционально для защиты домашнего IP.
    Один прокси на всю сессию — не ротация на каждый запрос
    (ротация выглядит подозрительно для площадок).
    """

    def __init__(self, proxies: list[ProxyConfig] | None = None):
        self._proxies = proxies or []
        self._current: Optional[ProxyConfig] = None

        if self._proxies:
            self._current = self._proxies[0]
            logger.info("proxy_configured", host=self._current.host)
        else:
            logger.info("proxy_disabled", reason="no proxies configured")

    @property
    def is_configured(self) -> bool:
        """Есть ли активный прокси."""
        return self._current is not None

    def get_playwright_proxy(self) -> Optional[dict]:
        """Получить прокси в формате Playwright.

        Возвращает None если прокси не настроены (прямое соединение).
        Поддерживает SOCKS5, HTTP, HTTPS протоколы.
        """
        if not self._current:
            return None

        proxy = {"server": f"{self._current.protocol}://{self._current.host}:{self._current.port}"}
        if self._current.username:
            proxy["username"] = self._current.username
        if self._current.password:
            proxy["password"] = self._current.password

        return proxy
