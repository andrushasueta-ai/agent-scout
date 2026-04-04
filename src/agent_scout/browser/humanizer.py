"""Имитация человеческого поведения в браузере."""

import asyncio
import math
import random
from typing import Optional

import structlog

logger = structlog.get_logger()


class HumanBehavior:
    """Имитация поведения реального пользователя в браузере.

    Все действия добавляют случайные задержки и вариативность,
    чтобы паттерн не выглядел автоматизированным.
    """

    async def random_delay(self, min_s: float = 0.5, max_s: float = 3.0) -> None:
        """Случайная пауза с нормальным распределением."""
        mean = (min_s + max_s) / 2
        std = (max_s - min_s) / 4
        delay = max(min_s, min(max_s, random.gauss(mean, std)))
        await asyncio.sleep(delay)

    async def human_scroll(self, page, scroll_count: Optional[int] = None) -> None:
        """Плавный скролл страницы с рандомными остановками.

        Скроллит как реальный человек: быстрые и медленные участки,
        иногда скролл назад, паузы для "чтения".
        """
        if scroll_count is None:
            scroll_count = random.randint(3, 8)

        for i in range(scroll_count):
            # Случайная дистанция скролла (200-600 px)
            distance = random.randint(200, 600)

            # Иногда скроллим немного назад (10% шанс)
            if random.random() < 0.1 and i > 0:
                distance = -random.randint(50, 150)

            await page.mouse.wheel(0, distance)

            # Пауза после скролла: имитируем чтение
            if random.random() < 0.3:
                # Длинная пауза — "читаем" контент
                await self.random_delay(1.5, 4.0)
            else:
                # Короткая пауза
                await self.random_delay(0.3, 1.0)

        logger.debug("human_scroll_done", scroll_count=scroll_count)

    async def human_mouse_move(self, page, selector: str) -> None:
        """Плавное перемещение мыши к элементу по кривой Безье."""
        element = await page.query_selector(selector)
        if not element:
            logger.warning("element_not_found", selector=selector)
            return

        box = await element.bounding_box()
        if not box:
            return

        # Целевая точка с небольшим рандомом внутри элемента
        target_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
        target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)

        # Текущая позиция мыши (примерная)
        viewport = page.viewport_size
        current_x = random.uniform(0, viewport["width"]) if viewport else 500
        current_y = random.uniform(0, viewport["height"]) if viewport else 400

        # Генерируем кривую Безье с 2 контрольными точками
        steps = random.randint(15, 30)
        points = self._bezier_curve(
            current_x, current_y, target_x, target_y, steps
        )

        for x, y in points:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.025))

        logger.debug("mouse_moved", target_selector=selector)

    async def human_type(self, page, selector: str, text: str) -> None:
        """Набор текста с человеческими задержками между символами."""
        await page.click(selector)
        await self.random_delay(0.2, 0.5)

        for char in text:
            await page.keyboard.type(char)

            # Задержка между символами
            if char == " ":
                delay = random.uniform(0.05, 0.15)
            elif char in ".,!?":
                delay = random.uniform(0.1, 0.3)
            else:
                delay = random.uniform(0.04, 0.18)

            await asyncio.sleep(delay)

            # Иногда делаем микро-паузу (имитация задумчивости)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.3, 0.8))

        logger.debug("human_type_done", length=len(text))

    async def random_page_interaction(self, page) -> None:
        """Случайные действия на странице для имитации живого пользователя."""
        actions = [
            self._random_hover,
            self._random_mini_scroll,
            self._random_mouse_wiggle,
        ]
        action = random.choice(actions)
        await action(page)

    async def _random_hover(self, page) -> None:
        """Навести мышь на случайный элемент."""
        viewport = page.viewport_size
        if not viewport:
            return
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        await page.mouse.move(x, y)
        await self.random_delay(0.5, 1.5)

    async def _random_mini_scroll(self, page) -> None:
        """Небольшой скролл вверх-вниз."""
        distance = random.randint(-100, 100)
        await page.mouse.wheel(0, distance)
        await self.random_delay(0.3, 0.8)

    async def _random_mouse_wiggle(self, page) -> None:
        """Небольшое дрожание мыши (как у реального человека)."""
        viewport = page.viewport_size
        if not viewport:
            return
        x = random.randint(200, viewport["width"] - 200)
        y = random.randint(200, viewport["height"] - 200)
        for _ in range(random.randint(3, 6)):
            dx = random.randint(-5, 5)
            dy = random.randint(-5, 5)
            await page.mouse.move(x + dx, y + dy)
            await asyncio.sleep(random.uniform(0.02, 0.08))

    @staticmethod
    def _bezier_curve(
        x0: float, y0: float, x1: float, y1: float, steps: int
    ) -> list[tuple[float, float]]:
        """Генерация точек по кубической кривой Безье."""
        # Контрольные точки со случайным отклонением
        dx = x1 - x0
        dy = y1 - y0
        cp1_x = x0 + dx * 0.3 + random.uniform(-50, 50)
        cp1_y = y0 + dy * 0.1 + random.uniform(-50, 50)
        cp2_x = x0 + dx * 0.7 + random.uniform(-30, 30)
        cp2_y = y0 + dy * 0.9 + random.uniform(-30, 30)

        points = []
        for i in range(steps + 1):
            t = i / steps
            # Кубическая формула Безье
            x = (
                (1 - t) ** 3 * x0
                + 3 * (1 - t) ** 2 * t * cp1_x
                + 3 * (1 - t) * t ** 2 * cp2_x
                + t ** 3 * x1
            )
            y = (
                (1 - t) ** 3 * y0
                + 3 * (1 - t) ** 2 * t * cp1_y
                + 3 * (1 - t) * t ** 2 * cp2_y
                + t ** 3 * y1
            )
            points.append((x, y))
        return points
