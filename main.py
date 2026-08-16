import asyncio
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8611335484:AAHoH8mg1OO9V7PDB3wUlZ6wU3HxsQx7avY")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

ADMIN_ID = int(os.getenv("ADMIN_ID", "5815294733"))

VIP_PRICE = 30000
VIP_DAYS = 7

CARD_NUMBER = "9860606750247151"
CARD_OWNER = "Abidjanov H"

DB_FILE = "bot.db"
SESSION_FILE = "telegram_search_session"


# ============================================================
# BOT / TELEGRAM CLIENT
# ============================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

tg = TelegramClient(
    SESSION_FILE,
    API_ID,
    API_HASH
)


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            joined_at TEXT,
            vip_until TEXT DEFAULT '',
            banned INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query TEXT,
            created_at TEXT
        )
    """)

    con.commit()
    con.close()


def add_user(user):
    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        datetime.now().isoformat()
    ))

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


def is_banned(user_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT banned FROM users WHERE id=?",
        (user_id,)
    )

    row = cur.fetchone()
    con.close()

    return bool(row and row[0])


def vip_active(user_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT vip_until FROM users WHERE id=?",
        (user_id,)
    )

    row = cur.fetchone()
    con.close()

    if not row or not row[0]:
        return False

    try:
        return datetime.fromisoformat(row[0]) > datetime.now()
    except Exception:
        return False


def vip_until(user_id):
    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT vip_until FROM users WHERE id=?",
        (user_id,)
    )

    row = cur.fetchone()
    con.close()

    return row[0] if row else ""


def give_vip(user_id, days=VIP_DAYS):
    now = datetime.now()

    old = vip_until(user_id)

    if old:
        try:
            old_dt = datetime.fromisoformat(old)
            if old_dt > now:
                until = old_dt + timedelta(days=days)
            else:
                until = now + timedelta(days=days)
        except Exception:
            until = now + timedelta(days=days)
    else:
        until = now + timedelta(days=days)

    con = db()
    cur = con.cursor()

    cur.execute(
        "UPDATE users SET vip_until=? WHERE id=?",
        (until.isoformat(), user_id)
    )

    con.commit()
    con.close()

    return until


def create_payment(user_id):
    con = db()
    cur = con.cursor()

    # Bitta pending ariza bo'lsa yangi ariza yaratmaymiz
    cur.execute("""
        SELECT id FROM payments
        WHERE user_id=? AND status='pending'
    """, (user_id,))

    existing = cur.fetchone()

    if existing:
        con.close()
        return existing[0]

    cur.execute("""
        INSERT INTO payments
        (user_id, amount, status, created_at)
        VALUES (?, ?, 'pending', ?)
    """, (
        user_id,
        VIP_PRICE,
        datetime.now().isoformat()
    ))

    payment_id = cur.lastrowid

    con.commit()
    con.close()

    return payment_id


def get_payment(payment_id):
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount, status, created_at
        FROM payments
        WHERE id=?
    """, (payment_id,))

    row = cur.fetchone()
    con.close()

    return row


def update_payment(payment_id, status):
    con = db()
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

    return changed


def pending_payments():
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount, created_at
        FROM payments
        WHERE status='pending'
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    con.close()

    return rows


def save_search(user_id, query):
    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO searches
        (user_id, query, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        query,
        datetime.now().isoformat()
    ))

    con.commit()
    con.close()


# ============================================================
# KEYBOARDS
# ============================================================

