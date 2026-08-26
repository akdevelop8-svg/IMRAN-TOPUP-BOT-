import os
import re
import html
import random
import asyncio
import logging
import sqlite3
from urllib.parse import urlparse
from contextlib import closing
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from flask import Flask
from threading import Thread

# ============================================================
# IMRAN TOPUP BOT — CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("CHAT_ID", "0") or 0)
PREMIUM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID", "5469921699367510137").strip() or "5469921699367510137"

CUSTOM_EMOJI_IDS_RAW = os.getenv("CUSTOM_EMOJI_IDS", "").strip()
CUSTOM_EMOJI_MAP = {}
CUSTOM_EMOJI_POOL = []

if CUSTOM_EMOJI_IDS_RAW:
    for item in CUSTOM_EMOJI_IDS_RAW.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            key, emoji_id = item.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            emoji_id = emoji_id.strip()
            if key and emoji_id:
                CUSTOM_EMOJI_MAP[key] = emoji_id
                CUSTOM_EMOJI_POOL.append(emoji_id)
        else:
            CUSTOM_EMOJI_POOL.append(item)

CUSTOM_EMOJI_MAP.update({
    "pubg": "5278246233889063347",
    "freefire": "6208513812077743191",
    "tiktok": "5397672154651181662",
    "delta": "6066360629487211677",
    "telegram": "5866355487255039002",
    "bloodstrike": "6221958163520819301",
    "orders": "5217877998937595307",
    "support": "5307746710682869587",
    "ticket": "5285376730003954510",
    "info": "5452002597592382164",
    "help": "6222116634929140568",
    "payment": "5961054379350955385",
    "telebirr": "5960632377339285724",
    "dashen": "5960773097647771692",
    "accept": "6221736233970700254",
    "reject": "6224185666704511761",
    "notrust": "6224089042825253392",
    "back": "5352759161945867747",
    "warning": "6222095018358740369",
    "fortnite": "5951592192735712173",
    "stars": "5954135079662916434",
    "default": "6221958163520819301",
})

_ALIAS_GROUPS = {
    "uc": "pubg",
    "products": "pubg",
    "product": "pubg",
    "payment_method": "payment",
    "trusted": "accept",
    "yes": "accept",
    "understand": "accept",
    "completed": "accept",
    "no": "reject",
    "cancel": "reject",
    "not_trusted": "notrust",
    "notrust": "notrust",
    "back": "back",
    "fortnite_vbucks": "fortnite",
    "vbucks": "fortnite",
    "stars_button": "stars",
    "cbe": "payment",
}
for alias, target in _ALIAS_GROUPS.items():
    if alias not in CUSTOM_EMOJI_MAP and target in CUSTOM_EMOJI_MAP:
        CUSTOM_EMOJI_MAP[alias] = CUSTOM_EMOJI_MAP[target]

if not CUSTOM_EMOJI_POOL:
    CUSTOM_EMOJI_POOL = [PREMIUM_EMOJI_ID]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")
if not OWNER_ID:
    raise RuntimeError("CHAT_ID is missing.")

CHANNEL_URL = "https://t.me/IMRAN_SH0P"
SUPPORT_USERNAME = "IMRAN_TOP_UP"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")

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
    "fortnite": os.path.join(IMAGE_DIR, "Fortnite.jpg"),
}

PAYMENTS = {
    "Telebirr": ("0982903324", "Kayamo"),
    "CBE": ("1000219425809", "Alemnesh"),
    "Dashen": ("5543988503011", "Alemnesh"),
}

DB = "bot.db"
logging.basicConfig(level=logging.INFO)

# ============================================================
# PRODUCTS DYNAMIC CACHE & DEFAULT VALUES
# ============================================================

PRODUCTS_CACHE = {}

DEFAULT_PRODUCTS = {
    "pubg_fast": [
        ("60 UC", 190), ("120 UC", 380), ("180 UC", 550),
        ("325 UC", 880), ("385 UC", 1100), ("660 UC", 1765),
        ("720 UC", 1920), ("985 UC", 2820), ("1320 UC", 3600),
        ("1800 UC", 4350), ("1920 UC", 4800), ("2460 UC", 6300),
        ("3850 UC", 8700),
    ],
    "pubg_manual": [
        ("30 UC", 130), ("240 UC", 700), ("325 UC", 850),
        ("385 UC", 1050), ("445 UC", 1230), ("660 UC", 1700),
        ("720 UC", 1890), ("780 UC", 2050), ("985 UC", 2600),
        ("1045 UC", 2750), ("1320 UC", 3500), ("1800 UC", 4300),
        ("2125 UC", 5300), ("3850 UC", 8550), ("4000 UC", 9150),
        ("8100 UC", 17000), ("16200 UC", 33900),
    ],
    "growth": [
        ("First purchase pack", 200),
        ("Upgradeable firearm pack", 550),
        ("Mythic Emblem pack", 900),
    ],
    "prime": [
        ("Prime 1 Month", 200), ("Prime 3 Months", 600),
        ("Prime 6 Months", 1150), ("Prime Plus 1 Month", 1700),
        ("Prime 12 Months", 2100), ("Prime Plus 3 Months", 5000),
        ("Prime Plus 6 Months", 9900), ("Prime Plus 12 Months", 19900),
    ],
    "rp": [
        ("ELITE PASS 150 + 50 UC GIFT", 1200),
        ("ELITE PASS 100 + 100 UC GIFT", 2300),
    ],
    "mythic": [
        ("Mythic Emblem Value Pack", 700),
    ],
    "freefire": [
        ("100+10", 230), ("210+21", 440), ("530+53", 950),
        ("1080+108", 1900), ("2200+220", 3750),
    ],
    "tiktok": [
        ("200 COIN", 500), ("500 COIN", 1200), ("800 COIN", 1800),
        ("1000 COIN", 2300), ("1500 COIN", 3300), ("2000 COIN", 4400),
        ("2500 COIN", 5500), ("3000 COIN", 6600), ("4000 COIN", 8650),
        ("5000 COIN", 10900), ("7500 COIN", 16500), ("10000 COIN", 22000),
    ],
    "delta_coin": [
        ("30 Coins", 130), ("60 Coins", 190), ("320 Coins", 800),
        ("460 Coins", 1200), ("750 Coins", 1650), ("1480 Coins", 3100),
        ("1980 Coins", 3950), ("3950 Coins", 7650),
    ],
    "delta_special": [
        ("Season Pass Operations Special", 900),
        ("Season Pass Warfare Special", 900),
        ("S/Pass Delta Force Deluxe", 1300),
    ],
    "premium": [
        ("Telegram Premium 1 Month", 350),
        ("Telegram Premium 3 Months", 950),
        ("Telegram Premium 6 Months", 1800),
        ("Telegram Premium 12 Months", 3300),
    ],
    "stars": [
        ("Telegram Stars 100", 250), ("Telegram Stars 500", 1100),
        ("Telegram Stars 1000", 2100),
    ],
    "bloodstrike_golds": [
        ("50+1 BC", 100), ("100+5 BC", 190), ("300+20 BC", 500),
        ("500+40 BC", 780), ("1100 BC", 1500), ("2260 BC", 2950),
    ],
    "bloodstrike_offers": [
        ("Ultra Skin Lucky Chest", 150),
        ("Season Pass", 250),
        ("Level Up Pass", 400),
        ("Strike Pass Elite", 700),
        ("Strike Pass Premium", 1550),
    ],
    "fortnite": [
        ("1000 V-BUCKS = 1800 BIRR💵", 1800),
        ("2800 V-BUCKS = 4000 BIRR💵", 4000),
        ("5000 V-BUCKS = 6300 BIRR💵", 6300),
        ("13,500 V-BUCKS = 15,000 BIRR💵", 15000),
    ]
}

