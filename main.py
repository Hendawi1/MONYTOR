import asyncio
import json
import logging
import uuid
import secrets
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Any, Optional

import aiosqlite
import httpx
import speech_recognition as sr
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image
from pydub import AudioSegment
from pyzbar.pyzbar import decode as qr_decode

# ---------- إعداد التسجيل ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------- المفاتيح الثابتة ----------
TELEGRAM_BOT_TOKEN = '8942399461:AAEVTC6_2bAXoe65Ukk5iWv1WFMYZ2YPpnA'
PROVERKACHEKA_TOKEN = '39298.gVTPH0QSvesACHosG'

# ---------- إعداد Gemini ----------
GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_API_KEYS = ['AIzaSyCCdmPCgsgOEDb0JAZk0dwFRrb2-jQXrX4',
 'AIzaSyC31Wt8GT0uEguGRQCzs1WgauHceqV1ZqE',
 'AIzaSyAl7XO-NmfC-XNveKA9UlFwEX8liqa2tmw',
 'AIzaSyAhPj6lIjijt_wTP2Aq6zQU7JPAHy5gujg']

# ---------- قاعدة بيانات SQLite ----------
DB_PATH = "finance_bot.db"

# ---------- التصنيفات ----------
VALID_CATEGORIES = [
    "خبز", "مياه", "سجائر", "مواصلات", "قهوة", "مطاعم وكافيهات",
    "خضار", "فواكه", "فراخ", "تونة", "لحوم", "أسماك", "ألبان",
    "بيض", "زيت وسمن", "معلبات", "حلويات", "مشروبات غازية",
    "أدوات تنظيف", "مستلزمات منزلية", "صحة وجمال", "ملابس",
    "اتصالات", "فواتير", "إيجار", "تعليم", "ترفيه", "هدايا",
    "سداد دين", "راتب", "استلاف", "بيع أغراض", "دخل إضافي", "أخرى",
    "مخبوزات", "مشروبات طاقة", "صوصات", "ملح/توابل/سكر",
    "اكسسوارات هاتف/كمبيوتر", "ادوات مطبخ", "اكسسوارات شخصية", "ادوات مدرسية"
]

# ---------- ترجمات التصنيفات ----------
CATEGORY_TRANSLATIONS = {
    "ru": {
        "خبز": "Хлеб", "مياه": "Вода", "سجائر": "Сигареты", "مواصلات": "Транспорт",
        "قهوة": "Кофе", "مطاعم وكافيهات": "Рестораны и кафе",
        "خضار": "Овощи", "فواكه": "Фрукты", "فراخ": "Курица", "تونة": "Тунец",
        "لحوم": "Мясо", "أسماك": "Рыба", "ألبان": "Молочные продукты",
        "بيض": "Яйца", "زيت وسمن": "Масло и жир", "معلبات": "Консервы",
        "حلويات": "Сладости", "مشروبات غازية": "Газированные напитки",
        "أدوات تنظيف": "Чистящие средства", "مستلزمات منزلية": "Товары для дома",
        "صحة وجمال": "Здоровье и красота", "ملابس": "Одежда",
        "اتصالات": "Связь", "فواتير": "Счета", "إيجار": "Аренда",
        "تعليم": "Образование", "ترفيه": "Развлечения", "هدايا": "Подарки",
        "سداد دين": "Погашение долга", "راتب": "Зарплата",
        "استلاف": "Заем", "بيع أغراض": "Продажа вещей", "دخل إضافي": "Дополнительный доход",
        "أخرى": "Другое", "مخبوزات": "Выпечка", "مشروبات طاقة": "Энергетики",
        "صوصات": "Соусы", "ملح/توابل/سكر": "Соль/Специи/Сахар",
        "اكسسوارات هاتف/كمبيوتر": "Аксессуары для телефона/ПК",
        "ادوات مطبخ": "Кухонные принадлежности",
        "اكسسوارات شخصية": "Личные аксессуары",
        "ادوات مدرسية": "Школьные принадлежности"
    },
    "en": {
        "خبز": "Bread", "مياه": "Water", "سجائر": "Cigarettes", "مواصلات": "Transport",
        "قهوة": "Coffee", "مطاعم وكافيهات": "Restaurants & Cafes",
        "خضار": "Vegetables", "فواكه": "Fruits", "فراخ": "Chicken", "تونة": "Tuna",
        "لحوم": "Meat", "أسماك": "Fish", "ألبان": "Dairy",
        "بيض": "Eggs", "زيت وسمن": "Oil & Ghee", "معلبات": "Canned Food",
        "حلويات": "Sweets", "مشروبات غازية": "Soft Drinks",
        "أدوات تنظيف": "Cleaning Supplies", "مستلزمات منزلية": "Household Items",
        "صحة وجمال": "Health & Beauty", "ملابس": "Clothing",
        "اتصالات": "Telecom", "فواتير": "Bills", "إيجار": "Rent",
        "تعليم": "Education", "ترفيه": "Entertainment", "هدايا": "Gifts",
        "سداد دين": "Debt Payment", "راتب": "Salary",
        "استلاف": "Borrowing", "بيع أغراض": "Selling Items", "دخل إضافي": "Extra Income",
        "أخرى": "Other", "مخبوزات": "Bakery", "مشروبات طاقة": "Energy Drinks",
        "صوصات": "Sauces", "ملح/توابل/سكر": "Salt/Spices/Sugar",
        "اكسسوارات هاتف/كمبيوتر": "Phone/PC Accessories",
        "ادوات مطبخ": "Kitchen Utensils",
        "اكسسوارات شخصية": "Personal Accessories",
        "ادوات مدرسية": "School Supplies"
    }
}

def translate_category(category: str, lang: str) -> str:
    if lang == "ar":
        return category
    return CATEGORY_TRANSLATIONS.get(lang, {}).get(category, category)

