import os
import re
import html
import random
import asyncio
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    MessageEntity, FSInputFile
)
from flask import Flask
from threading import Thread
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================================
# IMRAN TOPUP BOT — CONFIGURATION
#
# Render Environment Variables — ONLY THREE:
#   BOT_TOKEN
#   CHAT_ID             (owner/admin Telegram chat ID)
#   CUSTOM_EMOJI_ID     (Telegram custom/premium emoji ID)
#
# The 12 images are NOT Render environment variables.
# They live in ./images/ inside the GitHub repository and Render
# gets them automatically when it deploys the repository.
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("CHAT_ID", "0") or 0)
PREMIUM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")
if not OWNER_ID:
    raise RuntimeError("CHAT_ID is missing.")
if not PREMIUM_EMOJI_ID:
    raise RuntimeError("CUSTOM_EMOJI_ID is required for IMRAN TOPUP BOT.")
if not PREMIUM_EMOJI_ID.isdigit():
    raise RuntimeError("CUSTOM_EMOJI_ID must be a numeric Telegram custom emoji ID.")

CHANNEL_URL = "https://t.me/IMRAN_SH0P"
SUPPORT_USERNAME = "IMRAN_TOP_UP"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")

# EXACT filenames from the user's image folder.
# Linux/Render is case-sensitive, so do not rename these files.
PHOTOS = {
    "home": os.path.join(IMAGE_DIR, "imran.jpg"),
    "pubg": os.path.join(IMAGE_DIR, "pubg.jpg"),
    "uc": os.path.join(IMAGE_DIR, "uc.jpg"),
    "growth": os.path.join(IMAGE_DIR, "growth.jpg"),
    "prime": os.path.join(IMAGE_DIR, "prime.jpeg"),
    "mythic": os.path.join(IMAGE_DIR, "mythic.jpg"),
    "rp": os.path.join(IMAGE_DIR, "Rp.jpg"),
    "freefire": os.path.join(IMAGE_DIR, "freefire.jpg"),
    "tiktok": os.path.join(IMAGE_DIR, "TikTok.jpg"),
    "delta": os.path.join(IMAGE_DIR, "delta.jpg"),
    "premium": os.path.join(IMAGE_DIR, "telegram.jpg"),
    "bloodstrike": os.path.join(IMAGE_DIR, "blood.jpg"),
}

# Payment details from the project specification.
PAYMENTS = {
    "Telebirr": ("0982903324", "Kayamo"),
    "CBE": ("1000219425809", "Alemnesh"),
    "Dashen": ("5543988503011", "Alemnesh"),
}

DB = "bot.db"
logging.basicConfig(level=logging.INFO)

# ============================================================
# DATABASE
# ============================================================

def db_init():
    with closing(sqlite3.connect(DB)) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                product TEXT NOT NULL,
                amount REAL NOT NULL,
                player_id TEXT,
                payment_method TEXT,
                payment_sms TEXT,
                receipt_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                user_id INTEGER PRIMARY KEY,
                ticket_number INTEGER UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'open'
            )
        """)
        # Upgrade an older bot.db created by the previous version.
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(tickets)").fetchall()
        }
        if "ticket_number" not in columns:
            con.execute("ALTER TABLE tickets ADD COLUMN ticket_number INTEGER")
            rows = con.execute(
                "SELECT user_id FROM tickets WHERE ticket_number IS NULL"
            ).fetchall()
            used = set()
            for (uid,) in rows:
                while True:
                    number = random.randint(100000, 999999)
                    if number not in used:
                        used.add(number)
                        break
                con.execute(
                    "UPDATE tickets SET ticket_number=? WHERE user_id=?",
                    (number, uid),
                )
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_number "
                "ON tickets(ticket_number)"
            )
        con.commit()


def create_order(data):
    with closing(sqlite3.connect(DB)) as con:
        cur = con.execute("""
            INSERT INTO orders
            (user_id, username, product, amount, player_id, payment_method,
             payment_sms, receipt_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            data["user_id"], data["username"], data["product"], data["amount"],
            data.get("player_id", ""), data.get("payment_method", ""),
            data.get("payment_sms", ""), data.get("receipt_url", ""),
            datetime.utcnow().isoformat()
        ))
        con.commit()
        return cur.lastrowid


def update_order(order_id, **fields):
    allowed = {
        "payment_sms", "receipt_url", "status", "payment_method",
        "player_id"
    }
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [order_id]
    with closing(sqlite3.connect(DB)) as con:
        con.execute(f"UPDATE orders SET {sets} WHERE id=?", values)
        con.commit()


def get_order(order_id):
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_user_orders(user_id, limit=10):
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT * FROM orders
            WHERE user_id=?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(x) for x in rows]


# ============================================================
# PREMIUM CUSTOM EMOJI
# ============================================================

def pe(text: str) -> str:
    """
    Prefix every normal bot message with the configured Telegram
    custom-emoji entity.

    CUSTOM_EMOJI_ID must be a real Telegram custom emoji ID. A normal
    Unicode emoji is not a custom emoji ID. The custom emoji entity is
    rendered for users regardless of whether the user has Telegram
    Premium, as long as the ID is valid and Telegram supports that emoji.
    """
    text = "" if text is None else str(text)
    safe_text = html.escape(text, quote=False)
    return (
        f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">🙂</tg-emoji> '
        f'{safe_text}'
    )


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ============================================================
# FSM
# ============================================================