def load_products_cache():
    global PRODUCTS_CACHE
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT prefix, item_index, name, price FROM products ORDER BY prefix, item_index").fetchall()
        cache = {}
        for r in rows:
            p = r["prefix"]
            if p not in cache:
                cache[p] = []
            cache[p].append((r["name"], float(r["price"])))
        PRODUCTS_CACHE = cache

def update_product_price_in_db(prefix: str, item_index: int, new_price: float):
    with closing(sqlite3.connect(DB)) as con:
        con.execute(
            "UPDATE products SET price=? WHERE prefix=? AND item_index=?",
            (new_price, prefix, item_index)
        )
        con.commit()
    load_products_cache()

def get_products(prefix: str):
    return PRODUCTS_CACHE.get(prefix, [])

# ============================================================
# DATABASE INITIALIZATION
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
                tiktok_email TEXT,
                tiktok_phone TEXT,
                tiktok_password TEXT,
                payment_method TEXT,
                payment_sms TEXT,
                receipt_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        columns = {row[1] for row in con.execute("PRAGMA table_info(orders)").fetchall()}
        for column in ("tiktok_email", "tiktok_phone", "tiktok_password"):
            if column not in columns:
                con.execute(f"ALTER TABLE orders ADD COLUMN {column} TEXT")

        con.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                user_id INTEGER PRIMARY KEY,
                ticket_number INTEGER UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'open'
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                prefix TEXT NOT NULL,
                item_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                PRIMARY KEY (prefix, item_index)
            )
        """)
        con.commit()

        # Seed initial products if table is empty
        count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            for prefix, items in DEFAULT_PRODUCTS.items():
                for idx, (name, price) in enumerate(items):
                    con.execute(
                        "INSERT INTO products (prefix, item_index, name, price) VALUES (?, ?, ?, ?)",
                        (prefix, idx, name, price)
                    )
            con.commit()

    load_products_cache()

def create_order(data):
    with closing(sqlite3.connect(DB)) as con:
        cur = con.execute("""
            INSERT INTO orders
            (user_id, username, product, amount, player_id, tiktok_email,
             tiktok_phone, tiktok_password, payment_method, payment_sms,
             receipt_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            data["user_id"], data.get("username", ""), data["product"], data["amount"],
            data.get("player_id", ""), data.get("tiktok_email", ""),
            data.get("tiktok_phone", ""), data.get("tiktok_password", ""),
            data.get("payment_method", ""), data.get("payment_sms", ""),
            data.get("receipt_url", ""), datetime.utcnow().isoformat()
        ))
        con.commit()
        return cur.lastrowid

