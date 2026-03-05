"""
📋 Бот-визитка для портфолио
Telegram Bot на aiogram 3.x

Функции:
- Приветствие с кнопками
- Каталог услуг
- Форма заявки (пошаговый диалог)
- Сохранение заявок в базу данных
- Админ-панель
"""

import asyncio
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ============================================================
#   НАСТРОЙКИ
# ============================================================

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ← Замени на свой токен!

# ID администратора (твой Telegram ID)
# Чтобы узнать: напиши боту @userinfobot
ADMIN_ID = 123456789

# ============================================================
#   БАЗА ДАННЫХ
# ============================================================


def init_db():
    """Создаёт таблицы в базе данных."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at TEXT
        )
    """)

    # Таблица заявок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            phone TEXT,
            service TEXT,
            comment TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'new'
        )
    """)

    conn.commit()
    conn.close()


def save_user(user_id, username, first_name, last_name):
    """Сохраняет пользователя в БД."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, first_name, last_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def save_order(user_id, name, phone, service, comment):
    """Сохраняет заявку в БД."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, name, phone, service, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, phone, service, comment, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_stats():
    """Получает статистику."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    users_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    orders_count = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    new_orders = cursor.execute(
        "SELECT COUNT(*) FROM orders WHERE status='new'"
    ).fetchone()[0]
    conn.close()
    return users_count, orders_count, new_orders


def get_orders():
    """Получает последние заявки."""
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    orders = cursor.execute("""
        SELECT name, phone, service, comment, created_at, status
        FROM orders ORDER BY id DESC LIMIT 10
    """).fetchall()
    conn.close()
    return orders


# ============================================================
#   СОСТОЯНИЯ (для пошагового диалога)
# ============================================================


class OrderForm(StatesGroup):
    """Состояния формы заявки."""
    name = State()      # Ввод имени
    phone = State()     # Ввод телефона
    service = State()   # Выбор услуги
    comment = State()   # Комментарий


# ============================================================
#   КЛАВИАТУРЫ
# ============================================================


def main_keyboard():
    """Главная клавиатура (кнопки внизу)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Услуги"),
                KeyboardButton(text="💰 Цены"),
            ],
            [
                KeyboardButton(text="📝 Оставить заявку"),
                KeyboardButton(text="ℹ️ О нас"),
            ],
            [
                KeyboardButton(text="📞 Контакты"),
            ],
        ],
        resize_keyboard=True,
    )


def services_keyboard():
    """Инлайн-клавиатура с услугами."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 Telegram-бот",
                    callback_data="service_bot"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧠 AI-ассистент",
                    callback_data="service_ai"
                ),
            ],
             [
                 InlineKeyboardButton(
                     text="📊 Парсер данных",
                     callback_data="service_parser"
                 ),
             ],
            [
                InlineKeyboardButton(
                    text="📈 Трейдинг-бот",
                    callback_data="service_trading"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📝 Заказать",
                    callback_data="make_order"
                ),
            ],
        ]
    )


def confirm_keyboard():
    """Клавиатура подтверждения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data="confirm_order"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_order"
                ),
            ],
        ]
    )


def service_choice_keyboard():
    """Выбор услуги в форме заявки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 Telegram-бот",
                    callback_data="choose_bot"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🧠 AI-ассистент",
                    callback_data="choose_ai"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Парсер данных",
                    callback_data="choose_parser"
               ),
            ],
            [
                InlineKeyboardButton(
                    text="📈 Трейдинг-бот",
                    callback_data="choose_trading"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔧 Другое",
                    callback_data="choose_other"
                ),
            ],
        ]
    )


# ============================================================
#   РОУТЕР (обработчики)
# ============================================================

router = Router()


