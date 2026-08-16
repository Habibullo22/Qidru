import asyncio
import html
import re
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ddgs import DDGS


# =========================================================
# SOZLAMALAR
# =========================================================

BOT_TOKEN = "8611335484:AAHoH8mg1OO9V7PDB3wUlZ6wU3HxsQx7avY"
ADMIN_ID = 5815294733

CARD = "9860606750247151"
CARD_OWNER = "Abidjanov H"

VIP_PRICE = 30000
VIP_DAYS = 7

DB = "database.sqlite3"


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
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


def save_user(user):
    con = db()
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


def get_user(uid):
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name,
               balance, vip_until, banned
        FROM users
        WHERE id=?
    """, (uid,))

    row = cur.fetchone()
    con.close()
    return row


def vip_active(uid):
    user = get_user(uid)

    if not user or not user[4]:
        return False

    try:
        return datetime.fromisoformat(user[4]) > datetime.now()
    except:
        return False


def give_vip(uid, days=VIP_DAYS):
    user = get_user(uid)

    if not user:
        return None

    start = datetime.now()

    if user[4]:
        try:
            old = datetime.fromisoformat(user[4])
            if old > start:
                start = old
        except:
            pass

    until = start + timedelta(days=days)

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET vip_until=?
        WHERE id=?
    """, (until.isoformat(), uid))

    con.commit()
    con.close()

    return until