def update_order(order_id, **fields):
    allowed = {
        "payment_sms", "receipt_url", "status", "payment_method",
        "player_id", "tiktok_email", "tiktok_phone", "tiktok_password"
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

def get_latest_order_for_user(user_id, statuses=None):
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            row = con.execute(
                f"SELECT * FROM orders WHERE user_id=? AND status IN ({placeholders}) ORDER BY id DESC LIMIT 1",
                (user_id, *statuses),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

# ============================================================
# PREMIUM CUSTOM EMOJI HELPERS
# ============================================================

EMOJI_KEYWORDS = [
    ("pubg", ("pubg", "uc", "rp", "prime", "growth", "mythic")),
    ("freefire", ("free fire", "freefire", "diamond")),
    ("tiktok", ("tiktok", "coin")),
    ("delta", ("delta force", "delta")),
    ("telegram", ("telegram premium", "telegram stars", "premium", "stars")),
    ("bloodstrike", ("blood strike", "bloodstrike", "bc")),
    ("fortnite", ("fortnite", "v-bucks", "vbucks", "v bucks")),
    ("payment", ("payment", "payment method")),
    ("telebirr", ("telebirr",)),
    ("dashen", ("dashen",)),
    ("orders", ("my orders", "view orders", "order history")),
    ("ticket", ("ticket", "giveaway")),
    ("support", ("support", "message admin", "contact support")),
    ("channel", ("channel", "join channel")),
    ("info", ("about", "info")),
    ("help", ("help guide", "help")),
    ("accept", ("accept", "yes", "trusted", "understand", "completed successfully", "completed")),
    ("reject", ("reject", "no", "not trusted", "cancel", "cancelled", "canceled")),
    ("notrust", ("not trusted", "notrust")),
    ("warning", ("important", "warning", "do not", "invalid", "error", "failed", "not accepted")),
    ("back", ("back", "return", "go back")),
]

def _emoji_id_for(key: str = None, text: str = "") -> str:
    key = (key or "").strip().lower().replace(" ", "_")
    if key and key in CUSTOM_EMOJI_MAP:
        return CUSTOM_EMOJI_MAP[key]
    lowered = (text or "").lower()
    for semantic_key, words in EMOJI_KEYWORDS:
        if any(word in lowered for word in words):
            if semantic_key in CUSTOM_EMOJI_MAP:
                return CUSTOM_EMOJI_MAP[semantic_key]
    return CUSTOM_EMOJI_MAP.get("default", CUSTOM_EMOJI_POOL[0])

def pe(text: str, emoji_key: str = None, skip_fire: bool = False) -> str:
    text = "" if text is None else str(text)
    text = "\n".join(line.strip() for line in text.splitlines())
    safe_text = html.escape(text, quote=False)
    emoji_id = _emoji_id_for(emoji_key, text)
    if skip_fire:
        return safe_text
    return f'<tg-emoji emoji-id="{emoji_id}">🔥</tg-emoji> {safe_text}'

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ============================================================
# FSM STATES
# ============================================================

class OrderState(StatesGroup):
    waiting_player_id = State()
    waiting_confirmation = State()
    waiting_payment = State()
    waiting_sms = State()
    waiting_not_trusted_reason = State()
    waiting_delivery_receipt = State()
    waiting_tiktok_email = State()
    waiting_tiktok_phone = State()
    waiting_tiktok_password = State()

class AdminState(StatesGroup):
    waiting_broadcast_content = State()
    waiting_new_price = State()

# ============================================================
# KEYBOARD BUILDERS
# ============================================================

def premium_button(text: str, style: str = None, emoji_key: str = None, **kwargs):
    label = str(text).strip()
    upper = label.upper()
    callback_data = str(kwargs.get("callback_data", "")).lower()

    if style is None:
        if (
            "CANCEL" in upper
            or "REJECT" in upper
            or "NOT TRUSTED" in upper
            or upper == "NO"
            or callback_data.startswith("cancel")
            or callback_data.startswith("owner:reject:")
            or callback_data.startswith("notrust:")
            or callback_data == "confirm:no"
        ):
            style = "danger"
        elif (
            "ACCEPT" in upper
            or upper == "YES"
            or "TRUSTED" in upper
            or "I UNDERSTAND" in upper
            or "PAYMENT" in upper
            or callback_data.startswith("owner:accept:")
            or callback_data.startswith("trust:")
            or callback_data == "confirm:yes"
            or callback_data == "tiktok:understand"
            or callback_data.startswith("pay:")
        ):
            style = "success"
        else:
            style = "primary"

    if emoji_key is None:
        raw_key = callback_data.split(":", 1)[0] if callback_data else ""
        callback_keys = {
            "pay": "payment",
            "trust": "accept",
            "fortnite": "fortnite",
            "notrust": "notrust",
            "confirm": "accept" if callback_data == "confirm:yes" else "reject",
            "owner": "accept" if callback_data.startswith("owner:accept:") else "reject",
            "cancel": "reject",
            "back": "back",
        }
        emoji_key = callback_keys.get(raw_key)

    emoji_id = _emoji_id_for(emoji_key, f"{label} {callback_data}")

    return InlineKeyboardButton(
        text=label,
        icon_custom_emoji_id=emoji_id,
        style=style,
        **kwargs,
    )

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_menu():
    return kb([
        [premium_button(text=" PUBG MOBILE", style="primary", emoji_key="pubg", callback_data="cat:pubg"),
         premium_button(text=" FREE FIRE", style="success", emoji_key="freefire", callback_data="cat:freefire")],
        [premium_button(text=" TIKTOK COIN", style="primary", emoji_key="tiktok", callback_data="cat:tiktok"),
         premium_button(text=" DELTA FORCE", style="success", emoji_key="delta", callback_data="cat:delta")],
        [premium_button(text=" TELEGRAM PREMIUM & STARS", style="primary", emoji_key="telegram", callback_data="cat:telegram")],
        [premium_button(text=" BLOOD STRIKE", style="danger", emoji_key="bloodstrike", callback_data="cat:bloodstrike"),
         premium_button(text=" FORTNITE V-BUCKS", style="primary", emoji_key="fortnite", callback_data="cat:fortnite")],
        [premium_button(text=" MY ORDERS", style="primary", emoji_key="orders", callback_data="myorders")],
        [premium_button(text=" GET TICKET", style="success", emoji_key="ticket", callback_data="ticket"),
         premium_button(text=" SUPPORT", style="primary", emoji_key="support", callback_data="support")],
        [premium_button(text=" OUR CHANNEL", style="primary", emoji_key="channel", url=CHANNEL_URL),
         premium_button(text=" INFO", style="primary", emoji_key="info", callback_data="info")],
        [premium_button(text=" HELP", style="success", emoji_key="help", callback_data="help")],
    ])

def back_cancel(callback="home"):
    return [
        premium_button(text=" BACK", style="primary", emoji_key="back", callback_data=f"back:{callback}"),
        premium_button(text=" CANCEL", style="danger", emoji_key="notrust", callback_data="cancel"),
    ]

def category_menu(category):
    if category == "pubg":
        return kb([
            [premium_button(text=" FAST UC", style="primary", emoji_key="pubg", callback_data="prodmenu:pubg_fast")],
            [premium_button(text=" MANUAL UC", style="primary", emoji_key="uc", callback_data="prodmenu:pubg_manual")],
            [premium_button(text=" GROWTH PACK", style="primary", emoji_key="pubg", callback_data="prodmenu:growth")],
            [premium_button(text=" PRIME PLUS", style="primary", emoji_key="pubg", callback_data="prodmenu:prime")],
            [premium_button(text=" MYTHIC EMBLEM", style="primary", emoji_key="pubg", callback_data="prodmenu:mythic")],
            [premium_button(text=" RP", style="primary", emoji_key="pubg", callback_data="prodmenu:rp")],
            back_cancel("home"),
        ])
    if category == "freefire":
        return product_keyboard(get_products("freefire"), "freefire")
    if category == "tiktok":
        return product_keyboard(get_products("tiktok"), "tiktok")
    if category == "delta":
        return kb([
            [premium_button(text=" Delta Force Coins", style="primary", emoji_key="delta", callback_data="prodmenu:delta_coin")],
            [premium_button(text=" Special Offers", style="primary", emoji_key="delta", callback_data="prodmenu:delta_special")],
            back_cancel("home"),
        ])
    if category == "bloodstrike":
        return kb([
            [premium_button(text=" GOLDS", style="primary", emoji_key="bloodstrike", callback_data="prodmenu:bloodstrike_golds")],
            [premium_button(text=" OFFERS", style="primary", emoji_key="bloodstrike", callback_data="prodmenu:bloodstrike_offers")],
            back_cancel("home"),
        ])
    if category == "fortnite":
        return product_keyboard(get_products("fortnite"), "fortnite")
    if category == "telegram":
        return kb([
            [premium_button(text=" Telegram Premium", style="primary", emoji_key="telegram", callback_data="prodmenu:premium")],
            [premium_button(text=" Telegram Stars", style="primary", emoji_key="telegram", callback_data="prodmenu:stars")],
            back_cancel("home"),
        ])
    return kb([[*back_cancel("home")]])

def product_keyboard(products, prefix):
    rows = []
    product_emoji = {
        "premium": "telegram",
        "stars": "stars",
        "fortnite": "fortnite",
        "tiktok": "tiktok",
        "delta_coin": "delta",
    }.get(prefix)
    for i, (name, price) in enumerate(products):
        rows.append([premium_button(
            text=f"{name} — {price:.2f} ETB",
            emoji_key=product_emoji,
            callback_data=f"buy:{prefix}:{i}"
        )])
    rows.append(back_cancel("home"))
    return kb(rows)

def payment_keyboard():
    return kb([
        [premium_button(text=" Telebirr", style="success", emoji_key="telebirr", callback_data="pay:Telebirr")],
        [premium_button(text=" CBE", style="success", emoji_key="payment", callback_data="pay:CBE")],
        [premium_button(text=" Dashen", style="success", emoji_key="dashen", callback_data="pay:Dashen")],
        back_cancel("products"),
    ])

def yes_no_cancel():
    return kb([
        [premium_button(text=" YES", style="success", emoji_key="accept", callback_data="confirm:yes"),
         premium_button(text=" NO", style="danger", emoji_key="reject", callback_data="confirm:no"),
         premium_button(text=" CANCEL", style="danger", emoji_key="notrust", callback_data="cancel")],
    ])

def owner_order_keyboard(order_id):
    return kb([
        [
            premium_button(text="ACCEPT", style="success", emoji_key="accept", callback_data=f"owner:accept:{order_id}"),
            premium_button(text="REJECT", style="danger", emoji_key="reject", callback_data=f"owner:reject:{order_id}")
        ]
    ])

def trust_keyboard(order_id):
    return kb([
        [
            premium_button(text="TRUSTED", style="success", emoji_key="accept", callback_data=f"trust:{order_id}"),
            premium_button(text="NOT TRUSTED", style="danger", emoji_key="notrust", callback_data=f"notrust:{order_id}")
        ]
    ])

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def resolve_photo(path):
    if path and os.path.isfile(path):
        return path
    if path:
        name = os.path.basename(path)
        candidates = [os.path.join(BASE_DIR, name)]
        if name.lower() == "tiktok.jpg":
            candidates.append(os.path.join(IMAGE_DIR, "TikTok.jpg"))
        if name.lower() == "imran.jpg":
            candidates.append(os.path.join(IMAGE_DIR, "imran.jpg"))
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
    return ""

async def send_photo_or_text(message, photo, caption, reply_markup=None):
    photo = resolve_photo(photo)
    if photo:
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
    if not m:
        return None
    candidate = m.group(0).rstrip(".,);]}")
    try:
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return candidate
    except Exception:
        pass
    return None

def product_data(prefix, index):
    items = get_products(prefix)
    if 0 <= index < len(items):
        return items[index]
    return ("Unknown Product", 0.0)

# ============================================================
# START & HOME COMMAND
# ============================================================

async def show_home(message):
    raw_text = (
        "IMRAN TOPUP BOT — Your trusted digital top-up service!\n\n"
        "🎮 Top up your favorite games, purchase TikTok Coins, Telegram Premium & Stars, and access more digital services — all in one place.\n\n"
        "⚡ Fast Service\n"
        "🔒 Secure & Reliable\n"
        "💎 Easy & Convenient\n"
        "🌍 Available 24/7\n\n"
        "Choose your service and enjoy a smooth, simple top-up experience!"
    )
    text = pe(raw_text)
    await send_photo_or_text(message, PHOTOS["home"], text, main_menu())

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)

# ============================================================
# CATEGORY / PRODUCT MENUS
# ============================================================

async def show_category(callback: CallbackQuery, category: str):
    names = {
        "pubg": " PUBG MOBILE",
        "freefire": " FREE FIRE",
        "delta": " DELTA FORCE",
        "telegram": " TELEGRAM PREMIUM & STARS",
        "bloodstrike": " BLOOD STRIKE",
        "fortnite": " FORTNITE V-BUCKS",
    }
    photos = {
        "pubg": PHOTOS["pubg"],
        "freefire": PHOTOS["freefire"],
        "tiktok": PHOTOS["tiktok"],
        "delta": PHOTOS["delta"],
        "telegram": PHOTOS["premium"],
        "bloodstrike": PHOTOS["bloodstrike"],
        "fortnite": PHOTOS["fortnite"],
    }
    
    if category == "tiktok":
        tiktok_items = get_products("tiktok")
        lines = [f"{name} – {price:.2f} ETB" for name, price in tiktok_items]
        text = pe("\n".join(lines), skip_fire=True)
    else:
        text = pe(f"{names.get(category, category)}\n\nSelect a service:")
        
    try:
        photo = resolve_photo(photos.get(category, ""))
        if photo:
            await callback.message.delete()
            await callback.message.answer_photo(
                FSInputFile(photo),
                caption=text,
                reply_markup=category_menu(category)
            )
        else:
            await edit_or_send(callback, text, category_menu(category))
    except Exception:
        await edit_or_send(callback, text, category_menu(category))

async def show_product_menu(callback: CallbackQuery, prefix: str):
    maps = {
        "pubg_fast": (" PUBG FAST UC", "pubg"),
        "pubg_manual": (" PUBG MANUAL UC", "uc"),
        "growth": (" GROWTH PACK", "growth"),
        "prime": (" PRIME PLUS", "prime"),
        "rp": (" RP", "rp"),
        "freefire": (" FREE FIRE", "freefire"),
        "tiktok": (" TIKTOK COINS", "tiktok"),
        "delta_special": (" DELTA FORCE SPECIAL OFFERS", "delta"),
        "premium": (" TELEGRAM PREMIUM", "premium"),
        "stars": (" TELEGRAM STARS", "premium"),
        "bloodstrike_golds": (" BLOOD STRIKE GOLDS", "bloodstrike"),
        "bloodstrike_offers": (" BLOOD STRIKE OFFERS", "bloodstrike"),
        "fortnite": (" FORTNITE V-BUCKS", "fortnite"),
        "delta_coin": (" DELTA FORCE COINS", "delta"),
    }
    if prefix == "mythic":
        items = get_products("mythic")
        price = items[0][1] if items else 700.0
        text = pe(f" MYTHIC EMBLEM VALUE PACK\n\nMythic Emblem Value Pack — {price:.2f} ETB")
        photo_path = resolve_photo(PHOTOS["mythic"])
        try:
            if photo_path and os.path.isfile(photo_path):
                await callback.message.delete()
                await callback.message.answer_photo(
                    FSInputFile(photo_path),
                    caption=text,
                    reply_markup=product_keyboard([("Mythic Emblem Value Pack", price)], "mythic")
                )
            else:
                await edit_or_send(callback, text, product_keyboard([("Mythic Emblem Value Pack", price)], "mythic"))
        except Exception:
            await edit_or_send(callback, text, product_keyboard([("Mythic Emblem Value Pack", price)], "mythic"))
        return

    title, photo_key = maps[prefix]
    products = get_products(prefix)
    photo_path = resolve_photo(PHOTOS.get(photo_key, ""))
    caption = pe(f"{title}\n\nChoose your package:", emoji_key=photo_key)
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

@dp.callback_query(F.data.startswith("cat:"))
async def category_handler(callback: CallbackQuery):
    cat = callback.data.split(":")[1]
    await show_category(callback, cat)
    await callback.answer()

@dp.callback_query(F.data.startswith("prodmenu:"))
async def prodmenu_handler(callback: CallbackQuery):
    prefix = callback.data.split(":")[1]
    await show_product_menu(callback, prefix)
    await callback.answer()

# ============================================================
# ORDER CREATION & INPUT FLOW
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
        cancel_target="products",
    )

    if prefix == "tiktok":
        await state.update_data(
            player_id="", tiktok_email="", tiktok_phone="", tiktok_password=""
        )
        await state.set_state(OrderState.waiting_tiktok_email)
        await callback.message.answer(
            pe("⚠️ IMPORTANT: Please turn off 2-step verification before sharing."),
            reply_markup=kb([
                [premium_button(text="I UNDERSTAND", emoji_key="accept", callback_data="tiktok:understand"),
                 premium_button(text="CANCEL", emoji_key="cancel", callback_data="cancel")]
            ]),
        )
        await callback.answer()
        return

    needs_player_id = prefix not in {"premium", "stars"}
    if needs_player_id:
        await state.set_state(OrderState.waiting_player_id)
        await state.update_data(cancel_target="products")
        await callback.message.answer(
            pe(
                f"Product: {product}\n"
                f"Amount: {amount:.2f} ETB\n\n"
                "Please enter your PLAYER ID:"
            ),
            reply_markup=kb([back_cancel("products")]),
        )
    else:
        await state.update_data(player_id="", cancel_target="home")
        await state.set_state(OrderState.waiting_confirmation)
        await callback.message.answer(
            pe(
                f"Product: {product}\n"
                f"Amount: {amount:.2f} ETB\n\n"
                "Please confirm this order."
            ),
            reply_markup=yes_no_cancel(),
        )
    await callback.answer()

