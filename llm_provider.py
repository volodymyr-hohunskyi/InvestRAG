from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv

load_dotenv()


SYSTEM_PROMPT = """Ти — інвестиційний інформаційний помічник для початківців в Україні.

ПРАВИЛА:
1. Відповідай ТІЛЬКИ українською мовою.
2. Базуй відповіді ВИКЛЮЧНО на наданому контексті. Не вигадуй інформацію.
3. Якщо контексту недостатньо для відповіді — чесно скажи про це.
4. Це НЕ є інвестиційною порадою. Завжди нагадуй, що фінальне рішення за користувачем.
5. Будь простим і зрозумілим — пояснюй терміни, якщо вони складні.
6. Якщо питання стосується конкретного інструменту — вказуй і ризики, і переваги.

ФОРМАТ ВІДПОВІДІ:
- Коротко (2-4 абзаци максимум)
- Якщо є конкретні цифри в контексті (дохідність, мінімальна сума) — наводь їх
- Завершуй коротким дисклеймером

ДИСКЛЕЙМЕР (додавай в кінці кожної відповіді):
"⚠️ Це інформаційна підтримка, а не інвестиційна порада. Перед прийняттям рішень проконсультуйтесь з ліцензованим фінансовим радником."
"""

RISK_PROFILE_PROMPT = """Ти допомагаєш користувачу визначити його інвестиційний профіль.

Задай наступні питання (по одному):
1. Яку суму ви готові інвестувати? (в гривнях або доларах)
2. На який термін? (6 місяців / 1 рік / 3 роки / 5+ років)
3. Яка ваша мета? (пасивний дохід / збереження від інфляції / зростання капіталу)
4. Як ви ставитесь до ризику? (не готовий втрачати / готовий до -10% / готовий до -30% заради більшого прибутку)
5. Чи є у вас досвід інвестування? (ні / трохи / так, кілька років)

На основі відповідей визнач:
- risk_tolerance: 1-5 (1=консервативний, 5=агресивний)
- investment_horizon_months: число
- goals: масив цілей

Поверни результат у JSON форматі.
"""

SUGGESTION_PROMPT = """На основі профілю користувача та доступних інструментів,
запропонуй 2-3 варіанти інвестування.

ПРОФІЛЬ КОРИСТУВАЧА:
{profile}

ДОСТУПНІ ІНСТРУМЕНТИ:
{instruments}

КОНТЕКСТ З ОБГОВОРЕНЬ (відгуки інвесторів):
{context}

ПРАВИЛА:
1. Пропонуй ТІЛЬКИ інструменти зі списку доступних
2. Враховуй risk_tolerance користувача
3. Враховуй мінімальну суму інвестиції vs доступну суму користувача
4. Враховуй горизонт інвестування
5. Для кожної пропозиції вкажи: назву, очікувану дохідність, ризики, мін. суму
6. Додай контекст з обговорень якщо є релевантна інформація

ФОРМАТ:
📌 **[Назва]** від [Провайдер]
- Тип: ...
- Очікувана дохідність: X-Y% річних
- Мінімальна сума: ...
- Ризик: .../5
- Горизонт: ...
- Що кажуть інвестори: [коротко з контексту, якщо є]

Завершуй дисклеймером.
"""


class LLMProvider(ABC):
    @abstractmethod
    def synthesize(self, system_prompt: str, user_message: str) -> str:
        ...


class GeminiProvider(LLMProvider):
    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def synthesize(self, system_prompt: str, user_message: str) -> str:
        response = self.model.generate_content(
            f"{system_prompt}\n\n{user_message}"
        )
        return response.text


class HaikuProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()

    def synthesize(self, system_prompt: str, user_message: str) -> str:
        response = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return next(b.text for b in response.content if b.type == "text")


def get_provider() -> LLMProvider:
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    if provider == "haiku":
        return HaikuProvider()
    return GeminiProvider()