def translate_type(t: str, lang: str) -> str:
    if lang == "ar":
        return t
    if t == "دخل":
        return {"ru": "Доход", "en": "Income"}.get(lang, "Income")
    elif t == "مصروف":
        return {"ru": "Расход", "en": "Expense"}.get(lang, "Expense")
    return t

def get_language_name(lang: str) -> str:
    return {
        "ar": "العربية",
        "ru": "الروسية",
        "en": "الإنجليزية",
    }.get(lang, "الإنجليزية")

# ---------- القواميس المساعدة ----------
user_onboarding: Dict[int, str] = {}
user_temp_data: Dict[int, dict] = {}
user_cache: Dict[int, dict] = {}

# ---------- النصوص متعددة اللغات ----------
MESSAGES = {
    "ar": {
        "welcome": "مرحباً! لنبدأ بإعداد حسابك.\nاختر اللغة أولاً:",
        "choose_language": "اختر اللغة:",
        "enter_currency": "ما هي عملتك الأساسية؟ اكتبها (مثال: جنيه مصري، روبل روسي، دولار أمريكي)",
        "choose_account": "هل لديك حساب مسبق أم تريد إنشاء حساب جديد؟",
        "new_account": "إنشاء حساب جديد",
        "existing_account": "لدي رمز سابق",
        "enter_token": "أدخل رمز حسابك:",
        "token_generated": "تم إنشاء حسابك بنجاح!\nرمزك الخاص: {token}\nاحتفظ به للوصول من منصات أخرى.",
        "token_linked": "تم ربط حسابك الحالي برمزك السابق.",
        "account_exists": "حسابك موجود بالفعل.",
        "main_menu": "جاهز! يمكنك الآن إرسال معاملة مالية، صورة شيك، أو رسالة صوتية.",
        "qr_rub_only": "خدمة تحليل الشيكات تعمل فقط مع عملة الروبل الروسي.",
        "settings": "الإعدادات",
        "history": "📜 هيستوري",
        "statistics": "📊 احصائيات",
        "notion_settings": "⚙️ إعدادات نوشن",
        "no_transactions": "لا توجد أي معاملات حتى الآن.",
        "select_month": "اختر الشهر:",
        "month_data": "بيانات الشهر {month}",
        "income": "الدخل",
        "expense": "المصروفات",
        "total_income": "إجمالي الدخل",
        "total_expense": "إجمالي المصروفات",
        "transaction_added": "تمت إضافة {count} معاملة:\n{details}",
        "error": "حدث خطأ: {error}",
        "processing_voice": "🎙️ جارٍ تحويل الصوت إلى نص...",
        "voice_text": "النص المستخرج: {text}",
        "qr_processing": "جارٍ فك QR وجلب الشيك...",
        "qr_not_found": "لم أعثر على QR Code في الصورة.",
        "notion_not_configured": "لم يتم ربط نوشن. استخدم الإعدادات لإدخال المفتاح.",
        "notion_ask_key": "أرسل مفتاح نوشن API الخاص بك:",
        "notion_ask_db": "الآن أرسل معرف قاعدة البيانات (Database ID):",
        "notion_saved": "تم حفظ إعدادات نوشن بنجاح.",
        "notion_saved_synced": "تم حفظ إعدادات نوشن بنجاح ومزامنة {count} معاملة سابقة.",
        "delete_transaction": "🗑️ حذف معاملة",
        "delete_select": "اختر رقم المعاملة التي تريد حذفها من آخر 30 معاملة:\n\n{details}",
        "transaction_deleted": "تم حذف المعاملة رقم {number} بنجاح.",
        "delete_failed": "تعذر حذف المعاملة.",
        "invalid_delete_selection": "اختيار غير صحيح أو المعاملة غير موجودة.",
    },
    "ru": {
        "welcome": "Здравствуйте! Давайте настроим ваш аккаунт.\nСначала выберите язык:",
        "choose_language": "Выберите язык:",
        "enter_currency": "Какая у вас основная валюта? Напишите (например: российский рубль, доллар США)",
        "choose_account": "У вас уже есть аккаунт или создать новый?",
        "new_account": "Создать новый аккаунт",
        "existing_account": "У меня есть код",
        "enter_token": "Введите код вашего аккаунта:",
        "token_generated": "Аккаунт создан!\nВаш код: {token}\nСохраните его для доступа с других платформ.",
        "token_linked": "Ваш текущий аккаунт связан с предыдущим кодом.",
        "account_exists": "Ваш аккаунт уже существует.",
        "main_menu": "Готово! Отправьте финансовую операцию, фото чека или голосовое сообщение.",
        "qr_rub_only": "Анализ чеков работает только с российским рублём.",
        "settings": "Настройки",
        "history": "📜 История",
        "statistics": "📊 Статистика",
        "notion_settings": "⚙️ Настройки Notion",
        "no_transactions": "Пока нет ни одной транзакции.",
        "select_month": "Выберите месяц:",
        "month_data": "Данные за {month}",
        "income": "Доходы",
        "expense": "Расходы",
        "total_income": "Общий доход",
        "total_expense": "Общий расход",
        "transaction_added": "Добавлено {count} операций:\n{details}",
        "error": "Произошла ошибка: {error}",
        "processing_voice": "🎙️ Преобразование голоса в текст...",
        "voice_text": "Распознанный текст: {text}",
        "qr_processing": "Сканирую QR-код и загружаю чек...",
        "qr_not_found": "QR-код не найден на изображении.",
        "notion_not_configured": "Notion не настроен. Используйте настройки для ввода ключа.",
        "notion_ask_key": "Введите ваш Notion API ключ:",
        "notion_ask_db": "Теперь введите ID базы данных (Database ID):",
        "notion_saved": "Настройки Notion сохранены.",
        "notion_saved_synced": "Настройки Notion сохранены, синхронизировано старых операций: {count}.",
        "delete_transaction": "🗑️ Удалить операцию",
        "delete_select": "Выберите номер операции для удаления из последних 30 операций:\n\n{details}",
        "transaction_deleted": "Операция №{number} удалена.",
        "delete_failed": "Не удалось удалить операцию.",
        "invalid_delete_selection": "Неверный выбор или операция не найдена.",
    },
    "en": {
        "welcome": "Hello! Let's set up your account.\nFirst, choose your language:",
        "choose_language": "Choose language:",
        "enter_currency": "What is your primary currency? Type it (e.g., US Dollar, Russian Ruble)",
        "choose_account": "Do you have an existing account or create a new one?",
        "new_account": "Create new account",
        "existing_account": "I have a token",
        "enter_token": "Enter your account token:",
        "token_generated": "Account created!\nYour token: {token}\nKeep it to access from other platforms.",
        "token_linked": "Your current account linked with the previous token.",
        "account_exists": "Your account already exists.",
        "main_menu": "Ready! Send a financial transaction, receipt photo, or voice message.",
        "qr_rub_only": "Receipt analysis works only with Russian Ruble.",
        "settings": "Settings",
        "history": "📜 History",
        "statistics": "📊 Statistics",
        "notion_settings": "⚙️ Notion Settings",
        "no_transactions": "No transactions yet.",
        "select_month": "Select month:",
        "month_data": "Data for {month}",
        "income": "Income",
        "expense": "Expenses",
        "total_income": "Total Income",
        "total_expense": "Total Expenses",
        "transaction_added": "{count} transaction(s) added:\n{details}",
        "error": "An error occurred: {error}",
        "processing_voice": "🎙️ Converting voice to text...",
        "voice_text": "Recognized text: {text}",
        "qr_processing": "Scanning QR and fetching receipt...",
        "qr_not_found": "No QR code found in the image.",
        "notion_not_configured": "Notion is not configured. Use settings to enter your key.",
        "notion_ask_key": "Enter your Notion API key:",
        "notion_ask_db": "Now enter your Database ID:",
        "notion_saved": "Notion settings saved successfully.",
        "notion_saved_synced": "Notion settings saved successfully and {count} previous transaction(s) synced.",
        "delete_transaction": "🗑️ Delete transaction",
        "delete_select": "Choose the transaction number to delete from the last 30 transactions:\n\n{details}",
        "transaction_deleted": "Transaction #{number} deleted successfully.",
        "delete_failed": "Could not delete the transaction.",
        "invalid_delete_selection": "Invalid selection or transaction not found.",
    }
}

