"""Тесты для database/models.py и database/repository.py."""

import pytest

from agent_scout.database.repository import Repository


@pytest.fixture
async def repo(tmp_path):
    """Создать репозиторий с временной БД."""
    db_path = str(tmp_path / "test.db")
    r = Repository(db_path)
    await r.init_db()
    yield r
    await r.close()


async def test_create_and_get_seller(repo: Repository):
    """Создание и получение продавца."""
    seller = await repo.create_seller(
        platform="avito",
        external_id="12345",
        name="Иван Строитель",
        profile_url="https://avito.ru/user/12345",
        rating=4.8,
        reviews_count=42,
    )
    assert seller.id is not None
    assert seller.name == "Иван Строитель"
    assert seller.rating == 4.8

    fetched = await repo.get_seller(seller.id)
    assert fetched is not None
    assert fetched.external_id == "12345"


async def test_seller_upsert(repo: Repository):
    """Повторное создание продавца обновляет данные."""
    await repo.create_seller(
        platform="avito",
        external_id="12345",
        name="Иван",
        profile_url="https://avito.ru/user/12345",
        rating=4.0,
    )
    updated = await repo.create_seller(
        platform="avito",
        external_id="12345",
        name="Иван Обновлённый",
        profile_url="https://avito.ru/user/12345",
        rating=4.9,
    )
    sellers = await repo.list_sellers(platform="avito")
    assert len(sellers) == 1
    assert sellers[0].name == "Иван Обновлённый"
    assert sellers[0].rating == 4.9


async def test_create_listing(repo: Repository):
    """Создание объявления."""
    seller = await repo.create_seller(
        platform="avito",
        external_id="1",
        name="Тест",
        profile_url="https://avito.ru/user/1",
    )
    listing = await repo.create_listing(
        seller_id=seller.id,
        platform="avito",
        title="Ремонт квартир под ключ",
        url="https://avito.ru/item/123",
        price="50 000 ₽",
        category="Строительство",
        location="Москва",
    )
    assert listing.id is not None
    assert listing.title == "Ремонт квартир под ключ"

    listings = await repo.list_listings(seller_id=seller.id)
    assert len(listings) == 1


async def test_conversation_and_messages(repo: Repository):
    """Создание диалога и сообщений."""
    seller = await repo.create_seller(
        platform="avito",
        external_id="1",
        name="Тест",
        profile_url="https://avito.ru/user/1",
    )
    conv = await repo.create_conversation(
        seller_id=seller.id,
        platform="avito",
        goal="Узнать цены на ремонт",
    )
    assert conv.status == "new"

    msg1 = await repo.add_message(conv.id, "out", "Здравствуйте! Сколько стоит ремонт?")
    msg2 = await repo.add_message(conv.id, "in", "Добрый день! От 5000 за м2")

    messages = await repo.get_conversation_messages(conv.id)
    assert len(messages) == 2
    assert messages[0].direction == "out"
    assert messages[1].direction == "in"


async def test_conversation_status_update(repo: Repository):
    """Обновление статуса диалога."""
    seller = await repo.create_seller(
        platform="avito",
        external_id="1",
        name="Тест",
        profile_url="https://avito.ru/user/1",
    )
    conv = await repo.create_conversation(seller_id=seller.id, platform="avito")

    await repo.update_conversation_status(conv.id, "active")
    active = await repo.get_active_conversations()
    assert len(active) == 1

    await repo.update_conversation_status(conv.id, "completed")
    active = await repo.get_active_conversations()
    assert len(active) == 0


async def test_has_conversation_with_seller(repo: Repository):
    """Проверка наличия диалога с продавцом."""
    seller = await repo.create_seller(
        platform="avito",
        external_id="1",
        name="Тест",
        profile_url="https://avito.ru/user/1",
    )
    assert not await repo.has_conversation_with_seller(seller.id)

    await repo.create_conversation(seller_id=seller.id, platform="avito")
    assert await repo.has_conversation_with_seller(seller.id)
