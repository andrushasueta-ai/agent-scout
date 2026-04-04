# Agent Scout — PRD

## Продукт
Инструмент конкурентной разведки для строительных услуг.
Автоматический мониторинг конкурентов на Авито и других площадках.

## Пользователь
Владелец строительного бизнеса или маркетолог.

## Модель использования
- Один реальный аккаунт пользователя на площадке (не бот-аккаунт)
- Задача: за 3-5 дней собрать предложения в нише, для анализа
- Агент ведёт себя как обычный человек, который ищет исполнителя по штукатурке
- Не 24/7, а сессиями: поработал — отдохнул — вернулся

## Фичи (в порядке реализации)
1. Скрапинг объявлений с Авито, Profi.ru, Яндекс Услуги по запросу и категории
2. Парсинг объявлений по заданной задаче: описание, цены
3. Хранение данных в SQLite с возможностью экспорта
4. Anti-detection: человеческое поведение, реалистичные паузы между сессиями
5. AI-переписка с продавцами через Claude API (8-15 новых диалогов/день)
6. CLI для управления всеми операциями
7. Автоматический цикл с расписанием "живого человека"

## Критерий готовности фичи
Фича считается готовой, когда:
- Код написан и не ломает существующие модули
- Есть хотя бы один тест
- Можно запустить и проверить руками

## Структура проекта
```
agent-scout/
├── pyproject.toml
├── config.yaml
├── CLAUDE.md
├── PRD.md
├── src/
│   └── agent_scout/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── orchestrator.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── repository.py
│       ├── browser/
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   ├── humanizer.py
│       │   └── proxy.py
│       ├── platforms/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── avito.py
│       │   ├── youla.py
│       │   ├── cian.py
│       │   └── profi.py
│       └── messenger/
│           ├── __init__.py
│           ├── chat_ai.py
│           └── conversation.py
├── tests/
│   ├── __init__.py
│   ├── test_database.py
│   └── test_humanizer.py
└── data/
    └── sessions/
```

## Схема базы данных
- **sellers** — id, platform, external_id, name, rating, reviews_count, registration_date, listings_count, profile_url, created_at, updated_at
- **listings** — id, seller_id (FK), platform, title, description, price, category, location, photos_json, url, created_at
- **conversations** — id, seller_id (FK), platform, status (new/active/completed), goal, created_at
- **messages** — id, conversation_id (FK), direction (in/out), text, sent_at