def add_balance(uid, amount):
    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance=balance+?
        WHERE id=?
    """, (amount, uid))

    con.commit()
    con.close()


# =========================================================
# SEARCH
# =========================================================

def clean_username(q):
    q = q.strip()
    q = q.replace("https://t.me/", "")
    q = q.replace("http://t.me/", "")
    q = q.replace("t.me/", "")
    return q.lstrip("@").split()[0]


def telegram_link(url):
    """
    URL Telegram public sahifasimi?
    """
    try:
        host = urlparse(url).netloc.lower()
        return "t.me" in host or "telegram.me" in host
    except:
        return False


def classify(url, title="", body=""):
    """
    Ochiq Telegram natijasini taxminiy kategoriyaga ajratadi.
    Bu Telegram ichidagi yashirin a'zolikni aniqlamaydi.
    """

    text = f"{title} {body}".lower()

    if not telegram_link(url):
        return "web"

    if "channel" in text:
        return "channel"

    if "group" in text:
        return "group"

    return "telegram"


def search_public(username, section):
    """
    Faqat public/indexed web search.
    """

    username = clean_username(username)

    queries = []

    if section == "groups":
        queries = [
            f'site:t.me "{username}" "group"',
            f'site:t.me "{username}" Telegram group',
            f'"@{username}" Telegram group'
        ]

    elif section == "written":
        queries = [
            f'site:t.me "{username}"',
            f'"@{username}" Telegram message',
            f'"{username}" "t.me/"'
        ]

    elif section == "channels":
        queries = [
            f'site:t.me "{username}" "channel"',
            f'site:t.me "{username}" Telegram channel',
            f'"@{username}" Telegram channel'
        ]

    elif section == "activity":
        queries = [
            f'site:t.me "{username}"',
            f'"@{username}" Telegram'
        ]

    elif section == "profile":
        queries = [
            f'"@{username}" Telegram profile',
            f'site:t.me "{username}"'
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
        with DDGS() as ddgs:

            for query in queries:

                try:
                    items = ddgs.text(
                        query,
                        max_results=10
                    )
                except Exception as e:
                    print("SEARCH ERROR:", e)
                    continue

                for item in items:

                    url = item.get("href") or item.get("url")

                    if not url:
                        continue

                    if url in seen:
                        continue

                    seen.add(url)

                    title = item.get("title", "")
                    body = item.get("body", "")

                    results.append({
                        "title": title,
                        "body": body,
                        "url": url,
                        "type": classify(
                            url,
                            title,
                            body
                        )
                    })

                    if len(results) >= 30:
                        return results

    except Exception as e:
        print("DDGS ERROR:", e)

    return results


async def do_search(username, section):
    loop = asyncio.get_running_loop()

    return await loop.run_in_executor(
        None,
        search_public,
        username,
        section
    )


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard(uid):

    rows = [
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
                callback_data="myprofile"
            ),
            InlineKeyboardButton(
                text="⭐ VIP",
                callback_data="vip"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data="statistics"
            )
        ],
        [
            InlineKeyboardButton(
                text="ℹ️ Yordam",
                callback_data="help"
            )
        ]
    ]

    if uid == ADMIN_ID:
        rows.append([
            InlineKeyboardButton(
                text="🛠 Admin panel",
                callback_data="admin"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def back_keyboard():
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


def search_keyboard(username):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Profil",
                    callback_data=f"profile:{username}"
                ),
                InlineKeyboardButton(
                    text="📸 Ochiq rasmlar",
                    callback_data=f"photos:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Guruhlar",
                    callback_data=f"groups:{username}"
                ),
                InlineKeyboardButton(
                    text="💬 Yozgan guruhlari",
                    callback_data=f"written:{username}"
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
                    text="🏷 Username izlari",
                    callback_data=f"history:{username}"
                ),
                InlineKeyboardButton(
                    text="🕐 Faollik",
                    callback_data=f"activity:{username}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Web",
                    callback_data=f"web:{username}"
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


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    save_user(message.from_user)

    user = get_user(message.from_user.id)

    if user and user[5]:
        await message.answer(
            "🚫 Siz botdan foydalanishingiz bloklangan."
        )
        return

    await message.answer(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "🔎 Ochiq manbalardan username qidirish.\n"
        "⭐ VIP: 7 kun / 30 000 so‘m",
        parse_mode="HTML",
        reply_markup=main_keyboard(
            message.from_user.id
        )
    )


# =========================================================
# SEARCH
# =========================================================

@dp.callback_query(F.data == "search")
async def search_start(call):

    if not vip_active(call.from_user.id):

        await call.message.edit_text(
            "🔒 <b>VIP kerak</b>\n\n"
            "Qidiruvdan foydalanish uchun "
            "7 kunlik VIP kerak.\n\n"
            "💰 30 000 so‘m",
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
        "<code>@username</code>",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )

    await call.answer()


@dp.message(F.text.startswith("@"))
async def username_received(message: Message):

    save_user(message.from_user)

    if not vip_active(message.from_user.id):
        await message.answer(
            "🔒 Qidiruv uchun VIP kerak."
        )
        return

    username = clean_username(message.text)

    if len(username) < 3:
        await message.answer(
            "❌ Username noto‘g‘ri."
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO searches
        (user_id, query, created_at)
        VALUES (?, ?, ?)
    """, (
        message.from_user.id,
        username,
        datetime.now().isoformat()
    ))

    con.commit()
    con.close()

    await message.answer(
        "👤 <b>QIDIRUV TAYYOR</b>\n\n"
        f"🔎 <code>@{html.escape(username)}</code>\n\n"
        "Kerakli bo‘limni tanlang:",
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )


# =========================================================
# SECTION RESULT
# =========================================================

async def show_section(
    call,
    username,
    section,
    heading
):

    await call.answer("🔎 Qidirilmoqda...")

    await call.message.edit_text(
        f"🔎 <b>{heading}</b>\n\n"
        f"@{html.escape(username)}\n\n"
        "🌐 Ochiq manbalar tekshirilmoqda...",
        parse_mode="HTML"
    )

    results = await do_search(
        username,
        section
    )

    if not results:

        await call.message.edit_text(
            f"{heading}\n\n"
            "❌ Ochiq/indexlangan manbalarda "
            "tasdiqlangan ma'lumot topilmadi.",
            parse_mode="HTML",
            reply_markup=search_keyboard(username)
        )
        return

    text = (
        f"<b>{heading}</b>\n\n"
        f"👤 <code>@{html.escape(username)}</code>\n"
        f"📊 Topilgan manbalar: <b>{len(results)}</b>\n\n"
    )

    buttons = []

    for i, item in enumerate(results[:12], 1):

        title = html.escape(
            item["title"][:100]
        )

        body = html.escape(
            item["body"][:220]
        )

        text += f"<b>{i}. {title}</b>\n"

        if body:
            text += f"{body}\n"

        text += "\n"

        buttons.append([
            InlineKeyboardButton(
                text=f"🔗 {i}-manbani ochish",
                url=item["url"]
            )
        ])

    text += (
        "ℹ️ Natijalar ochiq/indexlangan "
        "manbalardan olingan."
    )

    if len(text) > 3900:
        text = text[:3900] + "\n..."

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Qidiruv bo‘limlari",
            callback_data=f"menu:{username}"
        )
    ])

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )


# =========================================================
# GROUPS
# =========================================================

@dp.callback_query(F.data.startswith("groups:"))
async def groups(call):

    username = call.data.split(":", 1)[1]

    await show_section(
        call,
        username,
        "groups",
        "👥 OCHIQ GURUHLAR"
    )


# =========================================================
# WRITTEN GROUPS
# =========================================================

@dp.callback_query(F.data.startswith("written:"))
async def written(call):

    username = call.data.split(":", 1)[1]

    await show_section(
        call,
        username,
        "written",
        "💬 OCHIQ XABARLAR / YOZGAN JOYLARI"
    )


# =========================================================
# CHANNELS
# =========================================================

@dp.callback_query(F.data.startswith("channels:"))
async def channels(call):

    username = call.data.split(":", 1)[1]

    await show_section(
        call,
        username,
        "channels",
        "📢 OCHIQ KANALLAR"
    )


# =========================================================
# WEB
# =========================================================

@dp.callback_query(F.data.startswith("web:"))
async def web(call):

    username = call.data.split(":", 1)[1]

    await show_section(
        call,
        username,
        "web",
        "🌐 WEB MANBALARI"
    )


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query(F.data.startswith("profile:"))
async def profile(call):

    username = call.data.split(":", 1)[1]

    results = await do_search(
        username,
        "profile"
    )

    text = (
        "👤 <b>PROFIL</b>\n\n"
        f"🔎 Username: <code>@{html.escape(username)}</code>\n\n"
    )

    if results:

        text += "🌐 Ochiq manbalarda topilgan:\n\n"

        for item in results[:8]:

            text += (
                f"• <b>{html.escape(item['title'][:100])}</b>\n"
                f"{html.escape(item['body'][:180])}\n\n"
            )

    else:

        text += (
            "❌ Ochiq manbalarda tasdiqlangan "
            "profil ma'lumoti topilmadi."
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )

    await call.answer()


# =========================================================
# PHOTOS
# =========================================================

@dp.callback_query(F.data.startswith("photos:"))
async def photos(call):

    username = call.data.split(":", 1)[1]

    await call.message.edit_text(
        "📸 <b>OCHIQ PROFIL RASMLARI</b>\n\n"
        f"👤 @{html.escape(username)}\n\n"
        "Bot faqat webda ochiq ko‘rinadigan "
        "rasm manbalarini ko‘rsatishi mumkin.\n\n"
        "Telegram Bot API boshqa odamning "
        "eski profil rasmlari tarixini bermaydi.",
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )

    await call.answer()


# =========================================================
# USERNAME HISTORY
# =========================================================

@dp.callback_query(F.data.startswith("history:"))
async def history(call):

    username = call.data.split(":", 1)[1]

    results = await do_search(
        username,
        "profile"
    )

    text = (
        "🏷 <b>USERNAME IZLARI</b>\n\n"
        f"🔎 Hozirgi so‘rov: "
        f"<code>@{html.escape(username)}</code>\n\n"
    )

    if results:

        text += (
            "Ochiq web manbalarida shu username "
            "bilan bog‘liq natijalar:\n\n"
        )

        for item in results[:10]:

            text += (
                f"• {html.escape(item['title'][:100])}\n"
                f"{html.escape(item['body'][:150])}\n\n"
            )

    else:

        text += (
            "❌ Ochiq manbalarda username tarixi "
            "bo‘yicha tasdiqlangan ma'lumot topilmadi."
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )

    await call.answer()


# =========================================================
# ACTIVITY
# =========================================================