def get_text(user_id: int, key: str, **kwargs) -> str:
    user_lang = user_cache.get(user_id, {}).get("language", "en")
    template = MESSAGES.get(user_lang, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))
    return template.format(**kwargs) if kwargs else template

# ---------- إعداد قاعدة البيانات ----------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                language TEXT NOT NULL DEFAULT 'en',
                currency TEXT NOT NULL DEFAULT 'Russian Ruble',
                token TEXT UNIQUE NOT NULL,
                notion_api_key TEXT,
                notion_database_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                receipt_id TEXT,
                photo_file_id TEXT,
                notion_page_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        cursor = await db.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "notion_page_id" not in columns:
            await db.execute("ALTER TABLE transactions ADD COLUMN notion_page_id TEXT")
        await db.commit()

# ---------- دوال المستخدم ----------

async def get_user(telegram_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "telegram_id": row[1],
                "language": row[2],
                "currency": row[3],
                "token": row[4],
                "notion_api_key": row[5],
                "notion_database_id": row[6],
                "created_at": row[7],
            }
        return None

async def create_user(telegram_id: int, language: str, currency: str, token: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (telegram_id, language, currency, token) VALUES (?,?,?,?)",
            (telegram_id, language, currency, token)
        )
        await db.commit()
        return await get_user(telegram_id)

async def update_user_token(telegram_id: int, token: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM users WHERE token=?", (token,))
        target_row = await cursor.fetchone()
        if not target_row:
            return None
        target_user_id = target_row[0]

        # حل مشكلة تسجيل الدخول بالكود عند وجود صف قديم لنفس تيليجرام
        await db.execute(
            "UPDATE users SET telegram_id=NULL WHERE telegram_id=? AND id<>?",
            (telegram_id, target_user_id)
        )
        await db.execute("UPDATE users SET telegram_id=? WHERE id=?", (telegram_id, target_user_id))
        await db.commit()
    return await get_user(telegram_id)

async def get_user_by_token(token: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE token=?", (token,))
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "telegram_id": row[1],
                "language": row[2],
                "currency": row[3],
                "token": row[4],
                "notion_api_key": row[5],
                "notion_database_id": row[6],
                "created_at": row[7],
            }
        return None

async def get_user_by_id(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "telegram_id": row[1],
                "language": row[2],
                "currency": row[3],
                "token": row[4],
                "notion_api_key": row[5],
                "notion_database_id": row[6],
                "created_at": row[7],
            }
        return None

def normalize_notion_database_id(database_id: str) -> str:
    value = database_id.strip()
    value = value.split("?")[0].split("#")[0]
    matches = re.findall(r"[0-9a-fA-F]{32}", value.replace("-", ""))
    if matches:
        raw = matches[-1]
        return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"
    return database_id.strip()

async def update_user_notion(telegram_id: int, api_key: str, database_id: str):
    database_id = normalize_notion_database_id(database_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET notion_api_key=?, notion_database_id=? WHERE telegram_id=?",
            (api_key, database_id, telegram_id)
        )
        await db.commit()

async def save_transaction(user_id: int, item: dict, photo_file_id: Optional[str] = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO transactions (user_id, date, amount, type, category, description, receipt_id, photo_file_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                user_id,
                item.get("date", datetime.now().strftime("%Y-%m-%d")),
                item.get("amount", 0),
                item.get("type", "مصروف"),
                item.get("category", "أخرى"),
                item.get("description", ""),
                item.get("receipt_id", ""),
                photo_file_id,
            )
        )
        await db.commit()
        return cursor.lastrowid

async def update_transaction_notion_page_id(transaction_id: int, notion_page_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE transactions SET notion_page_id=? WHERE id=?",
            (notion_page_id, transaction_id)
        )
        await db.commit()

def row_to_transaction(row) -> dict:
    return {
        "id": row[0],
        "user_id": row[1],
        "date": row[2],
        "amount": row[3],
        "type": row[4],
        "category": row[5],
        "description": row[6],
        "receipt_id": row[7],
        "photo_file_id": row[8],
        "created_at": row[9],
        "notion_page_id": row[10] if len(row) > 10 else None,
    }

async def query_transactions(user_id: int, month_str: str) -> List[dict]:
    try:
        year, month = map(int, month_str.split("-"))
    except ValueError:
        return []
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, date, amount, type, category, description, receipt_id, photo_file_id, created_at, notion_page_id "
            "FROM transactions WHERE user_id=? AND date >= ? AND date < ? ORDER BY date ASC",
            (user_id, start_date, end_date)
        )
        rows = await cursor.fetchall()
        return [row_to_transaction(row) for row in rows]