@dp.callback_query(F.data == "tiktok:understand")
async def tiktok_understand(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_tiktok_email)
    await state.update_data(cancel_target="products")
    await callback.message.answer(
        pe("Please enter your TikTok Email:"),
        reply_markup=kb([back_cancel("products")]),
    )
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_tiktok_email))
async def receive_tiktok_email(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    if len(email) > 150:
        await message.answer(pe("Invalid input. Please enter a valid TikTok account email."))
        return
    await state.update_data(tiktok_email=email, cancel_target="products")
    await state.set_state(OrderState.waiting_tiktok_phone)
    await message.answer(
        pe("Please enter your Phone Number:"),
        reply_markup=kb([back_cancel("products")]),
    )

@dp.message(StateFilter(OrderState.waiting_tiktok_phone))
async def receive_tiktok_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    await state.update_data(tiktok_phone=phone, cancel_target="products")
    await state.set_state(OrderState.waiting_tiktok_password)
    await message.answer(
        pe("Please enter your TikTok Password:"),
        reply_markup=kb([back_cancel("products")]),
    )

@dp.message(StateFilter(OrderState.waiting_tiktok_password))
async def receive_tiktok_password(message: Message, state: FSMContext):
    password = (message.text or "").strip()
    await state.update_data(tiktok_password=password, cancel_target="products")
    data = await state.get_data()
    await state.set_state(OrderState.waiting_confirmation)
    await message.answer(
        pe(
            f"Please verify your account details:\n\n"
            f"Email: {data['tiktok_email']}\n"
            f"Phone: {data['tiktok_phone']}\n"
            f"Password: {password}\n"
            f"Product: {data['product']}\n"
            f"Amount: {data['amount']:.2f} ETB\n\n"
            "Is this information correct?"
        ),
        reply_markup=yes_no_cancel(),
    )

@dp.message(StateFilter(OrderState.waiting_player_id))
async def receive_player_id(message: Message, state: FSMContext):
    player_id = message.text.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{3,40}", player_id):
        await message.answer(pe(" Invalid Player ID. Please send a valid ID."))
        return

    await state.update_data(player_id=player_id, cancel_target="home")
    data = await state.get_data()
    await state.set_state(OrderState.waiting_confirmation)

    confirmation_text = (
        f" Player ID: {player_id}\n"
        f" Product: {data['product']}\n"
        f" Amount: {data['amount']:.2f} ETB\n\n"
        " Please make sure the Player ID is correct.\n"
        "Confirm that this is your account:"
    )

    await message.answer(
        pe(confirmation_text, emoji_key="fortnite" if data.get("prefix") == "fortnite" else None),
        reply_markup=yes_no_cancel()
    )

@dp.callback_query(F.data == "confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_payment)
    await callback.message.answer(
        pe(" PAYMENT METHODS\n\nChoose your payment method:"),
        reply_markup=payment_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "confirm:no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prefix = data.get("prefix")
    await state.clear()
    if prefix:
        await show_product_menu(callback, prefix)
    else:
        await show_home(callback.message)
    await callback.answer()

# ============================================================
# PAYMENT & SMS SUBMISSION
# ============================================================

@dp.callback_query(F.data.startswith("pay:"))
async def choose_payment(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":", 1)[1]
    account, name = PAYMENTS.get(method, ("", ""))

    if not account:
        await callback.answer("Invalid payment method.", show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(payment_method=method, cancel_target="payment")

    text = pe(
        f"📦 Product: {data['product']}\n"
        f"💰 Amount: {data['amount']:.2f} ETB\n\n"
        f"🏦 {method}\n"
        f"📞 Account: {account}\n"
        f"👤 Name: {name}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ LEGAL WARNING:\n"
        "By paying, you confirm you are 18+ and agree to our Terms.\n"
        "🔹 INSTRUCTIONS:\n"
        "1️⃣ Copy account & verify name.\n"
        f"2️⃣ Send EXACTLY {data['amount']:.2f} ETB only.\n"
        "3️⃣ After payment, copy and paste your payment SMS here.\n"
        "4️⃣ We verify automatically using transaction reference.\n"
        "⚠️ ሕጋዊ ማስጠንቀቂያ:\n"
        "ክፍያ በማድረግ፣ ከ18 ዓመት በላይ መሆንን ተረድተዋል እና የእኛን ውሎች ተስማምተዋል።\n"
        "1️⃣ ሂሳብ ቁጥር እና ስም ያረጋግጡ።\n"
        f"2️⃣ በትክክል {data['amount']:.2f} ETB ብቻ ይላኩ።\n"
        "3️⃣ ከክፍያ በኋላ፣ የክፍያ ኤስ.ኤም.ኤስ ጽሑፍ እዚህ ይላኩ።\n"
        "4️⃣ በግብይት ማጣቀሻ በራስ-ሰር እናረጋግጣለን።\n"
        "🔗 Paste the SMS that contains your receipt URL (http/https link).\n\n"
        "Type /cancel to cancel."
    )

    await state.set_state(OrderState.waiting_sms)
    await callback.message.answer(text)
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_sms))
async def receive_sms(message: Message, state: FSMContext):
    await process_payment_sms(message, state)

async def process_payment_sms(message: Message, state: FSMContext = None):
    text = message.text or message.caption or "No SMS Text (Screenshot/Document)"
    url = receipt_url(text) or "No URL found in message"

    data = await state.get_data() if state else {}
    data["payment_sms"] = text
    data["receipt_url"] = url
    
    existing = get_latest_order_for_user(message.from_user.id, ["needs_payment_proof", "pending"])

    if existing and existing.get("status") == "needs_payment_proof":
        order_id = existing["id"]
        update_order(order_id, payment_sms=text, receipt_url=url, status="pending")
        order = get_order(order_id) or existing
        data.update(order)
    else:
        data.setdefault("user_id", message.from_user.id)
        data.setdefault("username", message.from_user.username or "")
        order_id = create_order(data)
        update_order(order_id, payment_sms=text, receipt_url=url)
        order = get_order(order_id)

    if state:
        await state.clear()

    await message.answer(
        pe(
            f"🔍 የላኩትን ክፍያ መረጃ ተቀብለናል! (Order #{order_id})\n"
            "⏳ ክፍያዎ ትክክለኛ መሆኑን ለማረጋገጥ መረጃው ወደ ኦውነሩ ተልኳል።\n"
            "ኦውነሩ እንደተመለከተው ወዲያውኑ ምላሽ ያገኛሉ። እባክዎን ጥቂት ደቂቃዎች ይታገሱ!"
        )
    )

    username_str = f"@{order.get('username') or message.from_user.username}" if (order.get('username') or message.from_user.username) else "No Username"
    
    owner_text = pe(
        f"🚨 **አዲስ የትእዛዝ ማረጋገጫ (ORDER #{order_id})**\n\n"
        f"👤 **ደንበኛ:** {username_str}\n"
        f"🆔 **User ID:** `{order.get('user_id', message.from_user.id)}`\n"
        f"📦 **ምርት:** {order.get('product', data.get('product', 'N/A'))}\n"
        f"💰 **የተላከው መጠን:** {float(order.get('amount', data.get('amount', 0))):.2f} ETB\n"
        f"🏦 **የክፍያ መንገድ:** {order.get('payment_method') or data.get('payment_method') or 'N/A'}\n"
        f"🎮 **Player ID:** `{order.get('player_id') or data.get('player_id') or 'N/A'}`\n"
        f"📧 **TikTok Email:** {order.get('tiktok_email') or data.get('tiktok_email') or 'N/A'}\n"
        f"📞 **TikTok Phone:** {order.get('tiktok_phone') or data.get('tiktok_phone') or 'N/A'}\n"
        f"🔑 **TikTok Password:** {order.get('tiktok_password') or data.get('tiktok_password') or 'N/A'}\n"
        f"🔗 **Receipt URL:** {url}\n\n"
        f"📲 **የክፍያ SMS Message:**\n{text[:3000]}"
    )

    try:
        await bot.send_message(OWNER_ID, owner_text, reply_markup=owner_order_keyboard(order_id))
        if message.photo:
            await bot.send_photo(
                OWNER_ID,
                message.photo[-1].file_id,
                caption=pe(f"📸 PAYMENT SCREENSHOT — ORDER #{order_id}\nReceipt URL: {url}"),
            )
        elif message.document:
            await bot.send_document(
                OWNER_ID,
                message.document.file_id,
                caption=pe(f"📄 PAYMENT DOCUMENT — ORDER #{order_id}\nReceipt URL: {url}"),
            )
    except Exception as e:
        logging.exception("Could not send order proof to owner: %s", e)

# ============================================================
# OWNER ACTIONS: ACCEPT / REJECT
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
                f"✅ **ትእዛዝ #{order_id} ተቀብለዋል!**\n\n"
                "እባክዎን የደንበኛውን የትእዛዝ መፈጸሚያ ደረሰኝ (Delivery Receipt Photo, File, or Text) አሁን እዚህ ይላኩ።\n"
                "ደረሰኙን እንደላኩ ወዲያውኑ ለደንበኛው ይላካል ከስሩም TRUSTED እና NOT TRUSTED በተኖች አብረው ይሄዳሉ።"
            )
        )

        await bot.send_message(
            order["user_id"],
            pe(
                f"✅ **ትእዛዝዎ በኦውነሩ ተቀባይነት አግኝቷል! (Order #{order_id})**\n\n"
                f"📦 **ምርት:** {order['product']}\n"
                f"💰 **ዋጋ:** {order['amount']:.2f} ETB\n\n"
                "ክፍያዎ ተረጋግጧል። ኦውነሩ አሁን የተዘዘውን እየሞላሎት ነው፤ የትእዛዝ መፈጸሚያ ደረሰኙ በቅርቡ ይደርስዎታል!"
            )
        )
    else: # Reject
        update_order(order_id, status="needs_payment_proof")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(pe(f"❌ Order #{order_id} rejected. Customer has been asked for valid proof."))
        
        await bot.send_message(
            order["user_id"],
            pe(
                f"❌ **ትእዛዝ #{order_id} አልተቀበለም!**\n\n"
                "የላኩት ደረሰኝ ወይም የክፍያ SMS ትክክለኛ አይደለም። እባክዎን የላኩትን ክፍያ ደግመው ያረጋግጡና ትክክለኛውን "
                "የክፍያ SMS እና የደረሰኝ (Receipt Link) መልእክት መልሰው ይላኩ።"
            )
        )
    await callback.answer()