# --- КОМАНДА /start ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Приветствие при первом запуске."""

    # Сохраняем пользователя
    save_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )

    welcome_text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n"
        f"\n"
        f"Я — бот компании <b>MF</b> 🚀\n"
        f"\n"
        f"Мы разрабатываем:\n"
        f"├── 🤖 Telegram-ботов\n"
        f"├── 🧠 AI-ассистентов\n"
        f"├── 📊 Парсеры данных\n"
        f"└── 📈 Трейдинг-ботов\n"
        f"\n"
        f"Выберите действие ниже 👇"
    )

    await message.answer(
        welcome_text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# --- КОМАНДА /help ---
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь."""
    help_text = (
        "📖 <b>Доступные команды:</b>\n"
        "\n"
        "/start — Главное меню\n"
        "/help — Помощь\n"
        "/services — Наши услуги\n"
        "/order — Оставить заявку\n"
        "/contacts — Контакты\n"
    )
    await message.answer(help_text, parse_mode="HTML")


# --- КОМАНДА /admin ---
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель."""
    if ADMIN_ID and message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа.")
        return

    users, orders, new_orders = get_stats()

    text = (
        "🔐 <b>Админ-панель</b>\n"
        f"\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"📝 Всего заявок: <b>{orders}</b>\n"
        f"🆕 Новых заявок: <b>{new_orders}</b>\n"
        f"\n"
    )

    # Показываем последние заявки
    recent = get_orders()
    if recent:
        text += "📋 <b>Последние заявки:</b>\n\n"
        for name, phone, service, comment, date, status in recent:
            emoji = "🆕" if status == "new" else "✅"
            text += (
                f"{emoji} <b>{name}</b>\n"
                f"   📱 {phone}\n"
                f"   🔧 {service}\n"
                f"   💬 {comment}\n"
                f"   📅 {date[:16]}\n\n"
            )
    else:
        text += "Заявок пока нет."

    await message.answer(text, parse_mode="HTML")


# --- КНОПКА "Услуги" ---
@router.message(F.text == "📋 Услуги")
@router.message(Command("services"))
async def show_services(message: Message):
    """Показывает услуги."""
    text = (
        "🛠 <b>Наши услуги:</b>\n"
        "\n"
        "Нажмите на услугу для подробностей 👇"
    )
    await message.answer(
        text,
        reply_markup=services_keyboard(),
        parse_mode="HTML",
    )


# --- КНОПКА "Цены" ---
@router.message(F.text == "💰 Цены")
async def show_prices(message: Message):
    """Показывает прайс."""
    text = (
        "💰 <b>Наши цены:</b>\n"
        "\n"
        "🤖 <b>Telegram-бот</b>\n"
        "├── Простой (кнопки, FAQ): от 5 000 ₽\n"
        "├── Средний (БД, формы): от 10 000 ₽\n"
        "└── Сложный (API, оплата): от 20 000 ₽\n"
        "\n"
        "🧠 <b>AI-ассистент</b>\n"
        "├── Базовый: от 10 000 ₽\n"
        "└── С обучением: от 25 000 ₽\n"
        "\n"
        "📊 <b>Парсер данных</b>\n"
        "├── Простой сайт: от 3 000 ₽\n"
        "└── Сложный (с защитой): от 10 000 ₽\n"
        "\n"
        "📈 <b>Трейдинг-бот</b>\n"
        "├── Сигналы в TG: от 15 000 ₽\n"
        "└── Полная система: от 30 000 ₽\n"
        "\n"
        "💡 Точная стоимость — после обсуждения ТЗ"
    )
    await message.answer(text, parse_mode="HTML")


# --- КНОПКА "О нас" ---
@router.message(F.text == "ℹ️ О нас")
async def show_about(message: Message):
    """О компании."""
    text = (
        "🏢 <b> MF </b>\n"
        "\n"
        "Мы команда разработчиков, создающих\n"
        "автоматизацию для бизнеса.\n"
        "\n"
        "✅ 50+ выполненных проектов\n"
        "✅ Опыт в трейдинге и финтехе\n"
        "✅ Работаем с AI технологиями\n"
        "✅ Поддержка после сдачи проекта\n"
        "\n"
        "🔧 <b>Технологии:</b>\n"
        "Python • aiogram • FastAPI • PostgreSQL\n"
        "OpenAI • DeepSeek • MetaTrader 5\n"
    )
    await message.answer(text, parse_mode="HTML")


# --- КНОПКА "Контакты" ---
@router.message(F.text == "📞 Контакты")
@router.message(Command("contacts"))
async def show_contacts(message: Message):
    """Контакты."""
    text = (
        "📞 <b>Контакты:</b>\n"
        "\n"
        "👤 Менеджер: https://t.me/your_username\n"
        "📧 Email: your@email.com \n"
        "🌐 Сайт: https://your_website\n"
        "\n"
        "⏰ Работаем: Пн-Пт, 10:00 — 20:00\n"
        "📍 Ответим в течение 1 часа"
    )
    await message.answer(text, parse_mode="HTML")


# ============================================================
#   ДЕТАЛИ УСЛУГ (инлайн-кнопки)
# ============================================================

@router.callback_query(F.data == "service_bot")
async def detail_bot(callback: CallbackQuery):
    """Подробности: Telegram-бот."""
    text = (
        "🤖 <b>Telegram-бот</b>\n"
        "\n"
        "Разрабатываем ботов любой сложности:\n"
        "\n"
        "📌 <b>Что входит:</b>\n"
        "├── Приветствие и меню\n"
        "├── Каталог товаров/услуг\n"
        "├── Форма заявки\n"
        "├── Уведомления админу\n"
        "├── База данных\n"
        "├── Админ-панель\n"
        "└── Интеграция с оплатой\n"
        "\n"
        "⏱ Сроки: 3-7 дней\n"
        "💰 Цена: от 5 000 ₽\n"
        "\n"
        "📝 Нажми <b>Заказать</b> для оформления заявки!"
    )
    await callback.message.edit_text(
        text,
        reply_markup=services_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "service_ai")
async def detail_ai(callback: CallbackQuery):
    """Подробности: AI-ассистент."""
    text = (
        "🧠 <b>AI-ассистент</b>\n"
        "\n"
        "Бот на базе искусственного интеллекта:\n"
        "\n"
        "📌 <b>Возможности:</b>\n"
        "├── Ответы на вопросы клиентов\n"
        "├── Помощь с выбором товара\n"
        "├── Генерация текстов\n"
        "├── Обучение на ваших данных\n"
        "└── Память контекста диалога\n"
        "\n"
        "⏱ Сроки: 5-10 дней\n"
        "💰 Цена: от 10 000 ₽"
    )
    await callback.message.edit_text(
        text,
        reply_markup=services_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "service_parser")
async def detail_parser(callback: CallbackQuery):
    """Подробности: Парсер."""
    text = (
        "📊 <b>Парсер данных</b>\n"
        "\n"
        "Автоматический сбор данных с сайтов:\n"
        "\n"
        "📌 <b>Что делаем:</b>\n"
        "├── Сбор каталогов товаров\n"
        "├── Мониторинг цен конкурентов\n"
        "├── Выгрузка в Excel/CSV\n"
        "├── Регулярный автопарсинг\n"
        "└── Обход защит\n"
        "\n"
        "⏱ Сроки: 2-5 дней\n"
        "💰 Цена: от 3 000 ₽"
    )
    await callback.message.edit_text(
        text,
        reply_markup=services_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "service_trading")
async def detail_trading(callback: CallbackQuery):
    """Подробности: Трейдинг-бот."""
    text = (
        "📈 <b>Трейдинг-бот</b>\n"
        "\n"
        "Автоматизация трейдинга:\n"
        "\n"
        "📌 <b>Что делаем:</b>\n"
        "├── Сигналы из MT5 → Telegram\n"
        "├── Мониторинг позиций\n"
        "├── Статистика сделок\n"
        "├── Торговые советники (EA)\n"
        "├── Копирование сделок\n"
        "└── Дашборд с аналитикой\n"
        "\n"
        "⏱ Сроки: 7-14 дней\n"
        "💰 Цена: от 15 000 ₽"
    )
    await callback.message.edit_text(
        text,
        reply_markup=services_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
#   ФОРМА ЗАЯВКИ (пошаговый диалог)
# ============================================================

@router.message(F.text == "📝 Оставить заявку")
@router.message(Command("order"))
@router.callback_query(F.data == "make_order")
async def start_order(event, state: FSMContext):
    """Начало формы заявки."""
    text = "📝 <b>Оформление заявки</b>\n\nВведите ваше <b>имя</b>:"

    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML")

    await state.set_state(OrderForm.name)


@router.message(OrderForm.name)
async def process_name(message: Message, state: FSMContext):
    """Получаем имя."""
    await state.update_data(name=message.text)
    await message.answer(
        "📱 Введите ваш <b>телефон</b> или Telegram:",
        parse_mode="HTML",
    )
    await state.set_state(OrderForm.phone)


@router.message(OrderForm.phone)
async def process_phone(message: Message, state: FSMContext):
    """Получаем телефон."""
    await state.update_data(phone=message.text)
    await message.answer(
        "🔧 Выберите <b>услугу</b>:",
        reply_markup=service_choice_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(OrderForm.service)


@router.callback_query(OrderForm.service, F.data.startswith("choose_"))
async def process_service(callback: CallbackQuery, state: FSMContext):
    """Получаем выбранную услугу."""
    services_map = {
        "choose_bot": "🤖 Telegram-бот",
        "choose_ai": "🧠 AI-ассистент",
        "choose_parser": "📊 Парсер данных",
        "choose_trading": "📈 Трейдинг-бот",
        "choose_other": "🔧 Другое",
    }
    service = services_map.get(callback.data, "Не указано")
    await state.update_data(service=service)

    await callback.message.answer(
        "💬 Опишите кратко что нужно сделать\n"
        "(или напишите «—» чтобы пропустить):",
    )
    await callback.answer()
    await state.set_state(OrderForm.comment)


@router.message(OrderForm.comment)
async def process_comment(message: Message, state: FSMContext):
    """Получаем комментарий и показываем сводку."""
    await state.update_data(comment=message.text)

    data = await state.get_data()

    summary = (
        "📋 <b>Ваша заявка:</b>\n"
        f"\n"
        f"👤 Имя: <b>{data['name']}</b>\n"
        f"📱 Телефон: <b>{data['phone']}</b>\n"
        f"🔧 Услуга: <b>{data['service']}</b>\n"
        f"💬 Комментарий: {data['comment']}\n"
        f"\n"
        f"Всё верно? Отправляем?"
    )

    await message.answer(
        summary,
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    """Подтверждение заявки."""
    data = await state.get_data()

    # Сохраняем в БД
    save_order(
        callback.from_user.id,
        data["name"],
        data["phone"],
        data["service"],
        data["comment"],
    )

    await callback.message.edit_text(
        "✅ <b>Заявка отправлена!</b>\n"
        "\n"
        "Мы свяжемся с вами в ближайшее время.\n"
        "Спасибо! 🙏",
        parse_mode="HTML",
    )

    # Уведомляем админа
    if ADMIN_ID:
        admin_text = (
            "🆕 <b>Новая заявка!</b>\n"
            f"\n"
            f"👤 {data['name']}\n"
            f"📱 {data['phone']}\n"
            f"🔧 {data['service']}\n"
            f"💬 {data['comment']}\n"
            f"🆔 @{callback.from_user.username or 'нет username'}"
        )
        try:
            await callback.bot.send_message(
                ADMIN_ID, admin_text, parse_mode="HTML"
            )
        except Exception:
            pass

    await callback.answer("✅ Отправлено!")
    await state.clear()


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    """Отмена заявки."""
    await state.clear()
    await callback.message.edit_text("❌ Заявка отменена.")
    await callback.answer()


# ============================================================
#   ЗАПУСК БОТА
# ============================================================

async def main():
    """Запуск бота."""
    # Настройка логов
    logging.basicConfig(level=logging.INFO)

    # Инициализация БД
    init_db()

    # Создаём бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутер
    dp.include_router(router)

    # Запускаем
    print("=" * 50)
    print("  🤖 Бот запущен!")
    print("  Нажми Ctrl+C чтобы остановить")
    print("=" * 50)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())