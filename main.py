import asyncio
import sqlite3
import html
from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ddgs import DDGS


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = "8611335484:AAHoH8mg1OO9V7PDB3wUlZ6wU3HxsQx7avY"
ADMIN_ID = 5815294733

CARD_NUMBER = "9860606750247151"
CARD_NAME = "Abidjanov H"

VIP_PRICE = 30000
VIP_DAYS = 7

DB_FILE = "bot.db"


if BOT_TOKEN == "BU_YERGA_BOT_TOKEN":
    raise RuntimeError("BOT_TOKEN ni main.py ichiga yozing")


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# DATABASE
# ============================================================

def connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    con = connect()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            balance INTEGER DEFAULT 0,
            vip_until TEXT DEFAULT '',
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
            created_at TEXT
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


# ============================================================
# USER DATABASE
# ============================================================

def save_user(user):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users
        (id, username, first_name, created_at)
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


def get_user(user_id):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name, balance,
               vip_until, banned, created_at
        FROM users
        WHERE id=?
    """, (user_id,))

    row = cur.fetchone()
    con.close()

    return row


def find_users(query):
    query = query.strip().lstrip("@")

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name,
               balance, vip_until, banned
        FROM users
        WHERE username LIKE ?
           OR CAST(id AS TEXT) LIKE ?
           OR first_name LIKE ?
        LIMIT 20
    """, (
        f"%{query}%",
        f"%{query}%",
        f"%{query}%"
    ))

    rows = cur.fetchall()
    con.close()

    return rows


def all_user_ids():
    con = connect()
    cur = con.cursor()

    cur.execute("SELECT id FROM users WHERE banned=0")

    rows = [x[0] for x in cur.fetchall()]

    con.close()

    return rows


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


def set_banned(user_id, value):
    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET banned=?
        WHERE id=?
    """, (value, user_id))

    con.commit()
    con.close()


def set_vip(user_id, days):
    user = get_user(user_id)

    if not user:
        return None

    now = datetime.now()

    if user[4]:
        try:
            old = datetime.fromisoformat(user[4])
            if old > now:
                now = old
        except:
            pass

    until = now + timedelta(days=days)

    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET vip_until=?
        WHERE id=?
    """, (
        until.isoformat(),
        user_id
    ))

    con.commit()
    con.close()

    return until


def is_vip(user_id):
    user = get_user(user_id)

    if not user or not user[4]:
        return False

    try:
        return datetime.fromisoformat(user[4]) > datetime.now()
    except:
        return False


# ============================================================
# SEARCH DATABASE
# ============================================================

def save_search(user_id, query):
    con = connect()
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
# REAL WEB SEARCH
# ============================================================

def web_search(username, mode="all"):
    """
    Faqat ochiq web/indexlangan natijalarni qidiradi.
    """

    username = username.strip().lstrip("@")

    if not username:
        return []

    queries = []

    if mode == "groups":
        queries = [
            f'site:t.me "{username}" group',
            f'"@{username}" group Telegram'
        ]

    elif mode == "channels":
        queries = [
            f'site:t.me "{username}" channel',
            f'"@{username}" channel Telegram'
        ]

    elif mode == "messages":
        queries = [
            f'site:t.me "{username}"',
            f'"@{username}" Telegram'
        ]

    elif mode == "web":
        queries = [
            f'"@{username}"',
            f'"{username}"'
        ]

    else:
        queries = [
            f'"@{username}"',
            f'"{username}" Telegram',
            f'site:t.me "{username}"'
        ]

    results = []
    seen = set()

    try:
        with DDGS() as search:

            for query in queries:

                try:
                    data = search.text(
                        query,
                        max_results=8
                    )
                except Exception as e:
                    print("SEARCH QUERY ERROR:", e)
                    continue

                for item in data:

                    url = item.get("href") or item.get("url")

                    if not url:
                        continue

                    if url in seen:
                        continue

                    seen.add(url)

                    results.append({
                        "title": item.get(
                            "title",
                            "Nomsiz"
                        ),
                        "url": url,
                        "body": item.get(
                            "body",
                            ""
                        )
                    })

                    if len(results) >= 20:
                        return results

    except Exception as e:
        print("SEARCH ERROR:", e)

    return results


async def async_search(username, mode):
    loop = asyncio.get_running_loop()

    return await loop.run_in_executor(
        None,
        web_search,
        username,
        mode
    )


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

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def back():
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