# ============================================================
# OWNER SENDS DELIVERY RECEIPT -> CUSTOMER
# ============================================================

@dp.message(StateFilter(OrderState.waiting_delivery_receipt))
async def receive_delivery_receipt(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    order = get_order(order_id) if order_id else None

    if not order:
        await state.clear()
        await message.answer(pe("Order not found."))
        return

    long_delivery_text = pe(
        f"✅ **ትእዛዞት በተሳካ ሁኔታ ተፈፅሟል! (ORDER COMPLETED!)**\n\n"
        f"📦 **ምርት:** {order['product']}\n"
        f"💰 **ዋጋ:** {order['amount']:.2f} ETB\n"
        f"🆔 **የትእዛዝ ቁጥር:** #{order['id']}\n\n"
        "ኦውነሩ የትእዛዝዎን መፈጸሚያ ደረሰኝ ልኮልዎታል። እባክዎን አካውንትዎን ወይም አገልግሎትዎን ያረጋግጡ። "
        "አገልግሎታችንን ስለጠቀሙ እጅግ እናመሰግናለን! አገልግሎታችን ከተመችዎት እና አስተማማኝ ሆኖ ካገኙት ከስር 'TRUSTED' የሚለውን በመንካት ይመስክሩልን።"
    )

    try:
        if message.photo:
            await bot.send_photo(
                order["user_id"],
                message.photo[-1].file_id,
                caption=long_delivery_text,
                reply_markup=trust_keyboard(order_id),
            )
        elif message.document:
            await bot.send_document(
                order["user_id"],
                message.document.file_id,
                caption=long_delivery_text,
                reply_markup=trust_keyboard(order_id),
            )
        else:
            receipt_text = message.text or message.caption or ""
            await bot.send_message(
                order["user_id"],
                f"{long_delivery_text}\n\n🧾 **የደረሰኝ ዝርዝር:**\n{receipt_text}",
                reply_markup=trust_keyboard(order_id),
            )
    except Exception as e:
        logging.exception("Could not send delivery receipt to customer: %s", e)
        await message.answer(pe("Could not send the delivery receipt to the customer. Please try again."))
        return

    update_order(order_id, status="delivered")
    await message.answer(pe(f"✅ Delivery receipt for order #{order_id} was successfully sent to the customer."))
    await state.clear()

# ============================================================
# CUSTOMER ACTIONS: TRUSTED / NOT TRUSTED
# ============================================================

@dp.callback_query(F.data.startswith("trust:"))
async def trusted(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    if callback.from_user.id != order["user_id"]:
        await callback.answer("Not authorized.", show_alert=True)
        return

    update_order(order_id, status="completed")
    await callback.message.edit_reply_markup(reply_markup=None)
    
    long_thank_you = pe(
        "🎉 **አምነውን ስለመጡ እናመሰግናለን! (Thank you for trusting us!)**\n\n"
        f"📦 **ምርት:** {order['product']}\n"
        f"💰 **መጠን:** {order['amount']:.2f} ETB\n"
        f"🆔 **የትእዛዝ ቁጥር:** #{order_id}\n\n"
        "ትእዛዝዎን በተሳካ ሁኔታ በማጠናቀቃችን እጅግ ደስ ብሎናል። የእርስዎ ድጋፍ እና እምነት ለኛ ትልቅ ጥንካሬ ነው። "
        "ቦታችን ለ24/7 ሰአት አገልግሎት ለመስጠት ዝግጁ ነው፤ በድጋሚ በደስታ እናገለግልዎታለን! 🙏✨"
    )
    await callback.message.answer(long_thank_you)
    
    try:
        await bot.send_message(
            OWNER_ID,
            pe(f"🌟 CUSTOMER TRUSTED ORDER #{order_id}\nUser: @{order.get('username') or 'No Username'}")
        )
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data.startswith("notrust:"))
async def not_trusted(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    order = get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    if callback.from_user.id != order["user_id"]:
        await callback.answer("Not authorized.", show_alert=True)
        return

    await state.set_state(OrderState.waiting_not_trusted_reason)
    await state.update_data(order_id=order_id)
    await callback.message.answer(
        pe("⚠️ እባክዎን ምን እንደጎደለዎት ወይም ያልተስተካከለ ነገር ካለ በዝርዝር ይጻፉልን (ለኦውነሩ ይላካል):")
    )
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_not_trusted_reason))
async def receive_not_trusted_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = get_order(order_id) if order_id else None
    if not order or message.from_user.id != order["user_id"]:
        return

    reason = (message.text or message.caption or "").strip()
    if not reason:
        await message.answer(pe("እባክዎን ዝርዝር ምክንያት ይጻፉ።"))
        return

    update_order(order_id, status="customer_feedback")
    
    await bot.send_message(
        OWNER_ID,
        pe(
            f"⚠️ **የደንበኛ ቅሬታ (NOT TRUSTED) — ORDER #{order_id}**\n\n"
            f"👤 **ደንበኛ:** @{order.get('username') or 'No username'}\n"
            f"🆔 **User ID:** {order['user_id']}\n"
            f"📦 **ምርት:** {order['product']}\n"
            f"💰 **መጠን:** {order['amount']:.2f} ETB\n\n"
            f"💬 **የተላከ ቅሬታ:**\n{reason}"
        )
    )
    await message.answer(pe("ቅሬታዎ ለኦውነሩ ተልኳል። ኦውነሩ አይቶ ያስተካክልዎታል! ስለገለጹልን እናመሰግናለን።"))
    await state.clear()

