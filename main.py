import io
import os
import re
import time
import json
import logging
import hashlib
import asyncio
from datetime import datetime
from io import BytesIO

import aiohttp
import asyncpg
import pandas as pd
import phonenumbers
import pycountry
from aiohttp import web
from bs4 import BeautifulSoup
from phonenumbers import region_code_for_number, country_code_for_region

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CopyTextButton,
    InputFile,
    ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN           = "8649162840:AAF0yZS9RX3RRy_flzDLOi3w8w4jgka8kec"
BOT_NAME            = "xyekezz otp"
BOT_LINK            = "https://t.me/+5dXNh2a7tr5mNDA1"
BASE_ADMIN_IDS      = [8525945799]

PANEL_BASE          = "http://139.99.69.196"
PANEL_LOGIN_PAGE    = f"{PANEL_BASE}/ints/login"
PANEL_SIGNIN_URL    = f"{PANEL_BASE}/ints/signin"
PANEL_CDR_URL       = f"{PANEL_BASE}/ints/client/SMSCDRStats"
PANEL_DATA_URL      = f"{PANEL_BASE}/ints/client/res/data_smscdr.php"
PANEL_USERNAME      = "WhatsappChannel"
PANEL_PASSWORD      = "WhatsappChannel"

PANEL2_BASE         = "http://2.59.169.96"
PANEL2_LOGIN_PAGE   = f"{PANEL2_BASE}/ints/login"
PANEL2_SIGNIN_URL   = f"{PANEL2_BASE}/ints/signin"
PANEL2_CDR_URL      = f"{PANEL2_BASE}/ints/client/SMSCDRStats"
PANEL2_DATA_URL     = f"{PANEL2_BASE}/ints/client/res/data_smscdr.php"
PANEL2_USERNAME     = "NigeriaTg019"
PANEL2_PASSWORD     = "NigeriaTg019"

PANEL3_BASE         = "http://15.235.182.3"
PANEL3_LOGIN_PAGE   = f"{PANEL3_BASE}/konekta/sign-in"
PANEL3_SIGNIN_URL   = f"{PANEL3_BASE}/konekta/signin"
PANEL3_CDR_URL      = f"{PANEL3_BASE}/konekta/client/SMSCDRStats"
PANEL3_DATA_URL     = f"{PANEL3_BASE}/konekta/client/res/data_smscdr.php"
PANEL3_USERNAME     = "Malik0"
PANEL3_PASSWORD     = "Malik0"

PANEL4_BASE         = "http://151.80.19.204"
PANEL4_LOGIN_PAGE   = f"{PANEL4_BASE}/ints/login"
PANEL4_SIGNIN_URL   = f"{PANEL4_BASE}/ints/signin"
PANEL4_CDR_URL      = f"{PANEL4_BASE}/ints/client/SMSCDRStats"
PANEL4_DATA_URL     = f"{PANEL4_BASE}/ints/client/res/data_smscdr.php"
PANEL4_USERNAME     = "alexmart"
PANEL4_PASSWORD     = "alexmart"

MAIN_CHANNEL        = "@xyekezz otp"
MAIN_CHANNEL_LINK   = "https://t.me/+5dXNh2a7tr5mNDA1"
BACKUP_CHANNEL      = "@xykess file"
BACKUP_CHANNEL_LINK = "https://t.me/adakanmi"
OTP_GROUP_LINK      = "https://t.me/+5dXNh2a7tr5mNDA1"
OTP_GROUP_ID        = -1003914110525
FORCE_CHANNELS      = ["@xyekes file", "@xyekezz otp"]

DATABASE_URL        = "postgresql://neondb_owner:npg_ocasy6rIX2vR@ep-cold-darkness-ak558puk.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require"
PORT                = int(os.environ.get("PORT", 8080))
POLL_INTERVAL       = 5
KEEPALIVE_INTERVAL  = 180
FLOOD_LIMIT         = 5
FLOOD_WINDOW        = 10
NUMBER_COOLDOWN     = 30
LOGIN_MIN_INTERVAL  = 60

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)

USER_STATE   = {}
flood_data   = {}
otp_cache    = set()
maintenance  = False
ADMIN_IDS    = list(BASE_ADMIN_IDS)

worker_info = {
    "running":         False,
    "logged_in":       False,
    "logged_in_p2":    False,
    "logged_in_p3":    False,
    "logged_in_p4":    False,
    "last_otp":        "—",
    "otps_today":      0,
    "last_login":      "—",
    "last_login_p2":   "—",
    "last_login_p3":   "—",
    "last_login_p4":   "—",
    "errors":          0,
    "login_errors":    0,
    "login_errors_p2": 0,
    "login_errors_p3": 0,
    "login_errors_p4": 0,
    "started_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ0123456789"
)

def sc(t: str) -> str:
    return t.translate(_SC)

def iso_to_flag(iso: str) -> str:
    try:
        code = (iso or "").upper()[:2]
        cid  = COUNTRY_CUSTOM_EMOJI_IDS.get(code)
        unicode_flag = "".join(chr(ord(c) + 127397) for c in code)
        if cid:
            return f'<tg-emoji emoji-id="{cid}">{unicode_flag}</tg-emoji>'
        return unicode_flag
    except Exception:
        return ""

def iso_to_name(iso: str) -> str:
    try:
        return pycountry.countries.get(alpha_2=iso).name
    except Exception:
        return iso

def parse_phone(raw: str):
    clean = re.sub(r"\D", "", str(raw))
    if not (7 <= len(clean) <= 15):
        return None, None, None, None
    try:
        p   = phonenumbers.parse("+" + clean)
        iso = region_code_for_number(p)
        if not iso:
            return clean, None, None, None
        name = iso_to_name(iso)
        dial = country_code_for_region(iso)
        return clean, iso, name, dial
    except Exception:
        return clean, None, None, None

def detect_phone_column(df: pd.DataFrame):
    priority = {"number", "phone", "phone number", "msisdn", "mobile", "tel", "telephone"}
    for col in df.columns:
        if col.strip().lower() in priority:
            return col
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(20)
        ratio  = sample.str.replace(r"\D", "", regex=True).str.len().between(7, 15).mean()
        if ratio >= 0.6:
            return col
    return None

def load_file_df(data: bytes, name: str) -> pd.DataFrame:
    n = name.lower()
    if n.endswith(".csv"):
        return pd.read_csv(BytesIO(data))
    if n.endswith(".xlsx"):
        return pd.read_excel(BytesIO(data), engine="openpyxl")
    if n.endswith(".xls"):
        return pd.read_excel(BytesIO(data), engine="xlrd")
    raise ValueError("unsupported format")

def extract_numbers_smart(data: bytes, name: str) -> dict:
    groups  = {}
    unknown = []
    dupes   = 0
    total   = 0
    seen    = set()
    n       = name.lower()

    if n.endswith((".csv", ".xlsx", ".xls")):
        try:
            df  = load_file_df(data, name)
            col = detect_phone_column(df)
            if col:
                raws = df[col].dropna().astype(str).tolist()
            else:
                raws = []
                for c2 in df.columns:
                    raws += df[c2].dropna().astype(str).tolist()
        except Exception:
            raws = data.decode("utf-8", errors="ignore").splitlines()
    else:
        raws = data.decode("utf-8", errors="ignore").splitlines()

    for raw in raws:
        raw = str(raw).strip()
        if not raw:
            continue
        total += 1
        clean, iso, cname, dial = parse_phone(raw)
        if clean is None:
            continue
        if clean in seen:
            dupes += 1
            continue
        seen.add(clean)
        if iso:
            if iso not in groups:
                groups[iso] = {"name": cname, "flag": iso_to_flag(iso), "dial": dial, "numbers": []}
            groups[iso]["numbers"].append(clean)
        else:
            unknown.append(clean)

    return {"groups": groups, "unknown": unknown, "dupes": dupes, "total": total}

_db_pool = None

async def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10, command_timeout=30)
    return _db_pool