@dp.callback_query(F.data.startswith("activity:"))
async def activity(call):

    username = call.data.split(":", 1)[1]

    results = await do_search(
        username,
        "activity"
    )

    text = (
        "🕐 <b>FAOLLIK</b>\n\n"
        f"👤 @{html.escape(username)}\n\n"
    )

    if not results:

        text += (
            "❌ Yetarli ochiq xabar topilmadi."
        )

    else:

        text += (
            f"📊 Ochiq manbalar: <b>{len(results)}</b>\n\n"
            "Bu online-history emas.\n"
            "Quyidagi natijalar ochiq web xabarlaridan "
            "olingan va ularning manba linklari orqali "
            "tekshiriladi.\n\n"
        )

        for i, item in enumerate(results[:8], 1):

            text += (
                f"{i}. {html.escape(item['title'][:100])}\n"
                f"{html.escape(item['body'][:150])}\n\n"
            )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )

    await call.answer()


# =========================================================
# SEARCH MENU
# =========================================================

@dp.callback_query(F.data.startswith("menu:"))
async def menu(call):

    username = call.data.split(":", 1)[1]

    await call.message.edit_text(
        "📋 <b>QIDIRUV BO‘LIMLARI</b>\n\n"
        f"👤 @{html.escape(username)}",
        parse_mode="HTML",
        reply_markup=search_keyboard(username)
    )

    await call.answer()


# =========================================================
# VIP
# =========================================================

