import os
import sys
import json
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters
)
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from db import match_chunks, get_instruments, get_profile, save_profile
from llm_provider import get_provider, SYSTEM_PROMPT, SUGGESTION_PROMPT
from embeddings import get_embedding

load_dotenv()

AMOUNT, HORIZON, GOAL, RISK, EXPERIENCE = range(5)


async def start(update: Update, context):
    await update.message.reply_text(
        "Привіт! 👋 Я допоможу тобі розібратись в інвестиціях в Україні.\n\n"
        "Команди:\n"
        "/ask [питання] — задати питання про інвестиції\n"
        "/profile — визначити твій інвестиційний профіль\n"
        "/suggest — отримати персональні рекомендації\n"
        "/instruments — переглянути доступні інструменти\n\n"
        "Або просто напиши своє питання!"
    )


async def ask(update: Update, context):
    text = update.message.text
    if text.startswith("/ask"):
        question = text[4:].strip()
    else:
        question = text

    if not question:
        await update.message.reply_text("Напиши своє питання після /ask")
        return

    await update.message.reply_text("🔍 Шукаю інформацію...")

    try:
        query_embedding = get_embedding(question)
        chunks = match_chunks(query_embedding, match_count=5, match_threshold=0.7)

        ctx = "\n\n---\n\n".join(r["content"] for r in chunks)
        if ctx:
            user_message = f"Контекст:\n{ctx}\n\nПитання: {question}"
        else:
            user_message = f"Контексту не знайдено. Питання: {question}"

        provider = get_provider()
        answer = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_message=user_message)

        sources = ", ".join(set(r["source_name"] for r in chunks))
        reply = answer
        if sources:
            reply += f"\n\n📚 Джерела: {sources}"
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(
            f"Вибач, сталася помилка при обробці запиту. Спробуй пізніше."
        )


async def instruments_cmd(update: Update, context):
    instruments = get_instruments(active_only=True)

    if not instruments:
        await update.message.reply_text("Поки що немає доступних інструментів.")
        return

    lines = ["📊 Доступні інструменти:\n"]
    for inst in instruments:
        yield_str = ""
        if inst.get("expected_yield_min") and inst.get("expected_yield_max"):
            yield_str = f" | {inst['expected_yield_min']}-{inst['expected_yield_max']}% річних"
        lines.append(
            f"• {inst['name']} ({inst['provider']}) — {inst['type']}{yield_str}"
        )
    await update.message.reply_text("\n".join(lines))


async def suggest_cmd(update: Update, context):
    user_id = str(update.effective_user.id)
    profile = get_profile(user_id)

    if not profile:
        await update.message.reply_text("Спочатку пройдіть оцінку профілю: /profile")
        return

    await update.message.reply_text("📊 Аналізую ваш профіль...")

    try:
        instruments = get_instruments(
            active_only=True,
            max_risk=profile["risk_tolerance"],
            max_amount=profile["available_amount"]
        )

        goals = json.loads(profile["goals"]) if isinstance(profile["goals"], str) else profile.get("goals", [])
        query = f"інвестиції {' '.join(goals)}"
        query_embedding = get_embedding(query)
        chunks = match_chunks(query_embedding, match_count=3, match_threshold=0.6)
        ctx = "\n\n".join(r["content"] for r in chunks)

        provider = get_provider()
        prompt = SUGGESTION_PROMPT.format(
            profile=json.dumps(profile, ensure_ascii=False, default=str),
            instruments=json.dumps(instruments, ensure_ascii=False, default=str),
            context=ctx or "Немає додаткового контексту."
        )

        answer = provider.synthesize(
            system_prompt="Ти — інвестиційний інформаційний помічник.",
            user_message=prompt
        )
        await update.message.reply_text(answer)
    except Exception:
        await update.message.reply_text("Помилка при генерації рекомендацій.")


# --- Risk Profile Conversation ---

async def profile_start(update: Update, context):
    context.user_data["profile"] = {}
    await update.message.reply_text(
        "🎯 Визначимо ваш інвестиційний профіль!\n\n"
        "Крок 1/5: Яку суму ви готові інвестувати?\n\n"
        "Напишіть число (наприклад: 50000 грн або $1000)",
        reply_markup=ReplyKeyboardRemove()
    )
    return AMOUNT