# ============================================================
# ADMIN PANEL LOGIC & HANDLERS (OWNER ONLY)
# ============================================================

def admin_main_kb():
    return kb([
        [premium_button(text="📢 Broadcast (Text / Image)", style="primary", callback_data="admin:broadcast")],
        [premium_button(text="💵 Change Product Prices", style="success", callback_data="admin:prices")],
        [premium_button(text="❌ Exit Admin Panel", style="danger", callback_data="admin:exit")]
    ])

def admin_categories_kb():
    return kb([
        [premium_button(text="🎮 PUBG Mobile", callback_data="admincat:pubg")],
        [premium_button(text="🔥 Free Fire", callback_data="admincat:freefire")],
        [premium_button(text="🎵 TikTok Coins", callback_data="admincat:tiktok")],
        [premium_button(text="⚡ Delta Force", callback_data="admincat:delta")],
        [premium_button(text="💥 Blood Strike", callback_data="admincat:bloodstrike")],
        [premium_button(text="⛏️ Fortnite V-Bucks", callback_data="admincat:fortnite")],
        [premium_button(text="✈️ Telegram Premium & Stars", callback_data="admincat:telegram")],
        [premium_button(text="◀️ Back to Admin Menu", callback_data="admin:home")]
    ])

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    await state.clear()
    await message.answer(
        pe("👑 **ADMIN PANEL**\n\nWelcome Owner! Choose an action below:"),
        reply_markup=admin_main_kb()
    )