def search_menu(username):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Profil",
                    callback_data=f"sprofile:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Guruhlar",
                    callback_data=f"sgroups:{username}"
                ),
                InlineKeyboardButton(
                    text="📢 Kanallar",
                    callback_data=f"schannels:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Ochiq xabarlar",
                    callback_data=f"smsgs:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🕐 Faollik",
                    callback_data=f"sactivity:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Web",
                    callback_data=f"sweb:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Username izlari",
                    callback_data=f"sall:{username}"
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


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start(message: Message):

    save_user(message.from_user)

    user = get_user(message.from_user.id)

    if user and user[5]:
        await message.answer(
            "🚫 Siz botdan foydalanishingiz bloklangansiz."
        )
        return

    await message.answer(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "🔎 User qidirish uchun qidiruv bo‘limidan foydalaning.\n\n"
        "Faqat ochiq manbalardagi ma'lumotlar ko‘rsatiladi.",
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
    )


# ============================================================
# SEARCH BUTTON
# ============================================================

@dp.callback_query(F.data == "search")
async def search_button(call: CallbackQuery):

    if not is_vip(call.from_user.id):

        await call.message.edit_text(
            "🔒 <b>VIP KERAK</b>\n\n"
            "Qidiruv funksiyasi VIP foydalanuvchilar uchun.\n\n"
            "⭐ 30 kunlik VIP: <b>30 000 so‘m</b>",
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

    await call.message.edit_text(
        "🔎 <b>QIDIRISH</b>\n\n"
        "👤 Username yuboring.\n\n"
        "Masalan:\n"
        "<code>@fon_abidjan</code>",
        parse_mode="HTML",
        reply_markup=back()
    )

    await call.answer()


# ============================================================
# RECEIVE USERNAME
# ============================================================

@dp.message(F.text.startswith("@"))
async def receive_username(message: Message):

    save_user(message.from_user)

    if not is_vip(message.from_user.id):

        await message.answer(
            "🔒 Qidiruv uchun VIP kerak."
        )
        return

    username = message.text.strip().lstrip("@")

    if len(username) < 3:
        await message.answer(
            "❌ Username juda qisqa."
        )
        return

    save_search(
        message.from_user.id,
        username
    )

    await message.answer(
        "🔎 <b>QIDIRUV BAJARILDI</b>\n\n"
        f"👤 <code>@{html.escape(username)}</code>\n\n"
        "Quyidagi bo‘limlardan keraklisini tanlang:",
        parse_mode="HTML",
        reply_markup=search_menu(username)
    )


# ============================================================
# SEARCH SECTIONS
# ============================================================

async def section_search(
    call,
    username,
    mode,
    title
):

    await call.answer("🔎 Qidirilmoqda...")

    msg = await call.message.edit_text(
        "🔎 <b>QIDIRILMOQDA...</b>\n\n"
        f"👤 @{html.escape(username)}\n"
        f"📂 {title}",
        parse_mode="HTML"
    )

    results = await async_search(
        username,
        mode
    )

    if not results:

        await msg.edit_text(
            f"{title}\n\n"
            "❌ Ochiq manbalardan ma'lumot topilmadi.",
            reply_markup=search_menu(username)
        )

        return

    text = (
        f"{title}\n\n"
        f"👤 <code>@{html.escape(username)}</code>\n"
        f"📊 Topildi: <b>{len(results)}</b>\n\n"
    )

    buttons = []

    for i, item in enumerate(results[:10], 1):

        title_text = html.escape(
            item["title"][:100]
        )

        body = html.escape(
            item["body"][:250]
        )

        text += (
            f"<b>{i}. {title_text}</b>\n"
        )

        if body:
            text += f"{body}\n"

        text += "\n"

        buttons.append([
            InlineKeyboardButton(
                text=f"🔗 {i}-manba",
                url=item["url"]
            )
        ])

    if len(text) > 3900:
        text = text[:3900] + "\n..."

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Qidiruv menyusi",
            callback_data=f"searchmenu:{username}"
        )
    ])

    await msg.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


@dp.callback_query(F.data.startswith("sgroups:"))
async def groups(call):
    username = call.data.split(":", 1)[1]

    await section_search(
        call,
        username,
        "groups",
        "👥 GURUHLAR"
    )