class OrderState(StatesGroup):
    waiting_player_id = State()
    waiting_confirmation = State()
    waiting_payment = State()
    waiting_sms = State()
    waiting_not_trusted_reason = State()
    waiting_delivery_receipt = State()
    waiting_tiktok_identifier = State()


# ============================================================
# DATA
# ============================================================

PUBG_FAST = [
    ("60 UC", 190), ("120 UC", 380), ("180 UC", 550),
    ("325 UC", 880), ("385 UC", 1100), ("660 UC", 1765),
    ("720 UC", 1920), ("985 UC", 2820), ("1320 UC", 3600),
    ("1800 UC", 4350), ("1920 UC", 4800), ("2460 UC", 6300),
    ("3850 UC", 8700),
]

PUBG_MANUAL = [
    ("30 UC", 130), ("240 UC", 700), ("325 UC", 850),
    ("385 UC", 1050), ("445 UC", 1230), ("660 UC", 1700),
    ("720 UC", 1890), ("780 UC", 2050), ("985 UC", 2600),
    ("1045 UC", 2750), ("1320 UC", 3500), ("1800 UC", 4300),
    ("2125 UC", 5300), ("3850 UC", 8550), ("4000 UC", 9150),
    ("8100 UC", 17000), ("16200 UC", 33900),
]

GROWTH = [
    ("First purchase pack", 200),
    ("Upgradeable firearm pack", 550),
    ("Mythic Emblem pack", 900),
]

PRIME = [
    ("Prime 1 Month", 200), ("Prime 3 Months", 600),
    ("Prime 6 Months", 1150), ("Prime Plus 1 Month", 1700),
    ("Prime 12 Months", 2100), ("Prime Plus 3 Months", 5000),
    ("Prime Plus 6 Months", 9900), ("Prime Plus 12 Months", 19900),
]

RP = [
    ("ELITE PASS 150 + 50 UC GIFT", 1200),
    ("ELITE PASS 100 + 100 UC GIFT", 2300),
]

FREEFIRE = [
    ("100+10", 230), ("210+21", 440), ("530+53", 950),
    ("1080+108", 1900), ("2200+220", 3750),
]

DELTA_SPECIAL = [
    ("Season Pass Operations Special", 900),
    ("Season Pass Warfare Special", 900),
    ("S/Pass Delta Force Deluxe", 1300),
]

TIKTOK = [
    ("200 COIN", 500), ("500 COIN", 1200), ("800 COIN", 1800),
    ("1000 COIN", 2300), ("1500 COIN", 3300), ("2000 COIN", 4400),
    ("2500 COIN", 5500), ("3000 COIN", 6600), ("4000 COIN", 8650),
    ("5000 COIN", 10900), ("7500 COIN", 16500), ("10000 COIN", 22000),
]

TELEGRAM_PREMIUM = [
    ("Telegram Premium 1 Month", 350),
    ("Telegram Premium 3 Months", 950),
    ("Telegram Premium 6 Months", 1800),
    ("Telegram Premium 12 Months", 3300),
]

STARS = [
    ("Telegram Stars 100", 250), ("Telegram Stars 500", 1100),
    ("Telegram Stars 1000", 2100),
]

# ============================================================
# KEYBOARDS
# ============================================================

def premium_button(text: str, **kwargs):
    """Create an inline button with the configured Premium custom-emoji icon."""
    return InlineKeyboardButton(
        text=text,
        icon_custom_emoji_id=PREMIUM_EMOJI_ID,
        **kwargs,
    )


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu():
    return kb([
        [premium_button(text="🎮 PUBG MOBILE", callback_data="cat:pubg"),
         premium_button(text="🔥 FREE FIRE", callback_data="cat:freefire")],
        [premium_button(text="📱 TIKTOK COIN", callback_data="cat:tiktok"),
         premium_button(text="⚔️ DELTA FORCE", callback_data="cat:delta")],
        [premium_button(text="⭐ TELEGRAM PREMIUM & STARS", callback_data="cat:telegram")],
        [premium_button(text="🎯 BLOOD STRIKE", callback_data="cat:bloodstrike"),
         premium_button(text="📦 MY ORDERS", callback_data="myorders")],
        [premium_button(text="🎟️ GET TICKET", callback_data="ticket"),
         premium_button(text="🆘 SUPPORT", callback_data="support")],
        [premium_button(text="📢 OUR CHANNEL", url=CHANNEL_URL),
         premium_button(text="ℹ️ INFO", callback_data="info")],
        [premium_button(text="❓ HELP", callback_data="help")],
    ])


def back_cancel(callback="home"):
    return [
        premium_button(text="🔙 BACK", callback_data=f"back:{callback}"),
        premium_button(text="❌ CANCEL", callback_data="cancel"),
    ]