def main_menu(user_id):

    buttons = [
        [
            InlineKeyboardButton(
                text="🔎 Qidirish",
                callback_data="search"
            )
        ],
        [
            InlineKeyboardButton(
                text="💳 Hisob to‘ldirish",
                callback_data="deposit"
            ),
            InlineKeyboardButton(
                text="⭐ VIP",
                callback_data="vip"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Profilim",
                callback_data="myprofile"
            ),
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

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


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


def search_sections(username):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Profil",
                    callback_data=f"profile:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Public guruhlar",
                    callback_data=f"groups:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Kanallar",
                    callback_data=f"channels:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Ochiq xabarlar",
                    callback_data=f"messages:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🕐 Faoliyat",
                    callback_data=f"activity:{username}"
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


def admin_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 To‘lovlar",
                    callback_data="admin_payments"
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
                    text="📊 Statistika",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="admin_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Ban / Unban",
                    callback_data="admin_ban_help"
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


# ============================================================
# TELEGRAM PUBLIC SEARCH
# ============================================================

async def resolve_user(username):

    username = username.strip().lstrip("@")

    try:
        entity = await tg.get_entity(username)

        return entity

    except (
        UsernameInvalidError,
        UsernameNotOccupiedError
    ):
        return None

    except Exception:
        return None


async def public_profile(username):

    entity = await resolve_user(username)

    if entity is None:
        return None

    result = {
        "type": type(entity).__name__,
        "id": getattr(entity, "id", None),
        "username": getattr(entity, "username", None),
        "first_name": getattr(entity, "first_name", None),
        "last_name": getattr(entity, "last_name", None),
        "title": getattr(entity, "title", None),
        "about": getattr(entity, "about", None),
        "phone": None,
    }

    # Telefonni boshqa foydalanuvchilardan chiqarishga urinmaymiz.
    return result


async def public_channels(username):

    entity = await resolve_user(username)

    if entity is None:
        return []

    results = []

    # Agar qidirilgan username kanal/guruh bo'lsa,
    # o'zining public ma'lumotini ko'rsatamiz.
    title = getattr(entity, "title", None)
    uname = getattr(entity, "username", None)

    if title:
        results.append({
            "title": title,
            "username": uname,
            "id": getattr(entity, "id", None)
        })

    return results


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start(message: Message):

    add_user(message.from_user)

    if is_banned(message.from_user.id):
        await message.answer(
            "🚫 Sizning akkauntingiz bloklangan."
        )
        return

    await message.answer(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "🔎 Public Telegram ma’lumotlarini "
        "qidirish tizimi.\n\n"
        "⭐ VIP xizmatidan foydalanish uchun "
        "VIP faollashtiring.",
        parse_mode="HTML",
        reply_markup=main_menu(
            message.from_user.id
        )
    )


# ============================================================
# SEARCH
# ============================================================

@dp.callback_query(F.data == "search")
async def search_start(call: CallbackQuery):

    if is_banned(call.from_user.id):
        await call.answer(
            "🚫 Siz bloklangansiz.",
            show_alert=True
        )
        return

    if not vip_active(call.from_user.id):

        await call.message.edit_text(
            "🔒 <b>Qidiruv VIP uchun mavjud.</b>\n\n"
            f"💰 VIP: {VIP_PRICE:,} so‘m\n"
            f"📅 Muddat: {VIP_DAYS} kun",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⭐ VIP olish",
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
        return

    await call.message.edit_text(
        "🔎 <b>Qidiruv</b>\n\n"
        "Telegram username yuboring.\n\n"
        "Masalan:\n"
        "<code>@username</code>",
        parse_mode="HTML",
        reply_markup=back_button()
    )

    await call.answer()


@dp.message(F.text.startswith("@"))
async def username_received(message: Message):

    add_user(message.from_user)

    if is_banned(message.from_user.id):
        await message.answer(
            "🚫 Siz bloklangansiz."
        )
        return

    if not vip_active(message.from_user.id):
        await message.answer(
            "🔒 Qidiruv uchun VIP kerak."
        )
        return

    username = message.text.strip().lstrip("@")

    if not username:
        await message.answer(
            "❌ Username noto‘g‘ri."
        )
        return

    save_search(
        message.from_user.id,
        username
    )

    await message.answer(
        f"🔎 <b>@{username}</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# PROFILE
# ============================================================

@dp.callback_query(F.data.startswith("profile:"))
async def profile_result(call: CallbackQuery):

    username = call.data.split(":", 1)[1]

    await call.answer(
        "🔎 Tekshirilmoqda..."
    )

    data = await public_profile(username)

    if not data:

        await call.message.edit_text(
            "👤 <b>PROFIL</b>\n\n"
            f"🔎 @{username}\n\n"
            "❌ Public profil topilmadi.",
            parse_mode="HTML",
            reply_markup=search_sections(username)
        )
        return

    text = (
        "👤 <b>PROFIL</b>\n\n"
        f"🆔 ID: <code>{data['id']}</code>\n"
        f"👤 Username: "
        f"@{data['username'] or '—'}\n"
        f"📝 Ism: "
        f"{data['first_name'] or '—'}\n"
        f"📝 Familiya: "
        f"{data['last_name'] or '—'}\n"
    )

    if data["about"]:
        text += (
            f"\n📄 Bio:\n"
            f"{data['about'][:500]}\n"
        )

    text += (
        "\nℹ️ Faqat Telegram orqali "
        "ko‘rinadigan ma’lumotlar ko‘rsatildi."
    )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# GROUPS
# ============================================================

@dp.callback_query(F.data.startswith("groups:"))
async def groups_result(call: CallbackQuery):

    username = call.data.split(":", 1)[1]

    await call.answer(
        "🔎 Tekshirilmoqda..."
    )

    entity = await resolve_user(username)

    if entity is None:

        text = (
            "👥 <b>PUBLIC GURUHLAR</b>\n\n"
            "❌ Ma’lumot topilmadi."
        )

    else:

        title = getattr(entity, "title", None)

        if title:

            uname = getattr(
                entity,
                "username",
                None
            )

            text = (
                "👥 <b>PUBLIC GURUH</b>\n\n"
                f"📌 {title}\n"
            )

            if uname:
                text += (
                    f"🔗 https://t.me/{uname}\n"
                )

        else:

            text = (
                "👥 <b>PUBLIC GURUHLAR</b>\n\n"
                "Telegram API ushbu username "
                "uchun foydalanuvchining barcha "
                "guruh a'zoligini bermadi.\n\n"
                "❗ Noto‘g‘ri ma’lumot chiqarilmaydi."
            )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# CHANNELS
# ============================================================

@dp.callback_query(F.data.startswith("channels:"))
async def channels_result(call: CallbackQuery):

    username = call.data.split(":", 1)[1]

    await call.answer(
        "🔎 Tekshirilmoqda..."
    )

    channels = await public_channels(username)

    if not channels:

        text = (
            "📢 <b>KANALLAR</b>\n\n"
            "❌ Public kanal topilmadi."
        )

    else:

        text = "📢 <b>KANALLAR</b>\n\n"

        for channel in channels:

            text += (
                f"📢 <b>{channel['title']}</b>\n"
            )

            if channel["username"]:
                text += (
                    f"🔗 https://t.me/"
                    f"{channel['username']}\n\n"
                )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# PUBLIC MESSAGES
# ============================================================

@dp.callback_query(F.data.startswith("messages:"))
async def messages_result(call: CallbackQuery):

    username = call.data.split(":", 1)[1]

    await call.answer(
        "🔎 Tekshirilmoqda..."
    )

    await call.message.edit_text(
        "💬 <b>OCHIQ XABARLAR</b>\n\n"
        f"🔎 @{username}\n\n"
        "Bu bo‘lim faqat public yoki "
        "qidirish mumkin bo‘lgan xabarlar "
        "uchun ishlatiladi.\n\n"
        "🔒 Private chatlar va yopiq "
        "xabarlar olinmaydi.",
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# ACTIVITY
# ============================================================

@dp.callback_query(F.data.startswith("activity:"))
async def activity_result(call: CallbackQuery):

    username = call.data.split(":", 1)[1]

    await call.answer(
        "🔎 Tekshirilmoqda..."
    )

    await call.message.edit_text(
        "🕐 <b>FAOLIYAT</b>\n\n"
        f"🔎 @{username}\n\n"
        "Telegram oddiy botga boshqa "
        "foydalanuvchining to‘liq online "
        "tarixini bermaydi.\n\n"
        "Shuning uchun soxta vaqtlar "
        "chiqarilmaydi.",
        parse_mode="HTML",
        reply_markup=search_sections(username)
    )


# ============================================================
# VIP
# ============================================================

@dp.callback_query(F.data == "vip")
async def vip_menu(call: CallbackQuery):

    status = (
        "✅ Faol"
        if vip_active(call.from_user.id)
        else "❌ Faol emas"
    )

    until = vip_until(call.from_user.id)

    text = (
        "⭐ <b>VIP</b>\n\n"
        f"💰 Narx: <b>{VIP_PRICE:,} so‘m</b>\n"
        f"📅 Muddat: <b>{VIP_DAYS} kun</b>\n"
        f"📌 Holat: {status}\n"
    )

    if until:
        text += (
            f"⏰ Tugash vaqti:\n"
            f"{until[:19]}\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 Hisob to‘ldirish",
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


# ============================================================
# DEPOSIT
# ============================================================

@dp.callback_query(F.data == "deposit")
async def deposit(call: CallbackQuery):

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id FROM payments
        WHERE user_id=? AND status='pending'
    """, (call.from_user.id,))

    pending = cur.fetchone()

    con.close()

    if pending:

        await call.message.edit_text(
            "⏳ <b>Arizangiz allaqachon yuborilgan.</b>\n\n"
            "Admin tasdiqlashini kuting.\n\n"
            "Yangi ariza yuborish uchun avvalgi "
            "ariza ko‘rib chiqilishi kerak.",
            parse_mode="HTML",
            reply_markup=back_button()
        )

        return

    payment_id = create_payment(
        call.from_user.id
    )

    await call.message.edit_text(
        "💳 <b>HISOB TO‘LDIRISH</b>\n\n"
        f"💰 To‘lov: <b>{VIP_PRICE:,} so‘m</b>\n\n"
        "💳 Karta:\n"
        f"<code>{CARD_NUMBER}</code>\n"
        f"👤 {CARD_OWNER}\n\n"
        "To‘lovni amalga oshirgach "
        "<b>“To‘lov qildim”</b> tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ To‘lov qildim",
                        callback_data=f"paid:{payment_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Bekor qilish",
                        callback_data="back"
                    )
                ]
            ]
        )
    )


@dp.callback_query(F.data.startswith("paid:"))
async def paid(call: CallbackQuery):

    payment_id = int(
        call.data.split(":", 1)[1]
    )

    payment = get_payment(payment_id)

    if not payment:
        await call.answer(
            "Ariza topilmadi.",
            show_alert=True
        )
        return

    _, user_id, amount, status, created = payment

    if user_id != call.from_user.id:
        await call.answer(
            "🚫 Bu ariza sizniki emas.",
            show_alert=True
        )
        return

    if status != "pending":

        await call.answer(
            "Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    admin_text = (
        "💰 <b>YANGI TO‘LOV</b>\n\n"
        f"🧾 Ariza: <code>#{payment_id}</code>\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💰 Summa: <b>{amount:,} so‘m</b>\n"
        f"🕐 {created[:19]}"
    )

    keyboard = InlineKeyboardMarkup(
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
        admin_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await call.message.edit_text(
        "📨 <b>Arizangiz yuborildi.</b>\n\n"
        "Admin tekshiruvini kuting.\n"
        "Tasdiqlanmaguncha yangi hisob "
        "to‘ldirish arizasini yubora olmaysiz.",
        parse_mode="HTML",
        reply_markup=back_button()
    )


# ============================================================
# ADMIN
# ============================================================

def admin_only(user_id):
    return user_id == ADMIN_ID


@dp.callback_query(F.data == "admin")
async def admin_panel(call: CallbackQuery):

    if not admin_only(call.from_user.id):

        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "🛠 <b>ADMIN PANEL</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# ============================================================
# APPROVE PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_payment(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    payment_id = int(
        call.data.split(":", 1)[1]
    )

    payment = get_payment(payment_id)

    if not payment:
        await call.answer(
            "Ariza topilmadi.",
            show_alert=True
        )
        return

    _, user_id, amount, status, created = payment

    if status != "pending":

        await call.answer(
            "Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    changed = update_payment(
        payment_id,
        "approved"
    )

    if changed == 0:
        await call.answer(
            "Ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    until = give_vip(
        user_id,
        VIP_DAYS
    )

    # Admin xabarini yopamiz
    try:
        await call.message.edit_text(
            "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
            f"🧾 Ariza: #{payment_id}\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 {amount:,} so‘m\n"
            f"⭐ VIP: {VIP_DAYS} kun\n"
            f"⏰ Tugaydi: {until:%Y-%m-%d %H:%M}",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await bot.send_message(
        user_id,
        "🎉 <b>To‘lovingiz tasdiqlandi!</b>\n\n"
        f"⭐ VIP <b>{VIP_DAYS} kunga</b> ochildi.\n"
        f"⏰ Tugash: <b>{until:%Y-%m-%d %H:%M}</b>\n\n"
        "Endi 🔎 Qidirish bo‘limidan "
        "foydalanishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )


# ============================================================
# REJECT PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_payment(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    payment_id = int(
        call.data.split(":", 1)[1]
    )

    payment = get_payment(payment_id)

    if not payment:
        await call.answer(
            "Ariza topilmadi.",
            show_alert=True
        )
        return

    _, user_id, amount, status, created = payment

    if status != "pending":

        await call.answer(
            "Bu ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    changed = update_payment(
        payment_id,
        "rejected"
    )

    if changed == 0:
        await call.answer(
            "Ariza allaqachon ko‘rib chiqilgan.",
            show_alert=True
        )
        return

    try:
        await call.message.edit_text(
            "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
            f"🧾 Ariza: #{payment_id}\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 {amount:,} so‘m",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await bot.send_message(
        user_id,
        "❌ <b>To‘lov arizangiz rad etildi.</b>\n\n"
        "Agar xato bo‘lgan deb hisoblasangiz, "
        "admin bilan bog‘laning.\n\n"
        "Yangi ariza yuborishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )


# ============================================================
# ADMIN PAYMENTS
# ============================================================

@dp.callback_query(F.data == "admin_payments")
async def admin_payments(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    rows = pending_payments()

    if not rows:

        text = (
            "💰 <b>TO‘LOVLAR</b>\n\n"
            "📭 Kutilayotgan to‘lov yo‘q."
        )

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=admin_menu()
        )

        return

    text = "💰 <b>KUTILAYOTGAN TO‘LOVLAR</b>\n\n"

    buttons = []

    for payment_id, user_id, amount, created in rows:

        text += (
            f"🧾 #{payment_id}\n"
            f"👤 <code>{user_id}</code>\n"
            f"💰 {amount:,} so‘m\n"
            f"🕐 {created[:19]}\n\n"
        )

        buttons.append([
            InlineKeyboardButton(
                text=f"#{payment_id} ✅",
                callback_data=f"approve:{payment_id}"
            ),
            InlineKeyboardButton(
                text=f"#{payment_id} ❌",
                callback_data=f"reject:{payment_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Admin panel",
            callback_data="admin"
        )
    ])

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# ============================================================
# ADMIN USERS
# ============================================================

@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name, vip_until, banned
        FROM users
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()

    con.close()

    if not rows:

        text = "👥 Userlar hali yo‘q."

    else:

        text = "👥 <b>OXIRGI USERLAR</b>\n\n"

        for row in rows:

            uid, username, name, vip, banned = row

            text += (
                f"🆔 <code>{uid}</code>\n"
                f"👤 @{username or '—'}\n"
                f"📝 {name or '—'}\n"
                f"⭐ {'✅' if vip_active(uid) else '❌'}\n"
                f"🚫 {'Ha' if banned else 'Yo‘q'}\n\n"
            )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# ============================================================
# ADMIN STATS
# ============================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )
    users = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM users WHERE banned=1"
    )
    banned = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM payments WHERE status='approved'"
    )
    approved = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM payments WHERE status='pending'"
    )
    pending = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM searches"
    )
    searches = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Userlar: <b>{users}</b>\n"
        f"🚫 Ban: <b>{banned}</b>\n"
        f"💰 Tasdiqlangan to‘lovlar: <b>{approved}</b>\n"
        f"⏳ Kutilayotgan to‘lovlar: <b>{pending}</b>\n"
        f"🔎 Qidiruvlar: <b>{searches}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


# ============================================================
# ADMIN BAN HELP
# ============================================================

@dp.callback_query(F.data == "admin_ban_help")
async def admin_ban_help(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "🚫 <b>BAN / UNBAN</b>\n\n"
        "Admin chatiga quyidagilarni yozing:\n\n"
        "<code>/ban USER_ID</code>\n"
        "<code>/unban USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


@dp.message(Command("ban"))
async def ban_user(message: Message):

    if not admin_only(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n<code>/ban USER_ID</code>",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ ID noto‘g‘ri."
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute(
        "UPDATE users SET banned=1 WHERE id=?",
        (user_id,)
    )

    con.commit()
    changed = cur.rowcount
    con.close()

    await message.answer(
        "✅ Ban qilindi."
        if changed
        else "❌ User topilmadi."
    )


@dp.message(Command("unban"))
async def unban_user(message: Message):

    if not admin_only(message.from_user.id):
        return

    parts = message.text.split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n<code>/unban USER_ID</code>",
            parse_mode="HTML"
        )
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ ID noto‘g‘ri."
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute(
        "UPDATE users SET banned=0 WHERE id=?",
        (user_id,)
    )

    con.commit()
    changed = cur.rowcount
    con.close()

    await message.answer(
        "✅ Unban qilindi."
        if changed
        else "❌ User topilmadi."
    )


# ============================================================
# BROADCAST
# ============================================================

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_help(call: CallbackQuery):

    if not admin_only(call.from_user.id):
        await call.answer(
            "🚫 Faqat admin!",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Admin sifatida yozing:\n"
        "<code>/broadcast Sizning xabaringiz</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


@dp.message(Command("broadcast"))
async def broadcast(message: Message):

    if not admin_only(message.from_user.id):
        return

    text = message.text[
        len("/broadcast"):
    ].strip()

    if not text:
        await message.answer(
            "❌ Xabar matni yo‘q."
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT id FROM users WHERE banned=0"
    )

    users = [
        row[0]
        for row in cur.fetchall()
    ]

    con.close()

    sent = 0

    for user_id in users:

        try:
            await bot.send_message(
                user_id,
                text
            )
            sent += 1

            await asyncio.sleep(0.05)

        except Exception:
            pass

    await message.answer(
        f"📢 Yuborildi: <b>{sent}</b>",
        parse_mode="HTML"
    )


# ============================================================
# PROFILE
# ============================================================

@dp.callback_query(F.data == "myprofile")
async def myprofile(call: CallbackQuery):

    user_id = call.from_user.id

    status = (
        "✅ Faol"
        if vip_active(user_id)
        else "❌ Faol emas"
    )

    until = vip_until(user_id)

    text = (
        "👤 <b>PROFILIM</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: "
        f"@{call.from_user.username or '—'}\n"
        f"⭐ VIP: {status}\n"
    )

    if until:
        text += (
            f"⏰ Tugashi: "
            f"{until[:19]}\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )


# ============================================================
# HELP
# ============================================================

@dp.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    await call.message.edit_text(
        "ℹ️ <b>YORDAM</b>\n\n"
        "1️⃣ ⭐ VIP oling\n"
        "2️⃣ 🔎 Qidirish tugmasini bosing\n"
        "3️⃣ @username yuboring\n"
        "4️⃣ Kerakli bo‘limni tanlang\n\n"
        "🔐 Bot faqat mavjud/public "
        "Telegram ma’lumotlarini ko‘rsatadi.\n\n"
        "Private chat, yopiq guruh va "
        "yashirin online tarixlar "
        "soxta tarzda ko‘rsatilmaydi.",
        parse_mode="HTML",
        reply_markup=main_menu(
            call.from_user.id
        )
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):

    await call.message.edit_text(
        "🏠 <b>ASOSIY MENYU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(
            call.from_user.id
        )
    )

    await call.answer()


# ============================================================
# MAIN
# ============================================================

async def main():

    if BOT_TOKEN == "BU_YERGA_BOT_TOKEN":
        print("BOT_TOKEN sozlanmagan!")
        return

    if API_ID == 0 or not API_HASH:
        print("API_ID / API_HASH sozlanmagan!")
        return

    init_db()

    print("Telegram client ishga tushmoqda...")

    await tg.start()

    print("Bot ishga tushdi.")

    try:
        await dp.start_polling(bot)

    finally:
        await tg.disconnect()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
