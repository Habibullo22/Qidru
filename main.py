import asyncio
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("8611335484:AAHoH8mg1OO9V7PDB3wUlZ6wU3HxsQx7avY")
ADMIN_ID = int(os.getenv("5815294733", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Secrets ichida topilmadi!")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

DB_NAME = "bot.db"
PAYMENT_AMOUNT = 30000
CARD_NUMBER = "9860 6067 5024 7151"
CARD_NAME = "Abidjanov H"


# =========================================================
# DATABASE
# =========================================================

def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 0,
            vip_until TEXT,
            banned INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT
        )
    """)

    con.commit()
    con.close()


def add_user(user):
    con = connect()
    cur = con.cursor()

    cur.execute("SELECT id FROM users WHERE id=?", (user.id,))
    exists = cur.fetchone()

    if not exists:
        cur.execute("""
            INSERT INTO users
            (id, username, first_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            user.id,
            user.username or "",
            user.first_name or "",
            datetime.now().isoformat()
        ))
    else:
        cur.execute("""
            UPDATE users
            SET username=?, first_name=?
            WHERE id=?
        """, (
            user.username or "",
            user.first_name or "",
            user.id
        ))

    con.commit()
    con.close()


def get_user(user_id):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name, balance,
               vip_until, banned, created_at
        FROM users
        WHERE id=?
    """, (user_id,))

    result = cur.fetchone()

    con.close()
    return result


def is_banned(user_id):
    user = get_user(user_id)
    return bool(user and user[5])


def is_vip(user_id):
    user = get_user(user_id)

    if not user or not user[4]:
        return False

    try:
        return datetime.fromisoformat(user[4]) > datetime.now()
    except ValueError:
        return False


def vip_until(user_id):
    user = get_user(user_id)

    if not user:
        return None

    return user[4]


def set_balance(user_id, amount):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance=?
        WHERE id=?
    """, (amount, user_id))

    con.commit()
    con.close()


def add_balance(user_id, amount):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance=balance+?
        WHERE id=?
    """, (amount, user_id))

    con.commit()
    con.close()


def give_vip(user_id, days):
    user = get_user(user_id)

    if not user:
        return None

    current = datetime.now()

    if user[4]:
        try:
            old_until = datetime.fromisoformat(user[4])

            if old_until > current:
                current = old_until
        except ValueError:
            pass

    new_until = current + timedelta(days=days)

    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET vip_until=?
        WHERE id=?
    """, (
        new_until.isoformat(),
        user_id
    ))

    con.commit()
    con.close()

    return new_until


# =========================================================
# PAYMENT FUNCTIONS
# =========================================================

def pending_payment(user_id):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, amount, created_at
        FROM payments
        WHERE user_id=? AND status='pending'
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))

    result = cur.fetchone()

    con.close()
    return result


def create_payment(user_id):
    existing = pending_payment(user_id)

    if existing:
        return existing[0]

    con = connect()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO payments
        (user_id, amount, status, created_at)
        VALUES (?, ?, 'pending', ?)
    """, (
        user_id,
        PAYMENT_AMOUNT,
        datetime.now().isoformat()
    ))

    payment_id = cur.lastrowid

    con.commit()
    con.close()

    return payment_id


def get_payment(payment_id):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount, status, created_at
        FROM payments
        WHERE id=?
    """, (payment_id,))

    result = cur.fetchone()

    con.close()
    return result