@dp.callback_query(F.data == "vip")
async def vip(call):

    user = get_user(call.from_user.id)

    if vip_active(call.from_user.id):

        await call.message.edit_text(
            "⭐ <b>VIP FAOL</b>\n\n"
            f"⏰ Tugashi:\n"
            f"<code>{user[4]}</code>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

    else:

        await call.message.edit_text(
            "⭐ <b>7 KUNLIK VIP</b>\n\n"
            "💰 Narxi: <b>30 000 so‘m</b>\n"
            "📅 Muddat: <b>7 kun</b>\n\n"
            "To‘lovni amalga oshirish uchun "
            "Hisob to‘ldirish bo‘limiga kiring.",
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
# DEPOSIT
# =========================================================

@dp.callback_query(F.data == "deposit")
async def deposit(call):

    con = db()
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
            "⏳ <b>TO‘LOV TEKSHIRILMOQDA</b>\n\n"
            "Admin oldingi arizangizni "
            "ko‘rib chiqmoqda.",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )

        await call.answer()
        return

    await call.message.edit_text(
        "💰 <b>HISOB TO‘LDIRISH</b>\n\n"
        f"💵 Summa: <b>{VIP_PRICE:,} so‘m</b>\n\n"
        f"💳 Karta:\n"
        f"<code>{CARD}</code>\n"
        f"👤 {CARD_OWNER}\n\n"
        "To‘lov qilgandan keyin "
        "«To‘lov qildim» tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ To‘lov qildim",
                        callback_data="paid"
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


@dp.callback_query(F.data == "paid")
async def paid(call):

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id
        FROM payments
        WHERE user_id=?
        AND status='pending'
        LIMIT 1
    """, (call.from_user.id,))

    exists = cur.fetchone()

    if exists:

        payment_id = exists[0]

    else:

        cur.execute("""
            INSERT INTO payments
            (user_id, amount, status, created_at)
            VALUES (?, ?, 'pending', ?)
        """, (
            call.from_user.id,
            VIP_PRICE,
            datetime.now().isoformat()
        ))

        payment_id = cur.lastrowid

    con.commit()
    con.close()

    user = get_user(call.from_user.id)

    username = (
        "@" + user[1]
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
        f"🆔 Ariza: #{payment_id}\n"
        f"👤 {html.escape(username)}\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 {VIP_PRICE:,} so‘m\n"
        f"⭐ VIP: {VIP_DAYS} kun",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await call.message.edit_text(
        "⏳ <b>Arizangiz admin'ga yuborildi.</b>\n\n"
        "Tasdiqlangandan keyin 7 kunlik VIP ochiladi.",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )

    await call.answer("Yuborildi")


# =========================================================
# APPROVE
# =========================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve(call):

    if call.from_user.id != ADMIN_ID:
        await call.answer(
            "🚫 Ruxsat yo‘q",
            show_alert=True
        )
        return

    pid = int(call.data.split(":")[1])

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
    """, (pid,))

    payment = cur.fetchone()

    if not payment:
        con.close()
        await call.answer("Topilmadi", show_alert=True)
        return

    uid, amount, status = payment

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
    """, (pid,))

    con.commit()
    con.close()

    add_balance(uid, amount)

    until = give_vip(
        uid,
        VIP_DAYS
    )

    await call.message.edit_text(
        "✅ <b>TO‘LOV TASDIQLANDI</b>\n\n"
        f"🆔 #{pid}\n"
        f"💰 {amount:,} so‘m\n"
        f"⭐ VIP: {VIP_DAYS} kun\n"
        f"⏰ {until}\n\n"
        "🔒 Ariza yopildi.",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            uid,
            "✅ <b>To‘lov tasdiqlandi!</b>\n\n"
            f"⭐ VIP: {VIP_DAYS} kun\n"
            f"⏰ Tugashi: <code>{until}</code>",
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer("Tasdiqlandi")


# =========================================================
# REJECT
# =========================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject(call):

    if call.from_user.id != ADMIN_ID:
        await call.answer(
            "🚫 Ruxsat yo‘q",
            show_alert=True
        )
        return

    pid = int(call.data.split(":")[1])

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
    """, (pid,))

    payment = cur.fetchone()

    if not payment:
        con.close()
        await call.answer("Topilmadi", show_alert=True)
        return

    uid, amount, status = payment

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
    """, (pid,))

    con.commit()
    con.close()

    await call.message.edit_text(
        "❌ <b>TO‘LOV RAD ETILDI</b>\n\n"
        f"🆔 #{pid}\n"
        f"💰 {amount:,} so‘m\n\n"
        "🔒 Ariza yopildi.",
        parse_mode="HTML"
    )

    try:
        await bot.send_message(
            uid,
            "❌ <b>To‘lovingiz rad etildi.</b>\n\n"
            "Qayta ariza yuborishingiz mumkin.",
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer("Rad etildi")


# =========================================================
# MY PROFILE
# =========================================================

@dp.callback_query(F.data == "myprofile")
async def myprofile(call):

    user = get_user(call.from_user.id)

    vip = "✅ Faol" if vip_active(
        call.from_user.id
    ) else "❌ Faol emas"

    await call.message.edit_text(
        "👤 <b>PROFILIM</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 @{html.escape(user[1] or 'yo‘q')}\n"
        f"💰 Balans: {user[3]:,} so‘m\n"
        f"⭐ VIP: {vip}\n"
        f"⏰ Tugashi: <code>{user[4] or '—'}</code>",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN
# =========================================================

def admin_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Userlar",
                    callback_data="a_users"
                ),
                InlineKeyboardButton(
                    text="🔎 User qidirish",
                    callback_data="a_search"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 To‘lovlar",
                    callback_data="a_payments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data="a_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ VIP berish",
                    callback_data="a_vip"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Balans",
                    callback_data="a_add"
                ),
                InlineKeyboardButton(
                    text="➖ Balans",
                    callback_data="a_sub"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Ban",
                    callback_data="a_ban"
                ),
                InlineKeyboardButton(
                    text="✅ Unban",
                    callback_data="a_unban"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="a_broadcast"
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
async def admin(call):

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
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(F.data == "a_stats")
async def admin_stats(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = db()
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
    """, (datetime.now().isoformat(),))

    vip = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE status='pending'
    """)
    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
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
        f"💰 Tushum: <b>{income:,} so‘m</b>\n"
        f"🔎 Qidiruvlar: <b>{searches}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN USERS
# =========================================================

@dp.callback_query(F.data == "a_users")
async def admin_users(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name,
               balance, vip_until, banned
        FROM users
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    con.close()

    text = "👥 <b>USERLAR</b>\n\n"

    for row in rows:

        uid, username, name, balance, vip, banned = row

        text += (
            f"🆔 <code>{uid}</code>\n"
            f"👤 @{html.escape(username or 'yo‘q')}\n"
            f"💰 {balance:,} so‘m\n"
            f"{'🚫 BAN' if banned else '✅ Aktiv'}\n\n"
        )

    if not rows:
        text += "Userlar yo‘q."

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

    await call.answer()


# =========================================================
# ADMIN COMMANDS
# =========================================================

@dp.message(F.text.startswith("/user "))
async def admin_user(message):

    if message.from_user.id != ADMIN_ID:
        return

    query = message.text[6:].strip().lstrip("@")

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, username, first_name,
               balance, vip_until, banned
        FROM users
        WHERE username LIKE ?
           OR CAST(id AS TEXT)=?
           OR first_name LIKE ?
        LIMIT 10
    """, (
        f"%{query}%",
        query,
        f"%{query}%"
    ))

    rows = cur.fetchall()
    con.close()

    if not rows:
        await message.answer(
            "❌ Bot bazasidan user topilmadi."
        )
        return

    for row in rows:

        uid, username, name, balance, vip, banned = row

        await message.answer(
            "👤 <b>USER</b>\n\n"
            f"🆔 <code>{uid}</code>\n"
            f"👤 @{html.escape(username or 'yo‘q')}\n"
            f"📝 {html.escape(name or '')}\n"
            f"💰 {balance:,} so‘m\n"
            f"⭐ {vip or 'VIP yo‘q'}\n"
            f"{'🚫 BAN' if banned else '✅ Aktiv'}",
            parse_mode="HTML"
        )


