import json
import os
from datetime import datetime, timedelta
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler

# === НАСТРОЙКИ ===
BOT_TOKEN = "8081585127:AAEZ0QyleeUQY4GI8_rPsAMEmYHt6SmZYp4С"
DATA_FILE = "data.json"
DEFAULT_BUDGET = 500

# === ХРАНЕНИЕ ДАННЫХ ===
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        return {"expenses": {}, "budget": DEFAULT_BUDGET}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# === УТИЛИТЫ ===
def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_week_dates():
    today = datetime.now()
    start = today - timedelta(days=today.weekday())
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

# === КОМАНДЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь сумму, чтобы записать трату.\n"
                                    "Команды:\n/setbudget 500 — установить дневной лимит\n"
                                    "/today — сколько потратил сегодня\n"
                                    "/week — таблица расходов\n/reset — сброс данных")

async def set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    try:
        new_budget = int(context.args[0])
        data["budget"] = new_budget
        save_data(data)
        await update.message.reply_text(f"Новый дневной лимит: {new_budget}₽")
    except:
        await update.message.reply_text("Используй так: /setbudget 500")

async def today_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = get_today()
    total = sum(data["expenses"].get(today, []))
    await update.message.reply_text(f"Сегодня потрачено: {total}₽")

async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_data({"expenses": {}, "budget": DEFAULT_BUDGET})
    await update.message.reply_text("Все данные сброшены.")

async def week_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    week = get_week_dates()
    rows = []
    for day in week:
        rows.append([day, sum(data["expenses"].get(day, []))])
    df = pd.DataFrame(rows, columns=["Дата", "Сумма (₽)"])
    msg = df.to_string(index=False)
    await update.message.reply_text(f"Расходы за неделю:\n{msg}")

# === ЗАПИСЬ ТРАТЫ ===
async def record_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = get_today()
    try:
        amount = int(update.message.text)
        data["expenses"].setdefault(today, []).append(amount)
        save_data(data)
        total = sum(data["expenses"][today])
        await update.message.reply_text(f"Записал {amount}₽. Сегодня всего: {total}₽")
    except ValueError:
        await update.message.reply_text("Отправь просто число — сумму в рублях.")

# === НАПОМИНАНИЯ ===
async def daily_reminder(app):
    chat_ids = app.chat_ids if hasattr(app, "chat_ids") else []
    for chat_id in chat_ids:
        try:
            await app.bot.send_message(chat_id=chat_id, text="Не забудь записать расходы за сегодня!")
        except:
            pass

async def weekly_summary(app):
    data = load_data()
    week = get_week_dates()
    rows = []
    for day in week:
        rows.append([day, sum(data["expenses"].get(day, []))])
    df = pd.DataFrame(rows, columns=["Дата", "Сумма (₽)"])
    msg = df.to_string(index=False)
    chat_ids = app.chat_ids if hasattr(app, "chat_ids") else []
    for chat_id in chat_ids:
        try:
            await app.bot.send_message(chat_id=chat_id, text=f"📊 Расходы за неделю:\n{msg}")
        except:
            pass

# === ОСНОВНОЙ ЗАПУСК ===
async def save_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not hasattr(context.application, "chat_ids"):
        context.application.chat_ids = []
    if update.effective_chat.id not in context.application.chat_ids:
        context.application.chat_ids.append(update.effective_chat.id)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setbudget", set_budget))
    app.add_handler(CommandHandler("today", today_expense))
    app.add_handler(CommandHandler("reset", reset_data))
    app.add_handler(CommandHandler("week", week_report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, record_expense))
    app.add_handler(MessageHandler(filters.ALL, save_chat_id))

    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    scheduler.add_job(lambda: app.create_task(daily_reminder(app)), "cron", hour=22, minute=0)
    scheduler.add_job(lambda: app.create_task(weekly_summary(app)), "cron", day_of_week="sun", hour=11, minute=0)
    scheduler.start()

    print("Бот запущен")
    app.run_polling()