def category_menu(category):
    if category == "pubg":
        return kb([
            [premium_button(text="⚡ FAST UC", callback_data="prodmenu:pubg_fast")],
            [premium_button(text="🛠️ MANUAL UC", callback_data="prodmenu:pubg_manual")],
            [premium_button(text="🎁 GROWTH PACK", callback_data="prodmenu:growth")],
            [premium_button(text="👑 PRIME PLUS", callback_data="prodmenu:prime")],
            [premium_button(text="💠 MYTHIC EMBLEM", callback_data="prodmenu:mythic")],
            [premium_button(text="🎟️ RP", callback_data="prodmenu:rp")],
            back_cancel("home"),
        ])
    if category == "freefire":
        return product_keyboard(FREEFIRE, "freefire")
    if category == "tiktok":
        return product_keyboard(TIKTOK, "tiktok")
    if category == "delta":
        return kb([
            [premium_button(text="🪙 Delta Force Coins", callback_data="prodmenu:delta_coin")],
            [premium_button(text="🎟️ Special Offers", callback_data="prodmenu:delta_special")],
            back_cancel("home"),
        ])
    if category == "telegram":
        return kb([
            [premium_button(text="⭐ Telegram Premium", callback_data="prodmenu:premium")],
            [premium_button(text="🌟 Telegram Stars", callback_data="prodmenu:stars")],
            back_cancel("home"),
        ])
    return kb([[*back_cancel("home")]])


def product_keyboard(products, prefix):
    rows = []
    for i, (name, price) in enumerate(products):
        rows.append([premium_button(
            text=f"{name} — {price:.2f} ETB",
            callback_data=f"buy:{prefix}:{i}"
        )])
    rows.append(back_cancel("home"))
    return kb(rows)


def payment_keyboard():
    return kb([
        [premium_button(text="🏦 Telebirr", callback_data="pay:Telebirr")],
        [premium_button(text="🏦 CBE", callback_data="pay:CBE")],
        [premium_button(text="🏦 Dashen", callback_data="pay:Dashen")],
        back_cancel("products"),
    ])


def yes_no_cancel():
    return kb([
        [premium_button(text="✅ YES", callback_data="confirm:yes"),
         premium_button(text="❌ NO", callback_data="confirm:no")],
        [premium_button(text="🚫 CANCEL", callback_data="cancel")],
    ])


def owner_order_keyboard(order_id):
    return kb([
        [premium_button(text="✅ ACCEPT", callback_data=f"owner:accept:{order_id}"),
         premium_button(text="❌ REJECT", callback_data=f"owner:reject:{order_id}")],
    ])


def trust_keyboard(order_id):
    return kb([
        [premium_button(text="🤝 TRUSTED", callback_data=f"trust:{order_id}"),
         premium_button(text="⚠️ NOT TRUSTED", callback_data=f"notrust:{order_id}")],
    ])


# ============================================================
# HELPERS
# ============================================================

async def send_photo_or_text(message, photo, caption, reply_markup=None):
    if photo and os.path.isfile(photo):
        try:
            return await message.answer_photo(
                photo=FSInputFile(photo),
                caption=caption,
                reply_markup=reply_markup
            )
        except Exception as exc:
            logging.warning("Could not send image %s: %s", photo, exc)
    return await message.answer(caption, reply_markup=reply_markup)


async def edit_or_send(callback, text, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)


def receipt_url(text):
    if not text:
        return None
    m = re.search(r"https?://[^\s<>\"]+", text)
    return m.group(0) if m else None


def product_data(prefix, index):
    maps = {
        "pubg_fast": PUBG_FAST,
        "pubg_manual": PUBG_MANUAL,
        "growth": GROWTH,
        "prime": PRIME,
        "rp": RP,
        "freefire": FREEFIRE,
        "tiktok": TIKTOK,
        "delta_special": DELTA_SPECIAL,
        "premium": TELEGRAM_PREMIUM,
        "stars": STARS,
    }
    if prefix == "mythic":
        return ("Mythic Emblem Value Pack", 700)
    if prefix == "delta_coin":
        # Pricing can be changed later without changing the flow.
        delta = [
            ("30 Coins", 130),
            ("60 Coins", 190),
            ("320 Coins", 800),
            ("460 Coins", 1200),
            ("750 Coins", 1650),
            ("1480 Coins", 3100),
            ("1980 Coins", 3950),
            ("3950 Coins", 7650),
        ]
        return delta[index]
    return maps[prefix][index]


# ============================================================
# START / MAIN
# ============================================================

async def show_home(message):
    text = pe(
        "👋 Welcome to IMRAN TOPUP BOT\n\n"
        "Choose a service below:\n"
        "🎮 PUBG MOBILE\n"
        "🔥 Free Fire\n"
        "📱 TikTok Coins\n"
        "⚔️ Delta Force\n"
        "⭐ Telegram Premium & Stars\n"
        "🎯 Blood Strike"
    )
    await send_photo_or_text(message, PHOTOS["home"], text, main_menu())


async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)


# ============================================================
# CATEGORY / PRODUCT MENUS
# ============================================================


