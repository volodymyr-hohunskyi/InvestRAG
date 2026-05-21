"""Seed the instruments table with initial data."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from db import get_db, init_db

init_db()

INSTRUMENTS = [
    ("Сонячна електростанція", "EcoTech Invest", "енергетика", 50000, "UAH", 18, 24, 3, 36, "низька",
     "Інвестиція в сонячну електростанцію з фіксованим зеленим тарифом."),
    ("Вітрова енергетика", "Varto", "енергетика", 100000, "UAH", 15, 22, 3, 48, "низька",
     "Частка у вітровій електростанції. Пасивний дохід від генерації."),
    ("Енергетичний проект Codex", "Ribas x Codex Energy", "енергетика", 75000, "UAH", 20, 28, 4, 24, "низька",
     "Інвестиція в енергетичну інфраструктуру."),
    ("Дохідна нерухомість Київ", "Standard One", "нерухомість", 500000, "UAH", 10, 14, 2, 60, "низька",
     "Комерційна нерухомість з орендним доходом."),
    ("Апартаменти Пхукет", "Sabai", "нерухомість", 200000, "UAH", 8, 12, 3, 36, "низька",
     "Курортна нерухомість Таїланду. Дохід від оренди + зростання вартості."),
    ("Дохідна нерухомість MYFREEDOM", "MYFREEDOM", "нерухомість", 300000, "UAH", 12, 16, 2, 48, "низька",
     "Колективна інвестиція з щомісячними виплатами."),
    ("Корпоративні облігації", "Aiffin", "облігації", 25000, "UAH", 16, 20, 2, 12, "середня",
     "Фіксований купонний дохід від українських компаній."),
    ("Equity участь у бізнесі", "Aiffin", "equity", 100000, "UAH", 25, 40, 4, 36, "низька",
     "Пайова участь у зростаючих компаніях. Високий ризик — високий потенціал."),
    ("Deus Robotics частка", "Deus Robotics", "робототехніка", 200000, "UAH", 30, 50, 5, 60, "низька",
     "Венчурна інвестиція в робототехнічний стартап."),
    ("ОВДП (держоблігації)", "НБУ / Банки", "облігації", 1000, "UAH", 15, 18, 1, 12, "висока",
     "Облігації внутрішньої державної позики. Гарантія держави."),
]


def seed():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
    if existing > 0:
        print(f"Instruments table already has {existing} rows. Skipping seed.")
        return

    conn.executemany("""
        INSERT INTO instruments (name, provider, type, min_amount, currency,
            expected_yield_min, expected_yield_max, risk_level, horizon_months,
            liquidity, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, INSTRUMENTS)
    conn.commit()
    conn.close()
    print(f"Seeded {len(INSTRUMENTS)} instruments.")


if __name__ == "__main__":
    seed()