@dp.callback_query(F.data.startswith("schannels:"))
async def channels(call):
    username = call.data.split(":", 1)[1]

    await section_search(
        call,
        username,
        "channels",
        "📢 KANALLAR"
    )


@dp.callback_query(F.data.startswith("smsgs:"))
async def messages_search(call):
    username = call.data.split(":", 1)[1]

    await section_search(
        call,
        username,
        "messages",
        "💬 OCHIQ XABARLAR"
    )


@dp.callback_query(F.data.startswith("sweb:"))
async def web_section(call):
    username = call.data.split(":", 1)[1]

    await section_search(
        call,
        username,
        "web",
        "🌐 WEB"
    )


@dp.callback_query(F.data.startswith("sall:"))
async def all_section(call):
    username = call.data.split(":", 1)[1]

    await section_search(
        call,
        username,
        "all",
        "🔗 USERNAME IZLARI"
    )


# ============================================================
# PROFILE SEARCH
# ============================================================

@dp.callback_query(F.data.startswith("sprofile:"))
async def profile_search(call):

    username = call.data.split(":", 1)[1]

    results = await async_search(
        username,
        "all"
    )

    text = (
        "👤 <b>PROFIL</b>\n\n"
        f"🔎 Username: <code>@{html.escape(username)}</code>\n\n"
    )

    if not results:
        text += (
            "❌ Ochiq manbalardan profilga oid "
            "tasdiqlangan natija topilmadi."
        )

    else:

        text += "🌐 Ochiq manbalarda topilgan:\n\n"

        for item in results[:5]:

            text += (
                f"• <b>{html.escape(item['title'][:100])}</b>\n"
                f"{html.escape(item['body'][:200])}\n\n"
            )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_menu(username)
    )

    await call.answer()


# ============================================================
# ACTIVITY
# ============================================================

@dp.callback_query(F.data.startswith("sactivity:"))
async def activity(call):

    username = call.data.split(":", 1)[1]

    await call.answer("🔎 Tahlil qilinmoqda...")

    results = await async_search(
        username,
        "messages"
    )

    text = (
        "🕐 <b>FAOLLIK TAHLILI</b>\n\n"
        f"👤 @{html.escape(username)}\n\n"
    )

    if not results:

        text += (
            "❌ Yetarli ochiq xabar topilmadi."
        )

    else:

        text += (
            f"📊 Ochiq manbalardan topilgan "
            f"natijalar: <b>{len(results)}</b>\n\n"
            "⚠️ Bu online-history emas.\n"
            "Tahlil faqat ochiq web xabarlarining "
            "ko‘rinadigan sana/vaqtlariga bog‘liq.\n\n"
            "🌐 Manbalar:\n"
        )

        for item in results[:8]:

            text += (
                f"• {html.escape(item['title'][:100])}\n"
            )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_menu(username)
    )


# ============================================================
# SEARCH MENU
# ============================================================

@dp.callback_query(F.data.startswith("searchmenu:"))
async def search_menu_back(call):

    username = call.data.split(":", 1)[1]

    await call.message.edit_text(
        "📋 <b>QIDIRUV BO‘LIMLARI</b>\n\n"
        f"👤 @{html.escape(username)}\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=search_menu(username)
    )

    await call.answer()


# ============================================================
# PROFILE
# ============================================================

@dp.callback_query(F.data == "profile")
async def my_profile(call):

    user = get_user(call.from_user.id)

    vip = (
        "⭐ FAOL"
        if is_vip(call.from_user.id)
        else "🆓 FAOL EMAS"
    )

    await call.message.edit_text(
        "👤 <b>PROFILIM</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 Username: @{html.escape(user[1] or 'yo‘q')}\n"
        f"💰 Balans: <b>{user[3]:,} so‘m</b>\n"
        f"⭐ VIP: {vip}\n"
        f"⏰ VIP tugashi: "
        f"<code>{user[4] or '—'}</code>",
        parse_mode="HTML",
        reply_markup=back()
    )

    await call.answer()


# ============================================================
# VIP
# ============================================================

