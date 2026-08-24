import os
import re
import html
import random
import asyncio
import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from flask import Flask
from threading import Thread

# ============================================================
# IMRAN TOPUP BOT — CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("CHAT_ID", "0") or 0)

PREMIUM_EMOJI_ID = os.getenv("CUSTOM_EMOJI_ID", "5469921699367510137").strip() or "5469921699367510137"
APPROVED_CUSTOM_EMOJI_ID = "5469921699367510137"

if PREMIUM_EMOJI_ID != APPROVED_CUSTOM_EMOJI_ID:
    PREMIUM_EMOJI_ID = APPROVED_CUSTOM_EMOJI_ID

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
}

PAYMENTS = {
    "Telebirr": ("0982903324", "Kayamo"),
    "CBE": ("1000219425809", "Alemnesh"),
    "Dashen": ("5543988503011", "Alemnesh"),
}

DB = "bot.db"
logging.basicConfig(level=logging.INFO)

# ============================================================
# INITIAL DEFAULT PRODUCTS DATA
# ============================================================

DEFAULT_PRODUCTS = [
    # PUBG FAST
    ("pubg_fast", "60 UC", 190.0), ("pubg_fast", "120 UC", 380.0), ("pubg_fast", "180 UC", 550.0),
    ("pubg_fast", "325 UC", 880.0), ("pubg_fast", "385 UC", 1100.0), ("pubg_fast", "660 UC", 1765.0),
    ("pubg_fast", "720 UC", 1920.0), ("pubg_fast", "985 UC", 2820.0), ("pubg_fast", "1320 UC", 3600.0),
    ("pubg_fast", "1800 UC", 4350.0), ("pubg_fast", "1920 UC", 4800.0), ("pubg_fast", "2460 UC", 6300.0),
    ("pubg_fast", "3850 UC", 8700.0),

    # PUBG MANUAL
    ("pubg_manual", "30 UC", 130.0), ("pubg_manual", "240 UC", 700.0), ("pubg_manual", "325 UC", 850.0),
    ("pubg_manual", "385 UC", 1050.0), ("pubg_manual", "445 UC", 1230.0), ("pubg_manual", "660 UC", 1700.0),
    ("pubg_manual", "720 UC", 1890.0), ("pubg_manual", "780 UC", 2050.0), ("pubg_manual", "985 UC", 2600.0),
    ("pubg_manual", "1045 UC", 2750.0), ("pubg_manual", "1320 UC", 3500.0), ("pubg_manual", "1800 UC", 4300.0),
    ("pubg_manual", "2125 UC", 5300.0), ("pubg_manual", "3850 UC", 8550.0), ("pubg_manual", "4000 UC", 9150.0),
    ("pubg_manual", "8100 UC", 17000.0), ("pubg_manual", "16200 UC", 33900.0),

    # PUBG OTHER
    ("growth", "First purchase pack", 200.0), ("growth", "Upgradeable firearm pack", 550.0), ("growth", "Mythic Emblem pack", 900.0),
    ("prime", "Prime 1 Month", 200.0), ("prime", "Prime 3 Months", 600.0), ("prime", "Prime 6 Months", 1150.0),
    ("prime", "Prime Plus 1 Month", 1700.0), ("prime", "Prime 12 Months", 2100.0), ("prime", "Prime Plus 3 Months", 5000.0),
    ("prime", "Prime Plus 6 Months", 9900.0), ("prime", "Prime Plus 12 Months", 19900.0),
    ("mythic", "Mythic Emblem Value Pack", 700.0),
    ("rp", "ELITE PASS 150 + 50 UC GIFT", 1200.0), ("rp", "ELITE PASS 100 + 100 UC GIFT", 2300.0),

    # FREE FIRE
    ("freefire", "100+10", 230.0), ("freefire", "210+21", 440.0), ("freefire", "530+53", 950.0),
    ("freefire", "1080+108", 1900.0), ("freefire", "2200+220", 3750.0),

    # DELTA FORCE
    ("delta_coin", "30 Coins", 130.0), ("delta_coin", "60 Coins", 190.0), ("delta_coin", "320 Coins", 800.0),
    ("delta_coin", "460 Coins", 1200.0), ("delta_coin", "750 Coins", 1650.0), ("delta_coin", "1480 Coins", 3100.0),
    ("delta_coin", "1980 Coins", 3950.0), ("delta_coin", "3950 Coins", 7650.0),
    ("delta_special", "Season Pass Operations Special", 900.0), ("delta_special", "Season Pass Warfare Special", 900.0),
    ("delta_special", "S/Pass Delta Force Deluxe", 1300.0),

    # TIKTOK
    ("tiktok", "200 COIN", 500.0), ("tiktok", "500 COIN", 1200.0), ("tiktok", "800 COIN", 1800.0),
    ("tiktok", "1000 COIN", 2300.0), ("tiktok", "1500 COIN", 3300.0), ("tiktok", "2000 COIN", 4400.0),
    ("tiktok", "2500 COIN", 5500.0), ("tiktok", "3000 COIN", 6600.0), ("tiktok", "4000 COIN", 8650.0),
    ("tiktok", "5000 COIN", 10900.0), ("tiktok", "7500 COIN", 16500.0), ("tiktok", "10000 COIN", 22000.0),

    # TELEGRAM
    ("premium", "Telegram Premium 1 Month", 350.0), ("premium", "Telegram Premium 3 Months", 950.0),
    ("premium", "Telegram Premium 6 Months", 1800.0), ("premium", "Telegram Premium 12 Months", 3300.0),
    ("stars", "Telegram Stars 100", 250.0), ("stars", "Telegram Stars 500", 1100.0), ("stars", "Telegram Stars 1000", 2100.0),

    # BLOOD STRIKE
    ("bloodstrike_golds", "50+1 BC", 100.0), ("bloodstrike_golds", "100+5 BC", 190.0), ("bloodstrike_golds", "300+20 BC", 500.0),
    ("bloodstrike_golds", "500+40 BC", 780.0), ("bloodstrike_golds", "1100 BC", 1500.0), ("bloodstrike_golds", "2260 BC", 2950.0),
    ("bloodstrike_offers", "Ultra Skin Lucky Chest", 150.0), ("bloodstrike_offers", "Season Pass", 250.0),
    ("bloodstrike_offers", "Level Up Pass", 400.0), ("bloodstrike_offers", "Strike Pass Elite", 700.0),
    ("bloodstrike_offers", "Strike Pass Premium", 1550.0),
]

