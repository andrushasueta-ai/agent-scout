"""Тесты для browser/humanizer.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest

from agent_scout.browser.humanizer import HumanBehavior


@pytest.fixture
def humanizer():
    return HumanBehavior()


@pytest.fixture
def mock_page():
    """Мок объекта page Playwright."""
    page = AsyncMock()
    page.viewport_size = {"width": 1440, "height": 900}
    page.mouse = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.mouse.move = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.type = AsyncMock()
    page.click = AsyncMock()

    # Мок элемента для query_selector
    element = AsyncMock()
    element.bounding_box = AsyncMock(
        return_value={"x": 100, "y": 200, "width": 200, "height": 50}
    )
    page.query_selector = AsyncMock(return_value=element)

    return page


async def test_random_delay_range(humanizer: HumanBehavior):
    """Задержка должна быть в заданном диапазоне."""
    start = time.monotonic()
    await humanizer.random_delay(0.05, 0.15)
    elapsed = time.monotonic() - start
    assert 0.04 <= elapsed <= 0.5  # с запасом на overhead


async def test_human_scroll_calls_wheel(humanizer: HumanBehavior, mock_page):
    """human_scroll должен вызывать mouse.wheel несколько раз."""
    await humanizer.human_scroll(mock_page, scroll_count=3)
    assert mock_page.mouse.wheel.call_count == 3


async def test_human_mouse_move_moves_to_element(humanizer: HumanBehavior, mock_page):
    """human_mouse_move должен двигать мышь к элементу."""
    await humanizer.human_mouse_move(mock_page, "button.submit")
    mock_page.query_selector.assert_called_once_with("button.submit")
    assert mock_page.mouse.move.call_count >= 15  # минимум шагов кривой Безье


async def test_human_mouse_move_missing_element(humanizer: HumanBehavior, mock_page):
    """human_mouse_move с несуществующим элементом не падает."""
    mock_page.query_selector = AsyncMock(return_value=None)
    await humanizer.human_mouse_move(mock_page, "missing.element")
    mock_page.mouse.move.assert_not_called()


async def test_human_type_types_each_char(humanizer: HumanBehavior, mock_page):
    """human_type должен набирать каждый символ отдельно."""
    text = "Привет"
    await humanizer.human_type(mock_page, "input.search", text)
    mock_page.click.assert_called_once_with("input.search")
    assert mock_page.keyboard.type.call_count == len(text)


async def test_random_page_interaction_runs(humanizer: HumanBehavior, mock_page):
    """random_page_interaction не должен падать."""
    for _ in range(5):
        await humanizer.random_page_interaction(mock_page)


def test_bezier_curve_endpoints():
    """Кривая Безье должна начинаться и заканчиваться в нужных точках."""
    points = HumanBehavior._bezier_curve(0, 0, 100, 100, 20)
    assert len(points) == 21
    # Начальная точка
    assert abs(points[0][0] - 0) < 0.01
    assert abs(points[0][1] - 0) < 0.01
    # Конечная точка
    assert abs(points[-1][0] - 100) < 0.01
    assert abs(points[-1][1] - 100) < 0.01