@dp.callback_query(F.data == "vip")
async def vip(call):

    if is_vip(call.from_user.id):

        user = get_user(call.from_user.id)

        await call.message.edit_text(
            "⭐ <b>VIP FAOL</b>\n\n"
            f"⏰ Tugashi:\n"
            f"<code>{user[4]}</code>",
            parse_mode="HTML",
            reply_markup=back()
        )

    else:

        await call.message.edit_text(
            "⭐ <b>VIP</b>\n\n"
            f"💰 Narxi: <b>{VIP_PRICE:,} so‘m</b>\n"
            f"📅 Muddat: <b>{VIP_DAYS} kun</b>\n\n"
            "VIP orqali qidiruv funksiyalaridan "
            "foydalanish mumkin.",
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


# ============================================================
# DEPOSIT
# ============================================================

@dp.callback_query(F.data == "deposit")
async def deposit(call):

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id
        FROM payments
        WHERE user_id=?
        AND status='pending'
        LIMIT 1
    """, (call.from_user.id,))

    pending = cur.fetchone()

    con.close()

    if pending:

        await call.message.edit_text(
            "⏳ <b>ARIZA TEKSHIRILMOQDA</b>\n\n"
            "Oldingi to‘lovingiz admin tomonidan "
            "ko‘rib chiqilmoqda.",
            parse_mode="HTML",
            reply_markup=back()
        )

        await call.answer()
        return

    await call.message.edit_text(
        "💰 <b>HISOB TO‘LDIRISH</b>\n\n"
        f"💵 Summa: <b>{VIP_PRICE:,} so‘m</b>\n\n"
        f"💳 Karta:\n"
        f"<code>{CARD_NUMBER}</code>\n"
        f"👤 Egasi: <b>{CARD_NAME}</b>\n\n"
        "To‘lovni amalga oshirgandan keyin "
        "tugmani bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ To‘lov qildim",
                        callback_data="payment_done"
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


@dp.callback_query(F.data == "payment_done")
async def payment_done(call):

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id
        FROM payments
        WHERE user_id=?
        AND status='pending'
        LIMIT 1
    """, (call.from_user.id,))

    existing = cur.fetchone()

    if existing:

        payment_id = existing[0]

    else:

        cur.execute("""
            INSERT INTO payments
            (user_id, amount, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (
            call.from_user.id,
            VIP_PRICE,
            "pending"
        ))

        payment_id = cur.lastrowid
        con.commit()

    con.close()

    user = get_user(call.from_user.id)

    username = (
        f"@{user[1]}"
        if user and user[1]
        else "username yo‘q"
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
        "🔔 <b>YANGI TO‘LOV</b>\n\n"
        f"🆔 Ariza: <code>#{payment_id}</code>\n"
        f"👤 {html.escape(username)}\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 <b>{VIP_PRICE:,} so‘m</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await call.message.edit_text(
        "⏳ <b>Arizangiz admin'ga yuborildi.</b>\n\n"
        "Admin to‘lovni tekshiradi.",
        parse_mode="HTML",
        reply_markup=back()
    )

    await call.answer("Yuborildi")


# ============================================================
# ADMIN APPROVE
# ============================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve(call):

    if call.from_user.id != ADMIN_ID:
        await call.answer(
            "🚫 Ruxsat yo‘q",
            show_alert=True
        )
        return

    payment_id = int(
        call.data.split(":")[1]
    )

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
    """, (payment_id,))

    payment = cur.fetchone()

    if not payment:
        con.close()
        await call.answer(
            "Topilmadi",
            show_alert=True
        )
        return

    user_id, amount, status = payment

    if status != "pending":
        con.close()

        await call.answer(
            "Bu ariza allaqachon ko‘rilgan",
            show_alert=True
        )
        return

    cur.execute("""
        UPDATE payments
        SET status='approved'
        WHERE id=? AND status='pending'
    """, (payment_id,))

    cur.execute("""
        UPDATE users
        SET balance=balance+?
        WHERE id=?
    """, (
        amount,
        user_id
    ))

    con.commit()
    con.close()

    until = set_vip(
        user_id,
        VIP_DAYS
    )

    await call.message.edit_text(
        "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
        f"🆔 #{payment_id}\n"
        f"💰 {amount:,} so‘m\n"
        f"⭐ VIP: {VIP_DAYS} kun\n\n"
        "🔒 Ariza yopildi.",
        parse_mode="HTML"
    )

    try:

        await bot.send_message(
            user_id,
            "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
            f"💰 Balans: +{amount:,} so‘m\n"
            f"⭐ VIP: {VIP_DAYS} kun\n"
            f"⏰ Tugashi: <code>{until}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        print("USER MESSAGE ERROR:", e)

    await call.answer("Tasdiqlandi")


# ============================================================
# ADMIN REJECT
# ============================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject(call):

    if call.from_user.id != ADMIN_ID:
        await call.answer(
            "🚫 Ruxsat yo‘q",
            show_alert=True
        )
        return

    payment_id = int(
        call.data.split(":")[1]
    )

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
    """, (payment_id,))

    payment = cur.fetchone()

    if not payment:
        con.close()
        await call.answer(
            "Topilmadi",
            show_alert=True
        )
        return

    user_id, amount, status = payment

    if status != "pending":
        con.close()

        await call.answer(
            "Bu ariza allaqachon ko‘rilgan",
            show_alert=True
        )
        return

    cur.execute("""
        UPDATE payments
        SET status='rejected'
        WHERE id=? AND status='pending'
    """, (payment_id,))

    con.commit()
    con.close()

    await call.message.edit_text(
        "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
        f"🆔 #{payment_id}\n"
        f"💰 {amount:,} so‘m\n\n"
        "🔒 Ariza yopildi.",
        parse_mode="HTML"
    )

    try:

        await bot.send_message(
            user_id,
            "❌ <b>To‘lovingiz rad etildi.</b>\n\n"
            "Qayta to‘lov arizasi yuborishingiz mumkin.",
            parse_mode="HTML"
        )

    except:
        pass

    await call.answer("Rad etildi")


# ============================================================
# ADMIN PANEL
# ============================================================

def admin_menu():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Userlar",
                    callback_data="ausers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔎 User qidirish",
                    callback_data="asearch"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 To‘lovlar",
                    callback_data="apayments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="astats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Balans qo‘shish",
                    callback_data="abalance_add"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➖ Balans ayirish",
                    callback_data="abalance_sub"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ VIP berish",
                    callback_data="avip"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Ban",
                    callback_data="aban"
                ),
                InlineKeyboardButton(
                    text="✅ Unban",
                    callback_data="aunban"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Xabar yuborish",
                    callback_data="abroadcast"
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


@dp.callback_query(F.data == "admin")
async def admin_panel(call):

    if call.from_user.id != ADMIN_ID:
        await call.answer(
            "🚫 Faqat admin",
            show_alert=True
        )
        return

    await call.message.edit_text(
        "🛠 <b>ADMIN PANEL</b>\n\n"
        "Kerakli funksiyani tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN STATS
# ============================================================

@dp.callback_query(F.data == "astats")
async def admin_stats(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = connect()
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE banned=1
    """)
    banned = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE vip_until > ?
    """, (
        datetime.now().isoformat(),
    ))

    vip = cur.fetchone()[0]

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

    cur.execute("""
        SELECT COUNT(*)
        FROM searches
    """)

    searches = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>ADMIN STATISTIKA</b>\n\n"
        f"👥 Userlar: <b>{users}</b>\n"
        f"⭐ VIP: <b>{vip}</b>\n"
        f"🚫 Ban: <b>{banned}</b>\n"
        f"⏳ Kutilayotgan to‘lov: <b>{pending}</b>\n"
        f"💰 Daromad: <b>{income:,} so‘m</b>\n"
        f"🔎 Qidiruvlar: <b>{searches}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN USERS
# ============================================================

@dp.callback_query(F.data == "ausers")
async def admin_users(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name,
               balance, vip_until, banned
        FROM users
        ORDER BY id DESC
        LIMIT 15
    """)

    rows = cur.fetchall()
    con.close()

    text = "👥 <b>OXIRGI USERLAR</b>\n\n"

    if not rows:
        text += "User yo‘q."

    for row in rows:

        uid, username, name, balance, vip, banned = row

        text += (
            f"🆔 <code>{uid}</code>\n"
            f"👤 @{html.escape(username or 'yo‘q')}\n"
            f"💰 {balance:,} so‘m\n"
            f"{'🚫 BAN' if banned else '✅ Aktiv'}\n\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN SEARCH
# ============================================================

@dp.callback_query(F.data == "asearch")
async def admin_search(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "🔎 <b>USER QIDIRISH</b>\n\n"
        "Username yoki Telegram ID yuboring.",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN TEXT COMMANDS
# ============================================================

@dp.message(F.text.regexp(r"^/user "))
async def admin_user_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    query = message.text[6:].strip()

    rows = find_users(query)

    if not rows:

        await message.answer(
            "❌ User topilmadi."
        )
        return

    for row in rows:

        uid, username, name, balance, vip, banned = row

        await message.answer(
            "👤 <b>USER</b>\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 @{html.escape(username or 'yo‘q')}\n"
            f"📝 {html.escape(name or '')}\n"
            f"💰 {balance:,} so‘m\n"
            f"⭐ VIP: {vip or 'yo‘q'}\n"
            f"{'🚫 BAN' if banned else '✅ Aktiv'}",
            parse_mode="HTML"
        )


# ============================================================
# ADMIN BALANCE COMMAND
# ============================================================

@dp.message(F.text.regexp(r"^/addbal "))
async def add_balance_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:

        await message.answer(
            "Format:\n"
            "/addbal USER_ID SUMMA"
        )
        return

    try:

        user_id = int(parts[1])
        amount = int(parts[2])

    except:

        await message.answer(
            "❌ ID yoki summa noto‘g‘ri."
        )
        return

    user = get_user(user_id)

    if not user:

        await message.answer(
            "❌ User topilmadi."
        )
        return

    add_balance(
        user_id,
        amount
    )

    await message.answer(
        f"✅ Balans qo‘shildi.\n\n"
        f"👤 {user_id}\n"
        f"💰 +{amount:,} so‘m"
    )


# ============================================================
# ADMIN VIP COMMAND
# ============================================================

@dp.message(F.text.regexp(r"^/vip "))
async def vip_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:

        await message.answer(
            "Format:\n"
            "/vip USER_ID KUN"
        )
        return

    try:

        user_id = int(parts[1])
        days = int(parts[2])

    except:

        await message.answer(
            "❌ Noto‘g‘ri."
        )
        return

    user = get_user(user_id)

    if not user:

        await message.answer(
            "❌ User topilmadi."
        )
        return

    until = set_vip(
        user_id,
        days
    )

    await message.answer(
        "⭐ VIP berildi.\n\n"
        f"👤 {user_id}\n"
        f"📅 {days} kun\n"
        f"⏰ {until}"
    )


# ============================================================
# BAN COMMAND
# ============================================================

@dp.message(F.text.regexp(r"^/ban "))
async def ban_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(
            message.text.split()[1]
        )
    except:
        await message.answer(
            "/ban USER_ID"
        )
        return

    set_banned(
        user_id,
        1
    )

    await message.answer(
        f"🚫 User {user_id} ban qilindi."
    )


# ============================================================
# UNBAN COMMAND
# ============================================================

@dp.message(F.text.regexp(r"^/unban "))
async def unban_command(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(
            message.text.split()[1]
        )
    except:
        await message.answer(
            "/unban USER_ID"
        )
        return

    set_banned(
        user_id,
        0
    )

    await message.answer(
        f"✅ User {user_id} unban qilindi."
    )


# ============================================================
# ADMIN BROADCAST
# ============================================================

@dp.message(F.text.regexp(r"^/broadcast "))
async def broadcast(message):

    if message.from_user.id != ADMIN_ID:
        return

    text = message.text[
        len("/broadcast "):
    ].strip()

    if not text:

        await message.answer(
            "Format:\n"
            "/broadcast Xabar"
        )
        return

    users = all_user_ids()

    success = 0
    failed = 0

    await message.answer(
        f"📢 {len(users)} ta userga yuborish boshlandi..."
    )

    for user_id in users:

        try:

            await bot.send_message(
                user_id,
                text
            )

            success += 1

        except:

            failed += 1

        await asyncio.sleep(0.05)

    await message.answer(
        "📢 <b>YAKUNLANDI</b>\n\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Xato: {failed}",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN PAYMENTS
# ============================================================

@dp.callback_query(F.data == "apayments")
async def admin_payments(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = connect()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount,
               status, created_at
        FROM payments
        ORDER BY id DESC
        LIMIT 15
    """)

    rows = cur.fetchall()

    con.close()

    text = "💳 <b>TO‘LOVLAR</b>\n\n"

    if not rows:

        text += "To‘lovlar yo‘q."

    for row in rows:

        pid, uid, amount, status, created = row

        if status == "pending":
            icon = "⏳"
        elif status == "approved":
            icon = "✅"
        else:
            icon = "❌"

        text += (
            f"{icon} #{pid}\n"
            f"👤 <code>{uid}</code>\n"
            f"💰 {amount:,} so‘m\n"
            f"📌 {status}\n\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN BALANCE BUTTONS
# ============================================================

@dp.callback_query(F.data == "abalance_add")
async def balance_add_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "➕ <b>BALANS QO‘SHISH</b>\n\n"
        "Format:\n"
        "<code>/addbal USER_ID SUMMA</code>\n\n"
        "Misol:\n"
        "<code>/addbal 123456789 50000</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.callback_query(F.data == "abalance_sub")
async def balance_sub_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "➖ <b>BALANS AYIRISH</b>\n\n"
        "Format:\n"
        "<code>/subbal USER_ID SUMMA</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.message(F.text.regexp(r"^/subbal "))
async def subtract_balance(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:

        await message.answer(
            "/subbal USER_ID SUMMA"
        )
        return

    try:

        user_id = int(parts[1])
        amount = int(parts[2])

    except:

        await message.answer(
            "❌ Noto‘g‘ri."
        )
        return

    user = get_user(user_id)

    if not user:

        await message.answer(
            "❌ User topilmadi."
        )
        return

    new_balance = max(
        0,
        user[3] - amount
    )

    con = connect()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance=?
        WHERE id=?
    """, (
        new_balance,
        user_id
    ))

    con.commit()
    con.close()

    await message.answer(
        f"✅ Balans ayirildi.\n\n"
        f"👤 {user_id}\n"
        f"💰 -{amount:,} so‘m\n"
        f"📊 Yangi balans: {new_balance:,} so‘m"
    )


# ============================================================
# ADMIN VIP BUTTON
# ============================================================

@dp.callback_query(F.data == "avip")
async def admin_vip_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "⭐ <b>VIP BERISH</b>\n\n"
        "Format:\n"
        "<code>/vip USER_ID KUN</code>\n\n"
        "Misol:\n"
        "<code>/vip 123456789 30</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# ADMIN BAN
# ============================================================

@dp.callback_query(F.data == "aban")
async def admin_ban_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "🚫 <b>BAN</b>\n\n"
        "<code>/ban USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


@dp.callback_query(F.data == "aunban")
async def admin_unban_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "✅ <b>UNBAN</b>\n\n"
        "<code>/unban USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# BROADCAST BUTTON
# ============================================================

@dp.callback_query(F.data == "abroadcast")
async def broadcast_info(call):

    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text(
        "📢 <b>XABAR YUBORISH</b>\n\n"
        "Format:\n"
        "<code>/broadcast Xabaringiz</code>",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )

    await call.answer()


# ============================================================
# STATISTICS
# ============================================================

@dp.callback_query(F.data == "stats")
async def public_stats(call):

    con = connect()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>",
        parse_mode="HTML",
        reply_markup=back()
    )

    await call.answer()


# ============================================================
# HELP
# ============================================================

@dp.callback_query(F.data == "help")
async def help_menu(call):

    await call.message.edit_text(
        "ℹ️ <b>YORDAM</b>\n\n"
        "🔎 Qidirish — username bo‘yicha "
        "ochiq web ma'lumotlarni qidiradi.\n\n"
        "👥 Guruhlar — ochiq/indexlangan "
        "guruh natijalari.\n\n"
        "📢 Kanallar — ochiq/indexlangan "
        "kanal natijalari.\n\n"
        "💬 Ochiq xabarlar — webda ochiq "
        "ko‘rinadigan xabarlar.\n\n"
        "🕐 Faollik — ochiq xabarlar sanasi/"
        "vaqtlariga asoslangan tahlil.\n\n"
        "🔒 Maxfiy ma'lumotlar olinmaydi.",
        parse_mode="HTML",
        reply_markup=back()
    )

    await call.answer()


# ============================================================
# BACK
# ============================================================

@dp.callback_query(F.data == "back")
async def back_handler(call):

    await call.message.edit_text(
        "🏠 <b>ASOSIY MENYU</b>",
        parse_mode="HTML",
        reply_markup=main_menu(
            call.from_user.id
        )
    )

    await call.answer()


# ============================================================
# RUN
# ============================================================

async def main():

    init_db()

    print("================================")
    print("BOT ISHLAYAPTI")
    print("REAL WEB SEARCH: ON")
    print("ADMIN PANEL: ON")
    print("DATABASE: ON")
    print("================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