async def get_all_transactions_for_user(user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, date, amount, type, category, description, receipt_id, photo_file_id, created_at, notion_page_id "
            "FROM transactions WHERE user_id=? ORDER BY date ASC, id ASC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [row_to_transaction(row) for row in rows]

async def get_last_transactions_for_user(user_id: int, limit: int = 30) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, date, amount, type, category, description, receipt_id, photo_file_id, created_at, notion_page_id "
            "FROM transactions WHERE user_id=? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [row_to_transaction(row) for row in rows]

async def get_transaction_by_id(user_id: int, transaction_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, date, amount, type, category, description, receipt_id, photo_file_id, created_at, notion_page_id "
            "FROM transactions WHERE user_id=? AND id=?",
            (user_id, transaction_id)
        )
        row = await cursor.fetchone()
        return row_to_transaction(row) if row else None

async def delete_transaction_by_id(user_id: int, transaction_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM transactions WHERE user_id=? AND id=?",
            (user_id, transaction_id)
        )
        await db.commit()
        return cursor.rowcount > 0

async def get_available_months_for_user(user_id: int) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT DISTINCT substr(date,1,7) as month FROM transactions WHERE user_id=? ORDER BY month DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows if row[0]]

# ---------- Gemini API ----------
async def call_gemini(text: str, receipt_id: Optional[str] = None, reference_date: Optional[str] = None, language: str = "en") -> list[dict]:
    if reference_date is None:
        reference_date = datetime.now().strftime("%Y-%m-%d")
    categories_str = ", ".join(VALID_CATEGORIES)
    receipt_id_part = f'"{receipt_id}"' if receipt_id else "null"
    language_name = get_language_name(language)
    system_prompt = f"""
أنت مساعد يستخرج المعاملات المالية من النصوص ويعيدها بصيغة JSON صالحة.
اليوم هو: {reference_date}. إذا لم يُذكر تاريخ العملية صراحةً، استخدم هذا التاريخ.
لغة المستخدم المختارة هي: {language_name}.
يحتوي JSON على مفتاح "items" وهو مصفوفة من الكائنات، كل كائن يمثل معاملة.
الخصائص المطلوبة لكل كائن:
- date: تاريخ العملية بصيغة YYYY-MM-DD. استخدم {reference_date} إذا لم يذكر.
- amount: رقم موجب (المبلغ دائماً موجب).
- type: يجب أن يكون فقط "دخل" أو "مصروف" ولا تترجمه.
- category: يجب أن يكون واحداً بالضبط من هذه القائمة: {categories_str}. لا تستخدم تصنيفات عامة ولا تترجم التصنيف.
- description: وصف دقيق ومختصر للعملية، ويجب أن يكون بنفس لغة المستخدم المختارة: {language_name}.
- receipt_id: استخدم القيمة {receipt_id_part} ولا تخترع شيئاً.
أعد **فقط** JSON بدون أي نص إضافي.
"""
    user_text = f"النص: {text}"
    last_error = None
    for api_key in GEMINI_API_KEYS:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                    params={"key": api_key},
                    json={
                        "system_instruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"parts": [{"text": user_text}]}],
                        "generation_config": {
                            "response_mime_type": "application/json",
                            "temperature": 0.0,
                        }
                    }
                )
            if resp.status_code != 200:
                logger.warning(f"Gemini API key failed: {resp.status_code}")
                if resp.status_code == 429:
                    await asyncio.sleep(1)
                continue
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                continue
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                continue
            raw = parts[0].get("text", "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw)
            items = parsed.get("items", [])
            if not isinstance(items, list):
                raise ValueError("items ليس مصفوفة")
            for item in items:
                item.setdefault("receipt_id", receipt_id)
                item.setdefault("date", reference_date)
                if item.get("type") not in ("دخل", "مصروف"):
                    item["type"] = "مصروف"
                if item.get("category") not in VALID_CATEGORIES:
                    item["category"] = "أخرى"
            return items
        except Exception as e:
            last_error = e
            logger.error(f"Gemini error: {e}")
            continue
    raise Exception(f"فشل الاتصال بجميع مفاتيح Gemini. آخر خطأ: {last_error}")

async def parse_currency_with_gemini(currency_text: str) -> str:
    prompt = f"""
أنت مساعد يحدد اسم العملة من النص ويعيد الاسم بالإنجليزية فقط بشكل رسمي ومختصر.
مثال: "دولار أمريكي" -> "US Dollar"، "روبل روسي" -> "Russian Ruble"، "جنيه مصري" -> "Egyptian Pound".
النص: {currency_text}
أعد **فقط** اسم العملة بالإنجليزية.
"""
    for api_key in GEMINI_API_KEYS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generation_config": {"temperature": 0.0},
                    }
                )
            if resp.status_code != 200:
                continue
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text
        except:
            continue
    return currency_text.strip().title()