# ============================================================
# DATABASE SETUP & HELPERS
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
                tiktok_username TEXT,
                tiktok_password TEXT,
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

        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)
        
        # Populate initial products if table is empty
        cursor = con.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            con.executemany("INSERT INTO products (category, name, price) VALUES (?, ?, ?)", DEFAULT_PRODUCTS)
            
        con.commit()

def get_products(category: str):
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM products WHERE category=?", (category,)).fetchall()
        return [dict(r) for r in rows]

def get_product_by_id(prod_id: int):
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM products WHERE id=?", (prod_id,)).fetchone()
        return dict(row) if row else None

def update_product_price(prod_id: int, new_price: float):
    with closing(sqlite3.connect(DB)) as con:
        con.execute("UPDATE products SET price=? WHERE id=?", (new_price, prod_id))
        con.commit()

def get_all_users():
    with closing(sqlite3.connect(DB)) as con:
        rows = con.execute("SELECT DISTINCT user_id FROM orders UNION SELECT user_id FROM tickets").fetchall()
        return [r[0] for r in rows]

def create_order(data):
    with closing(sqlite3.connect(DB)) as con:
        cur = con.execute("""
            INSERT INTO orders
            (user_id, username, product, amount, player_id, tiktok_email,
             tiktok_phone, tiktok_username, tiktok_password, payment_method, payment_sms,
             receipt_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            data["user_id"], data["username"], data["product"], data["amount"],
            data.get("player_id", ""), data.get("tiktok_email", ""),
            data.get("tiktok_phone", ""), data.get("tiktok_username", ""),
            data.get("tiktok_password", ""), data.get("payment_method", ""),
            data.get("payment_sms", ""), data.get("receipt_url", ""), datetime.utcnow().isoformat()
        ))
        con.commit()
        return cur.lastrowid

def update_order(order_id, **fields):
    allowed = {
        "payment_sms", "receipt_url", "status", "payment_method",
        "player_id", "tiktok_email", "tiktok_phone", "tiktok_username", "tiktok_password"
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
        rows = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
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
            row = con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        return dict(row) if row else None

# ============================================================
# BOT ENGINE & EMOJI
# ============================================================

def pe(text: str) -> str:
    text = "" if text is None else str(text)
    text = "\n".join(line.strip() for line in text.splitlines())
    safe_text = html.escape(text, quote=False)
    return f'<tg-emoji emoji-id="{PREMIUM_EMOJI_ID}">⭐</tg-emoji> {safe_text}'

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ============================================================
# STATES
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
    waiting_broadcast_msg = State()
    waiting_new_price = State()

# ============================================================
# KEYBOARDS
# ============================================================

def premium_button(text: str, **kwargs):
    return InlineKeyboardButton(text=str(text).strip(), icon_custom_emoji_id=PREMIUM_EMOJI_ID, **kwargs)

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_menu():
    return kb([
        [premium_button(text="PUBG MOBILE", callback_data="cat:pubg"), premium_button(text="FREE FIRE", callback_data="cat:freefire")],
        [premium_button(text="TIKTOK COIN", callback_data="cat:tiktok"), premium_button(text="DELTA FORCE", callback_data="cat:delta")],
        [premium_button(text="TELEGRAM PREMIUM & STARS", callback_data="cat:telegram")],
        [premium_button(text="BLOOD STRIKE", callback_data="cat:bloodstrike"), premium_button(text="MY ORDERS", callback_data="myorders")],
        [premium_button(text="GET TICKET", callback_data="ticket"), premium_button(text="SUPPORT", callback_data="support")],
        [premium_button(text="OUR CHANNEL", url=CHANNEL_URL), premium_button(text="INFO", callback_data="info")],
        [premium_button(text="HELP", callback_data="help")],
    ])

def back_cancel(callback="home"):
    return [premium_button(text="BACK", callback_data=f"back:{callback}"), premium_button(text="CANCEL", callback_data="cancel")]

def category_menu(category):
    if category == "pubg":
        return kb([
            [premium_button(text="FAST UC", callback_data="prodmenu:pubg_fast")],
            [premium_button(text="MANUAL UC", callback_data="prodmenu:pubg_manual")],
            [premium_button(text="GROWTH PACK", callback_data="prodmenu:growth")],
            [premium_button(text="PRIME PLUS", callback_data="prodmenu:prime")],
            [premium_button(text="MYTHIC EMBLEM", callback_data="prodmenu:mythic")],
            [premium_button(text="RP", callback_data="prodmenu:rp")],
            back_cancel("home"),
        ])
    if category == "freefire": return product_keyboard("freefire")
    if category == "tiktok": return product_keyboard("tiktok")
    if category == "delta":
        return kb([
            [premium_button(text="Delta Force Coins", callback_data="prodmenu:delta_coin")],
            [premium_button(text="Special Offers", callback_data="prodmenu:delta_special")],
            back_cancel("home"),
        ])
    if category == "bloodstrike":
        return kb([
            [premium_button(text="GOLDS", callback_data="prodmenu:bloodstrike_golds")],
            [premium_button(text="OFFERS", callback_data="prodmenu:bloodstrike_offers")],
            back_cancel("home"),
        ])
    if category == "telegram":
        return kb([
            [premium_button(text="Telegram Premium", callback_data="prodmenu:premium")],
            [premium_button(text="Telegram Stars", callback_data="prodmenu:stars")],
            back_cancel("home"),
        ])
    return kb([[*back_cancel("home")]])

def product_keyboard(prefix):
    products = get_products(prefix)
    rows = []
    for prod in products:
        rows.append([premium_button(text=f"{prod['name']} — {prod['price']:.2f} ETB", callback_data=f"buy:{prod['id']}")])
    rows.append(back_cancel("home"))
    return kb(rows)

def payment_keyboard():
    return kb([
        [premium_button(text="Telebirr", callback_data="pay:Telebirr")],
        [premium_button(text="CBE", callback_data="pay:CBE")],
        [premium_button(text="Dashen", callback_data="pay:Dashen")],
        back_cancel("products"),
    ])

def yes_no_cancel():
    return kb([
        [premium_button(text="YES", callback_data="confirm:yes"), premium_button(text="NO", callback_data="confirm:no")],
        [premium_button(text="CANCEL", callback_data="cancel")],
    ])

def owner_order_keyboard(order_id):
    return kb([
        [premium_button(text="ACCEPT", callback_data=f"owner:accept:{order_id}"), premium_button(text="REJECT", callback_data=f"owner:reject:{order_id}")],
    ])

def trust_keyboard(order_id):
    return kb([
        [premium_button(text="TRUSTED", callback_data=f"trust:{order_id}"), premium_button(text="NOT TRUSTED", callback_data=f"notrust:{order_id}")],
    ])

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def resolve_photo(path):
    if path and os.path.isfile(path): return path
    if path:
        name = os.path.basename(path)
        candidates = [os.path.join(BASE_DIR, name)]
        if name.lower() == "tiktok.jpg": candidates.append(os.path.join(IMAGE_DIR, "TikTok.jpg"))
        if name.lower() == "imran.jpg": candidates.append(os.path.join(IMAGE_DIR, "imran.jpg"))
        for candidate in candidates:
            if os.path.isfile(candidate): return candidate
    return ""

async def edit_or_send(callback, text, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup)

def receipt_url(text):
    if not text: return None
    m = re.search(r"https?://[^\s<>\"]+", text)
    if not m: return None
    candidate = m.group(0).rstrip(".,);]}")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate

# ============================================================
# START / MAIN MENUS
# ============================================================

async def show_home(message):
    text = pe("Welcome to IMRAN TOPUP BOT\n\nChoose a service below:\nPUBG MOBILE\nFree Fire\nTikTok Coins\nDelta Force\nTelegram Premium & Stars\nBlood Strike")
    home_photo = resolve_photo(PHOTOS["home"])
    if home_photo:
        try:
            await message.answer_photo(photo=FSInputFile(home_photo), caption=text, reply_markup=main_menu())
            return
        except Exception:
            logging.exception("Could not send imran.jpg")
    await message.answer(text, reply_markup=main_menu())

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)

# ============================================================
# ADMIN PANEL (NEW FEATURES)
# ============================================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    await state.clear()
    text = pe("⚙️ ADMIN PANEL\n\nእባክዎ የሚፈልጉትን የአድሚን ተግባር ይምረጡ፡")
    menu = kb([
        [premium_button(text="📢 ብሮድካስት (Broadcast)", callback_data="admin:broadcast")],
        [premium_button(text="💵 የፓኬጅ ዋጋ ለመቀየር", callback_data="admin:change_price")],
        [premium_button(text="🏠 ዋና ገጽ", callback_data="back:home")]
    ])
    await message.answer(text, reply_markup=menu)

@dp.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await state.set_state(AdminState.waiting_broadcast_msg)
    await callback.message.answer(pe("📢 BROADCAST\n\nለበሬታው ለሁሉም ተጠቃሚዎች የሚላከውን መልእክት (ፅሁፍ ወይም ፎቶ ከነፅሁፉ) ይላኩ።\n\nለመሰረዝ /cancel ብለው ይፃፉ።"))
    await callback.answer()

@dp.message(StateFilter(AdminState.waiting_broadcast_msg))
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    users = get_all_users()
    sent = 0
    await message.answer(pe(f"ብሮድካስት መላክ ተጀምሯል... ለ {len(users)} ተጠቃሚዎች ይላካል።"))

    for uid in users:
        try:
            if message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            else:
                await bot.send_message(uid, message.text or "")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(pe(f"✅ ብሮድካስት ተጠናቋል። ለ {sent} ተጠቃሚዎች በስኬት ተልኳል።"))
    await state.clear()

# --- PRICE MANAGER ---

@dp.callback_query(F.data == "admin:change_price")
async def admin_change_price_cats(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    text = pe("💵 PRICE MANAGER\n\nዋጋ መቀየር የሚፈልጉትን ጨዋታ ይምረጡ፡")
    menu = kb([
        [premium_button(text="PUBG FAST UC", callback_data="admin:select_cat:pubg_fast"), premium_button(text="PUBG MANUAL UC", callback_data="admin:select_cat:pubg_manual")],
        [premium_button(text="FREE FIRE", callback_data="admin:select_cat:freefire"), premium_button(text="DELTA COINS", callback_data="admin:select_cat:delta_coin")],
        [premium_button(text="DELTA SPECIAL", callback_data="admin:select_cat:delta_special"), premium_button(text="BLOODSTRIKE GOLDS", callback_data="admin:select_cat:bloodstrike_golds")],
        [premium_button(text="BLOODSTRIKE OFFERS", callback_data="admin:select_cat:bloodstrike_offers"), premium_button(text="TIKTOK COINS", callback_data="admin:select_cat:tiktok")],
        [premium_button(text="🔙 BACK", callback_data="back:home")]
    ])
    await edit_or_send(callback, text, menu)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin:select_cat:"))
async def admin_select_cat_products(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    cat = callback.data.split(":")[2]
    products = get_products(cat)

    rows = []
    for prod in products:
        rows.append([premium_button(text=f"{prod['name']} (አሁን: {prod['price']} ETB)", callback_data=f"admin:edit_prod:{prod['id']}")])
    rows.append([premium_button(text="🔙 BACK", callback_data="admin:change_price")])

    await edit_or_send(callback, pe(f"የ {cat.upper()} ፓኬጆች፡\n\nዋጋውን መቀየር የሚፈልጉትን ፓኬጅ ይምረጡ፡"), kb(rows))
    await callback.answer()

@dp.callback_query(F.data.startswith("admin:edit_prod:"))
async def admin_edit_product_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    prod_id = int(callback.data.split(":")[2])
    prod = get_product_by_id(prod_id)

    if not prod:
        await callback.answer("ፓኬጁ አልተገኘም።", show_alert=True)
        return

    await state.update_data(edit_prod_id=prod_id)
    await state.set_state(AdminState.waiting_new_price)
    await callback.message.answer(pe(f"የተመረጠው ፓኬጅ፡ {prod['name']}\nየአሁኑ ዋጋ፡ {prod['price']:.2f} ETB\n\nእባክዎ አዲሱን ዋጋ በቁጥር ብቻ ያስገቡ (ምሳሌ: 250):"))
    await callback.answer()

@dp.message(StateFilter(AdminState.waiting_new_price))
async def process_new_price(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    text = (message.text or "").strip()
    try:
        new_price = float(text)
    except ValueError:
        await message.answer(pe("እባክዎ ትክክለኛ የቁጥር ዋጋ ያስገቡ! (ምሳሌ: 350 ወይም 350.5)"))
        return

    data = await state.get_data()
    prod_id = data.get("edit_prod_id")
    prod = get_product_by_id(prod_id)

    if prod:
        update_product_price(prod_id, new_price)
        await message.answer(pe(f"✅ ዋጋው በስኬት ተቀይሯል!\n\nፓኬጅ: {prod['name']}\nአዲስ ዋጋ: {new_price:.2f} ETB"))
    else:
        await message.answer(pe("ስህተት ተፈጥሯል፤ ፓኬጁ አልተገኘም።"))

    await state.clear()

# ============================================================
# USER CATEGORIES & BUY FLOW
# ============================================================

async def show_category(callback: CallbackQuery, category: str):
    names = {"pubg": "PUBG MOBILE", "freefire": "FREE FIRE", "tiktok": "TIKTOK COINS", "delta": "DELTA FORCE", "telegram": "TELEGRAM PREMIUM & STARS", "bloodstrike": "BLOOD STRIKE"}
    photos = {"pubg": PHOTOS["pubg"], "freefire": PHOTOS["freefire"], "tiktok": PHOTOS["tiktok"], "delta": PHOTOS["delta"], "telegram": PHOTOS["premium"], "bloodstrike": PHOTOS["bloodstrike"]}
    text = pe(f"{names.get(category, category)}\n\nSelect a service:")
    try:
        if resolve_photo(photos.get(category, "")):
            await callback.message.delete()
            await callback.message.answer_photo(FSInputFile(resolve_photo(photos[category])), caption=text, reply_markup=category_menu(category))
        else:
            await edit_or_send(callback, text, category_menu(category))
    except Exception:
        await edit_or_send(callback, text, category_menu(category))

async def show_product_menu(callback: CallbackQuery, prefix: str):
    titles = {
        "pubg_fast": "PUBG FAST UC", "pubg_manual": "PUBG MANUAL UC", "growth": "GROWTH PACK",
        "prime": "PRIME PLUS", "rp": "RP", "freefire": "FREE FIRE", "tiktok": "TIKTOK COINS",
        "delta_special": "DELTA FORCE SPECIAL OFFERS", "premium": "TELEGRAM PREMIUM", "stars": "TELEGRAM STARS",
        "bloodstrike_golds": "BLOOD STRIKE GOLDS", "bloodstrike_offers": "BLOOD STRIKE OFFERS",
        "delta_coin": "DELTA FORCE COINS", "mythic": "MYTHIC EMBLEM VALUE PACK"
    }

    photo_map = {
        "pubg_fast": "pubg", "pubg_manual": "uc", "growth": "growth", "prime": "prime",
        "rp": "rp", "freefire": "freefire", "tiktok": "tiktok", "delta_special": "delta",
        "premium": "premium", "stars": "premium", "bloodstrike_golds": "bloodstrike",
        "bloodstrike_offers": "bloodstrike", "delta_coin": "delta", "mythic": "mythic"
    }

    title = titles.get(prefix, prefix.upper())
    photo_key = photo_map.get(prefix, "home")
    photo_path = resolve_photo(PHOTOS.get(photo_key, ""))
    caption = pe(f"{title}\n\nChoose your package:")

    try:
        if photo_path and os.path.isfile(photo_path):
            await callback.message.delete()
            await callback.message.answer_photo(FSInputFile(photo_path), caption=caption, reply_markup=product_keyboard(prefix))
        else:
            await edit_or_send(callback, caption, product_keyboard(prefix))
    except Exception:
        await edit_or_send(callback, caption, product_keyboard(prefix))

@dp.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split(":")[1])
    prod = get_product_by_id(prod_id)

    if not prod:
        await callback.answer("Product not found.", show_alert=True)
        return

    prefix = prod["category"]
    product = prod["name"]
    amount = prod["price"]

    await state.update_data(
        prefix=prefix,
        product=product,
        amount=float(amount),
        user_id=callback.from_user.id,
        username=callback.from_user.username or "",
        cancel_target="products",
    )

    if prefix == "tiktok":
        await state.update_data(player_id="", tiktok_email="", tiktok_phone="", tiktok_username="", tiktok_password="")
        warning = pe("IMPORTANT: Please turn off 2-step verification before sharing.")
        await callback.message.answer(
            warning,
            reply_markup=kb([
                [premium_button(text="I understand", callback_data="tiktok:understand")],
                [premium_button(text="cancel", callback_data="cancel")],
            ]),
        )
        await callback.answer()
        return

    needs_player_id = prefix not in {"premium", "stars"}
    if needs_player_id:
        await state.set_state(OrderState.waiting_player_id)
        await state.update_data(cancel_target="products")
        await callback.message.answer(
            pe(f"Product: {product}\nAmount: {amount:.2f} ETB\n\nPlease enter your PLAYER ID:"),
            reply_markup=kb([back_cancel("products")]),
        )
    else:
        await state.update_data(player_id="", cancel_target="home")
        await state.set_state(OrderState.waiting_confirmation)
        await callback.message.answer(
            pe(f"Product: {product}\nAmount: {amount:.2f} ETB\n\nPlease confirm this order."),
            reply_markup=yes_no_cancel(),
        )
    await callback.answer()

@dp.callback_query(F.data == "tiktok:understand")
async def tiktok_understand(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_tiktok_email)
    await state.update_data(cancel_target="products")
    await callback.message.answer(pe("እባክዎ የ TikTok አካውንቶን Email ያስገቡ፡"), reply_markup=kb([back_cancel("products")]))
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_tiktok_email))
async def receive_tiktok_email(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    await state.update_data(tiktok_email=email, cancel_target="products")
    await state.set_state(OrderState.waiting_tiktok_phone)
    await message.answer(pe("እባክዎ የ TikTok አካውንቶን ስልክ ቁጥር ያስገቡ፡"), reply_markup=kb([back_cancel("products")]))

@dp.message(StateFilter(OrderState.waiting_tiktok_phone))
async def receive_tiktok_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    await state.update_data(tiktok_phone=phone, cancel_target="products")
    await state.set_state(OrderState.waiting_tiktok_password)
    await message.answer(pe("እባክዎ የ TikTok አካውንቶን Password ያስገቡ፡"), reply_markup=kb([back_cancel("products")]))

@dp.message(StateFilter(OrderState.waiting_tiktok_password))
async def receive_tiktok_password(message: Message, state: FSMContext):
    password = (message.text or "").strip()
    await state.update_data(tiktok_password=password, cancel_target="products")
    
    data = await state.get_data()
    await state.set_state(OrderState.waiting_confirmation)
    confirmation_text = pe(
        f"እባክዎ ያስገቡት መረጃ ትክክል መሆኑን ያረጋግጡ። አካውንቶት ይሄ ነው?\n\n"
        f"Email: {data['tiktok_email']}\n"
        f"Phone: {data['tiktok_phone']}\n"
        f"Password: {data['tiktok_password']}\n"
        f"Product: {data['product']}\n"
        f"Amount: {data['amount']:.2f} ETB"
    )
    await message.answer(confirmation_text, reply_markup=yes_no_cancel())

@dp.message(StateFilter(OrderState.waiting_player_id))
async def receive_player_id(message: Message, state: FSMContext):
    player_id = message.text.strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{3,40}", player_id):
        await message.answer(pe("Invalid Player ID. Please send a valid ID."))
        return
    await state.update_data(player_id=player_id, cancel_target="home")
    data = await state.get_data()
    await state.set_state(OrderState.waiting_confirmation)
    await message.answer(
        pe(f"Player ID: {player_id}\nProduct: {data['product']}\nAmount: {data['amount']:.2f} ETB\n\nPlease make sure the Player ID is correct.\nConfirm that this is your account:"),
        reply_markup=yes_no_cancel()
    )

@dp.callback_query(F.data == "confirm:yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_payment)
    await callback.message.answer(pe("PAYMENT METHODS\n\nChoose your payment method:"), reply_markup=payment_keyboard())
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
# PAYMENT & ORDERS
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
        f"Product: {data['product']}\n"
        f"Amount: {data['amount']:.2f} ETB\n\n"
        f"Payment Method: {method}\n"
        f"Account: {account}\n"
        f"Name: {name}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "INSTRUCTIONS:\n"
        "1. Copy account & verify name.\n"
        f"2. Send EXACTLY {data['amount']:.2f} ETB only.\n"
        "3. After payment, copy and paste your payment SMS here.\n"
        "Paste the SMS that contains your receipt URL (http/https link).\n\n"
        "Type /cancel to cancel."
    )

    await state.set_state(OrderState.waiting_sms)
    await callback.message.answer(text)
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_sms))
async def receive_sms(message: Message, state: FSMContext):
    await process_payment_sms(message, state)

async def process_payment_sms(message: Message, state: FSMContext = None):
    text = message.text or message.caption or ""
    url = receipt_url(text)
    if not url:
        await message.answer(
            pe("Could not find a receipt URL in your SMS.\nPlease paste the SMS that contains the receipt link (http/https).\nType /cancel to cancel.")
        )
        return

    data = await state.get_data() if state else {}
    data["payment_sms"] = text
    data["receipt_url"] = url
    existing = get_latest_order_for_user(message.from_user.id, ["needs_payment_proof"])

    if existing:
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

    await message.answer(pe(f"Found transaction ID: {url}\nVerifying payment..."))

    owner_text = pe(
        f"NEW ORDER #{order_id}\n\n"
        f"User: @{order.get('username') or data.get('username') or 'No username'}\n"
        f"User ID: {order.get('user_id', message.from_user.id)}\n"
        f"Product: {order.get('product', data.get('product', 'N/A'))}\n"
        f"Amount: {float(order.get('amount', data.get('amount', 0))):.2f} ETB\n"
        f"Player ID: {order.get('player_id') or data.get('player_id') or 'N/A'}\n"
        f"Payment: {order.get('payment_method') or data.get('payment_method') or 'N/A'}\n"
        f"Receipt URL: {url}\n\n"
        f"Payment SMS:\n{text[:3000]}"
    )

    try:
        await bot.send_message(OWNER_ID, owner_text, reply_markup=owner_order_keyboard(order_id))
    except Exception:
        logging.exception("Could not send order/proof to owner")

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
            pe(f"Order #{order_id} accepted.\n\nክፍያ ተረጋግጧል! እባክዎ ደንበኛው ያዘዘው እንደገባለት የሚያሳይ ደረሰኝ (Screenshot ወይም Text) እዚህ ይላኩ።")
        )
    else:
        update_order(order_id, status="needs_payment_proof")
        await callback.message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            order["user_id"],
            pe("የላኩት ክፍያ ወይም ደረሰኝ ትክክል አይደለም። እባክዎ ክፍያዎን በትክክል ፈፅመው፣ ትክክለኛውን የክፍያ SMS እና Receipt URL ይላኩልን።")
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
        await message.answer(pe("Order not found."))
        return

    caption_text = pe(
        f"ውድ ደንበኛችን ትዕዛዞት በሚገባ ተፈፅሟል!\n\n"
        f"የገዛችሁት {order['product']} ወደ አካውንቶ ገብቷል።\n"
        f"እባክዎ አገልግሎታችንን ካመኑ 'TRUSTED' የሚለውን ይጫኑ፣ ካልሆነ ደግሞ 'NOT TRUSTED'።"
    )

    try:
        if message.photo:
            await bot.send_photo(order["user_id"], message.photo[-1].file_id, caption=caption_text, reply_markup=trust_keyboard(order_id))
        else:
            await bot.send_message(order["user_id"], caption_text, reply_markup=trust_keyboard(order_id))
    except Exception:
        logging.exception("Could not send delivery receipt to customer")

    update_order(order_id, status="delivered")
    await message.answer(pe(f"Delivery receipt for order #{order_id} was sent to customer."))
    await state.clear()

@dp.callback_query(F.data.startswith("trust:"))
async def trusted(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    update_order(order_id, status="completed")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(pe("አምነውን ስለመጡ ከልብ እናመሰግናለን! ታማኝነት መለያችን ነው!"))
    await callback.answer()

@dp.callback_query(F.data.startswith("notrust:"))
async def not_trusted(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.set_state(OrderState.waiting_not_trusted_reason)
    await state.update_data(order_id=order_id)
    await callback.message.answer(pe("ምን እንደጎደለብዎ ወይም ችግሩን በዝርዝር እባክዎ ይፃፉልን።"))
    await callback.answer()

@dp.message(StateFilter(OrderState.waiting_not_trusted_reason))
async def receive_not_trusted_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    reason = (message.text or "").strip()
    update_order(order_id, status="customer_feedback")
    await bot.send_message(OWNER_ID, pe(f"CUSTOMER FEEDBACK — ORDER #{order_id}\n\nFeedback:\n{reason}"))
    await message.answer(pe("እናመሰግናለን! ቅሬታዎ ለባለቤቱ ተልኳል።"))
    await state.clear()

# ============================================================
# EXTRA COMMANDS & CALLBACKS
# ============================================================

@dp.callback_query(F.data == "myorders")
async def myorders(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)
    if not orders:
        await edit_or_send(callback, pe("MY ORDERS\n\nYou don't have any orders yet."), kb([back_cancel("home")]))
        return
    lines = ["MY ORDERS\n"]
    for o in orders:
        lines.append(f"#{o['id']} — {o['product']}\n{o['amount']:.2f} ETB — {o['status']}\n")
    await edit_or_send(callback, pe("\n".join(lines)), kb([back_cancel("home")]))
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await edit_or_send(
        callback,
        pe("SUPPORT\n\nNeed help? Message the administrator."),
        kb([[premium_button(text="MESSAGE ADMIN", url=f"https://t.me/{SUPPORT_USERNAME}")], back_cancel("home")])
    )
    await callback.answer()

@dp.callback_query(F.data == "info")
async def info(callback: CallbackQuery):
    await edit_or_send(callback, pe("ABOUT IMRAN TOPUP BOT\nVersion: 2.0.0\nSecure & Fast Service"), kb([back_cancel("home")]))
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    await edit_or_send(callback, pe("HELP GUIDE\n\nUse /start to open the main menu."), kb([back_cancel("home")]))
    await callback.answer()

@dp.callback_query(F.data == "ticket")
async def ticket(callback: CallbackQuery):
    user_id = callback.from_user.id
    with closing(sqlite3.connect(DB)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM tickets WHERE user_id=?", (user_id,)).fetchone()
        if row:
            await callback.message.answer(pe(f"YOUR TICKET NUMBER: #{row['ticket_number']}"))
            await callback.answer()
            return
        ticket_number = random.randint(100000, 999999)
        con.execute("INSERT INTO tickets(user_id, ticket_number, created_at, status) VALUES(?,?,?,?)", (user_id, ticket_number, datetime.utcnow().isoformat(), "open"))
        con.commit()
    await callback.message.answer(pe(f"TICKET CREATED SUCCESSFULLY\n\nTicket Number: #{ticket_number}"))
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_home(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("back:"))
async def back_callback(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":", 1)[1]
    await state.clear()
    if target == "home":
        await show_home(callback.message)
    else:
        await show_home(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("cat:"))
async def category_callback(callback: CallbackQuery):
    await show_category(callback, callback.data.split(":", 1)[1])
    await callback.answer()

@dp.callback_query(F.data.startswith("prodmenu:"))
async def product_menu_callback(callback: CallbackQuery):
    await show_product_menu(callback, callback.data.split(":", 1)[1])
    await callback.answer()

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await show_home(message)

# ============================================================
# HEALTH SERVER & RUNNER
# ============================================================

app = Flask(__name__)

@app.get("/")
def home_health(): return "IMRAN TOPUP BOT is running", 200

def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

async def main():
    db_init()
    Thread(target=run_health_server, daemon=True).start()
    logging.info("IMRAN TOPUP BOT is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