def process_payment(payment_id, status):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE payments
        SET status=?, processed_at=?
        WHERE id=? AND status='pending'
    """, (
        status,
        datetime.now().isoformat(),
        payment_id
    ))

    changed = cur.rowcount

    con.commit()
    con.close()

    return changed == 1


# =========================================================
# KEYBOARDS
# =========================================================

def main_menu(user_id):

    buttons = [
        [
            InlineKeyboardButton(
                text="🔎 Qidiruv",
                callback_data="search"
            )
        ],
        [
            InlineKeyboardButton(
                text="💰 Hisob to‘ldirish",
                callback_data="deposit"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Profilim",
                callback_data="profile"
            ),
            InlineKeyboardButton(
                text="⭐ VIP",
                callback_data="vip"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data="stats"
            )
        ],
        [
            InlineKeyboardButton(
                text="ℹ️ Yordam",
                callback_data="help"
            )
        ]
    ]

    if user_id == ADMIN_ID:
        buttons.append([
            InlineKeyboardButton(
                text="🛠 Admin panel",
                callback_data="admin"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="back"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    await state.clear()

    add_user(message.from_user)

    if is_banned(message.from_user.id):
        await message.answer("🚫 Siz botdan foydalanishingiz bloklangan.")
        return

    await message.answer(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "🔎 Ochiq ma’lumotlarni qidirish\n"
        "⭐ VIP xizmatlar\n"
        "💰 Hisob to‘ldirish\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
    )


# =========================================================
# DEPOSIT
# =========================================================

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):

    user_id = call.from_user.id

    if is_banned(user_id):
        await call.answer("🚫 Siz bloklangansiz.", show_alert=True)
        return

    existing = pending_payment(user_id)

    if existing:
        await call.message.edit_text(
            "⏳ <b>Sizning to‘lov arizangiz tekshirilmoqda.</b>\n\n"
            f"💰 Summa: {existing[1]:,} so‘m\n"
            "Admin tasdiqlashini kuting.\n\n"
            "Ariza tasdiqlanmaguncha yangi ariza yubora olmaysiz.",
            parse_mode="HTML",
            reply_markup=back_button()
        )
        await call.answer()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 30 000 so‘m to‘lash",
                    callback_data="pay_30000"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="back"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "💰 <b>HISOB TO‘LDIRISH</b>\n\n"
        "Minimal to‘lov: <b>30 000 so‘m</b>\n\n"
        f"💳 Karta:\n"
        f"<code>{CARD_NUMBER}</code>\n"
        f"👤 Karta egasi: <b>{CARD_NAME}</b>\n\n"
        "To‘lovni amalga oshirgandan keyin "
        "«To‘lov qildim» tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await call.answer()


@dp.callback_query(F.data == "pay_30000")
async def pay_30000(call: CallbackQuery):

    user_id = call.from_user.id

    if pending_payment(user_id):
        await call.answer(
            "⏳ Sizda allaqachon kutilayotgan ariza bor.",
            show_alert=True
        )
        return

    payment_id = create_payment(user_id)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ To‘lov qildim",
                    callback_data=f"payment_done:{payment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data="back"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "💳 <b>30 000 SO‘M TO‘LOV</b>\n\n"
        f"Karta:\n<code>{CARD_NUMBER}</code>\n"
        f"Egasi: <b>{CARD_NAME}</b>\n\n"
        "To‘lovni amalga oshiring.\n"
        "Keyin quyidagi tugmani bosing:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await call.answer()


@dp.callback_query(F.data.startswith("payment_done:"))
async def payment_done(call: CallbackQuery):

    payment_id = int(call.data.split(":")[1])
    payment = get_payment(payment_id)

    if not payment:
        await call.answer(
            "❌ Ariza topilmadi.",
            show_alert=True
        )
        return

    payment_id_db, user_id, amount, status, created_at = payment

    if user_id != call.from_user.id:
        await call.answer(
            "❌ Bu ariza sizniki emas.",
            show_alert=True
        )
        return

    if status != "pending":
        await call.answer(
            "❌ Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    user = get_user(user_id)

    username = (
        f"@{user[1]}"
        if user and user[1]
        else "username yo‘q"
    )

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"approve:{payment_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"reject:{payment_id}"
                )
            ]
        ]
    )

    await bot.send_message(
        ADMIN_ID,
        "🔔 <b>YANGI TO‘LOV ARIZASI</b>\n\n"
        f"🆔 Ariza: <code>#{payment_id}</code>\n"
        f"👤 User: {username}\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n"
        f"⏰ Vaqt: {created_at}",
        parse_mode="HTML",
        reply_markup=admin_keyboard
    )

    await call.message.edit_text(
        "⏳ <b>Arizangiz admin'ga yuborildi.</b>\n\n"
        f"💰 Summa: {amount:,} so‘m\n"
        "Admin to‘lovni tekshiradi.\n\n"
        "Tasdiqlanguncha yangi hisob to‘ldirish arizasini "
        "yubora olmaysiz.",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer("✅ Ariza yuborildi.")


# =========================================================
# ADMIN PAYMENT APPROVE
# =========================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_payment(call: CallbackQuery):

    if call.from_user.id != ADMIN_ID:
        await call.answer("🚫 Ruxsat yo‘q.", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    payment = get_payment(payment_id)

    if not payment:
        await call.answer("❌ Ariza topilmadi.", show_alert=True)
        return

    _, user_id, amount, status, _ = payment

    if status != "pending":
        await call.answer(
            "ℹ️ Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    if not process_payment(payment_id, "approved"):
        await call.answer(
            "❌ Ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    add_balance(user_id, amount)
    until = give_vip(user_id, 30)

    await call.message.edit_text(
        "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
        f"🆔 Ariza: <code>#{payment_id}</code>\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n"
        "⭐ VIP: <b>30 kun</b>\n\n"
        "🔒 Bu ariza ko‘rib chiqilgan.",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            user_id,
            "✅ <b>To‘lovingiz tasdiqlandi!</b>\n\n"
            f"💰 Balansingizga: <b>{amount:,} so‘m</b> qo‘shildi.\n"
            "⭐ Sizga <b>30 kunlik VIP</b> ochildi.\n\n"
            f"⏰ VIP tugashi: <code>{until.strftime('%Y-%m-%d %H:%M')}</code>",
            parse_mode="HTML",
            reply_markup=main_menu(user_id)
        )
    except Exception:
        pass

    await call.answer("✅ Tasdiqlandi.")


# =========================================================
# ADMIN PAYMENT REJECT
# =========================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_payment(call: CallbackQuery):

    if call.from_user.id != ADMIN_ID:
        await call.answer("🚫 Ruxsat yo‘q.", show_alert=True)
        return

    payment_id = int(call.data.split(":")[1])
    payment = get_payment(payment_id)

    if not payment:
        await call.answer("❌ Ariza topilmadi.", show_alert=True)
        return

    _, user_id, amount, status, _ = payment

    if status != "pending":
        await call.answer(
            "ℹ️ Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    if not process_payment(payment_id, "rejected"):
        await call.answer(
            "❌ Ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
        f"🆔 Ariza: <code>#{payment_id}</code>\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n\n"
        "🔒 Bu ariza ko‘rib chiqilgan.",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            user_id,
            "❌ <b>To‘lovingiz rad etildi.</b>\n\n"
            f"💰 Summa: {amount:,} so‘m\n\n"
            "Ariza tasdiqlanmadi.\n"
            "Istasangiz, yangi to‘lov arizasi yuborishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=main_menu(user_id)
        )
    except Exception:
        pass

    await call.answer("❌ Rad etildi.")


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):

    user = get_user(call.from_user.id)

    if not user:
        add_user(call.from_user)
        user = get_user(call.from_user.id)

    vip_text = "⭐ FAOL" if is_vip(call.from_user.id) else "🆓 FAOL EMAS"

    balance = user[3]
    until = user[4] or "—"

    await call.message.edit_text(
        "👤 <b>PROFIL</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 Username: @{user[1] or 'yo‘q'}\n"
        f"💰 Balans: <b>{balance:,} so‘m</b>\n"
        f"⭐ VIP: <b>{vip_text}</b>\n"
        f"⏰ VIP tugashi: <code>{until}</code>",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer()


# =========================================================
# VIP
# =========================================================

@dp.callback_query(F.data == "vip")
async def vip(call: CallbackQuery):

    user_id = call.from_user.id

    if is_vip(user_id):
        await call.message.edit_text(
            "⭐ <b>VIP FAOL</b>\n\n"
            f"⏰ Tugash vaqti:\n"
            f"<code>{vip_until(user_id)}</code>\n\n"
            "🔎 Kengaytirilgan ochiq ma’lumot qidiruvi mavjud.",
            parse_mode="HTML",
            reply_markup=back_button()
        )
    else:
        await call.message.edit_text(
            "⭐ <b>VIP</b>\n\n"
            "VIP faollashtirish uchun hisobingizni "
            "kamida 30 000 so‘mga to‘ldiring.\n\n"
            "Tasdiqlangan to‘lovdan keyin:\n"
            "⭐ 30 kun VIP ochiladi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💰 Hisob to‘ldirish",
                            callback_data="deposit"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Orqaga",
                            callback_data="back"
                        )
                    ]
                ]
            )
        )

    await call.answer()


# =========================================================
# SEARCH
# =========================================================

class SearchState(StatesGroup):
    waiting = State()


@dp.callback_query(F.data == "search")
async def search_start(call: CallbackQuery, state: FSMContext):

    if not is_vip(call.from_user.id):
        await call.message.edit_text(
            "🔒 <b>VIP kerak</b>\n\n"
            "Qidiruv funksiyasidan foydalanish uchun "
            "VIP faol bo‘lishi kerak.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⭐ VIP",
                            callback_data="vip"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Orqaga",
                            callback_data="back"
                        )
                    ]
                ]
            )
        )
        await call.answer()
        return

    await state.set_state(SearchState.waiting)

    await call.message.edit_text(
        "🔎 <b>QIDIRUV</b>\n\n"
        "Username yoki Telegram ID yuboring.\n\n"
        "Masalan:\n"
        "<code>@username</code>",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer()


@dp.message(SearchState.waiting)
async def search_user(message: Message, state: FSMContext):

    if not is_vip(message.from_user.id):
        await state.clear()
        await message.answer("🔒 VIP muddati tugagan.")
        return

    query = message.text.strip()

    await message.answer(
        "🔎 Qidirilmoqda...\n\n"
        f"🔍 So‘rov: <code>{query}</code>\n\n"
        "🌐 Ochiq manbalar tekshirilmoqda...",
        parse_mode="HTML"
    )

    # Bu yerda keyinchalik haqiqiy OPEN-SOURCE qidiruv API/moduli ulanadi.
    # Telegram Bot API istalgan userning yopiq guruhlarini,
    # kontaktlarini yoki shaxsiy yozishmalarini bera olmaydi.

    await message.answer(
        "📊 <b>QIDIRUV NATIJASI</b>\n\n"
        f"🔍 So‘rov: <code>{query}</code>\n\n"
        "👤 Profil: mavjud bo‘lsa ko‘rsatiladi\n"
        "👥 Ochiq guruhlar: ochiq manbalardan\n"
        "📢 Ochiq kanallar: ochiq manbalardan\n"
        "💬 Ochiq xabarlar: ochiq manbalardan\n\n"
        "ℹ️ Yopiq yoki maxfiy ma’lumotlar olinmaydi.",
        parse_mode="HTML"
    )

    await state.clear()


# =========================================================
# STATISTICS
# =========================================================

@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):

    con = connect()
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE vip_until IS NOT NULL
    """)
    vip_users = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE status='approved'
    """)
    income = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Userlar: <b>{users}</b>\n"
        f"⭐ VIP userlar: <b>{vip_users}</b>\n"
        f"💰 Tasdiqlangan to‘lovlar: <b>{income:,} so‘m</b>",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer()


# =========================================================
# HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    await call.message.edit_text(
        "ℹ️ <b>YORDAM</b>\n\n"
        "🔎 Qidiruv — faqat ochiq ma’lumotlar.\n"
        "💰 Hisob to‘ldirish — admin tasdiqlashi orqali.\n"
        "⭐ VIP — tasdiqlangan to‘lovdan keyin 30 kun.\n\n"
        "🔒 Yopiq guruhlar, shaxsiy yozishmalar, "
        "yashirin kontaktlar yoki IP kabi maxfiy "
        "ma’lumotlar olinmaydi.",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer()


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery, state: FSMContext):

    await state.clear()

    await call.message.edit_text(
        "🏠 <b>ASOSIY MENYU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(call.from_user.id)
    )

    await call.answer()


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Userlar",
                    callback_data="admin_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 To‘lovlar",
                    callback_data="admin_payments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ VIP berish",
                    callback_data="admin_vip"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Balans boshqarish",
                    callback_data="admin_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Ban / Unban",
                    callback_data="admin_ban"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Reklama",
                    callback_data="admin_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Asosiy menyu",
                    callback_data="back"
                )
            ]
        ]
    )


def admin_only(user_id):
    return user_id == ADMIN_ID


@dp.callback_query(F.data == "admin")
async def admin_panel(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Siz admin emassiz.",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "🛠 <b>ADMIN PANEL</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer("🚫 Ruxsat yo‘q.", show_alert=True)
        return

    con = connect()
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE vip_until IS NOT NULL
    """)
    vip_users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE status='pending'
    """)
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(amount),0)
        FROM payments
        WHERE status='approved'
    """)
    income = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>ADMIN STATISTIKA</b>\n\n"
        f"👥 Userlar: {users}\n"
        f"⭐ VIP: {vip_users}\n"
        f"⏳ Kutilayotgan to‘lov: {pending}\n"
        f"💰 Daromad: {income:,} so‘m",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer("🚫 Ruxsat yo‘q.", show_alert=True)
        return

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, balance, vip_until, banned
        FROM users
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    con.close()

    if not rows:
        text = "👥 Userlar yo‘q."
    else:
        lines = ["👥 <b>SO‘NGGI USERLAR</b>\n"]

        for row in rows:
            uid, username, balance, vip, banned = row

            lines.append(
                f"🆔 <code>{uid}</code>\n"
                f"👤 @{username or 'yo‘q'}\n"
                f"💰 {balance:,} so‘m\n"
                f"⭐ {'Ha' if vip else 'Yo‘q'}\n"
                f"🚫 {'BAN' if banned else 'OK'}\n"
            )

        text = "\n".join(lines)

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.callback_query(F.data == "admin_payments")
async def admin_payments(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer("🚫 Ruxsat yo‘q.", show_alert=True)
        return

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount, status
        FROM payments
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    con.close()

    if not rows:
        text = "💳 To‘lovlar yo‘q."
    else:
        lines = ["💳 <b>TO‘LOVLAR</b>\n"]

        for pid, uid, amount, status in rows:
            lines.append(
                f"#{pid} | ID: {uid}\n"
                f"💰 {amount:,} so‘m\n"
                f"📌 {status}\n"
            )

        text = "\n".join(lines)

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# =========================================================
# ADMIN COMMANDS
# =========================================================

@dp.message(Command("vip"))
async def admin_vip_command(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "Foydalanish:\n"
            "/vip USER_ID KUN\n\n"
            "Misol:\n"
            "/vip 123456789 30"
        )
        return

    try:
        user_id = int(parts[1])
        days = int(parts[2])

        if not get_user(user_id):
            await message.answer("❌ User topilmadi.")
            return

        until = give_vip(user_id, days)

        await message.answer(
            f"✅ VIP berildi.\n\n"
            f"🆔 ID: {user_id}\n"
            f"⭐ Muddat: {days} kun\n"
            f"⏰ Tugashi: {until}"
        )

        try:
            await bot.send_message(
                user_id,
                f"⭐ Sizga admin tomonidan {days} kun VIP berildi!\n\n"
                f"⏰ Tugashi: {until}"
            )
        except Exception:
            pass

    except ValueError:
        await message.answer("❌ ID yoki kun noto‘g‘ri.")


@dp.message(Command("balance"))
async def admin_balance_command(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "/balance USER_ID SUMMA\n\n"
            "Misol:\n"
            "/balance 123456789 30000"
        )
        return

    try:
        user_id = int(parts[1])
        amount = int(parts[2])

        if not get_user(user_id):
            await message.answer("❌ User topilmadi.")
            return

        add_balance(user_id, amount)

        await message.answer(
            f"✅ Balans o‘zgartirildi.\n"
            f"🆔 ID: {user_id}\n"
            f"💰 +{amount:,} so‘m"
        )

    except ValueError:
        await message.answer("❌ Noto‘g‘ri qiymat.")


@dp.message(Command("ban"))
async def admin_ban(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer("/ban USER_ID")
        return

    try:
        user_id = int(parts[1])

        con = connect()
        cur = con.cursor()

        cur.execute(
            "UPDATE users SET banned=1 WHERE id=?",
            (user_id,)
        )

        con.commit()
        con.close()

        await message.answer(f"🚫 {user_id} ban qilindi.")

    except ValueError:
        await message.answer("❌ ID noto‘g‘ri.")


@dp.message(Command("unban"))
async def admin_unban(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer("/unban USER_ID")
        return

    try:
        user_id = int(parts[1])

        con = connect()
        cur = con.cursor()

        cur.execute(
            "UPDATE users SET banned=0 WHERE id=?",
            (user_id,)
        )

        con.commit()
        con.close()

        await message.answer(f"✅ {user_id} unban qilindi.")

    except ValueError:
        await message.answer("❌ ID noto‘g‘ri.")


# =========================================================
# UNKNOWN COMMANDS / BAN CHECK
# =========================================================

@dp.message()
async def all_messages(message: Message):

    add_user(message.from_user)

    if is_banned(message.from_user.id):
        await message.answer(
            "🚫 Siz botdan foydalanishingiz bloklangan."
        )
        return

    await message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=main_menu(message.from_user.id)
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    init_db()

    print("BOT ISHLAMOQDA...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