async def profile_amount(update: Update, context):
    text = update.message.text.strip()
    numbers = re.findall(r"[\d\s]+", text)
    if not numbers:
        await update.message.reply_text("Будь ласка, вкажіть суму цифрами.")
        return AMOUNT

    amount = int(re.sub(r"\s", "", numbers[0]))
    currency = "USD" if "$" in text or "дол" in text.lower() else "UAH"
    context.user_data["profile"]["available_amount"] = amount
    context.user_data["profile"]["currency"] = currency

    keyboard = [["6 місяців", "1 рік"], ["3 роки", "5+ років"]]
    await update.message.reply_text(
        f"✅ {amount} {currency}\n\n"
        "Крок 2/5: На який термін ви плануєте інвестувати?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return HORIZON


async def profile_horizon(update: Update, context):
    text = update.message.text.strip().lower()
    horizon_map = {
        "6 місяців": 6, "6": 6,
        "1 рік": 12, "рік": 12, "1": 12,
        "3 роки": 36, "3": 36,
        "5+ років": 60, "5": 60,
    }
    horizon = None
    for key, val in horizon_map.items():
        if key in text:
            horizon = val
            break
    if not horizon:
        horizon = 12

    context.user_data["profile"]["investment_horizon_months"] = horizon

    keyboard = [["Пасивний дохід", "Збереження від інфляції"], ["Зростання капіталу"]]
    await update.message.reply_text(
        "Крок 3/5: Яка ваша головна мета?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return GOAL


async def profile_goal(update: Update, context):
    text = update.message.text.strip().lower()
    goals = []
    if "пасивн" in text or "дохід" in text:
        goals.append("пасивний дохід")
    if "інфляц" in text or "збереж" in text:
        goals.append("збереження від інфляції")
    if "зрост" in text or "капітал" in text:
        goals.append("зростання капіталу")
    if not goals:
        goals.append(text)

    context.user_data["profile"]["goals"] = goals

    keyboard = [
        ["Не готовий втрачати"],
        ["Готовий до -10%"],
        ["Готовий до -30% заради більшого прибутку"]
    ]
    await update.message.reply_text(
        "Крок 4/5: Як ви ставитесь до ризику?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return RISK


async def profile_risk(update: Update, context):
    text = update.message.text.strip().lower()
    if "не готов" in text or "втрач" in text:
        risk = 1
    elif "-10" in text or "помірн" in text:
        risk = 3
    elif "-30" in text or "більш" in text:
        risk = 5
    else:
        risk = 3

    context.user_data["profile"]["risk_tolerance"] = risk

    keyboard = [["Ні, початківець"], ["Трохи є"], ["Так, кілька років"]]
    await update.message.reply_text(
        "Крок 5/5: Чи є у вас досвід інвестування?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )
    return EXPERIENCE


async def profile_experience(update: Update, context):
    text = update.message.text.strip().lower()
    if "ні" in text or "початків" in text:
        exp = "початківець"
    elif "трохи" in text:
        exp = "середній"
    else:
        exp = "досвідчений"

    context.user_data["profile"]["experience_level"] = exp
    profile_data = context.user_data["profile"]

    save_profile(str(update.effective_user.id), profile_data)

    risk_labels = {1: "Консервативний", 2: "Помірно-консервативний",
                   3: "Помірний", 4: "Помірно-агресивний", 5: "Агресивний"}

    summary = (
        f"✅ Ваш профіль збережено!\n\n"
        f"💰 Сума: {profile_data['available_amount']} {profile_data['currency']}\n"
        f"📅 Горизонт: {profile_data['investment_horizon_months']} місяців\n"
        f"🎯 Цілі: {', '.join(profile_data['goals'])}\n"
        f"⚖️ Ризик-профіль: {risk_labels.get(profile_data['risk_tolerance'], '?')}\n"
        f"📚 Досвід: {profile_data['experience_level']}\n\n"
        f"Тепер ви можете отримати персональні рекомендації: /suggest"
    )

    await update.message.reply_text(summary, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def profile_cancel(update: Update, context):
    await update.message.reply_text(
        "Оцінку профілю скасовано.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    profile_handler = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_amount)],
            HORIZON: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_horizon)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_goal)],
            RISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_risk)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_experience)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("instruments", instruments_cmd))
    app.add_handler(CommandHandler("suggest", suggest_cmd))
    app.add_handler(profile_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