@dp.message(F.text.startswith("/addbal "))
async def admin_add(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "/addbal USER_ID SUMMA"
        )
        return

    try:
        uid = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Noto‘g‘ri.")
        return

    if not get_user(uid):
        await message.answer("❌ User topilmadi.")
        return

    add_balance(uid, amount)

    await message.answer(
        f"✅ +{amount:,} so‘m qo‘shildi."
    )


@dp.message(F.text.startswith("/subbal "))
async def admin_sub(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "/subbal USER_ID SUMMA"
        )
        return

    try:
        uid = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Noto‘g‘ri.")
        return

    user = get_user(uid)

    if not user:
        await message.answer("❌ User topilmadi.")
        return

    new_balance = max(
        0,
        user[3] - amount
    )

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET balance=?
        WHERE id=?
    """, (new_balance, uid))

    con.commit()
    con.close()

    await message.answer(
        f"✅ Balansdan {amount:,} so‘m ayirildi."
    )


@dp.message(F.text.startswith("/vip "))
async def admin_vip(message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer(
            "/vip USER_ID KUN"
        )
        return

    try:
        uid = int(parts[1])
        days = int(parts[2])
    except:
        await message.answer("❌ Noto‘g‘ri.")
        return

    if not get_user(uid):
        await message.answer("❌ User topilmadi.")
        return

    until = give_vip(uid, days)

    await message.answer(
        "⭐ VIP berildi.\n\n"
        f"👤 {uid}\n"
        f"📅 {days} kun\n"
        f"⏰ {until}"
    )


@dp.message(F.text.startswith("/ban "))
async def admin_ban(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(message.text.split()[1])
    except:
        await message.answer(
            "/ban USER_ID"
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET banned=1
        WHERE id=?
    """, (uid,))

    con.commit()
    con.close()

    await message.answer(
        f"🚫 {uid} ban qilindi."
    )