# ---------- تحويل الصوت إلى نص ----------
async def transcribe_voice(audio_bytes: bytes, language: str = "ar-AR") -> str:
    try:
        audio = AudioSegment.from_file(BytesIO(audio_bytes), format="ogg")
    except Exception as e:
        logger.error(f"Ogg to WAV failed: {e}")
        raise Exception("تنسيق الصوت غير مدعوم أو تالف.")
    wav_io = BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)
    try:
        text = await asyncio.to_thread(recognizer.recognize_google, audio_data, language=language)
        logger.info(f"STT result: {text}")
        return text
    except sr.UnknownValueError:
        raise Exception("لم يتم التعرف على أي كلام.")
    except sr.RequestError as e:
        logger.error(f"STT request error: {e}")
        raise Exception("خدمة التعرف على الصوت غير متاحة حالياً.")

# ---------- دوال الشيك (QR) ----------
def decode_qr_from_image(image_bytes: bytes) -> Optional[str]:
    try:
        pil_image = Image.open(BytesIO(image_bytes))
        decoded = qr_decode(pil_image)
        if not decoded:
            return None
        return decoded[0].data.decode("utf-8")
    except Exception as e:
        logger.warning(f"QR decode failed: {e}")
        return None

async def fetch_check_via_qrraw(qrraw: str) -> dict:
    payload = {"token": PROVERKACHEKA_TOKEN, "qrraw": qrraw}
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    url = "https://proverkacheka.com/api/v1/check/get"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"خطأ في API (HTTP {resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        if data.get("code") != 1:
            raise Exception(f"رمز استجابة غير متوقع: {data.get('code')}")
        return data

def extract_products_from_check_data(data: dict) -> tuple[list[dict], Optional[str]]:
    inner = data.get("data", {}).get("json", {})
    items = inner.get("items", [])
    for item in items:
        if "price" in item:
            item["price"] = item["price"] / 100
        if "sum" in item:
            item["sum"] = item["sum"] / 100
    date_str = inner.get("dateTime")
    return items, date_str

# ---------- دوال نوشن (اختياري) ----------
def build_notion_properties(user: dict, item: dict, photo_file_id: Optional[str] = None) -> dict:
    lang = user.get("language", "en")
    description = item.get("description", "عملية") or "عملية"
    properties = {
        "Name": {"title": [{"text": {"content": description}}]},
        "Date": {"date": {"start": item.get("date", datetime.now().strftime("%Y-%m-%d"))}},
        "Type": {"select": {"name": translate_type(item.get("type", "مصروف"), lang)}},
        "Amount": {"number": item.get("amount", 0)},
        "Category": {"select": {"name": translate_category(item.get("category", "أخرى"), lang)}},
        "Description": {"rich_text": [{"text": {"content": item.get("description", "")}}]},
        "Receipt ID": {"rich_text": [{"text": {"content": item.get("receipt_id", "") or ""}}]},
    }
    if photo_file_id:
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{photo_file_id}"
        properties["Photo"] = {"files": [{"name": "receipt.jpg", "external": {"url": photo_url}}]}
    return properties

async def add_to_notion_if_configured(user: dict, item: dict, photo_file_id: Optional[str] = None) -> Optional[str]:
    if not user or not user.get("notion_api_key") or not user.get("notion_database_id"):
        return None
    notion_headers = {
        "Authorization": f"Bearer {user['notion_api_key']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    payload = {
        "parent": {"database_id": user["notion_database_id"]},
        "properties": build_notion_properties(user, item, photo_file_id),
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.notion.com/v1/pages", headers=notion_headers, json=payload)
            if resp.status_code not in (200, 201):
                logger.error(f"Notion add failed: {resp.status_code} - {resp.text}")
                return None
            data = resp.json()
            return data.get("id")
    except Exception as e:
        logger.error(f"Notion request error: {e}")
        return None

async def sync_user_transactions_to_notion(user: dict) -> int:
    if not user or not user.get("notion_api_key") or not user.get("notion_database_id"):
        return 0
    records = await get_all_transactions_for_user(user["id"])
    synced_count = 0
    for rec in records:
        if rec.get("notion_page_id"):
            continue
        page_id = await add_to_notion_if_configured(user, rec, rec.get("photo_file_id"))
        if page_id:
            await update_transaction_notion_page_id(rec["id"], page_id)
            synced_count += 1
    return synced_count

async def delete_from_notion_if_possible(user: dict, notion_page_id: Optional[str]) -> bool:
    if not user or not notion_page_id or not user.get("notion_api_key"):
        return False
    notion_headers = {
        "Authorization": f"Bearer {user['notion_api_key']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.patch(
                f"https://api.notion.com/v1/pages/{notion_page_id}",
                headers=notion_headers,
                json={"archived": True}
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Notion delete failed: {resp.status_code} - {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Notion delete request error: {e}")
        return False

# ---------- إعداد البوت ----------
dp = Dispatcher()

def generate_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text(user_id, "history")),
             KeyboardButton(text=get_text(user_id, "statistics"))],
            [KeyboardButton(text=get_text(user_id, "notion_settings")),
             KeyboardButton(text=get_text(user_id, "delete_transaction"))],
        ],
        resize_keyboard=True,
    )