async def show_category(callback: CallbackQuery, category: str):
    names = {
        "pubg": "🎮 PUBG MOBILE",
        "freefire": "🔥 FREE FIRE",
        "tiktok": "📱 TIKTOK COINS",
        "delta": "⚔️ DELTA FORCE",
        "telegram": "⭐ TELEGRAM PREMIUM & STARS",
        "bloodstrike": "🎯 BLOOD STRIKE",
    }
    photos = {
        "pubg": PHOTOS["pubg"],
        "freefire": PHOTOS["freefire"],
        "tiktok": PHOTOS["tiktok"],
        "delta": PHOTOS["delta"],
        "telegram": PHOTOS["premium"],
        "bloodstrike": PHOTOS["bloodstrike"],
    }
    text = pe(f"{names.get(category, category)}\n\nSelect a service:")
    try:
        if photos.get(category):
            await callback.message.delete()
            await callback.message.answer_photo(
                FSInputFile(photos[category]),
                caption=text,
                reply_markup=category_menu(category)
            )
        else:
            await edit_or_send(callback, text, category_menu(category))
    except Exception:
        await edit_or_send(callback, text, category_menu(category))


async def show_product_menu(callback: CallbackQuery, prefix: str):
    maps = {
        "pubg_fast": ("⚡ PUBG FAST UC", PUBG_FAST, "pubg"),
        "pubg_manual": ("🛠️ PUBG MANUAL UC", PUBG_MANUAL, "uc"),
        "growth": ("🎁 GROWTH PACK", GROWTH, "growth"),
        "prime": ("👑 PRIME PLUS", PRIME, "prime"),
        "rp": ("🎟️ RP", RP, "rp"),
        "freefire": ("🔥 FREE FIRE", FREEFIRE, "freefire"),
        "tiktok": ("📱 TIKTOK COINS", TIKTOK, "tiktok"),
        "delta_special": ("🎟️ DELTA FORCE SPECIAL OFFERS", DELTA_SPECIAL, "delta"),
        "premium": ("⭐ TELEGRAM PREMIUM", TELEGRAM_PREMIUM, "premium"),
        "stars": ("🌟 TELEGRAM STARS", STARS, "premium"),
        "delta_coin": ("🪙 DELTA FORCE COINS",
                       [
                           ("30 Coins", 130),
                           ("60 Coins", 190),
                           ("320 Coins", 800),
                           ("460 Coins", 1200),
                           ("750 Coins", 1650),
                           ("1480 Coins", 3100),
                           ("1980 Coins", 3950),
                           ("3950 Coins", 7650),
                       ], "delta"),
    }
    if prefix == "mythic":
        text = pe("💠 MYTHIC EMBLEM VALUE PACK\n\nMythic Emblem Value Pack — 700.00 ETB")
        photo_path = PHOTOS["mythic"]
        try:
            if os.path.isfile(photo_path):
                await callback.message.delete()
                await callback.message.answer_photo(
                    FSInputFile(photo_path),
                    caption=text,
                    reply_markup=product_keyboard([("Mythic Emblem Value Pack", 700)], "mythic")
                )
            else:
                await edit_or_send(callback, text, product_keyboard([("Mythic Emblem Value Pack", 700)], "mythic"))
        except Exception:
            await edit_or_send(callback, text, product_keyboard([("Mythic Emblem Value Pack", 700)], "mythic"))
        return

    title, products, photo_key = maps[prefix]
    photo_path = PHOTOS.get(photo_key, "")
    caption = pe(f"{title}\n\nChoose your package:")
    try:
        if photo_path and os.path.isfile(photo_path):
            await callback.message.delete()
            await callback.message.answer_photo(
                FSInputFile(photo_path),
                caption=caption,
                reply_markup=product_keyboard(products, prefix)
            )
        else:
            await edit_or_send(callback, caption, product_keyboard(products, prefix))
    except Exception:
        await edit_or_send(callback, caption, product_keyboard(products, prefix))


# ============================================================
# BUY -> PLAYER ID -> CONFIRM -> PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery, state: FSMContext):
    _, prefix, index = callback.data.split(":")
    index = int(index)
    product, amount = product_data(prefix, index)

    await state.update_data(
        prefix=prefix,
        product=product,
        amount=float(amount),
        user_id=callback.from_user.id,
        username=callback.from_user.username or "",
    )

    # Telegram Premium / Stars do not use a PUBG-style Player ID.
    # TikTok uses a separate account-identification flow below.
    needs_player_id = prefix not in {"premium", "stars", "tiktok"}

    if prefix == "tiktok":
        await state.update_data(player_id="", tiktok_identifier="")
        await state.set_state(OrderState.waiting_tiktok_identifier)
        await callback.message.answer(
            pe(
                f"📱 Product: {product}\n"
                f"💰 Amount: {amount:.2f} ETB\n\n"
                "⚠️ ACCOUNT SECURITY\n"
                "For your security, never send your TikTok password or "
                "2-step verification code to this bot.\n\n"
                "Tap I UNDERSTAND to continue with password-free account "
                "identification."
            ),
            reply_markup=kb([
                [premium_button(text="✅ I UNDERSTAND", callback_data="tiktok:understand")],
                [premium_button(text="🚫 CANCEL", callback_data="cancel")],
            ]),
        )
        await callback.answer()
        return

    if needs_player_id:
        await state.set_state(OrderState.waiting_player_id)
        await callback.message.answer(
            pe(
                f"🎮 Product: {product}\n"
                f"💰 Amount: {amount:.2f} ETB\n\n"
                "Please enter your PLAYER ID:"
            ),
            reply_markup=kb([back_cancel("products")])
        )
    else:
        await state.update_data(player_id="")
        await state.set_state(OrderState.waiting_confirmation)
        await callback.message.answer(
            pe(
                f"📦 Product: {product}\n"
                f"💰 Amount: {amount:.2f} ETB\n\n"
                "Please confirm this order."
            ),
            reply_markup=yes_no_cancel()
        )
    await callback.answer()