@dp.message(F.text.startswith("/unban "))
async def admin_unban(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(message.text.split()[1])
    except:
        await message.answer(
            "/unban USER_ID"
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        UPDATE users
        SET banned=0
        WHERE id=?
    """, (uid,))

    con.commit()
    con.close()

    await message.answer(
        f"✅ {uid} unban qilindi."
    )


@dp.message(F.text.startswith("/broadcast "))
async def broadcast(message):

    if message.from_user.id != ADMIN_ID:
        return

    text = message.text[len("/broadcast "):].strip()

    if not text:
        await message.answer(
            "/broadcast XABAR"
        )
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id FROM users
        WHERE banned=0
    """)

    users = [
        x[0]
        for x in cur.fetchall()
    ]

    con.close()

    success = 0
    failed = 0

    for uid in users:

        try:
            await bot.send_message(
                uid,
                text
            )
            success += 1
        except:
            failed += 1

        await asyncio.sleep(0.05)

    await message.answer(
        "📢 <b>YAKUNLANDI</b>\n\n"
        f"✅ {success}\n"
        f"❌ {failed}",
        parse_mode="HTML"
    )


# =========================================================
# ADMIN INFO BUTTONS
# =========================================================

@dp.callback_query(F.data == "a_search")
async def a_search(call):

    await call.message.edit_text(
        "🔎 <b>USER QIDIRISH</b>\n\n"
        "Bot bazasidan user qidirish:\n\n"
        "<code>/user username</code>\n"
        "yoki\n"
        "<code>/user USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_vip")
async def a_vip(call):

    await call.message.edit_text(
        "⭐ <b>VIP BERISH</b>\n\n"
        "<code>/vip USER_ID KUN</code>\n\n"
        "Masalan:\n"
        "<code>/vip 123456789 7</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_add")
async def a_add(call):

    await call.message.edit_text(
        "➕ <b>BALANS QO‘SHISH</b>\n\n"
        "<code>/addbal USER_ID SUMMA</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_sub")
async def a_sub(call):

    await call.message.edit_text(
        "➖ <b>BALANS AYIRISH</b>\n\n"
        "<code>/subbal USER_ID SUMMA</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_ban")
async def a_ban(call):

    await call.message.edit_text(
        "🚫 <b>BAN</b>\n\n"
        "<code>/ban USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_unban")
async def a_unban(call):

    await call.message.edit_text(
        "✅ <b>UNBAN</b>\n\n"
        "<code>/unban USER_ID</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_broadcast")
async def a_broadcast(call):

    await call.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "<code>/broadcast Xabar</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "a_payments")
async def a_payments(call):

    if call.from_user.id != ADMIN_ID:
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, user_id, amount,
               status, created_at
        FROM payments
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    con.close()

    text = "💳 <b>TO‘LOVLAR</b>\n\n"

    if not rows:
        text += "To‘lovlar yo‘q."

    for row in rows:

        pid, uid, amount, status, created = row

        icon = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌"
        }.get(status, "❔")

        text += (
            f"{icon} <b>#{pid}</b>\n"
            f"👤 <code>{uid}</code>\n"
            f"💰 {amount:,} so‘m\n"
            f"📌 {status}\n\n"
        )

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# =========================================================
# PUBLIC STATISTICS
# =========================================================

@dp.callback_query(F.data == "statistics")
async def statistics(call):

    con = db()
    cur = con.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]

    con.close()

    await call.message.edit_text(
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )


# =========================================================
# HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help(call):

    await call.message.edit_text(
        "ℹ️ <b>YORDAM</b>\n\n"
        "🔎 Username yuborasiz.\n"
        "Keyin kerakli bo‘limni tanlaysiz.\n\n"
        "👥 Guruhlar — ochiq/indexlangan "
        "guruh natijalari.\n\n"
        "💬 Yozgan guruhlari — ochiq "
        "xabarlar orqali aniqlangan joylar.\n\n"
        "📢 Kanallar — ochiq kanal natijalari.\n\n"
        "📸 Rasmlar — faqat ochiq web "
        "manbalaridagi rasmlar.\n\n"
        "🕐 Faollik — ochiq xabarlarning "
        "sana/vaqtlariga asoslangan.\n\n"
        "🔒 Yopiq guruhlar, shaxsiy xabarlar "
        "va yashirin online-history olinmaydi.",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(call):

    await call.message.edit_text(
        "🏠 <b>ASOSIY MENYU</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard(
            call.from_user.id
        )
    )

    await call.answer()


# =========================================================
# RUN
# =========================================================

async def main():

    init_db()

    print("====================================")
    print("BOT STARTED")
    print("PUBLIC WEB SEARCH: ON")
    print("VIP: 7 DAYS")
    print("ADMIN PANEL: ON")
    print("DATABASE: ON")
    print("====================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