async def db_execute(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(sql, *args)

async def db_fetchone(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)

async def db_fetchall(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *args)

async def db_fetchval(sql, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(sql, *args)

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    BIGINT PRIMARY KEY,
                username   TEXT    DEFAULT '',
                first_name TEXT    DEFAULT '',
                joined_at  TIMESTAMP DEFAULT NOW(),
                is_banned  BOOLEAN DEFAULT FALSE
            );
            CREATE TABLE IF NOT EXISTS otp_history (
                id         BIGSERIAL PRIMARY KEY,
                hash       TEXT    UNIQUE NOT NULL,
                number     TEXT,
                otp        TEXT,
                service    TEXT,
                sms        TEXT,
                range_name TEXT,
                added_at   TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS traffic (
                id          BIGSERIAL PRIMARY KEY,
                range_name  TEXT,
                number      TEXT,
                sms         TEXT,
                otp         TEXT,
                service     TEXT,
                received_at TEXT
            );
            CREATE TABLE IF NOT EXISTS numbers (
                id       BIGSERIAL PRIMARY KEY,
                country  TEXT    NOT NULL,
                flag     TEXT    DEFAULT '',
                number   TEXT    NOT NULL UNIQUE,
                service  TEXT    DEFAULT 'All',
                is_used  BOOLEAN DEFAULT FALSE,
                used_by  BIGINT  DEFAULT NULL,
                use_date TIMESTAMP DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id   BIGINT PRIMARY KEY,
                ts        BIGINT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_otp_hash     ON otp_history(hash);
            CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
            CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
            CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
        """)
        try:
            await conn.execute("ALTER TABLE numbers ADD COLUMN IF NOT EXISTS flag TEXT DEFAULT ''")
        except Exception:
            pass
    logger.info("DB ready")

async def get_setting(key, default=""):
    row = await db_fetchone("SELECT value FROM settings WHERE key=$1", key)
    return row["value"] if row else default

async def set_setting(key, value):
    await db_execute(
        "INSERT INTO settings (key,value) VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        key, value,
    )

CHANNEL_LABELS = {
    "@oracron":  ("ᴏʀᴀᴄʀᴏɴ",  MAIN_CHANNEL_LINK),
    "@oracbott": ("ᴏʀᴀᴄ ʙᴏᴛ", BACKUP_CHANNEL_LINK),
}

SERVICE_FULL_NAMES = {
    "whatsapp": "WhatsApp", "telegram": "Telegram", "instagram": "Instagram",
    "facebook": "Facebook", "messenger": "Messenger", "google": "Google",
    "gmail": "Gmail", "youtube": "YouTube", "tiktok": "TikTok",
    "twitter": "Twitter", "twitter/x": "Twitter", "x": "Twitter",
    "snapchat": "Snapchat", "discord": "Discord", "line": "Line",
    "wechat": "WeChat", "viber": "Viber", "signal": "Signal",
    "skype": "Skype", "threads": "Threads", "twitch": "Twitch",
    "kakaotalk": "KakaoTalk", "kakao": "KakaoTalk", "zalo": "Zalo",
    "imo": "imo", "tinder": "Tinder", "bumble": "Bumble", "hinge": "Hinge",
    "badoo": "Badoo", "grindr": "Grindr", "okcupid": "OkCupid", "match": "Match",
    "linkedin": "LinkedIn", "pinterest": "Pinterest", "reddit": "Reddit",
    "tumblr": "Tumblr", "vk": "VK", "ok": "OK.ru", "weibo": "Weibo", "qq": "QQ",
    "binance": "Binance", "bybit": "Bybit", "okx": "OKX", "bitget": "Bitget",
    "coinbase": "Coinbase", "kraken": "Kraken", "kucoin": "KuCoin",
    "huobi": "Huobi", "htx": "HTX", "mexc": "MEXC", "gateio": "Gate.io",
    "gate": "Gate.io", "bitfinex": "Bitfinex", "crypto.com": "Crypto.com",
    "cryptocom": "Crypto.com", "blockchain": "Blockchain",
    "amazon": "Amazon", "apple": "Apple", "microsoft": "Microsoft",
    "netflix": "Netflix", "spotify": "Spotify", "uber": "Uber", "lyft": "Lyft",
    "bolt": "Bolt", "didi": "DiDi", "olacabs": "Ola", "ola": "Ola",
    "grab": "Grab", "doordash": "DoorDash", "ubereats": "Uber Eats",
    "deliveroo": "Deliveroo", "glovo": "Glovo", "wolt": "Wolt",
    "paypal": "PayPal", "stripe": "Stripe", "venmo": "Venmo", "zelle": "Zelle",
    "cashapp": "Cash App", "wise": "Wise", "revolut": "Revolut", "n26": "N26",
    "monzo": "Monzo", "chime": "Chime", "robinhood": "Robinhood",
    "etrade": "E*Trade", "fidelity": "Fidelity", "schwab": "Schwab",
    "westernunion": "Western Union", "moneygram": "MoneyGram",
    "remitly": "Remitly", "paysafe": "Paysafecard", "skrill": "Skrill",
    "neteller": "Neteller", "payoneer": "Payoneer", "alipay": "Alipay",
    "wechatpay": "WeChat Pay", "googlepay": "Google Pay", "applepay": "Apple Pay",
    "samsungpay": "Samsung Pay", "mpesa": "M-Pesa", "klarna": "Klarna",
    "afterpay": "Afterpay", "affirm": "Affirm",
    "ebay": "eBay", "etsy": "Etsy", "shopee": "Shopee", "lazada": "Lazada",
    "aliexpress": "AliExpress", "alibaba": "Alibaba", "wish": "Wish",
    "temu": "Temu", "shein": "Shein", "mercadolibre": "Mercado Libre",
    "olx": "OLX", "wallapop": "Wallapop", "depop": "Depop",
    "vinted": "Vinted", "craigslist": "Craigslist", "kijiji": "Kijiji",
    "booking": "Booking", "airbnb": "Airbnb", "agoda": "Agoda",
    "expedia": "Expedia", "trip": "Trip.com", "skyscanner": "Skyscanner",
    "hotels": "Hotels.com", "kayak": "Kayak", "trivago": "Trivago",
    "tripadvisor": "TripAdvisor", "vrbo": "Vrbo",
    "steam": "Steam", "epic": "Epic Games", "epicgames": "Epic Games",
    "playstation": "PlayStation", "psn": "PlayStation", "xbox": "Xbox",
    "nintendo": "Nintendo", "ea": "EA", "origin": "Origin", "ubisoft": "Ubisoft",
    "riot": "Riot Games", "blizzard": "Blizzard", "battlenet": "Battle.net",
    "roblox": "Roblox", "minecraft": "Minecraft", "supercell": "Supercell",
    "pubg": "PUBG", "fortnite": "Fortnite", "valorant": "Valorant",
    "mihoyo": "miHoYo", "hoyoverse": "HoYoverse", "genshin": "Genshin Impact",
    "github": "GitHub", "gitlab": "GitLab", "bitbucket": "Bitbucket",
    "stackoverflow": "Stack Overflow", "openai": "OpenAI", "chatgpt": "ChatGPT",
    "anthropic": "Anthropic", "claude": "Claude", "gemini": "Gemini",
    "huggingface": "Hugging Face", "midjourney": "Midjourney",
    "notion": "Notion", "slack": "Slack", "zoom": "Zoom", "teams": "MS Teams",
    "webex": "Webex", "skype": "Skype", "trello": "Trello", "asana": "Asana",
    "monday": "Monday", "clickup": "ClickUp", "jira": "Jira",
    "dropbox": "Dropbox", "drive": "Google Drive", "onedrive": "OneDrive",
    "box": "Box", "icloud": "iCloud", "mega": "MEGA",
    "yandex": "Yandex", "mail.ru": "Mail.ru", "mailru": "Mail.ru",
    "outlook": "Outlook", "hotmail": "Hotmail", "yahoo": "Yahoo",
    "protonmail": "ProtonMail", "proton": "Proton", "tutanota": "Tuta",
    "discord": "Discord", "guilded": "Guilded", "matrix": "Matrix",
    "telegram_x": "Telegram X", "session": "Session", "wickr": "Wickr",
    "bluesky": "Bluesky", "mastodon": "Mastodon", "truthsocial": "Truth Social",
    "parler": "Parler", "gettr": "Gettr", "rumble": "Rumble", "kick": "Kick",
    "onlyfans": "OnlyFans", "fansly": "Fansly", "patreon": "Patreon",
    "fiverr": "Fiverr", "upwork": "Upwork", "freelancer": "Freelancer",
    "indeed": "Indeed", "glassdoor": "Glassdoor", "ziprecruiter": "ZipRecruiter",
    "doordash": "DoorDash", "instacart": "Instacart", "postmates": "Postmates",
    "walmart": "Walmart", "target": "Target", "costco": "Costco",
    "bestbuy": "Best Buy", "homedepot": "Home Depot", "wayfair": "Wayfair",
    "ikea": "IKEA", "zara": "Zara", "hm": "H&M", "nike": "Nike",
    "adidas": "Adidas", "puma": "Puma", "underarmour": "Under Armour",
    "starbucks": "Starbucks", "mcdonalds": "McDonald's", "kfc": "KFC",
    "burgerking": "Burger King", "dominos": "Domino's", "pizzahut": "Pizza Hut",
    "subway": "Subway", "chipotle": "Chipotle", "wendys": "Wendy's",
    "duolingo": "Duolingo", "babbel": "Babbel", "rosettastone": "Rosetta Stone",
    "coursera": "Coursera", "udemy": "Udemy", "khanacademy": "Khan Academy",
    "edx": "edX", "skillshare": "Skillshare", "lingoda": "Lingoda",
    "other": "Other",
}

DEFAULT_SERVICES = [
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Google",
    "TikTok", "Twitter", "Snapchat", "Discord", "Line",
    "WeChat", "Viber", "Signal", "Skype", "Messenger",
    "Threads", "Twitch", "YouTube", "Binance", "Bybit",
    "OKX", "Bitget", "Coinbase", "Kraken", "Stripe",
    "PayPal", "Amazon", "Apple", "Microsoft", "Netflix",
    "Spotify", "Uber", "Other",
]

def _abbrev_from_name(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", name or "")
    if not s:
        return "OT"
    return s[:2].upper()

_ABBREV_OVERRIDES = {
    "whatsapp": "WA", "telegram": "TG", "instagram": "IG", "facebook": "FB",
    "messenger": "MS", "google": "GG", "gmail": "GM", "youtube": "YT",
    "tiktok": "TT", "twitter": "TW", "twitter/x": "TW", "x": "TW",
    "snapchat": "SC", "discord": "DC", "line": "LN", "wechat": "WC",
    "viber": "VB", "signal": "SG", "skype": "SK", "threads": "TH",
    "twitch": "TC", "kakaotalk": "KK", "zalo": "ZL", "imo": "IM",
    "linkedin": "LI", "pinterest": "PT", "reddit": "RD", "tumblr": "TM",
    "vk": "VK", "weibo": "WB", "qq": "QQ",
    "binance": "BN", "bybit": "BB", "okx": "OK", "bitget": "BG",
    "coinbase": "CB", "kraken": "KR", "kucoin": "KC", "mexc": "MX",
    "gateio": "GT", "gate": "GT", "huobi": "HB", "htx": "HX",
    "crypto.com": "CR", "cryptocom": "CR",
    "amazon": "AM", "apple": "AP", "microsoft": "MC", "netflix": "NF",
    "spotify": "SP", "uber": "UB", "lyft": "LY", "bolt": "BL",
    "paypal": "PP", "stripe": "ST", "venmo": "VN", "cashapp": "CA",
    "wise": "WS", "revolut": "RV", "skrill": "SR", "payoneer": "PY",
    "alipay": "AL", "mpesa": "MP", "klarna": "KL",
    "ebay": "EB", "etsy": "ET", "shopee": "SH", "lazada": "LZ",
    "aliexpress": "AE", "alibaba": "AB", "temu": "TE", "shein": "SI",
    "booking": "BK", "airbnb": "AI", "agoda": "AG", "expedia": "EX",
    "steam": "SM", "epic": "EP", "epicgames": "EP", "playstation": "PS",
    "xbox": "XB", "nintendo": "NT", "roblox": "RB", "minecraft": "MN",
    "github": "GH", "gitlab": "GL", "openai": "OA", "chatgpt": "GP",
    "claude": "CL", "gemini": "GE", "notion": "NO", "slack": "SL",
    "zoom": "ZM", "teams": "TS", "trello": "TR", "asana": "AS",
    "dropbox": "DB", "drive": "DR", "onedrive": "OD", "icloud": "IC",
    "mega": "MG", "yandex": "YX", "outlook": "OL", "yahoo": "YH",
    "proton": "PR", "protonmail": "PR",
    "bluesky": "BS", "mastodon": "MD", "kick": "KI", "rumble": "RM",
    "onlyfans": "OF", "patreon": "PA", "fiverr": "FV", "upwork": "UP",
    "tinder": "TD", "bumble": "BM", "hinge": "HG", "badoo": "BD",
    "duolingo": "DL", "coursera": "CO", "udemy": "UD",
    "other": "OT",
}

SERVICE_ABBREVS = {k: _ABBREV_OVERRIDES.get(k, _abbrev_from_name(v)) for k, v in SERVICE_FULL_NAMES.items()}

SERVICE_CUSTOM_EMOJI_IDS = {
    "discord":     "5325612636467903082",
    "facebook":    "5323261730283863478",
    "instagram":   "5319160079465857105",
    "line":        "5323608076446613036",
    "messenger":   "5323687726615119535",
    "signal":      "5325742125436910868",
    "skype":       "5328064671951896068",
    "snapchat":    "5327959866159938948",
    "telegram":    "5330321861949539755",
    "threads":     "5328050550099427291",
    "tiktok":      "5328175271654736902",
    "twitch":      "5334792209940102096",
    "viber":       "5328242556612395440",
    "wechat":      "5332449498553663205",
    "whatsapp":    "5321533581472842536",
    "twitter":     "5334932883003949665",
    "twitter/x":   "5334932883003949665",
    "x":           "5334932883003949665",
    "youtube":     "5346056560537779652",
    "amazon":      "5346309375197725525",
    "apple":       "5357184657592962696",
    "netflix":     "5346134750417403743",
    "spotify":     "5345967461441223890",
    "paypal":      "5346259862814734771",
    "google":      "5359480394922082925",
    "gmail":       "5359480394922082925",
    "googlevoice": "5359480394922082925",
    "googleads":   "5359480394922082925",
    "googlepay":   "5359480394922082925",
    "googleplay":  "5359480394922082925",
    "uber":        "5359772714691216710",
    "ubereats":    "5359772714691216710",
    "microsoft":   "5359437015752401733",
    "outlook":     "5359437015752401733",
    "hotmail":     "5359437015752401733",
    "xbox":        "5359437015752401733",
    "live":        "5359437015752401733",
    "binance":     "5361575381184823162",
    "bitget":      "5361963895336485277",
    "kraken":      "5362034259785694259",
    "stripe":      "5346251367369425932",
}

COUNTRY_CUSTOM_EMOJI_IDS = {
    "AD": "5221987861733061751",
    "AE": "5224565851427976312",
    "AF": "5222096009009575868",
    "AG": "5224544866217765554",
    "AL": "5224312057515486246",
    "AM": "5224369957969603463",
    "AO": "5224379767674907895",
    "AR": "5221980461504411710",
    "AT": "5224520754271366661",
    "AU": "5224659803837574114",
    "AZ": "5224426544163728284",
    "BA": "5224496092569155254",
    "BB": "5222156533688712094",
    "BD": "5224407289825340729",
    "BE": "5224513182244024630",
    "BF": "5222356541725749790",
    "BG": "5222092074819530668",
    "BH": "5224492892818518587",
    "BI": "5224490444687158452",
    "BJ": "5222024115552009151",
    "BM": "5222482143749353810",
    "BN": "5224435958732042406",
    "BO": "5224675484763170798",
    "BR": "5224688610183228070",
    "BS": "5224504167107668172",
    "BT": "5224541065171710147",
    "BW": "5224288456670196085",
    "BY": "5280820319458707404",
    "BZ": "5224316292353241916",
    "CA": "5222001124592071204",
    "CD": "5224398158724871677",
    "CF": "5222073662294733523",
    "CG": "5222104268231684600",
    "CH": "5224707263226194753",
    "CL": "5222350726340032308",
    "CM": "5222270788408717651",
    "CN": "5224435456220868088",
    "CO": "5224455152940886669",
    "CR": "5222453801260168022",
    "CV": "5222347737042792258",
    "CY": "5222431454545327055",
    "CZ": "5222073533445714675",
    "DE": "5222165617544542414",
    "DJ": "5224203012590810589",
    "DK": "5222297215342490217",
    "DM": "5222337489250824921",
    "DO": "5224286412265763450",
    "DZ": "5224260376174015500",
    "EC": "5224191188545840926",
    "EE": "5222195463272281351",
    "EG": "5222161185138292290",
    "ES": "5222024776976970940",
    "ET": "5224467805914542024",
    "EU": "5222108911091331711",
    "FI": "5224282903277482188",
    "FJ": "5221962676044838178",
    "FM": "5222280486444873367",
    "FO": "5280985770188885026",
    "FR": "5222029789203804982",
    "GA": "5224669733801963467",
    "GB": "5224518800061245598",
    "GD": "5222234560359577687",
    "GE": "5222152195771742239",
    "GH": "5224511339703056124",
    "GM": "5221949872747330159",
    "GN": "5222337588035073000",
    "GQ": "5222172811614762423",
    "GR": "5222463490706389920",
    "GT": "5222128302868672826",
    "GW": "5224705704153066489",
    "GY": "5224570532942329532",
    "HN": "5222229234600130045",
    "HR": "5221967765581085099",
    "HT": "5224683146984831315",
    "HU": "5224691998912427164",
    "ID": "5224405893960969756",
    "IE": "5224257017509588818",
    "IL": "5224720599099648709",
    "IN": "5222300011366200403",
    "IQ": "5221980268230882832",
    "IR": "5224374154152653367",
    "IS": "5222063229819172521",
    "IT": "5222460101977190141",
    "JM": "5222007034467074185",
    "JO": "5222292177345853436",
    "JP": "5222390089715299207",
    "KE": "5222089648163009103",
    "KG": "5224388147156102493",
    "KH": "5224189882875785448",
    "KI": "5224652244695134610",
    "KM": "5222398735484466247",
    "KR": "5222345550904439270",
    "KW": "5221949726718442491",
    "KZ": "5222276376161171525",
    "LA": "5224200843632324642",
    "LB": "5222244425899455269",
    "LC": "5222000927023577045",
    "LK": "5224277294050192388",
    "LR": "5221998371518034740",
    "LS": "5224245850594619415",
    "LT": "5224245902134226386",
    "LU": "5224499567197700690",
    "LV": "5224401229626484931",
    "LY": "5222194286451242896",
    "MA": "5224530035695693965",
    "MC": "5221937224068640464",
    "MD": "5224216473018314447",
    "ME": "5224463399278096980",
    "MG": "5222042605386217334",
    "MH": "5224538449536624503",
    "MK": "5222470435668505656",
    "ML": "5224322352552096671",
    "MN": "5224192257992701543",
    "MQ": "5281027792148909351",
    "MT": "5224731388057497620",
    "MU": "5224238347286752315",
    "MV": "5224393700548814960",
    "MX": "5221971386238514431",
    "MY": "5224312886444174057",
    "MZ": "5222470388423864826",
    "NA": "5224690826386351746",
    "NE": "5222099049846420864",
    "NG": "5224723614166691638",
    "NL": "5224516489368841614",
    "NO": "5224465228934163949",
    "NP": "5222444378101925267",
    "NZ": "5224573595254009705",
    "OM": "5222396686785066306",
    "PA": "5222111719999945107",
    "PE": "5224482026551258766",
    "PG": "5224500164198149905",
    "PH": "5222065042295376892",
    "PK": "5224637061985742245",
    "PL": "5224670399521892983",
    "PR": "5224220115150582423",
    "PS": "5222041677673282461",
    "PT": "5224404094369672274",
    "PY": "5222152565138929235",
    "QA": "5222225596762830469",
    "RO": "5222273794885826118",
    "RS": "5222145396838512729",
    "RU": "5280582975270963511",
    "RW": "5222449197055227754",
    "SA": "5224698145010624573",
    "SB": "5222290588207954120",
    "SC": "5224467496676896871",
    "SD": "5224372990216514135",
    "SE": "5222201098269373561",
    "SG": "5224194023224257181",
    "SI": "5224660718665607511",
    "SK": "5222401879400528047",
    "SL": "5224420995065983217",
    "SN": "5224358988623130949",
    "SO": "5222370504664428325",
    "SR": "5224567367551428669",
    "SS": "5224618146949773268",
    "ST": "5221953304426198315",
    "SV": "5224337131534559907",
    "SZ": "5224269666188274723",
    "TD": "5222060468155204001",
    "TG": "5222408051268532030",
    "TH": "5224638530864556281",
    "TJ": "5222217865821696536",
    "TL": "5224515905253291409",
    "TM": "5224256935905208951",
    "TN": "5221991375016310330",
    "TR": "5224601903383457698",
    "TT": "5224391883777651050",
    "TZ": "5224397364155923150",
    "UA": "5222250679371839695",
    "UG": "5222464040462200940",
    "UN": "5451772687993031127",
    "US": "5224321781321442532",
    "UY": "5222466849370813232",
    "UZ": "5222404546575219535",
    "VA": "5222420266155520507",
    "VC": "5224541228380467535",
    "VI": "5224395882392201810",
    "VN": "5222359651282071925",
    "VU": "5222126748090512778",
    "WS": "5224660353593387686",
    "XK": "5222197129719592160",
    "YE": "5222300655611294950",
    "ZA": "5224696216570309138",
    "ZM": "5224646626877911277",
    "ZW": "5222060442385397848",
}

BUTTON_ICONS = {
    "get_number": "", "live_traffic": "", "otp_group": "",
    "admin": "", "channel": "", "bot": "",
    "change_number": "", "change_country": "", "back": "",
    "verify": "", "joined": "", "cancel": "",
    "add": "", "delete": "", "status": "", "all": "",
    "copy_otp": "", "copy_sms": "", "stock": "",
}

def _norm_service(service: str) -> str:
    return re.sub(r"\s+", "", (service or "").lower().strip())

def service_full_name(service: str) -> str:
    key = (service or "").lower().strip()
    if key in SERVICE_FULL_NAMES:
        return SERVICE_FULL_NAMES[key]
    nk = _norm_service(service)
    if nk in SERVICE_FULL_NAMES:
        return SERVICE_FULL_NAMES[nk]
    return (service or "Other").strip().title()

def service_tag(service: str) -> str:
    name = service_full_name(service)
    return "#" + re.sub(r"[^A-Za-z0-9]", "", name) if name else "#Other"

def service_abbrev(service: str) -> str:
    key = (service or "").lower().strip()
    if key in SERVICE_ABBREVS:
        return SERVICE_ABBREVS[key]
    nk = _norm_service(service)
    if nk in SERVICE_ABBREVS:
        return SERVICE_ABBREVS[nk]
    return _abbrev_from_name(service)

def service_icon(service: str) -> str:
    key = (service or "").lower().strip()
    cid = SERVICE_CUSTOM_EMOJI_IDS.get(key) or SERVICE_CUSTOM_EMOJI_IDS.get(_norm_service(service))
    if not cid:
        return ""
    return f'<tg-emoji emoji-id="{cid}">📱</tg-emoji>'


def _btn(text, *, cb=None, url=None, style=None, copy=None):
    if copy is not None:
        return InlineKeyboardButton(text, copy_text=CopyTextButton(copy), style=style)
    if url is not None:
        return InlineKeyboardButton(text, url=url, style=style)
    return InlineKeyboardButton(text, callback_data=cb, style=style)

def _markup(rows):
    return InlineKeyboardMarkup(rows)

def join_gate_markup(statuses):
    rows = []
    pair = []
    for channel, (label, link) in CHANNEL_LABELS.items():
        joined = statuses.get(channel, False)
        if joined:
            btn = _btn(label, cb=f"noop_joined__{channel}", style="primary")
        else:
            btn = _btn(label, url=link, style="danger")
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")])
    rows.append([_btn("ᴠᴇʀɪꜰʏ", cb="check_join", style="success")])
    return _markup(rows)

def main_menu_markup(user_id=None):
    rows = [
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ",   cb="menu_get_number",  style="success"),
            _btn("ʟɪᴠᴇ ᴛʀᴀꜰꜰɪᴄ", cb="menu_live_traffic", style="danger"),
        ],
        [_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")],
    ]
    if user_id and is_admin(user_id):
        rows.append([_btn("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", cb="menu_admin", style="danger")])
    return _markup(rows)

def otp_markup(otp: str, sms: str):
    return _markup([
        [
            _btn(str(otp),         copy=otp, style="success"),
            _btn("ᴄᴏᴘʏ ꜰᴜʟʟ ꜱᴍꜱ", copy=sms, style="primary"),
        ],
        [
            _btn("ᴄʜᴀɴɴᴇʟ", url=MAIN_CHANNEL_LINK, style="primary"),
            _btn("ʙᴏᴛ",         url=BOT_LINK,           style="primary"),
        ],
    ])

def stock_markup():
    return _markup([
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,       style="success"),
            _btn("ᴏᴛᴘ ɢʀᴏᴜᴘ",   url=OTP_GROUP_LINK, style="primary"),
        ],
    ])

def number_assigned_markup(country, service, num_id):
    return _markup([
        [
            _btn("ᴄʜᴀɴɢᴇ ɴᴜᴍʙᴇʀ",  cb=f"chgn__{country}__{service}__{num_id}", style="success"),
            _btn("ᴄʜᴀɴɢᴇ ᴄᴏᴜɴᴛʀʏ", cb=f"gns__{service}",                       style="primary"),
        ],
        [_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")],
        [_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")],
    ])

def admin_markup():
    return _markup([
        [
            _btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ",    cb="adm_add_numbers",    style="success"),
            _btn("ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀꜱ", cb="adm_delete_numbers", style="danger"),
        ],
        [
            _btn("ʙʀᴏᴀᴅᴄᴀꜱᴛ", cb="adm_broadcast", style="success"),
            _btn("ꜱᴛᴀᴛᴜꜱ",   cb="adm_status",    style="primary"),
        ],
        [_btn("ʙᴀᴄᴋ",    cb="menu_back",   style="danger")],
    ])

def back_to_menu():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")]])

def back_to_admin():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]])

def cancel_state_markup(back_cb="adm_back"):
    return _markup([
        [
            _btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger"),
            _btn("ʙᴀᴄᴋ",   cb=back_cb,            style="danger"),
        ]
    ])

def method_picker_markup():
    return _markup([
        [
            _btn("ᴜᴘʟᴏᴀᴅ ꜰɪʟᴇ",   cb="adm_addmethod_file", style="primary"),
            _btn("ᴛʏᴘᴇ ɴᴜᴍʙᴇʀꜱ", cb="adm_addmethod_type", style="primary"),
        ],
        [_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger")],
    ])

def service_picker_markup():
    buttons = []
    row_buf = []
    for svc in DEFAULT_SERVICES:
        row_buf.append(_btn(sc(svc), cb=f"adm_svc__{svc}", style="primary"))
        if len(row_buf) == 3:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ᴄᴜꜱᴛᴏᴍ", cb="adm_svc_custom", style="primary")])
    buttons.append([_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger")])
    return _markup(buttons)

async def build_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        row_buf.append(_btn(sc(r['service']), cb=f"gns__{r['service']}", style="success"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")])
    return rows, _markup(buttons)

async def build_country_grid(service):
    rows = await db_fetchall(
        "SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE AND service=$1 GROUP BY country, flag ORDER BY country",
        service,
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        flag  = r["flag"] or ""
        label = f"{flag} {sc(r['country'])}".strip()
        row_buf.append(_btn(label, cb=f"gnc__{r['country']}__{service}", style="success"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb="menu_get_number", style="danger")])
    return rows, _markup(buttons)

async def build_delete_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        row_buf.append(_btn(sc(r['service']), cb=f"del_svc__{r['service']}", style="danger"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ᴀʟʟ", cb="del_svc__ALL", style="danger")])
    buttons.append([_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")])
    return rows, _markup(buttons)

async def build_delete_country_grid(service):
    if service == "ALL":
        rows = await db_fetchall("SELECT country, flag, COUNT(*) AS cnt FROM numbers GROUP BY country, flag ORDER BY country")
    else:
        rows = await db_fetchall("SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE service=$1 GROUP BY country, flag ORDER BY country", service)
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        flag  = r["flag"] or ""
        label = f"{flag} {sc(r['country'])}".strip()
        row_buf.append(_btn(label, cb=f"del_cntry__{service}__{r['country']}", style="danger"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ᴀʟʟ ᴄᴏᴜɴᴛʀɪᴇꜱ", cb=f"del_cntry__{service}__ALL", style="danger")])
    buttons.append([_btn("ʙᴀᴄᴋ", cb="adm_delete_numbers", style="danger")])
    return rows, _markup(buttons)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_flooded(user_id):
    if is_admin(user_id):
        return False
    now     = time.time()
    history = [t for t in flood_data.get(user_id, []) if now - t < FLOOD_WINDOW]
    history.append(now)
    flood_data[user_id] = history
    return len(history) > FLOOD_LIMIT

async def register_user(user):
    await db_execute(
        "INSERT INTO users (user_id, username, first_name) VALUES ($1,$2,$3) "
        "ON CONFLICT (user_id) DO UPDATE SET username=$2, first_name=$3",
        user.id, user.username or "", user.first_name or "",
    )

async def is_banned_user(user_id):
    row = await db_fetchone("SELECT is_banned FROM users WHERE user_id=$1", user_id)
    return bool(row and row["is_banned"])

async def check_membership(bot, user_id):
    if is_admin(user_id):
        return True
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "banned"):
                return False
        except Exception:
            return False
    return True

async def check_membership_per_channel(bot, user_id):
    statuses = {}
    for channel in FORCE_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            statuses[channel] = member.status not in ("left", "kicked", "banned")
        except Exception:
            statuses[channel] = False
    return statuses

async def check_number_cooldown(user_id):
    row = await db_fetchone("SELECT ts FROM cooldowns WHERE user_id=$1", user_id)
    if row:
        elapsed = int(time.time()) - row["ts"]
        if elapsed < NUMBER_COOLDOWN:
            return NUMBER_COOLDOWN - elapsed
    return 0

async def set_number_cooldown(user_id):
    await db_execute(
        "INSERT INTO cooldowns (user_id,ts) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET ts=$2",
        user_id, int(time.time()),
    )

def mask_number(number):
    clean = re.sub(r"\D", "", str(number))
    if len(clean) >= 9:
        return f"{clean[:3]}•••••{clean[-3:]}"
    if len(clean) >= 6:
        return f"{clean[:3]}•••{clean[-3:]}"
    return f"{clean}•••"

def extract_otp(sms):
    if not sms:
        return None
    for pattern in (r"\b\d{3}[-\s]\d{3}\b", r"\b\d{6,8}\b", r"\b\d{4,5}\b"):
        m = re.search(pattern, sms)
        if m:
            return m.group().strip()
    return None

async def send_msg(bot, chat_id, text, reply_markup=None):
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

async def edit_msg(query, text, reply_markup=None):
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except Exception:
        pass

async def notify_admins(app, text):
    for aid in ADMIN_IDS:
        try:
            await app.bot.send_message(
                chat_id=aid,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

async def broadcast_stock(app, country, flag, service, count, numbers_list):
    filename   = f"{flag} {sc(country)} — {sc(service)}.txt".replace("/", "-")
    file_bytes = "\n".join(numbers_list).encode("utf-8")
    caption    = (
        f"┌─ ɴᴇᴡ ꜱᴛᴏᴄᴋ ᴀᴅᴅᴇᴅ\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country)}\n"
        f"├─❏ ꜱᴇʀᴠɪᴄᴇ  : {service_icon(service)} {service_full_name(service)}\n"
        f"├─❏ ɴᴜᴍʙᴇʀꜱ  : {count}\n"
        f"└─❏"
    )
    markup = stock_markup()
    try:
        await app.bot.send_document(
            chat_id=MAIN_CHANNEL,
            document=InputFile(BytesIO(file_bytes), filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Channel notify: {e}")

    all_users = await db_fetchall("SELECT user_id FROM users WHERE is_banned=FALSE")
    for row in all_users:
        uid = row["user_id"]
        if uid in ADMIN_IDS:
            continue
        try:
            await app.bot.send_document(
                chat_id=uid,
                document=InputFile(BytesIO(file_bytes), filename=filename),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            await asyncio.sleep(0.05)
        except Exception:
            pass

def format_otp_message(row, otp, panel_name=""):
    masked           = mask_number(row["number"])
    clean            = re.sub(r"\D", "", str(row["number"]))
    _, iso, cname, _ = parse_phone(clean)
    flag             = iso_to_flag(iso) if iso else ""
    sms_txt          = (row.get("sms") or "").strip()
    raw_service      = (row.get("service") or "unknown").strip()
    abbrev           = service_abbrev(raw_service)
    tag              = service_tag(raw_service)
    icon             = service_icon(raw_service)

    head_bits = [p for p in [flag, f"#{iso}" if iso else "", f"#{abbrev}" if abbrev else "", icon, f"<code>{masked}</code>"] if p]
    header = " ".join(head_bits)

    text = f"<b>{header}</b>\n\n{tag}"
    return text, otp_markup(otp, sms_txt)

def number_display_text(number, country_name, flag, service):
    display = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴀꜱꜱɪɢɴᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ   : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ ꜱᴇʀᴠɪᴄᴇ  : {service_icon(service)} {service_full_name(service)}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴏᴛᴘ..."
    )

def number_changed_text(number, country_name, flag, service):
    display = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴄʜᴀɴɢᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ   : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ ꜱᴇʀᴠɪᴄᴇ  : {service_icon(service)} {service_full_name(service)}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴏᴛᴘ..."
    )

def admin_text():
    return f"┌─ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ\n├─❏ ᴍᴀɴᴀɢᴇ ɴᴜᴍʙᴇʀ ᴅᴀᴛᴀʙᴀꜱᴇ\n└─❏"

async def status_text():
    total   = await db_fetchval("SELECT COUNT(*) FROM numbers") or 0
    avail   = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE is_used=FALSE") or 0
    users   = await db_fetchval("SELECT COUNT(*) FROM users") or 0
    otps    = await db_fetchval("SELECT COUNT(*) FROM otp_history") or 0
    p1_stat = "ᴏɴʟɪɴᴇ" if worker_info["logged_in"]    else "ᴏꜰꜰʟɪɴᴇ"
    p2_stat = "ᴏɴʟɪɴᴇ" if worker_info["logged_in_p2"] else "ᴏꜰꜰʟɪɴᴇ"
    p3_stat = "ᴏɴʟɪɴᴇ" if worker_info["logged_in_p3"] else "ᴏꜰꜰʟɪɴᴇ"
    p4_stat = "ᴏɴʟɪɴᴇ" if worker_info["logged_in_p4"] else "ᴏꜰꜰʟɪɴᴇ"
    return (
        f"┌─ ꜱᴛᴀᴛᴜꜱ\n"
        f"├─❏ ᴢʏʀᴏɴ        : {p4_stat} | {worker_info['last_login_p4']}\n"
        f"├─❏ ꜱᴍꜱ ʜᴀᴅɪ    : {p1_stat} | {worker_info['last_login']}\n"
        f"├─❏ ɴɪɢᴇʀɪᴀ      : {p2_stat} | {worker_info['last_login_p2']}\n"
        f"├─❏ ᴋᴏɴᴇᴋᴛᴀ      : {p3_stat} | {worker_info['last_login_p3']}\n"
        f"├─❏ ᴏᴛᴘꜱ ᴛᴏᴅᴀʏ  : {worker_info['otps_today']}\n"
        f"├─❏ ʟᴀꜱᴛ ᴏᴛᴘ    : {worker_info['last_otp']}\n"
        f"├─❏ ɴᴜᴍʙᴇʀꜱ     : {total} ᴛᴏᴛᴀʟ / {avail} ᴀᴠᴀɪʟ\n"
        f"├─❏ ᴜꜱᴇʀꜱ        : {users}\n"
        f"├─❏ ᴏᴛᴘ ʜɪꜱᴛᴏʀʏ  : {otps}\n"
        f"└─❏"
    )

def solve_captcha(html):
    try:
        soup      = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text(" ", strip=True)
        m         = re.search(r"[Ww]hat\s+is\s+(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*[=?]", full_text)
        if not m:
            for tag in soup.find_all(True):
                t = tag.get_text(strip=True)
                m = re.search(r"(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*=\s*\?", t)
                if m:
                    break
        if m:
            a, op, b = int(m.group(1)), m.group(2).strip(), int(m.group(3))
            if op == "+":                    return str(a + b)
            if op == "-":                    return str(a - b)
            if op in ("*", "×", "x", "X"):  return str(a * b)
            if op in ("÷", "/") and b != 0: return str(a // b)
    except Exception as e:
        logger.error(f"Captcha: {e}")
    return "0"


class PanelSession:
    def __init__(self, base, login_page, signin_url, cdr_url, data_url, username, password, name="panel",
                 wi_logged="logged_in", wi_login="login_errors", wi_last_login="last_login"):
        self._base           = base
        self._login_page     = login_page
        self._signin_url     = signin_url
        self._cdr_url        = cdr_url
        self._data_url       = data_url
        self._username       = username
        self._password       = password
        self._name           = name
        self._session        = None
        self._logged_in      = False
        self._sesskey        = ""
        self._last_login_try = 0
        self._login_backoff  = LOGIN_MIN_INTERVAL
        self._last_activity  = 0
        self._last_ping      = 0
        self._wi_logged      = wi_logged
        self._wi_login       = wi_login
        self._wi_last_login  = wi_last_login

    async def _get_session(self):
        if self._session is None or self._session.closed:
            connector     = aiohttp.TCPConnector(ssl=False, limit=10, ttl_dns_cache=600, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection":      "keep-alive",
                    "Cache-Control":   "max-age=0",
                },
                timeout=aiohttp.ClientTimeout(total=60, connect=20),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
        return self._session

    def _can_attempt_login(self):
        return time.time() - self._last_login_try >= self._login_backoff

    async def _keepalive_ping(self):
        if not self._logged_in:
            return
        now = time.time()
        if now - self._last_ping < 120:
            return
        try:
            sess = await self._get_session()
            async with sess.get(
                self._cdr_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "Referer":                  f"{self._base}/ints/client/SMSDashboard",
                    "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                },
            ) as resp:
                final = str(resp.url)
                login_path = self._login_page.split(self._base)[-1].lower()
                if login_path in final.lower() or "/sign-in" in final.lower():
                    logger.warning(f"[{self._name}] Keepalive: session died, marking for relogin")
                    self._logged_in              = False
                    worker_info[self._wi_logged] = False
                else:
                    self._last_ping     = now
                    self._last_activity = now
        except Exception as e:
            logger.warning(f"[{self._name}] Keepalive ping failed: {e}")

    async def login(self) -> bool:
        if not self._can_attempt_login():
            return False

        self._last_login_try = time.time()
        logger.info(f"Attempting panel login (backoff={self._login_backoff}s)")

        try:
            sess = await self._get_session()

            async with sess.get(
                self._login_page,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[{self._name}] Login page status: {resp.status}")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    worker_info[self._wi_login] = worker_info.get(self._wi_login, 0) + 1
                    return False
                login_html = await resp.text(errors="replace")

            capt = solve_captcha(login_html)
            logger.info(f"[{self._name}] Login: capt={capt}")

            payload = {
                "username": self._username,
                "password": self._password,
                "capt":     capt,
            }

            async with sess.post(
                self._signin_url,
                data=payload,
                headers={
                    "Referer":                  self._login_page,
                    "Origin":                   self._base,
                    "Content-Type":             "application/x-www-form-urlencoded",
                    "Upgrade-Insecure-Requests": "1",
                },
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                location = resp.headers.get("Location", "")
                logger.info(f"[{self._name}] Signin: status={resp.status} location={location}")
                if resp.status not in (301, 302):
                    logger.error(f"[{self._name}] Login not redirected: {resp.status}")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    worker_info[self._wi_login] = worker_info.get(self._wi_login, 0) + 1
                    return False
                if self._login_page.split(self._base)[-1].lower() in location.lower() or "/sign-in" in location.lower():
                    logger.error(f"[{self._name}] Login rejected — redirected back to login")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    worker_info[self._wi_login] = worker_info.get(self._wi_login, 0) + 1
                    return False

            await asyncio.sleep(1)

            async with sess.get(
                self._cdr_url,
                allow_redirects=True,
                headers={
                    "Referer":                  f"{self._base}/ints/client/SMSDashboard",
                    "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as cdr_resp:
                cdr_final = str(cdr_resp.url)
                logger.info(f"[{self._name}] CDR after login: status={cdr_resp.status} url={cdr_final}")
                login_path = self._login_page.split(self._base)[-1].lower()
                if login_path in cdr_final.lower() or "/sign-in" in cdr_final.lower():
                    logger.error(f"[{self._name}] CDR redirected to login — session not accepted")
                    self._login_backoff = min(self._login_backoff * 2, 3600)
                    worker_info[self._wi_login] = worker_info.get(self._wi_login, 0) + 1
                    return False
                cdr_html = await cdr_resp.text(errors="replace")

            self._logged_in     = True
            self._login_backoff = LOGIN_MIN_INTERVAL
            self._last_activity = time.time()
            self._last_ping     = time.time()
            worker_info[self._wi_login]      = 0
            worker_info[self._wi_last_login] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            worker_info[self._wi_logged]     = True
            await self._extract_sesskey(cdr_html)
            logger.info(f"[{self._name}] Panel login OK")
            return True

        except Exception as e:
            logger.error(f"[{self._name}] Login exception: {type(e).__name__}: {e}")
            self._login_backoff = min(self._login_backoff * 2, 3600)
            worker_info[self._wi_login] = worker_info.get(self._wi_login, 0) + 1
            return False

    async def _extract_sesskey(self, html: str):
        for pat in (
            r'["\']sesskey["\']\s*[,:=]\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
            r'sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
            r'var\s+sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
        ):
            m = re.search(pat, html)
            if m:
                self._sesskey = m.group(1)
                return
        try:
            sess = await self._get_session()
            async with sess.get(self._cdr_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if "/ints/login" in str(resp.url).lower():
                    self._logged_in         = False
                    worker_info[self._wi_logged] = False
                    return
                h = await resp.text(errors="replace")
                for pat in (
                    r'["\']sesskey["\']\s*[,:=]\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                ):
                    m = re.search(pat, h)
                    if m:
                        self._sesskey = m.group(1)
                        return
        except Exception as e:
            logger.warning(f"sesskey fetch: {e}")

    async def verify_session(self) -> bool:
        try:
            sess = await self._get_session()
            async with sess.get(self._cdr_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                final = str(resp.url)
                login_path = self._login_page.split(self._base)[-1].lower()
                if login_path in final.lower() or "/sign-in" in final.lower():
                    self._logged_in         = False
                    worker_info[self._wi_logged] = False
                    return False
                self._last_activity = time.time()
                return True
        except Exception as e:
            logger.error(f"Session verify: {e}")
            return False

    async def fetch_cdr(self):
        try:
            sess   = await self._get_session()
            now_dt = datetime.now()
            fdate1 = now_dt.strftime("%Y-%m-01 00:00:00")
            fdate2 = now_dt.strftime("%Y-%m-%d 23:59:59")
            params = {
                "fdate1":         fdate1,
                "fdate2":         fdate2,
                "frange":         "",
                "fnum":           "",
                "fcli":           "",
                "fgdate":         "",
                "fgmonth":        "",
                "fgrange":        "",
                "fgnumber":       "",
                "fgcli":          "",
                "fg":             "0",
                "sEcho":          "1",
                "iColumns":       "7",
                "sColumns":       "......",
                "iDisplayStart":  "0",
                "iDisplayLength": "50",
                "mDataProp_0":    "0",
                "sSearch_0":      "",
                "bRegex_0":       "false",
                "bSearchable_0":  "true",
                "bSortable_0":    "true",
                "mDataProp_1":    "1",
                "sSearch_1":      "",
                "bRegex_1":       "false",
                "bSearchable_1":  "true",
                "bSortable_1":    "true",
                "mDataProp_2":    "2",
                "sSearch_2":      "",
                "bRegex_2":       "false",
                "bSearchable_2":  "true",
                "bSortable_2":    "true",
                "mDataProp_3":    "3",
                "sSearch_3":      "",
                "bRegex_3":       "false",
                "bSearchable_3":  "true",
                "bSortable_3":    "true",
                "mDataProp_4":    "4",
                "sSearch_4":      "",
                "bRegex_4":       "false",
                "bSearchable_4":  "true",
                "bSortable_4":    "true",
                "mDataProp_5":    "5",
                "sSearch_5":      "",
                "bRegex_5":       "false",
                "bSearchable_5":  "true",
                "bSortable_5":    "true",
                "mDataProp_6":    "6",
                "sSearch_6":      "",
                "bRegex_6":       "false",
                "bSearchable_6":  "true",
                "bSortable_6":    "true",
                "sSearch":        "",
                "bRegex":         "false",
                "iSortCol_0":     "0",
                "sSortDir_0":     "desc",
                "iSortingCols":   "1",
                "_":              str(int(time.time() * 1000)),
            }
            if self._sesskey:
                params["sesskey"] = self._sesskey

            async with sess.get(
                self._data_url,
                params=params,
                headers={
                    "Referer":          f"{self._base}/ints/client/SMSDashboard",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept":           "application/json, text/javascript, */*; q=0.01",
                    "Connection":       "keep-alive",
                },
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                final = str(resp.url)
                login_path = self._login_page.split(self._base)[-1].lower()
                if login_path in final.lower() or "/sign-in" in final.lower():
                    self._logged_in         = False
                    worker_info[self._wi_logged] = False
                    return None, "session_expired"
                text = await resp.text(errors="replace")
                if not text.strip():
                    return None, "empty_response"
                try:
                    data = json.loads(text)
                except Exception:
                    if ("login" in text.lower() or "sign-in" in text.lower()) and len(text) < 5000:
                        self._logged_in         = False
                        worker_info[self._wi_logged] = False
                        return None, "session_expired"
                    return None, "parse_error"

                aa   = data.get("aaData", [])
                rows = []
                for row in aa:
                    if len(row) < 5:
                        continue
                    rows.append({
                        "date":    str(row[0]).strip(),
                        "range":   str(row[1]).strip(),
                        "number":  str(row[2]).strip(),
                        "service": str(row[3]).strip(),
                        "sms":     str(row[4]).strip(),
                    })
                self._last_activity = time.time()
                return rows, None

        except Exception as e:
            logger.error(f"Fetch CDR: {e}")
            return None, str(e)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


panel  = PanelSession(
    base=PANEL_BASE, login_page=PANEL_LOGIN_PAGE, signin_url=PANEL_SIGNIN_URL,
    cdr_url=PANEL_CDR_URL, data_url=PANEL_DATA_URL,
    username=PANEL_USERNAME, password=PANEL_PASSWORD, name="sms hadi",
    wi_logged="logged_in", wi_login="login_errors", wi_last_login="last_login",
)
panel2 = PanelSession(
    base=PANEL2_BASE, login_page=PANEL2_LOGIN_PAGE, signin_url=PANEL2_SIGNIN_URL,
    cdr_url=PANEL2_CDR_URL, data_url=PANEL2_DATA_URL,
    username=PANEL2_USERNAME, password=PANEL2_PASSWORD, name="nigeria",
    wi_logged="logged_in_p2", wi_login="login_errors_p2", wi_last_login="last_login_p2",
)
panel3 = PanelSession(
    base=PANEL3_BASE, login_page=PANEL3_LOGIN_PAGE, signin_url=PANEL3_SIGNIN_URL,
    cdr_url=PANEL3_CDR_URL, data_url=PANEL3_DATA_URL,
    username=PANEL3_USERNAME, password=PANEL3_PASSWORD, name="konekta",
    wi_logged="logged_in_p3", wi_login="login_errors_p3", wi_last_login="last_login_p3",
)
panel4 = PanelSession(
    base=PANEL4_BASE, login_page=PANEL4_LOGIN_PAGE, signin_url=PANEL4_SIGNIN_URL,
    cdr_url=PANEL4_CDR_URL, data_url=PANEL4_DATA_URL,
    username=PANEL4_USERNAME, password=PANEL4_PASSWORD, name="zyron",
    wi_logged="logged_in_p4", wi_login="login_errors_p4", wi_last_login="last_login_p4",
)
PANELS = [panel4, panel, panel2, panel3]


async def _watch_membership(app, user_id):
    await asyncio.sleep(60)
    try:
        statuses   = await check_membership_per_channel(app.bot, user_id)
        all_joined = all(statuses.values())
        if not all_joined:
            try:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=JOIN_TEXT,
                    parse_mode=ParseMode.HTML,
                    reply_markup=join_gate_markup(statuses),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
    except Exception:
        pass


async def _panel_worker(app, p, wi_logged, wi_login, wi_last_login):
    last_reset_day = datetime.now().day
    while True:
        try:
            today = datetime.now().day
            if today != last_reset_day:
                worker_info["otps_today"] = 0
                last_reset_day = today

            if not p._logged_in:
                worker_info[wi_logged] = False
                if not p._can_attempt_login():
                    wait = p._login_backoff - (time.time() - p._last_login_try)
                    await asyncio.sleep(min(wait, POLL_INTERVAL))
                    continue

                ok = await p.login()
                if not ok:
                    if worker_info[wi_login] == 1:
                        await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ʟᴏɢɪɴ ꜰᴀɪʟᴇᴅ\n└─❏ ʀᴇᴛʀʏɪɴɢ ɪɴ {p._login_backoff}s")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                worker_info[wi_logged]     = True
                worker_info[wi_last_login] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ʟᴏɢɪɴ ᴏᴋ\n└─❏ ʟɪᴠᴇ")

                startup_rows, _ = await p.fetch_cdr()
                if startup_rows:
                    for r in startup_rows:
                        if not r.get("number") or not r.get("sms"):
                            continue
                        h = hashlib.md5(f"{r['date']}{r['number']}{r['sms']}".encode()).hexdigest()
                        otp_cache.add(h)
                    logger.info(f"[{p._name}] Startup cache: {len(startup_rows)} rows")
                continue

            await p._keepalive_ping()
            if not p._logged_in:
                continue

            rows, err = await p.fetch_cdr()

            if err == "session_expired":
                worker_info[wi_logged] = False
                await notify_admins(app, f"┌─ [{p._name}]\n├─❏ ꜱᴇꜱꜱɪᴏɴ ᴇxᴘɪʀᴇᴅ\n└─❏ ʀᴇʟᴏɢɢɪɴɢ...")
                await asyncio.sleep(10)
                continue

            if err:
                logger.warning(f"[{p._name}] Fetch CDR error: {err}")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if rows:
                logger.info(f"[{p._name}] Fetched {len(rows)} rows from panel")
                for row in rows:
                    try:
                        sms    = row.get("sms", "").strip()
                        number = row.get("number", "").strip()
                        date   = row.get("date", "").strip()
                        if not sms or not number:
                            continue
                        clean_num = re.sub(r"\D", "", number)
                        if not clean_num or len(clean_num) < 5:
                            continue
                        otp = extract_otp(sms)
                        if not otp:
                            logger.debug(f"[{p._name}] No OTP in: {sms[:60]}")
                            continue
                        h = hashlib.md5(f"{date}{number}{sms}".encode()).hexdigest()
                        if h in otp_cache:
                            continue
                        existing = await db_fetchone("SELECT id FROM otp_history WHERE hash=$1", h)
                        if existing:
                            otp_cache.add(h)
                            continue
                        logger.info(f"[{p._name}] New OTP: {mask_number(number)} | {otp} — sending")
                        text_msg, markup = format_otp_message(row, otp)
                        await app.bot.send_message(
                            chat_id=OTP_GROUP_ID,
                            text=text_msg,
                            parse_mode=ParseMode.HTML,
                            reply_markup=markup,
                            disable_web_page_preview=True,
                        )
                        otp_cache.add(h)
                        await db_execute(
                            "INSERT INTO otp_history (hash,number,otp,service,sms,range_name) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (hash) DO NOTHING",
                            h, number, otp, row.get("service",""), sms, row.get("range",""),
                        )
                        await db_execute(
                            "INSERT INTO traffic (range_name,number,sms,otp,service,received_at) VALUES ($1,$2,$3,$4,$5,$6)",
                            row.get("range",""), number, sms, otp, row.get("service",""), date,
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                        logger.info(f"[{p._name}] OTP sent -> group | {mask_number(number)} | {otp}")
                    except Exception as row_err:
                        logger.error(f"[{p._name}] Row error: {row_err}", exc_info=True)
                        continue
            else:
                logger.debug(f"[{p._name}] No rows returned")

            if len(otp_cache) > 50000:
                otp_cache.clear()
                recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
                for r in recent:
                    otp_cache.add(r["hash"])

            await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as e:
            worker_info["errors"] = worker_info.get("errors", 0) + 1
            logger.error(f"[{p._name}] Worker loop: {e}")
            await asyncio.sleep(15)


async def sms_worker(app):
    if worker_info["running"]:
        return
    worker_info["running"] = True
    await asyncio.gather(
        _panel_worker(app, panel,  "logged_in",    "login_errors",    "last_login"),
        _panel_worker(app, panel2, "logged_in_p2", "login_errors_p2", "last_login_p2"),
        _panel_worker(app, panel3, "logged_in_p3", "login_errors_p3", "last_login_p3"),
        _panel_worker(app, panel4, "logged_in_p4", "login_errors_p4", "last_login_p4"),
    )
    worker_info["running"] = False


JOIN_TEXT    = f"┌─ {BOT_NAME}\n├─❏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ\n└─❏ ᴛᴀᴘ ᴠᴇʀɪꜰʏ ᴡʜᴇɴ ᴅᴏɴᴇ"
WELCOME_TEXT = f"┌─ {BOT_NAME}\n├─❏ ʟɪᴠᴇ ᴏᴛᴘ ᴍᴏɴɪᴛᴏʀɪɴɢ 24/7\n└─❏"
ADMIN_TEXT   = f"┌─ {BOT_NAME}\n├─❏ ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴀᴅᴍɪɴ\n└─❏"
GET_NUM_TEXT = f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if await is_banned_user(user.id):
        await send_msg(context.bot, update.effective_chat.id, "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.")
        return
    if not is_admin(user.id):
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ꜱʟᴏᴡ ᴅᴏᴡɴ.")
            return
        if maintenance:
            await send_msg(context.bot, update.effective_chat.id, "ʙᴏᴛ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.")
            return
    statuses   = await check_membership_per_channel(context.bot, user.id)
    all_joined = all(statuses.values())
    if not all_joined:
        await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
        return
    welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=".",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_msg(context.bot, update.effective_chat.id, welcome, reply_markup=main_menu_markup(user.id))
    asyncio.create_task(_watch_membership(context.application, user.id))

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE.pop(update.effective_user.id, None)
    await send_msg(context.bot, update.effective_chat.id, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=main_menu_markup(update.effective_user.id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    if await is_banned_user(user.id) and data not in ("check_join",):
        await query.answer("ʙᴀɴɴᴇᴅ.", show_alert=True)
        return

    if data == "check_join":
        statuses   = await check_membership_per_channel(context.bot, user.id)
        all_joined = all(statuses.values())
        if all_joined:
            await register_user(user)
            welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
            asyncio.create_task(_watch_membership(context.application, user.id))
        else:
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            await query.answer("ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ꜰɪʀꜱᴛ.", show_alert=True)
        return

    if data.startswith("noop_joined__"):
        await query.answer("ᴀʟʀᴇᴀᴅʏ ᴊᴏɪɴᴇᴅ.", show_alert=False)
        return

    if data == "menu_back":
        statuses   = await check_membership_per_channel(context.bot, user.id)
        all_joined = all(statuses.values())
        if not all_joined:
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            return
        welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
        return


    if data == "menu_admin":
        if not is_admin(user.id):
            await query.answer("ᴀᴅᴍɪɴꜱ ᴏɴʟʏ.", show_alert=True)
            return
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "menu_live_traffic":
        total  = await db_fetchval("SELECT COUNT(*) FROM traffic") or 0
        recent = await db_fetchall("SELECT number, service, otp, received_at FROM traffic ORDER BY id DESC LIMIT 5")
        lines  = []
        for r in recent:
            lines.append(f"├─❏ {service_icon(r['service'] or '')} {mask_number(r['number'])} | {service_tag(r['service'] or '')} | <code>{r['otp']}</code>")

        body = "\n".join(lines) if lines else "├─❏ ɴᴏ ʀᴇᴄᴇɴᴛ ᴛʀᴀꜰꜰɪᴄ"
        text = f"┌─ ʟɪᴠᴇ ᴛʀᴀꜰꜰɪᴄ\n├─❏ ᴛᴏᴛᴀʟ ᴏᴛᴘꜱ : {total}\n{body}\n└─❏"
        await edit_msg(query, text, reply_markup=back_to_menu())
        return


    if data == "menu_stock":
        rows = await db_fetchall("SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE GROUP BY service ORDER BY cnt DESC")
        if not rows:
            await edit_msg(query, "┌─ ꜱᴛᴏᴄᴋ\n├─❏ ɴᴏ ꜱᴛᴏᴄᴋ ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏", reply_markup=back_to_menu())
            return
        lines = "\n".join(f"├─❏ {service_icon(r['service'])} {service_full_name(r['service'])} : {r['cnt']}" for r in rows)

        await edit_msg(query, f"┌─ ꜱᴛᴏᴄᴋ\n{lines}\n└─❏", reply_markup=back_to_menu())
        return


    if data == "menu_get_number":
        statuses   = await check_membership_per_channel(context.bot, user.id)
        all_joined = all(statuses.values())
        if not all_joined:
            await edit_msg(query, JOIN_TEXT, reply_markup=join_gate_markup(statuses))
            return
        if not is_admin(user.id) and maintenance:
            await query.answer("ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.", show_alert=True)
            return
        _, markup = await build_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ɴᴜᴍʙᴇʀꜱ\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀꜱ ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏", reply_markup=back_to_menu())
            return
        await edit_msg(query, GET_NUM_TEXT, reply_markup=markup)
        return

    if data.startswith("gns__"):
        service  = data[5:]
        _, markup = await build_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀꜱ.", show_alert=True)
            return
        await edit_msg(query, f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("gnc__"):
        parts   = data[5:].split("__", 1)
        country = parts[0]
        service = parts[1] if len(parts) > 1 else "All"

        wait = await check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT id, number, flag FROM numbers WHERE country=$1 AND service=$2 AND is_used=FALSE LIMIT 1 FOR UPDATE SKIP LOCKED",
                    country, service,
                )
                if not row:
                    await query.answer("ɴᴏ ɴᴜᴍʙᴇʀꜱ ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or ""

        if not is_admin(user.id):
            await set_number_cooldown(user.id)

        await edit_msg(query, number_display_text(number, country, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
        return

    if data.startswith("chgn__"):
        parts   = data.split("__")
        if len(parts) < 4:
            await query.answer("ɪɴᴠᴀʟɪᴅ.", show_alert=True)
            return
        old_id  = parts[-1]
        service = parts[-2]
        country = "__".join(parts[1:-2])

        wait = await check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return

        if old_id.isdigit():
            await db_execute(
                "UPDATE numbers SET is_used=FALSE, used_by=NULL, use_date=NULL WHERE id=$1 AND used_by=$2",
                int(old_id), user.id,
            )

        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT id, number, flag FROM numbers WHERE country=$1 AND service=$2 AND is_used=FALSE LIMIT 1 FOR UPDATE SKIP LOCKED",
                    country, service,
                )
                if not row:
                    await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀꜱ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or ""

        if not is_admin(user.id):
            await set_number_cooldown(user.id)

        await edit_msg(query, number_changed_text(number, country, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
        return

    if not is_admin(user.id):
        return

    if data == "adm_back":
        USER_STATE.pop(user.id, None)
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "adm_cancel_state":
        USER_STATE.pop(user.id, None)
        await edit_msg(query, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=admin_markup())
        return

    if data == "adm_broadcast":
        USER_STATE[user.id] = "ADM_BROADCAST_WAIT"
        await edit_msg(
            query,
            "┌─ ʙʀᴏᴀᴅᴄᴀꜱᴛ\n├─❏ ꜱᴇɴᴅ ᴀ ᴍᴇꜱꜱᴀɢᴇ ᴏʀ ᴘʜᴏᴛᴏ ᴛᴏ ꜰᴏʀᴡᴀʀᴅ ᴛᴏ ᴀʟʟ ᴜꜱᴇʀꜱ\n└─❏",
            reply_markup=cancel_state_markup("adm_back"),
        )
        return

    if data == "adm_status":
        await edit_msg(query, await status_text(), reply_markup=back_to_admin())
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_PICK_SERVICE"
        await edit_msg(query, "┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=service_picker_markup())
        return

    if data == "adm_delete_numbers":
        _, markup = await build_delete_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀꜱ ɪɴ ᴅʙ\n└─❏", reply_markup=back_to_admin())
            return
        await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʟᴇᴄᴛ ꜱᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_svc__"):
        service  = data[9:]
        _, markup = await build_delete_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏᴛʜɪɴɢ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        svc_label = sc(service) if service != "ALL" else "ᴀʟʟ"
        await edit_msg(query, f"┌─ ᴅᴇʟᴇᴛᴇ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {svc_label}\n├─❏ ꜱᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_cntry__"):
        parts   = data[11:].split("__", 1)
        service = parts[0]
        country = parts[1] if len(parts) > 1 else "ALL"

        if service == "ALL" and country == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers")
            await db_execute("DELETE FROM numbers")
        elif service == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE country=$1", country)
            await db_execute("DELETE FROM numbers WHERE country=$1", country)
        elif country == "ALL":
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE service=$1", service)
            await db_execute("DELETE FROM numbers WHERE service=$1", service)
        else:
            deleted = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE country=$1 AND service=$2", country, service)
            await db_execute("DELETE FROM numbers WHERE country=$1 AND service=$2", country, service)

        svc_label     = sc(service) if service != "ALL" else "ᴀʟʟ"
        country_label = sc(country) if country != "ALL" else "ᴀʟʟ"
        await edit_msg(
            query,
            f"┌─ ᴅᴇʟᴇᴛᴇᴅ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {svc_label}\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country_label}\n├─❏ ʀᴇᴍᴏᴠᴇᴅ : {deleted}\n└─❏",
            reply_markup=back_to_admin(),
        )
        return

    if data.startswith("adm_svc__"):
        service = data[9:]
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        await edit_msg(query, f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏꜱᴇ ᴍᴇᴛʜᴏᴅ\n└─❏", reply_markup=method_picker_markup())
        return

    if data == "adm_svc_custom":
        USER_STATE[user.id] = "ADM_CUSTOM_SVC"
        await edit_msg(query, "┌─ ᴄᴜꜱᴛᴏᴍ ꜱᴇʀᴠɪᴄᴇ\n├─❏ ꜱᴇɴᴅ ꜱᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏", reply_markup=cancel_state_markup("adm_add_numbers"))
        return

    if data == "adm_addmethod_file":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_PICK_METHOD__"):
            service = state[17:]
            USER_STATE[user.id] = f"WAITING_FILE__{service}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇɴᴅ ꜰɪʟᴇ (.ᴛxᴛ .ᴄꜱᴠ .xʟꜱx .xʟꜱ)\n└─❏ ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛꜱ ᴄᴏᴜɴᴛʀʏ",
                reply_markup=cancel_state_markup("adm_add_numbers"),
            )
        return

    if data == "adm_addmethod_type":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_PICK_METHOD__"):
            service = state[17:]
            USER_STATE[user.id] = f"TYPING_NUMBERS__{service}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜱᴇɴᴅ ɴᴜᴍʙᴇʀꜱ, ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ\n└─❏ ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛꜱ ᴄᴏᴜɴᴛʀʏ",
                reply_markup=cancel_state_markup("adm_add_numbers"),
            )
        return


async def _insert_numbers_bulk(service: str, result: dict):
    total_added = 0
    total_dupes = 0
    by_country  = {}

    pool = await get_pool()
    async with pool.acquire() as conn:
        for iso, v in result["groups"].items():
            country   = v["name"]
            flag      = v["flag"]
            added_for = []
            for num in v["numbers"]:
                r = await conn.execute(
                    "INSERT INTO numbers (country,flag,number,service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                    country, flag, num, service,
                )
                if r == "INSERT 0 1":
                    total_added += 1
                    added_for.append(num)
                else:
                    total_dupes += 1
            if added_for:
                by_country[iso] = {"name": country, "flag": flag, "numbers": added_for}

        for num in result["unknown"]:
            r = await conn.execute(
                "INSERT INTO numbers (country,flag,number,service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                "Unknown", "", num, service,
            )
            if r == "INSERT 0 1":
                total_added += 1
            else:
                total_dupes += 1

    return total_added, total_dupes, by_country


async def _do_broadcast(app, text=None, photo=None, caption=None):
    rows = await db_fetchall("SELECT user_id FROM users WHERE is_banned=FALSE")
    sent = 0
    failed = 0
    for r in rows:
        uid = r["user_id"]
        try:
            if photo:
                await app.bot.send_photo(chat_id=uid, photo=photo, caption=caption or "", parse_mode=ParseMode.HTML)
            else:
                await app.bot.send_message(chat_id=uid, text=text or "", parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1
    return sent, failed


async def photo_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if USER_STATE.get(user.id) != "ADM_BROADCAST_WAIT":
        return
    USER_STATE.pop(user.id, None)
    photo   = update.message.photo[-1].file_id
    caption = (update.message.caption or "").strip()
    sent, failed = await _do_broadcast(context.application, text=None, photo=photo, caption=caption)
    await send_msg(
        context.bot, update.effective_chat.id,
        f"┌─ ʙʀᴏᴀᴅᴄᴀꜱᴛ ꜱᴇɴᴛ\n├─❏ ᴅᴇʟɪᴠᴇʀᴇᴅ : {sent}\n├─❏ ꜰᴀɪʟᴇᴅ    : {failed}\n└─❏",
        reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
    )



async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()

    if not is_admin(user.id):
        if await is_banned_user(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ʙᴀɴɴᴇᴅ.")
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ꜱʟᴏᴡ ᴅᴏᴡɴ.")
            return
        return

    state = USER_STATE.get(user.id)
    if not state:
        return

    if state == "ADM_BROADCAST_WAIT":
        USER_STATE.pop(user.id, None)
        sent, failed = await _do_broadcast(context.application, text=text, photo=None, caption=None)
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ʙʀᴏᴀᴅᴄᴀꜱᴛ ꜱᴇɴᴛ\n├─❏ ᴅᴇʟɪᴠᴇʀᴇᴅ : {sent}\n├─❏ ꜰᴀɪʟᴇᴅ    : {failed}\n└─❏",
            reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
        )
        return

    if state == "ADM_CUSTOM_SVC":
        service = text.strip()
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀꜱ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏꜱᴇ ᴍᴇᴛʜᴏᴅ\n└─❏",
            reply_markup=method_picker_markup(),
        )
        return

    if state.startswith("TYPING_NUMBERS__"):
        service = state[16:]
        lines   = [re.sub(r"\D", "", line) for line in text.splitlines()]
        lines   = [n for n in lines if 7 <= len(n) <= 15]
        raw     = "\n".join(lines).encode("utf-8")
        loop    = asyncio.get_event_loop()
        result  = await loop.run_in_executor(None, extract_numbers_smart, raw, "numbers.txt")
        status_msg = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇꜱꜱɪɴɢ...")

        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)
        USER_STATE.pop(user.id, None)

        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}" for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇꜱ ᴅᴇᴛᴇᴄᴛᴇᴅ"

        result_text = (
            f"┌─ ᴅᴏɴᴇ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n"
            f"├─❏ ᴀᴅᴅᴇᴅ   : {total_added}\n├─❏ ᴅᴜᴘᴇꜱ   : {total_dupes}\n"
            f"{countries_summary}\n└─❏"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=result_text,
                parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            await send_msg(context.bot, update.effective_chat.id, result_text, reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]))

        for v in by_country.values():
            asyncio.create_task(broadcast_stock(context.application, v["name"], v["flag"], service, len(v["numbers"]), v["numbers"]))
        return


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    if not is_admin(user.id):
        return
    state = USER_STATE.get(user.id)
    if not state or not state.startswith("WAITING_FILE__"):
        return
    service = state[14:]
    doc     = update.message.document
    name    = doc.file_name or "file.txt"
    ext     = name.lower().rsplit(".", 1)[-1]
    if ext not in ("txt", "csv", "xlsx", "xls"):
        await send_msg(context.bot, update.effective_chat.id, "ɪɴᴠᴀʟɪᴅ ꜰɪʟᴇ. ᴜꜱᴇ .ᴛxᴛ .ᴄꜱᴠ .xʟꜱx .xʟꜱ")
        return

    status_msg = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇꜱꜱɪɴɢ...")
    USER_STATE.pop(user.id, None)

    try:
        f       = await doc.get_file()
        content = bytes(await f.download_as_bytearray())
        loop    = asyncio.get_event_loop()
        result  = await loop.run_in_executor(None, extract_numbers_smart, content, name)

        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)

        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}" for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇꜱ ᴅᴇᴛᴇᴄᴛᴇᴅ"

        result_text = (
            f"┌─ ᴅᴏɴᴇ\n├─❏ ꜱᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ꜰɪʟᴇ    : {name}\n"
            f"├─❏ ᴛᴏᴛᴀʟ   : {result['total']}\n├─❏ ᴀᴅᴅᴇᴅ   : {total_added}\n"
            f"├─❏ ᴅᴜᴘᴇꜱ   : {total_dupes}\n{countries_summary}\n└─❏"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=result_text,
                parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            await send_msg(context.bot, update.effective_chat.id, result_text, reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]))

        for v in by_country.values():
            asyncio.create_task(broadcast_stock(context.application, v["name"], v["flag"], service, len(v["numbers"]), v["numbers"]))

    except Exception as e:
        logger.error(f"Document handler: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="ᴇʀʀᴏʀ ᴘʀᴏᴄᴇꜱꜱɪɴɢ ꜰɪʟᴇ.",
                parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            pass


async def health_handler(request):
    return web.Response(
        text=json.dumps({
            "status":       "ok",
            "bot":          BOT_NAME,
            "worker":       worker_info["running"],
            "logged_in":    worker_info["logged_in"],
            "otps_today":   worker_info["otps_today"],
            "last_otp":     worker_info["last_otp"],
            "login_errors": worker_info["login_errors"],
        }),
        content_type="application/json",
        status=200,
    )


async def post_init(application):
    global maintenance
    await init_db()

    saved_maint = await get_setting("maintenance")
    if saved_maint == "1":
        maintenance = True

    extra = await get_setting("extra_admins")
    if extra:
        for eid in extra.split(","):
            eid = eid.strip()
            if eid.isdigit():
                aid = int(eid)
                if aid not in ADMIN_IDS:
                    ADMIN_IDS.append(aid)

    recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
    for r in recent:
        otp_cache.add(r["hash"])
    logger.info(f"OTP cache: {len(otp_cache)} hashes")

    await application.bot.set_my_commands([
        BotCommand("start",  "start"),
        BotCommand("cancel", "cancel"),
    ])

    app_web = web.Application()
    app_web.router.add_get("/",       health_handler)
    app_web.router.add_get("/health", health_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Health on :{PORT}")

    asyncio.get_event_loop().create_task(sms_worker(application))
    logger.info(f"{BOT_NAME} live")


if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    application.add_handler(CommandHandler("start",  start))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_input_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))

    logger.info(f"Starting {BOT_NAME}...")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