@dp.callback_query(F.data == "tiktok:understand")
async def tiktok_understand(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("prefix") != "tiktok":
        await callback.answer("This action is not available.", show_alert=True)
        return

    await callback.message.answer(
        pe(
            "📱 TikTok account verification\n\n"
            "Send the TikTok email, username, or other non-password account "
            "identifier required for this order.\n\n"
            "🔐 Never send your TikTok password or verification code here."
        )
    )
    await callback.answer()


@dp.message(StateFilter(OrderState.waiting_tiktok_identifier))
async def receive_tiktok_identifier(message: Message, state: FSMContext):
    identifier = (message.text or "").strip()
    if not identifier or len(identifier) > 100:
        await message.answer(
            pe("❌ Invalid account identifier. Please send your TikTok email or username.")
        )
        return

    data = await state.get_data()
    await state.update_data(
        tiktok_identifier=identifier,
        player_id=identifier,
    )
    await state.set_state(OrderState.waiting_confirmation)

    await message.answer(
        pe(
            f"📱 TikTok account: {identifier}\n"
            f"📦 Product: {data['product']}\n"
            f"💰 Amount: {data['amount']:.2f} ETB\n\n"
            "Please confirm that this is the correct account."
        ),
        reply_markup=yes_no_cancel(),
    )


@dp.message(StateFilter(OrderState.waiting_player_id))
async def receive_player_id(message: Message, state: FSMContext):
    player_id = message.text.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{3,40}", player_id):
        await message.answer(pe("❌ Invalid Player ID. Please send a valid ID."))
        return

    # Real account-name lookup needs the game's official/provider API.
    # We do not fake the account name.
    await state.update_data(player_id=player_id)
    data = await state.get_data()
    await state.set_state(OrderState.waiting_confirmation)

    await message.answer(
        pe(
            f"👤 Player ID: {player_id}\n"
            f"📦 Product: {data['product']}\n"
            f"💰 Amount: {data['amount']:.2f} ETB\n\n"
            "⚠️ Please make sure the Player ID is correct.\n"
            "Confirm that this is your account:"
        ),
        reply_markup=yes_no_cancel()
    )


@dp.callback_query(F.data == "confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(OrderState.waiting_payment)
    await callback.message.answer(
        pe(
            "💳 PAYMENT METHODS\n\n"
            "Choose your payment method:"
        ),
        reply_markup=payment_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "confirm:no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("prefix") == "tiktok":
        await state.set_state(OrderState.waiting_tiktok_identifier)
        await callback.message.answer(
            pe(
                "Please enter the correct TikTok email or username.\n\n"
                "🔐 Do not send your TikTok password or verification code."
            )
        )
    else:
        await state.set_state(OrderState.waiting_player_id)
        await callback.message.answer(
            pe("Please enter the correct PLAYER ID:"),
            reply_markup=kb([back_cancel("products")])
        )
    await callback.answer()


# ============================================================
# PAYMENT
# ============================================================

@dp.callback_query(F.data.startswith("pay:"))
async def choose_payment(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":", 1)[1]
    account, name = PAYMENTS.get(method, ("", ""))

    if not account:
        await callback.answer("Invalid payment method.", show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(payment_method=method)

    text = pe(
        f"💳 PAYMENT — {method}\n\n"
        f"📦 Product: {data['product']}\n"
        f"💰 Amount: {data['amount']:.2f} ETB\n"
        f"🏦 {method}\n"
        f"📞 Account: {account}\n"
        f"👤 Name: {name}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ LEGAL WARNING:\n"
        "By paying, you confirm you are 18+ and agree to our Terms.\n\n"
        "🔹 INSTRUCTIONS:\n"
        "1️⃣ Copy account & verify name.\n"
        f"2️⃣ Send EXACTLY {data['amount']:.2f} ETB only.\n"
        "3️⃣ After payment, copy and paste your payment SMS here.\n"
        "4️⃣ The receipt URL is required for verification.\n\n"
        "🔗 Your SMS must contain an http/https receipt URL.\n"
        "⏳ Order expires in 30 minutes.\n\n"
        "Type /cancel to cancel."
    )

    await state.set_state(OrderState.waiting_sms)
    await callback.message.answer(text)
    await callback.answer()


@dp.message(StateFilter(OrderState.waiting_sms))
async def receive_sms(message: Message, state: FSMContext):
    text = message.text or message.caption or ""
    url = receipt_url(text)

    if not url:
        await message.answer(
            pe(
                "Could not find a receipt URL in your SMS. ❌\n"
                "Please paste the SMS that contains the receipt link (http/https).\n"
                "Type /cancel to cancel."
            )
        )
        return

    data = await state.get_data()
    data["payment_sms"] = text
    data["receipt_url"] = url

    order_id = create_order(data)
    update_order(order_id, payment_sms=text, receipt_url=url)

    await state.clear()

    await message.answer(
        pe(
            f"🔍 Found transaction ID: {url}\n"
            f"⏳ Verifying payment...\n\n"
            f"Order #{order_id} has been sent to the owner for review."
        )
    )

    owner_text = pe(
        f"🧾 NEW ORDER #{order_id}\n\n"
        f"👤 User: @{data.get('username') or 'No username'}\n"
        f"🆔 User ID: {data['user_id']}\n"
        f"📦 Product: {data['product']}\n"
        f"💰 Amount: {data['amount']:.2f} ETB\n"
        f"🎮 Player ID: {data.get('player_id') or 'N/A'}\n"
        f"🏦 Payment: {data.get('payment_method')}\n"
        f"🔗 Receipt URL: {url}\n\n"
        f"📨 SMS:\n{data['payment_sms'][:3000]}"
    )

    try:
        await bot.send_message(
            OWNER_ID,
            owner_text,
            reply_markup=owner_order_keyboard(order_id)
        )
    except Exception:
        logging.exception("Could not send order to owner")


# ============================================================
# OWNER ACCEPT / REJECT
# ============================================================

@dp.callback_query(F.data.startswith("owner:"))
async def owner_action(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Not authorized.", show_alert=True)
        return

    _, action, order_id_text = callback.data.split(":")
    order_id = int(order_id_text)
    order = get_order(order_id)

    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return

    if action == "accept":
        update_order(order_id, status="accepted")
        await callback.message.edit_reply_markup(reply_markup=None)

        await state.set_state(OrderState.waiting_delivery_receipt)
        await state.update_data(order_id=order_id)

        await callback.message.answer(
            pe(
                f"✅ Order #{order_id} accepted.\n\n"
                "Payment/order details were accepted.\n"
                "Now send the delivery receipt/photo/document here. "
                "After the receipt is sent to the customer, you will "
                "get the TRUSTED / NOT TRUSTED buttons."
            )
        )

        await bot.send_message(
            order["user_id"],
            pe(
                f"✅ Your order #{order_id} has been accepted.\n\n"
                f"📦 {order['product']}\n"
                f"💰 {order['amount']:.2f} ETB\n\n"
                "Your payment was accepted and the owner is now "
                "completing your order. Please wait for the delivery confirmation."
            )
        )
    else:
        update_order(order_id, status="rejected")
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            order["user_id"],
            pe(
                f"❌ Order #{order_id} could not be accepted.\n\n"
                "Please send the correct payment SMS and receipt URL."
            )
        )
    await callback.answer()


@dp.message(StateFilter(OrderState.waiting_delivery_receipt))
async def receive_delivery_receipt(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    order = get_order(order_id) if order_id else None

    if not order:
        await state.clear()
        await message.answer(pe("❌ Order not found."))
        return

    # Forward the owner's delivery proof to the customer without
    # exposing internal bot state.
    try:
        if message.photo:
            await bot.send_photo(
                order["user_id"],
                message.photo[-1].file_id,
                caption=pe(
                    f"📦 DELIVERY CONFIRMATION — ORDER #{order_id}\n\n"
                    f"Product: {order['product']}\n"
                    "Your order has been completed by the owner. "
                    "The delivery receipt is attached above."
                ),
            )
        elif message.document:
            await bot.send_document(
                order["user_id"],
                message.document.file_id,
                caption=pe(
                    f"📦 DELIVERY CONFIRMATION — ORDER #{order_id}\n\n"
                    f"Product: {order['product']}\n"
                    "Your order has been completed by the owner. "
                    "The delivery receipt is attached."
                ),
            )
        else:
            receipt_text = message.text or message.caption or ""
            await bot.send_message(
                order["user_id"],
                pe(
                    f"📦 DELIVERY CONFIRMATION — ORDER #{order_id}\n\n"
                    f"Product: {order['product']}\n"
                    "Your order has been completed by the owner.\n\n"
                    f"Receipt/confirmation:\n{receipt_text}"
                ),
            )
    except Exception:
        logging.exception("Could not send delivery receipt to customer")
        await message.answer(
            pe("❌ Could not send the delivery receipt to the customer. Please try again.")
        )
        return

    await message.answer(
        pe(
            f"✅ Delivery receipt for order #{order_id} was sent to the customer.\n\n"
            "Choose the final customer trust status:"
        ),
        reply_markup=trust_keyboard(order_id),
    )
    await state.clear()


@dp.callback_query(F.data.startswith("trust:"))
async def trusted(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Not authorized.", show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return

    update_order(order_id, status="completed")
    await callback.message.edit_reply_markup(reply_markup=None)

    await bot.send_message(
        order["user_id"],
        pe(
            "🎉 ORDER COMPLETED SUCCESSFULLY!\n\n"
            f"📦 Product: {order['product']}\n"
            f"💰 Amount: {order['amount']:.2f} ETB\n"
            f"🧾 Order ID: #{order_id}\n\n"
            "Thank you for trusting our service! ❤️\n"
            "We appreciate your order and hope to serve you again."
        )
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("notrust:"))
async def not_trusted(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Not authorized.", show_alert=True)
        return
    order_id = int(callback.data.split(":")[1])
    await state.set_state(OrderState.waiting_not_trusted_reason)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        pe("⚠️ Please describe what was missing or incorrect:")
    )
    await callback.answer()


@dp.message(StateFilter(OrderState.waiting_not_trusted_reason))
async def receive_not_trusted_reason(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    data = await state.get_data()
    order_id = data["order_id"]
    order = get_order(order_id)

    if order:
        await bot.send_message(
            order["user_id"],
            pe(
                f"⚠️ Order #{order_id}\n\n"
                "Your order could not be trusted yet.\n"
                f"Reason from owner:\n{message.text}\n\n"
                "Please correct the issue and send the required receipt/payment proof."
            )
        )
        await bot.send_message(
            OWNER_ID,
            f"📝 Not-trusted reason for order #{order_id} was sent to the customer."
        )
        update_order(order_id, status="needs_correction")

    await state.clear()


# ============================================================
# ORDERS / SUPPORT / INFO / HELP / TICKET
# ============================================================

@dp.callback_query(F.data == "myorders")
async def myorders(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    if not orders:
        await edit_or_send(
            callback,
            pe("📦 MY ORDERS\n\nYou don't have any orders yet."),
            kb([back_cancel("home")])
        )
        return

    lines = ["📦 MY ORDERS\n"]
    for o in orders:
        lines.append(
            f"#{o['id']} — {o['product']}\n"
            f"💰 {o['amount']:.2f} ETB — {o['status']}\n"
            f"📅 {o['created_at'][:16]}\n"
        )
    await edit_or_send(callback, pe("\n".join(lines)), kb([back_cancel("home")]))
    await callback.answer()


@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            "🆘 SUPPORT\n\n"
            "Need help with an order?\n"
            "Press the button below to message the administrator."
        ),
        kb([
            [premium_button(text="💬 MESSAGE ADMIN",
                                  url=f"https://t.me/{SUPPORT_USERNAME}")],
            back_cancel("home"),
        ])
    )
    await callback.answer()


@dp.callback_query(F.data == "info")
async def info(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            "ℹ️ ABOUT IMRAN TOPUP BOT\n"
            "Version: 2.0.0\n"
            "Platform: Telegram Bot\n\n"
            "FEATURES:\n"
            "24/7 Service\n"
            "✅ Instant & Manual Delivery\n"
            "✅ Secure Payment\n"
            "✅ Order Tracking\n"
            "✅ Customer Support\n\n"
            "🎮 PUBG UC\n"
            "🔥 Free Fire\n"
            "📱 TikTok Coins\n"
            "⚔️ Delta Force\n"
            "⭐ Telegram Premium & Stars\n\n"
            f"Contact: @{SUPPORT_USERNAME}\n\n"
            "Thank you! 🚀"
        ),
        kb([back_cancel("home")])
    )
    await callback.answer()


@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            "❓ HELP GUIDE\n\n"
            "Commands:\n"
            "/start — Main menu\n"
            "/myorders — View orders\n"
            "/support — Contact support\n"
            "/channel — Join channel\n"
            "/info — About bot\n"
            "/help — This message\n"
            "/cancel — Cancel current order\n\n"
            "How to Order:\n"
            "1. Select category\n"
            "2. Choose product\n"
            "3. Enter ID when required\n"
            "4. Confirm\n"
            "5. Select payment\n"
            "6. Paste payment SMS with receipt URL\n\n"
            "Need help? Contact support."
        ),
        kb([back_cancel("home")])
    )
    await callback.answer()


@dp.callback_query(F.data == "ticket")
async def ticket(callback: CallbackQuery):
    user_id = callback.from_user.id

    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM tickets WHERE user_id=?",
            (user_id,),
        ).fetchone()

        if row:
            ticket_number = row["ticket_number"]
            await callback.message.answer(
                pe(
                    f"🎟️ YOUR TICKET NUMBER: #{ticket_number}\n\n"
                    "This ticket number was already assigned to you. "
                    "One customer can receive only one ticket number."
                )
            )
            await callback.answer()
            return

        while True:
            ticket_number = random.randint(100000, 999999)
            exists = con.execute(
                "SELECT 1 FROM tickets WHERE ticket_number=?",
                (ticket_number,),
            ).fetchone()
            if not exists:
                break

        con.execute(
            """
            INSERT INTO tickets(user_id, ticket_number, created_at, status)
            VALUES(?,?,?,?)
            """,
            (user_id, ticket_number, datetime.utcnow().isoformat(), "open"),
        )
        con.commit()

    username = callback.from_user.username or "No username"

    await callback.message.answer(
        pe(
            "🎟️ TICKET CREATED SUCCESSFULLY\n\n"
            f"Your ticket number is: #{ticket_number}\n\n"
            "Keep this number safe. It can be used for the giveaway. "
            "Each customer can receive a ticket number only once."
        )
    )

    await bot.send_message(
        OWNER_ID,
        pe(
            "🎟️ NEW GIVEAWAY TICKET\n\n"
            f"Ticket Number: #{ticket_number}\n"
            f"User: @{username}\n"
            f"User ID: {user_id}"
        ),
    )
    await callback.answer()


# ============================================================
# BACK / CANCEL
# ============================================================

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        pe("❌ Current order cancelled."),
        reply_markup=main_menu()
    )
    await callback.answer()


@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        pe("❌ Current order cancelled."),
        reply_markup=main_menu()
    )


