"""AI-генерация сообщений через Claude API."""

from typing import Optional

import anthropic
import structlog

from agent_scout.database.models import Message

logger = structlog.get_logger()

SYSTEM_PROMPT = """Ты — обычный человек, которому нужна механизированная штукатурка стен.
Ты пишешь потенциальному исполнителю на Авито или другой площадке.

Правила:
- Пиши КОРОТКО, 1-3 предложения максимум
- Используй разговорный стиль, как в мессенджере
- Иногда допускай мелкие ошибки или опечатки (не всегда)
- Не используй формальный стиль, канцеляризмы
- Задавай конкретные вопросы: цена за м2, сроки, какая смесь, толщина слоя, гарантии
- НЕ упоминай что ты бот, ИИ, программа или автоматическая система
- Веди себя как реальный заказчик, которому нужна штукатурка
- Если собеседник спрашивает что-то — отвечай естественно

Примеры стиля:
- "Здравствуйте, подскажите сколько у вас м2 механизированной штукатурки стоит?"
- "а вы какой смесью работаете? кнауф или волма?"
- "а по срокам — двушка 60м2 стены, сколько дней примерно?"
- "Добрый день! Нужна мех штукатурка стен, квартира 80м2. Какие цены?"
"""


class ChatAI:
    """Генерация человекоподобных сообщений через Claude API."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: Optional[str] = None):
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_first_message(self, goal: str) -> str:
        """Сгенерировать первое сообщение продавцу.

        Args:
            goal: Цель переписки (например, "узнать цены на мех. штукатурку стен 80м2")
        """
        user_prompt = (
            f"Напиши ПЕРВОЕ сообщение исполнителю механизированной штукатурки. "
            f"Цель: {goal}. "
            f"Одно-два предложения, максимально естественно."
        )
        return await self._generate(user_prompt, context=[])

    async def generate_reply(
        self, context: list[Message], goal: str
    ) -> str:
        """Сгенерировать ответ на основе истории диалога.

        Args:
            context: История сообщений в диалоге
            goal: Цель переписки
        """
        # Формируем историю диалога для контекста
        history = ""
        for msg in context:
            role = "Я" if msg.direction == "out" else "Продавец"
            history += f"{role}: {msg.text}\n"

        user_prompt = (
            f"История переписки:\n{history}\n"
            f"Цель: {goal}\n"
            f"Напиши следующий ответ от моего лица. "
            f"Одно-два предложения, естественно, по делу."
        )
        return await self._generate(user_prompt, context)

    async def should_continue_conversation(
        self, context: list[Message], goal: str
    ) -> bool:
        """Определить, нужно ли продолжать диалог.

        Возвращает False если цель достигнута или диалог зашёл в тупик.
        """
        if not context:
            return True

        history = ""
        for msg in context:
            role = "Я" if msg.direction == "out" else "Продавец"
            history += f"{role}: {msg.text}\n"

        user_prompt = (
            f"История переписки:\n{history}\n"
            f"Цель переписки: {goal}\n"
            f"Ответь ОДНИМ словом: нужно ли продолжать переписку? "
            f"ДА — если цель ещё не достигнута и есть о чём спросить. "
            f"НЕТ — если основная информация получена или продавец не отвечает по делу."
        )
        response = await self._generate(user_prompt, context)
        return "да" in response.lower()

    async def _generate(self, user_prompt: str, context: list) -> str:
        """Вызов Claude API."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text.strip()
            logger.debug("ai_generated", text=text[:100])
            return text

        except Exception as e:
            logger.error("ai_generation_error", error=str(e))
            raise