@dp.callback_query(F.data == "admin:home")
async def admin_home_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    await state.clear()
    await edit_or_send(
        callback,
        pe("👑 **ADMIN PANEL**\n\nWelcome Owner! Choose an action below:"),
        admin_main_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin:exit")
async def admin_exit_cb(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    await state.clear()
    await callback.message.delete()
    await callback.answer("Admin Panel closed.")

# --- BROADCAST SYSTEM ---

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    await state.set_state(AdminState.waiting_broadcast_content)
    await edit_or_send(
        callback,
        pe(
            "📢 **BROADCAST MESSAGE**\n\n"
            "Please send the broadcast content now.\n"
            "You can send a **Text Message** or a **Photo with Text Caption**.\n\n"
            "Press Cancel to abort."
        ),
        kb([[premium_button(text="CANCEL", style="danger", callback_data="admin:home")]])
    )
    await callback.answer()

@dp.message(StateFilter(AdminState.waiting_broadcast_content))
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    # Get all distinct user IDs from orders & tickets
    with closing(sqlite3.connect(DB)) as con:
        rows = con.execute("""
            SELECT user_id FROM orders
            UNION
            SELECT user_id FROM tickets
        """).fetchall()

    user_ids = [r[0] for r in rows if r[0]]

    if not user_ids:
        await message.answer(pe("No users found in database to broadcast to."))
        await state.clear()
        return

    await message.answer(pe(f"⏳ Sending broadcast to {len(user_ids)} users... Please wait."))

    success_count = 0
    fail_count = 0

    for u_id in user_ids:
        try:
            if message.photo:
                photo_file_id = message.photo[-1].file_id
                caption_text = message.caption or ""
                await bot.send_photo(u_id, photo_file_id, caption=caption_text)
            else:
                await bot.send_message(u_id, message.text or "")
            success_count += 1
            await asyncio.sleep(0.05) # Prevent hitting rate limits
        except Exception:
            fail_count += 1

    await state.clear()
    await message.answer(
        pe(
            f"✅ **BROADCAST COMPLETED!**\n\n"
            f"📊 **Successful:** {success_count}\n"
            f"❌ **Failed:** {fail_count}\n"
            f"👥 **Total Targeted:** {len(user_ids)}"
        ),
        reply_markup=admin_main_kb()
    )

# --- PRICE MODIFICATION SYSTEM ---

@dp.callback_query(F.data == "admin:prices")
async def admin_prices_menu(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    await edit_or_send(
        callback,
        pe("💵 **CHANGE PRICES**\n\nSelect a category to view and edit product prices:"),
        admin_categories_kb()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admincat:"))
async def admin_category_selected(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    category = callback.data.split(":")[1]

    submenus = {
        "pubg": [
            ("Fast UC", "adminlist:pubg_fast"),
            ("Manual UC", "adminlist:pubg_manual"),
            ("Growth Pack", "adminlist:growth"),
            ("Prime Plus", "adminlist:prime"),
            ("Mythic Emblem", "adminlist:mythic"),
            ("RP", "adminlist:rp"),
        ],
        "delta": [
            ("Delta Force Coins", "adminlist:delta_coin"),
            ("Special Offers", "adminlist:delta_special"),
        ],
        "bloodstrike": [
            ("Golds", "adminlist:bloodstrike_golds"),
            ("Offers", "adminlist:bloodstrike_offers"),
        ],
        "telegram": [
            ("Telegram Premium", "adminlist:premium"),
            ("Telegram Stars", "adminlist:stars"),
        ],
    }

    if category in submenus:
        rows = [[premium_button(text=title, callback_data=cb_data)] for title, cb_data in submenus[category]]
        rows.append([premium_button(text="◀️ Back to Categories", callback_data="admin:prices")])
        await edit_or_send(
            callback,
            pe(f"📂 Select a subcategory for {category.upper()}:"),
            kb(rows)
        )
    else:
        # Direct categories: freefire, tiktok, fortnite
        prefix_map = {
            "freefire": "freefire",
            "tiktok": "tiktok",
            "fortnite": "fortnite"
        }
        await show_admin_item_list(callback, prefix_map[category])

    await callback.answer()

@dp.callback_query(F.data.startswith("adminlist:"))
async def admin_item_list_cb(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        return
    prefix = callback.data.split(":")[1]
    await show_admin_item_list(callback, prefix)
    await callback.answer()

async def show_admin_item_list(callback: CallbackQuery, prefix: str):
    products = get_products(prefix)
    rows = []
    for idx, (name, price) in enumerate(products):
        rows.append([
            premium_button(
                text=f"{name} — {price:.2f} ETB",
                callback_data=f"adminedit:{prefix}:{idx}"
            )
        ])
    rows.append([premium_button(text="◀️ Back to Categories", callback_data="admin:prices")])

    await edit_or_send(
        callback,
        pe(f"⚙️ **Select a item from [{prefix.upper()}] to edit price:**"),
        kb(rows)
    )

@dp.callback_query(F.data.startswith("adminedit:"))
async def admin_edit_item_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID:
        return
    _, prefix, index_str = callback.data.split(":")
    index = int(index_str)
    
    products = get_products(prefix)
    if index >= len(products):
        await callback.answer("Item not found.", show_alert=True)
        return

    name, current_price = products[index]

    await state.set_state(AdminState.waiting_new_price)
    await state.update_data(prefix=prefix, index=index, item_name=name, old_price=current_price)

    await edit_or_send(
        callback,
        pe(
            f"✏️ **EDIT PRICE**\n\n"
            f"📦 **Item:** {name}\n"
            f"💰 **Current Price:** {current_price:.2f} ETB\n\n"
            "Please send the **NEW PRICE** in ETB (numbers only):"
        ),
        kb([[premium_button(text="CANCEL", style="danger", callback_data=f"adminlist:{prefix}")]])
    )
    await callback.answer()

@dp.message(StateFilter(AdminState.waiting_new_price))
async def process_new_price(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    text = (message.text or "").strip()
    try:
        new_price = float(text)
        if new_price <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(pe("❌ Invalid price! Please enter a valid positive number (e.g. 250 or 1500.50):"))
        return

    data = await state.get_data()
    prefix = data["prefix"]
    index = data["index"]
    item_name = data["item_name"]
    old_price = data["old_price"]

    update_product_price_in_db(prefix, index, new_price)

    await state.clear()

    rows = [
        [premium_button(text=f"◀️ Back to {prefix.upper()} List", callback_data=f"adminlist:{prefix}")],
        [premium_button(text="👑 Admin Home", callback_data="admin:home")]
    ]

    await message.answer(
        pe(
            f"✅ **PRICE UPDATED SUCCESSFULLY!**\n\n"
            f"📦 **Item:** {item_name}\n"
            f"📉 **Old Price:** {old_price:.2f} ETB\n"
            f"📈 **New Price:** {new_price:.2f} ETB"
        ),
        reply_markup=kb(rows)
    )

# ============================================================
# ORDERS / SUPPORT / INFO / HELP / TICKET
# ============================================================

@dp.callback_query(F.data == "myorders")
async def myorders(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    if not orders:
        await edit_or_send(
            callback,
            pe(" MY ORDERS\n\nYou don't have any orders yet."),
            kb([back_cancel("home")])
        )
        return

    lines = [" MY ORDERS\n"]
    for o in orders:
        lines.append(
            f"#{o['id']} — {o['product']}\n"
            f" {o['amount']:.2f} ETB — {o['status']}\n"
            f" {o['created_at'][:16]}\n"
        )
    await edit_or_send(callback, pe("\n".join(lines)), kb([back_cancel("home")]))
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            " SUPPORT\n\n"
            "Need help with an order?\n"
            "Press the button below to message the administrator."
        ),
        kb([
            [premium_button(text=" MESSAGE ADMIN", url=f"https://t.me/{SUPPORT_USERNAME}")],
            back_cancel("home"),
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "info")
async def info(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            " ABOUT IMRAN TOPUP BOT\n"
            "Version: 2.0.0\n"
            "Platform: Telegram Bot\n\n"
            "FEATURES:\n"
            " 24/7 Service\n"
            " Instant & Manual Delivery\n"
            " Secure Payment\n"
            " Order Tracking\n"
            " Customer Support\n\n"
            f"Contact: @{SUPPORT_USERNAME}\n"
        ),
        kb([back_cancel("home")])
    )
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe(
            "HELP GUIDE\n\n"
            "Commands:\n"
            "/start — Main menu\n"
            "/myorders — View orders\n"
            "/support — Contact support\n"
            "/channel — Join channel\n"
            "/info — About bot\n"
            "/help — This message\n"
            "/cancel — Cancel current order\n"
            "/admin — Owner Admin Panel\n\n"
            "How to Order:\n"
            "1. Select category\n"
            "2. Choose product\n"
            "3. Enter ID/credentials\n"
            "4. Confirm\n"
            "5. Select payment\n"
            "6. Paste payment SMS",
            "help"
        ),
        kb([back_cancel("home")])
    )
    await callback.answer()

@dp.callback_query(F.data == "ticket")
async def ticket(callback: CallbackQuery):
    user_id = callback.from_user.id

    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM tickets WHERE user_id=?", (user_id,)).fetchone()

        if row:
            ticket_number = row["ticket_number"]
            await callback.message.answer(
                pe(
                    f" YOUR TICKET NUMBER: #{ticket_number}\n\n"
                    "This ticket number was already assigned to you. "
                    "One customer can receive only one ticket number."
                )
            )
            await callback.answer()
            return

        while True:
            ticket_number = random.randint(100000, 999999)
            exists = con.execute("SELECT 1 FROM tickets WHERE ticket_number=?", (ticket_number,)).fetchone()
            if not exists:
                break

        con.execute(
            "INSERT INTO tickets(user_id, ticket_number, created_at, status) VALUES(?,?,?,?)",
            (user_id, ticket_number, datetime.utcnow().isoformat(), "open"),
        )
        con.commit()

    username = callback.from_user.username or "No username"

    await callback.message.answer(
        pe(
            " TICKET CREATED SUCCESSFULLY\n\n"
            f"Your ticket number is: #{ticket_number}\n\n"
            "Keep this number safe. It can be used for the giveaway. "
            "Each customer can receive a ticket number only once."
        )
    )

    await bot.send_message(
        OWNER_ID,
        pe(
            " NEW GIVEAWAY TICKET\n\n"
            f"Ticket Number: #{ticket_number}\n"
            f"User: @{username}\n"
            f"User ID: {user_id}"
        ),
    )
    await callback.answer()

# ============================================================
# CANCEL / BACK HANDLERS
# ============================================================

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target = data.get("cancel_target")
    prefix = data.get("prefix")
    await state.clear()
    if target == "home":
        await show_home(callback.message)
    elif target == "payment":
        await callback.message.answer(pe("PAYMENT METHODS\n\nChoose your payment method:"), reply_markup=payment_keyboard())
    elif target == "products" and prefix:
        await show_product_menu(callback, prefix)
    else:
        await show_home(callback.message)
    await callback.answer()

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)

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
# COMMAND ROUTERS
# ============================================================

@dp.message(Command("myorders"))
async def myorders_command(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(pe(" You don't have any orders yet."), reply_markup=main_menu())
        return
    lines = [" MY ORDERS\n"]
    for o in orders:
        lines.append(f"#{o['id']} — {o['product']}\n {o['amount']:.2f} ETB — {o['status']}\n")
    await message.answer(pe("\n".join(lines)), reply_markup=main_menu())

@dp.message(Command("support"))
async def support_command(message: Message):
    await message.answer(
        pe(" Support:"),
        reply_markup=kb([
            [premium_button(text=" MESSAGE ADMIN", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [premium_button(text=" HOME", callback_data="back:home")]
        ])
    )

@dp.message(Command("channel"))
async def channel_command(message: Message):
    await message.answer(
        pe(" Our Channel:"),
        reply_markup=kb([
            [premium_button(text=" JOIN CHANNEL", url=CHANNEL_URL)],
            [premium_button(text=" HOME", callback_data="back:home")]
        ])
    )

@dp.message(Command("info"))
async def info_command(message: Message):
    await message.answer(
        pe(
            " ABOUT IMRAN TOPUP BOT\n"
            "Version: 2.0.0\n\n"
            "Trusted Top-Up Service Platform for Gamers and Digital Enthusiasts."
        ),
        reply_markup=kb([[premium_button(text=" HOME", callback_data="back:home")]])
    )

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        pe("HELP GUIDE\n\nUse /start to go to main menu."),
        reply_markup=kb([[premium_button(text=" HOME", callback_data="back:home")]])
    )

# ============================================================
# FLASK KEEP-ALIVE SERVER (FOR HOSTING)
# ============================================================

app = Flask(__name__)

@app.route("/")
def home_route():
    return "Bot is running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ============================================================
# MAIN ENTRYPOINT
# ============================================================

async def main():
    db_init()
    Thread(target=run_flask, daemon=True).start()
    logging.info("Starting Telegram Bot Polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())