# ---------- بدء المحادثة والإعداد ----------
@dp.message(CommandStart())
async def start(message: Message):
    telegram_id = message.from_user.id
    existing_user = await get_user(telegram_id)
    if existing_user:
        user_cache[telegram_id] = existing_user
        await message.answer(
            get_text(telegram_id, "main_menu"),
            reply_markup=generate_main_keyboard(telegram_id)
        )
        return
    user_onboarding[telegram_id] = "language"
    inline_kb = InlineKeyboardBuilder()
    inline_kb.button(text="العربية", callback_data="lang_ar")
    inline_kb.button(text="Русский", callback_data="lang_ru")
    inline_kb.button(text="English", callback_data="lang_en")
    await message.answer(MESSAGES["en"]["choose_language"], reply_markup=inline_kb.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
async def language_chosen(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    lang = callback.data.split("_")[1]
    user_temp_data[telegram_id] = {"language": lang}
    user_onboarding[telegram_id] = "currency"
    user_cache[telegram_id] = {"language": lang}
    await callback.message.edit_text(get_text(telegram_id, "enter_currency"))
    await callback.answer()

@dp.message(lambda msg: user_onboarding.get(msg.from_user.id) == "currency")
async def currency_input(message: Message):
    telegram_id = message.from_user.id
    currency_text = message.text.strip()
    try:
        currency_name = await parse_currency_with_gemini(currency_text)
    except:
        currency_name = currency_text
    user_temp_data.setdefault(telegram_id, {})["currency"] = currency_name
    user_onboarding[telegram_id] = "account_type"
    inline_kb = InlineKeyboardBuilder()
    inline_kb.button(text=get_text(telegram_id, "new_account"), callback_data="acc_new")
    inline_kb.button(text=get_text(telegram_id, "existing_account"), callback_data="acc_existing")
    user_cache[telegram_id]["language"] = user_temp_data[telegram_id].get("language", "en")
    await message.answer(get_text(telegram_id, "choose_account"), reply_markup=inline_kb.as_markup())

@dp.callback_query(F.data.startswith("acc_"))
async def account_choice(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    lang = user_temp_data[telegram_id]["language"]
    currency = user_temp_data[telegram_id]["currency"]
    if callback.data == "acc_new":
        token = secrets.token_hex(6)
        user = await create_user(telegram_id, lang, currency, token)
        user_cache[telegram_id] = user
        await callback.message.edit_text(get_text(telegram_id, "token_generated", token=token))
        await asyncio.sleep(1)
        await callback.message.answer(
            get_text(telegram_id, "main_menu"),
            reply_markup=generate_main_keyboard(telegram_id)
        )
        user_onboarding.pop(telegram_id, None)
        user_temp_data.pop(telegram_id, None)
    elif callback.data == "acc_existing":
        user_onboarding[telegram_id] = "enter_token"
        await callback.message.edit_text(get_text(telegram_id, "enter_token"))
    await callback.answer()

@dp.message(lambda msg: user_onboarding.get(msg.from_user.id) == "enter_token")
async def token_entry(message: Message):
    telegram_id = message.from_user.id
    token = message.text.strip()
    existing_user = await get_user_by_token(token)
    if existing_user:
        user = await update_user_token(telegram_id, token)
        if not user:
            await message.reply("رمز غير صحيح، حاول مرة أخرى:")
            return
        user_cache[telegram_id] = user
        user_onboarding.pop(telegram_id, None)
        user_temp_data.pop(telegram_id, None)
        await message.answer(
            get_text(telegram_id, "token_linked"),
            reply_markup=generate_main_keyboard(telegram_id)
        )
    else:
        await message.reply("رمز غير صحيح، حاول مرة أخرى:")

# ---------- معالج النصوص الموحد (الأزرار أو المعاملات) ----------
@dp.message(lambda msg: msg.text and not msg.text.startswith("/") and not user_onboarding.get(msg.from_user.id))
async def unified_text_handler(message: Message):
    telegram_id = message.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    if not user:
        await message.answer("Please complete setup first with /start")
        return

    history_text = get_text(telegram_id, "history")
    statistics_text = get_text(telegram_id, "statistics")
    notion_text = get_text(telegram_id, "notion_settings")
    delete_text = get_text(telegram_id, "delete_transaction")

    if message.text == history_text:
        await handle_history_button(message, user)
    elif message.text == statistics_text:
        await handle_statistics_button(message, user)
    elif message.text == notion_text:
        await handle_notion_button(message)
    elif message.text == delete_text:
        await handle_delete_button(message, user)
    else:
        await handle_transaction(message, user)

async def handle_history_button(message: Message, user: dict):
    telegram_id = message.from_user.id
    months = await get_available_months_for_user(user["id"])
    if not months:
        await message.answer(get_text(telegram_id, "no_transactions"))
        return
    builder = InlineKeyboardBuilder()
    for m in months:
        builder.button(text=m, callback_data=f"hist_{m}")
    builder.adjust(2)
    await message.answer(get_text(telegram_id, "select_month"), reply_markup=builder.as_markup())

async def handle_statistics_button(message: Message, user: dict):
    telegram_id = message.from_user.id
    months = await get_available_months_for_user(user["id"])
    if not months:
        await message.answer(get_text(telegram_id, "no_transactions"))
        return
    builder = InlineKeyboardBuilder()
    for m in months:
        builder.button(text=m, callback_data=f"stat_{m}")
    builder.adjust(2)
    await message.answer(get_text(telegram_id, "select_month"), reply_markup=builder.as_markup())

async def handle_notion_button(message: Message):
    telegram_id = message.from_user.id
    user_onboarding[telegram_id] = "notion_key"
    user_temp_data[telegram_id] = {}
    await message.answer(get_text(telegram_id, "notion_ask_key"))

async def handle_delete_button(message: Message, user: dict):
    telegram_id = message.from_user.id
    records = await get_last_transactions_for_user(user["id"], 30)
    if not records:
        await message.answer(get_text(telegram_id, "no_transactions"))
        return
    lang = user.get("language", "en")
    lines = []
    builder = InlineKeyboardBuilder()
    for idx, rec in enumerate(records, start=1):
        desc = rec.get("description", "")
        cat = translate_category(rec.get("category", "أخرى"), lang)
        t = translate_type(rec.get("type", "مصروف"), lang)
        amt = rec.get("amount", 0)
        date = rec.get("date", "")
        lines.append(f"{idx}) {desc} | {cat} | {amt:.2f} | {t} | {date}")
        builder.button(text=str(idx), callback_data=f"del_{rec['id']}_{idx}")
    builder.adjust(5)
    await message.answer(
        get_text(telegram_id, "delete_select", details="\n".join(lines)),
        reply_markup=builder.as_markup()
    )

async def handle_transaction(message: Message, user: dict):
    telegram_id = message.from_user.id
    text = message.text.strip()
    receipt_id = str(uuid.uuid4())
    message_date = message.date.strftime("%Y-%m-%d")
    try:
        items = await call_gemini(text, receipt_id, reference_date=message_date, language=user.get("language", "en"))
        if not items:
            await message.reply("لم أتمكن من استخراج أي معاملة.")
            return

        lang = user["language"]
        details_lines = []
        for item in items:
            transaction_id = await save_transaction(user["id"], item)
            page_id = await add_to_notion_if_configured(user, item)
            if page_id:
                await update_transaction_notion_page_id(transaction_id, page_id)
            # بناء تفاصيل العملية باللغة المناسبة
            cat_display = translate_category(item.get("category", "أخرى"), lang)
            type_display = translate_type(item.get("type", "مصروف"), lang)
            desc = item.get("description", "")
            amt = item.get("amount", 0)
            date = item.get("date", "")
            details_lines.append(f"• {desc}: {amt:.2f} ({cat_display}, {type_display})")
        details = "\n".join(details_lines)
        await message.reply(get_text(telegram_id, "transaction_added", count=len(items), details=details))
    except Exception as e:
        logger.error(f"Transaction error: {e}")
        await message.reply(get_text(telegram_id, "error", error=str(e)))

# ---------- الصور (الشيكات) ----------
@dp.message(F.photo)
async def handle_receipt_photo(message: Message):
    telegram_id = message.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    if not user:
        await message.answer("Please complete setup first with /start")
        return
    if user["currency"].lower() != "russian ruble":
        await message.reply(get_text(telegram_id, "qr_rub_only"))
        return
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    image_bytes = await message.bot.download_file(file.file_path)
    if not image_bytes:
        await message.reply("تعذر تحميل الصورة.")
        return
    await message.reply(get_text(telegram_id, "qr_processing"))
    qr_raw = decode_qr_from_image(image_bytes.read())
    if not qr_raw:
        await message.reply(get_text(telegram_id, "qr_not_found"))
        return
    try:
        check_data = await fetch_check_via_qrraw(qr_raw)
        receipt_items, receipt_date_str = extract_products_from_check_data(check_data)
    except Exception as e:
        await message.reply(f"فشل جلب الشيك: {e}")
        return
    if not receipt_items:
        await message.reply("الشيك لا يحتوي على منتجات.")
        return
    receipt_date_str = receipt_date_str[:10] if receipt_date_str else message.date.strftime("%Y-%m-%d")
    lines = []
    for prod in receipt_items:
        name = prod.get("name", "منتج")
        price = prod.get("price", 0)
        qty = prod.get("quantity", 1)
        total = price * qty
        lines.append(f"{name} - {total:.2f} RUB (الكمية: {qty})")
    combined_text = "منتجات من شيك:\n" + "\n".join(lines)
    receipt_id = str(uuid.uuid4())
    try:
        items = await call_gemini(combined_text, receipt_id, reference_date=receipt_date_str, language=user.get("language", "en"))
    except Exception as e:
        await message.reply(f"فشل تحليل المنتجات: {e}")
        return

    lang = user["language"]
    details_lines = []
    for item in items:
        try:
            transaction_id = await save_transaction(user["id"], item, photo.file_id)
            page_id = await add_to_notion_if_configured(user, item, photo.file_id)
            if page_id:
                await update_transaction_notion_page_id(transaction_id, page_id)
            cat_display = translate_category(item.get("category", "أخرى"), lang)
            type_display = translate_type(item.get("type", "مصروف"), lang)
            desc = item.get("description", "")
            amt = item.get("amount", 0)
            details_lines.append(f"• {desc}: {amt:.2f} ({cat_display}, {type_display})")
        except Exception as e:
            logger.error(f"فشل حفظ المنتج: {e}")
    details = "\n".join(details_lines)
    await message.reply(get_text(telegram_id, "transaction_added", count=len(items), details=details))

# ---------- الرسائل الصوتية ----------
@dp.message(F.voice)
async def handle_voice_message(message: Message):
    telegram_id = message.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    if not user:
        await message.answer("Please complete setup first with /start")
        return
    lang_map = {"ar": "ar-AR", "ru": "ru-RU", "en": "en-US"}
    stt_lang = lang_map.get(user.get("language", "en"), "en-US")
    await message.reply(get_text(telegram_id, "processing_voice"))
    voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    audio_buffer = await message.bot.download_file(file.file_path)
    if not audio_buffer:
        await message.reply("تعذر تحميل الملف الصوتي.")
        return
    raw_bytes = audio_buffer.read()
    try:
        transcript = await transcribe_voice(raw_bytes, language=stt_lang)
        if not transcript:
            await message.reply("لم أتمكن من التعرف على أي كلام.")
            return
        await message.reply(get_text(telegram_id, "voice_text", text=transcript))
        receipt_id = str(uuid.uuid4())
        message_date = message.date.strftime("%Y-%m-%d")
        items = await call_gemini(transcript, receipt_id, reference_date=message_date, language=user.get("language", "en"))
        if not items:
            await message.reply("لم يتم استخراج معاملات من الصوت.")
            return

        lang = user["language"]
        details_lines = []
        for item in items:
            transaction_id = await save_transaction(user["id"], item)
            page_id = await add_to_notion_if_configured(user, item)
            if page_id:
                await update_transaction_notion_page_id(transaction_id, page_id)
            cat_display = translate_category(item.get("category", "أخرى"), lang)
            type_display = translate_type(item.get("type", "مصروف"), lang)
            desc = item.get("description", "")
            amt = item.get("amount", 0)
            details_lines.append(f"• {desc}: {amt:.2f} ({cat_display}, {type_display})")
        details = "\n".join(details_lines)
        await message.reply(get_text(telegram_id, "transaction_added", count=len(items), details=details))
    except Exception as e:
        logger.error(f"Voice error: {e}")
        await message.reply(get_text(telegram_id, "error", error=str(e)))

# ---------- إعدادات نوشن (مدخلات متسلسلة) ----------
@dp.message(lambda msg: user_onboarding.get(msg.from_user.id) == "notion_key")
async def notion_key_input(message: Message):
    telegram_id = message.from_user.id
    api_key = message.text.strip()
    user_temp_data.setdefault(telegram_id, {})["notion_api_key"] = api_key
    user_onboarding[telegram_id] = "notion_db"
    await message.answer(get_text(telegram_id, "notion_ask_db"))

@dp.message(lambda msg: user_onboarding.get(msg.from_user.id) == "notion_db")
async def notion_db_input(message: Message):
    telegram_id = message.from_user.id
    database_id = message.text.strip()
    api_key = user_temp_data[telegram_id]["notion_api_key"]
    await update_user_notion(telegram_id, api_key, database_id)
    user = await get_user(telegram_id)
    user_cache[telegram_id] = user
    synced_count = await sync_user_transactions_to_notion(user)
    user_onboarding.pop(telegram_id, None)
    user_temp_data.pop(telegram_id, None)
    await message.answer(get_text(telegram_id, "notion_saved_synced", count=synced_count),
                         reply_markup=generate_main_keyboard(telegram_id))

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_transaction_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    if not user:
        await callback.answer()
        return
    try:
        _, transaction_id_str, number_str = callback.data.split("_", 2)
        transaction_id = int(transaction_id_str)
        number = int(number_str)
    except Exception:
        await callback.message.edit_text(get_text(telegram_id, "invalid_delete_selection"))
        await callback.answer()
        return

    transaction = await get_transaction_by_id(user["id"], transaction_id)
    if not transaction:
        await callback.message.edit_text(get_text(telegram_id, "invalid_delete_selection"))
        await callback.answer()
        return

    await delete_from_notion_if_possible(user, transaction.get("notion_page_id"))
    deleted = await delete_transaction_by_id(user["id"], transaction_id)
    if deleted:
        await callback.message.edit_text(get_text(telegram_id, "transaction_deleted", number=number))
    else:
        await callback.message.edit_text(get_text(telegram_id, "delete_failed"))
    await callback.answer()

# ---------- عرض التاريخ والإحصائيات ----------
@dp.callback_query(lambda c: c.data.startswith("hist_"))
async def show_history(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    month = callback.data[5:]
    records = await query_transactions(user["id"], month)
    if not records:
        await callback.message.edit_text(get_text(telegram_id, "no_transactions"))
        return
    lang = user["language"]
    lines = [get_text(telegram_id, "month_data", month=month) + ":\n"]
    for rec in records:
        desc = rec["description"]
        cat = translate_category(rec["category"], lang)
        t = translate_type(rec["type"], lang)
        amt = rec["amount"]
        date = rec["date"]
        lines.append(f"• {desc} | {cat} | {amt:.2f} | {t} | {date}")
    text = "\n".join(lines)
    if len(text) > 4000:
        await callback.message.edit_text("Text too long, sending in parts...")
        for i in range(0, len(text), 4000):
            await callback.message.answer(text[i:i+4000])
    else:
        await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("stat_"))
async def show_statistics(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    user = user_cache.get(telegram_id) or await get_user(telegram_id)
    month = callback.data[5:]
    records = await query_transactions(user["id"], month)
    if not records:
        await callback.message.edit_text(get_text(telegram_id, "no_transactions"))
        return
    lang = user["language"]
    income_by_cat = {}
    expense_by_cat = {}
    for rec in records:
        cat = rec["category"]
        amt = rec["amount"]
        if rec["type"] == "دخل":
            income_by_cat[cat] = income_by_cat.get(cat, 0) + amt
        else:
            expense_by_cat[cat] = expense_by_cat.get(cat, 0) + amt
    text = get_text(telegram_id, "month_data", month=month) + ":\n\n"
    text += get_text(telegram_id, "income") + ":\n"
    if income_by_cat:
        total_income = sum(income_by_cat.values())
        for cat, total in sorted(income_by_cat.items()):
            cat_disp = translate_category(cat, lang)
            text += f"  - {cat_disp}: {total:.2f}\n"
        text += get_text(telegram_id, "total_income") + f": {total_income:.2f}\n"
    else:
        text += "  " + get_text(telegram_id, "no_transactions") + "\n"  # fallback
    text += "\n" + get_text(telegram_id, "expense") + ":\n"
    if expense_by_cat:
        total_expense = sum(expense_by_cat.values())
        for cat, total in sorted(expense_by_cat.items()):
            cat_disp = translate_category(cat, lang)
            text += f"  - {cat_disp}: {total:.2f}\n"
        text += get_text(telegram_id, "total_expense") + f": {total_expense:.2f}\n"
    else:
        text += "  " + get_text(telegram_id, "no_transactions") + "\n"
    await callback.message.edit_text(text)
    await callback.answer()

# ---------- تشغيل البوت ----------
async def main():
    await init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