@dp.callback_query(F.data.startswith("back:"))
async def back_callback(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":", 1)[1]
    if target == "home":
        await state.clear()
        await show_home(callback.message)
    elif target == "products":
        data = await state.get_data()
        prefix = data.get("prefix", "pubg_fast")
        await show_product_menu(callback, prefix)
    else:
        await state.clear()
        await show_home(callback.message)
    await callback.answer()


# ============================================================
# COMMANDS
# ============================================================

@dp.message(Command("star"))
async def star_command(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)


@dp.message(Command("myorders"))
async def myorders_command(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(
            pe("📦 You don't have any orders yet."),
            reply_markup=main_menu(),
        )
        return
    lines = ["📦 MY ORDERS\n"]
    for o in orders:
        lines.append(
            f"#{o['id']} — {o['product']}\n"
            f"💰 {o['amount']:.2f} ETB — {o['status']}\n"
        )
    await message.answer(pe("\n".join(lines)), reply_markup=main_menu())


@dp.message(Command("support"))
async def support_command(message: Message):
    await message.answer(
        pe("🆘 Support:"),
        reply_markup=kb([
            [premium_button(text="💬 MESSAGE ADMIN",
                                  url=f"https://t.me/{SUPPORT_USERNAME}")],
            [premium_button(text="🏠 HOME", callback_data="back:home")]
        ])
    )


@dp.message(Command("channel"))
async def channel_command(message: Message):
    await message.answer(
        pe("📢 Our Channel"),
        reply_markup=kb([
            [premium_button(text="📢 JOIN CHANNEL", url=CHANNEL_URL)],
            [premium_button(text="🏠 HOME", callback_data="back:home")]
        ])
    )


@dp.message(Command("info"))
async def info_command(message: Message):
    await message.answer(
        pe("ℹ️ About IMRAN TOPUP BOT\n\n24/7 Service\n✅ Secure Payment\n✅ Order Tracking"),
        reply_markup=main_menu()
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        pe(
            "❓ HELP GUIDE\n\n"
            "/start — Main menu\n"
            "/myorders — View orders\n"
            "/support — Contact support\n"
            "/channel — Join channel\n"
            "/info — About bot\n"
            "/help — This message\n"
            "/cancel — Cancel current order"
        ),
        reply_markup=main_menu()
    )


# ============================================================
# GENERIC CALLBACK ROUTER
# ============================================================

@dp.callback_query(F.data.startswith("cat:"))
async def category_callback(callback: CallbackQuery):
    await show_category(callback, callback.data.split(":", 1)[1])
    await callback.answer()


@dp.callback_query(F.data.startswith("prodmenu:"))
async def product_menu_callback(callback: CallbackQuery):
    await show_product_menu(callback, callback.data.split(":", 1)[1])
    await callback.answer()


# ============================================================
# ADMIN COMMANDS
# ============================================================

@dp.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer(pe("Usage: /broadcast your message"))
        return

    with closing(sqlite3.connect(DB)) as con:
        users = con.execute("SELECT DISTINCT user_id FROM orders").fetchall()

    sent = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, pe(text))
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(pe(f"📢 Broadcast sent to {sent} users."))


# ============================================================
# FALLBACK
# ============================================================

@dp.message()
async def fallback(message: Message):
    await message.answer(
        pe("Please use the menu below 👇"),
        reply_markup=main_menu()
    )



# ============================================================
# RENDER HEALTH SERVER + STARTUP
# ============================================================

app = Flask(__name__)

@app.get("/")
def home_health():
    return "IMRAN TOPUP BOT is running ✅", 200

@app.get("/health")
def health():
    return {"status": "ok", "bot": "IMRAN TOPUP BOT"}, 200


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


async def main():
    db_init()

    # Warn early if an image is missing from the GitHub repository.
    for key, path in PHOTOS.items():
        if not os.path.isfile(path):
            logging.warning("Missing image: %s -> %s", key, path)

    # Flask runs in a small background thread so Render/UptimeRobot
    # can reach /health while the Telegram bot uses long polling.
    Thread(target=run_health_server, daemon=True).start()

    logging.info("IMRAN TOPUP BOT is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
