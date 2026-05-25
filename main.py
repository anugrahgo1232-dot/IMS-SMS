import os
import io
import logging
import time
import re
import hashlib
import asyncio
import json
import aiohttp
import phonenumbers
import pycountry
import pandas as pd
from phonenumbers import region_code_for_number
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
from aiohttp import web
import asyncpg

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputFile,
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

BOT_TOKEN           = "8313925262:AAFBgY13zTdARtEuWuIdFp8-rKac6DopNjU"
BOT_NAME            = "ᴍʀ.ᴀғʀɪx"
BOT_USERNAME        = "mrafrix_bot"
BOT_LINK            = "https://t.me/mrafrix_bot"
BASE_ADMIN_IDS      = [8339856952, 6524840104]

PANEL_BASE          = "https://imssms.org"
PANEL_LOGIN_PAGE    = f"{PANEL_BASE}/login"
PANEL_SIGNIN_URL    = f"{PANEL_BASE}/signin"
PANEL_CDR_URL       = f"{PANEL_BASE}/client/SMSCDRStats"
PANEL_DASHBOARD_URL = f"{PANEL_BASE}/client/SMSDashboard"
PANEL_DATA_URL      = f"{PANEL_BASE}/client/res/data_smscdr.php"
PANEL_USERNAME      = "jadendev"
PANEL_PASSWORD      = "jadendev"

MAIN_CHANNEL        = "@sage_xd"
MAIN_CHANNEL_LINK   = "https://t.me/sage_xd"
BACKUP_CHANNEL      = "@mr_afrix"
BACKUP_CHANNEL_LINK = "https://t.me/mr_afrix"
THIRD_CHANNEL       = "@oxellabs"
THIRD_CHANNEL_LINK  = "https://t.me/oxellabs"
FOURTH_CHANNEL      = "@oracron"
FOURTH_CHANNEL_LINK = "https://t.me/oracron"
OTP_GROUP_LINK      = "https://t.me/afrixotpgc"
OTP_GROUP_ID        = -1003053441379
FORCE_CHANNELS      = ["@sage_xd", "@mr_afrix", "@oxellabs", "@oracron"]

STOCK_NOTIFY_CHANNEL_ID = -1002506491665

DATABASE_URL     = "postgresql://neondb_owner:npg_ocasy6rIX2vR@ep-cold-darkness-ak558puk.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require"
PORT             = int(os.environ.get("PORT", 8080))
POLL_INTERVAL    = 5
KEEPALIVE_INTERVAL = 60
FLOOD_LIMIT      = 5
FLOOD_WINDOW     = 10
NUMBER_COOLDOWN  = 30

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

USER_STATE  = {}
flood_data  = {}
otp_cache   = set()
maintenance = False
ADMIN_IDS   = list(BASE_ADMIN_IDS)

worker_info = {
    "running":    False,
    "logged_in":  False,
    "last_otp":   "—",
    "otps_today": 0,
    "last_login": "—",
    "errors":     0,
    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

CHANNEL_LABELS = {
    "@sage_xd":  ("sᴀɢᴇ",    MAIN_CHANNEL_LINK),
    "@mr_afrix": ("ᴍʀᴀғʀɪx",  BACKUP_CHANNEL_LINK),
    "@oxellabs": ("ᴏxᴇʟʟᴀʙs", THIRD_CHANNEL_LINK),
    "@oracron":  ("ᴏʀᴀᴄʀᴏɴ",  FOURTH_CHANNEL_LINK),
}

DEFAULT_SERVICES = [
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Google",
    "TikTok", "Twitter/X", "Snapchat", "Discord", "Line",
    "WeChat", "Viber", "Signal", "Binance", "Bybit",
    "OKX", "Bitget", "Coinbase", "Kraken", "Other",
]

_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘqʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘqʀꜱᴛᴜᴠᴡxʏᴢ"
)

def sc(t: str) -> str:
    return t.translate(_SC)

def iso_to_flag(iso: str) -> str:
    try:
        return "".join(chr(ord(c) + 127397) for c in iso.upper()[:2])
    except Exception:
        return "🌐"

def iso_to_name(iso: str) -> str:
    try:
        return pycountry.countries.get(alpha_2=iso).name
    except Exception:
        return iso

def btn(text, *, cb=None, url=None, style=None):
    kwargs = {}
    if url is not None:
        kwargs["url"] = url
    elif cb is not None:
        kwargs["callback_data"] = cb
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(text, **kwargs)

def mk(rows):
    return InlineKeyboardMarkup(rows)

_db_pool = None
_db_lock = None

async def get_pool():
    global _db_pool, _db_lock
    if _db_lock is None:
        _db_lock = asyncio.Lock()
    if _db_pool is not None:
        return _db_pool
    async with _db_lock:
        if _db_pool is None:
            _db_pool = await asyncpg.create_pool(
                DATABASE_URL, min_size=2, max_size=10, command_timeout=30,
            )
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
                flag     TEXT    DEFAULT '🌐',
                number   TEXT    NOT NULL UNIQUE,
                service  TEXT    DEFAULT 'All',
                is_used  BOOLEAN DEFAULT FALSE,
                used_by  BIGINT  DEFAULT NULL,
                use_date TIMESTAMP DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id BIGINT PRIMARY KEY,
                ts      BIGINT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_otp_hash     ON otp_history(hash);
            CREATE INDEX IF NOT EXISTS idx_otp_added    ON otp_history(added_at);
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
            CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
            CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
            CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
        """)
    logger.info("Database initialised")

async def get_setting(key, default=""):
    row = await db_fetchone("SELECT value FROM settings WHERE key=$1", key)
    return row["value"] if row else default

async def set_setting(key, value):
    await db_execute(
        "INSERT INTO settings (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        key, value,
    )

def parse_phone(raw: str):
    clean = re.sub(r"\D", "", str(raw))
    if not (7 <= len(clean) <= 15):
        return None, None, None
    try:
        p   = phonenumbers.parse("+" + clean)
        iso = region_code_for_number(p)
        if not iso:
            return clean, "Unknown", "🌐"
        return clean, iso_to_name(iso), iso_to_flag(iso)
    except Exception:
        return clean, "Unknown", "🌐"

def get_country_info(number):
    _, name, flag = parse_phone(re.sub(r"\D", "", str(number)))
    return name or "Unknown", flag or "🌐"

def mask_number(number):
    clean = re.sub(r"\D", "", str(number))
    if len(clean) >= 9:
        return f"+{clean[:5]}····{clean[-3:]}"
    if len(clean) >= 6:
        return f"+{clean[:3]}···{clean[-3:]}"
    return f"+{clean}···"

def extract_otp(sms):
    if not sms:
        return None
    for pattern in (r"\b\d{3}[-\s]\d{3}\b", r"\b\d{6,8}\b", r"\b\d{4,5}\b"):
        m = re.search(pattern, sms)
        if m:
            return m.group().strip()
    return None

def detect_number_column(df: pd.DataFrame) -> str:
    priority = {"number", "phone", "phone number", "msisdn", "mobile", "tel", "telephone", "num", "numbers"}
    for col in df.columns:
        if col.strip().lower() in priority:
            return col
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(20)
        ratio  = sample.str.replace(r"\D", "", regex=True).str.len().between(7, 15).mean()
        if ratio >= 0.5:
            return col
    return df.columns[0]

def load_numbers_file(data: bytes, filename: str) -> list:
    nums = []
    try:
        name = filename.lower()
        if name.endswith(".xlsx"):
            df  = pd.read_excel(BytesIO(data), engine="openpyxl")
            col = detect_number_column(df)
            raw = df[col].dropna().astype(str).tolist()
        elif name.endswith(".xls"):
            df  = pd.read_excel(BytesIO(data), engine="xlrd")
            col = detect_number_column(df)
            raw = df[col].dropna().astype(str).tolist()
        elif name.endswith(".csv"):
            df  = pd.read_csv(BytesIO(data))
            col = detect_number_column(df)
            raw = df[col].dropna().astype(str).tolist()
        else:
            raw = data.decode("utf-8", errors="ignore").splitlines()
        for r in raw:
            clean = re.sub(r"\D", "", r.strip())
            if 7 <= len(clean) <= 15:
                nums.append(clean)
    except Exception as e:
        logger.error(f"File load error: {e}")
    return nums

def _process_numbers_sync(data: bytes, filename: str) -> dict:
    nums   = load_numbers_file(data, filename)
    seen   = set()
    groups = {}
    dupes  = 0
    for raw in nums:
        clean = re.sub(r"\D", "", raw)
        if not (7 <= len(clean) <= 15):
            continue
        if clean in seen:
            dupes += 1
            continue
        seen.add(clean)
        _, cname, flag = parse_phone(clean)
        key = cname or "Unknown"
        if key not in groups:
            groups[key] = {"flag": flag or "🌐", "numbers": []}
        groups[key]["numbers"].append(clean)
    return {"groups": groups, "dupes": dupes, "total": len(nums)}

async def process_numbers_async(data: bytes, filename: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _process_numbers_sync, data, filename)

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
        "INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) "
        "ON CONFLICT (user_id) DO UPDATE SET username=$2, first_name=$3",
        user.id, user.username or "", user.first_name or "",
    )

async def is_banned(user_id):
    row = await db_fetchone("SELECT is_banned FROM users WHERE user_id=$1", user_id)
    return bool(row and row["is_banned"])

async def check_membership(bot, user_id):
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
        "INSERT INTO cooldowns (user_id, ts) VALUES ($1, $2) "
        "ON CONFLICT (user_id) DO UPDATE SET ts=$2",
        user_id, int(time.time()),
    )

async def get_monthly_users():
    now            = datetime.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return await db_fetchval(
        "SELECT COUNT(*) FROM users WHERE joined_at >= $1 AND is_banned=FALSE",
        first_of_month,
    ) or 0

def join_markup_dynamic(statuses):
    rows = []
    pair = []
    for channel, (label, link) in CHANNEL_LABELS.items():
        joined = statuses.get(channel, False)
        if joined:
            b = btn(label, cb=f"joined_noop__{channel}", style="primary")
        else:
            b = btn(label, url=link, style="danger")
        pair.append(b)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([btn("ᴠᴇʀɪғʏ", cb="check_join", style="success")])
    return mk(rows)

async def main_menu_markup(bot, user_id=None):
    rows = [[btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", cb="menu_get_number", style="success")]]
    if user_id:
        statuses = await check_membership_per_channel(bot, user_id)
        unjoined = [
            (label, link)
            for channel, (label, link) in CHANNEL_LABELS.items()
            if not statuses.get(channel, False)
        ]
        pair = []
        for label, link in unjoined:
            pair.append(btn(label, url=link, style="danger"))
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
    rows.append([btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary")])
    if user_id and is_admin(user_id):
        rows.append([btn("ᴀᴅᴍɪɴ", cb="menu_admin", style="danger")])
    return mk(rows)

def otp_markup():
    return mk([
        [btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,           style="success"),
         btn("ᴍʀᴀғʀɪx",     url=BACKUP_CHANNEL_LINK, style="primary")],
        [btn("ᴏxᴇʟʟᴀʙs",    url=THIRD_CHANNEL_LINK,  style="primary"),
         btn("ᴏʀᴀᴄʀᴏɴ",     url=FOURTH_CHANNEL_LINK, style="primary")],
        [btn("sᴀɢᴇ",         url=MAIN_CHANNEL_LINK,   style="primary")],
    ])

def stock_notification_markup():
    return mk([
        [btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,      style="success"),
         btn("ᴏᴛᴘ ɢʀᴏᴜᴘ",   url=OTP_GROUP_LINK, style="primary")],
    ])

def number_assigned_markup(country, service, num_id):
    return mk([
        [btn("ᴄʜᴀɴɢᴇ ɴᴜᴍʙᴇʀ", cb=f"chgn__{country}__{service}__{num_id}", style="primary")],
        [btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK, style="primary"),
         btn("ʙᴀᴄᴋ",       cb="menu_back",      style="danger")],
    ])

def admin_markup():
    return mk([
        [btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀs",    cb="adm_numbers",        style="success"),
         btn("ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs", cb="adm_delete_numbers", style="danger")],
        [btn("sᴛᴀᴛᴜs", cb="adm_status",  style="primary")],
        [btn("ʙᴀᴄᴋ",   cb="menu_back",   style="danger")],
    ])

def back_to_menu():
    return mk([[btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")]])

def back_to_admin():
    return mk([[btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]])

def cancel_state_markup(back_cb="adm_back"):
    return mk([[
        btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger"),
        btn("ʙᴀᴄᴋ",   cb=back_cb,             style="danger"),
    ]])

def numbers_markup():
    return mk([
        [btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀs", cb="adm_add_numbers", style="success")],
        [btn("ʙᴀᴄᴋ",         cb="adm_back",         style="danger")],
    ])

async def build_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    pair    = []
    for r in rows:
        pair.append(btn(sc(r["service"]), cb=f"gns__{r['service']}", style="success"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)
    buttons.append([btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")])
    return rows, mk(buttons)

async def build_country_grid_for_service(service):
    rows = await db_fetchall(
        "SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE is_used=FALSE AND service=$1 "
        "GROUP BY country, flag ORDER BY country",
        service,
    )
    if not rows:
        return None, None
    buttons = []
    pair    = []
    for r in rows:
        pair.append(btn(f"{r['flag']} {sc(r['country'])}", cb=f"gnc__{r['country']}__{service}", style="primary"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)
    buttons.append([btn("ʙᴀᴄᴋ", cb=f"gns__{service}", style="danger")])
    return rows, mk(buttons)

async def build_delete_service_grid():
    rows = await db_fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    pair    = []
    for r in rows:
        pair.append(btn(sc(r["service"]), cb=f"del_svc__{r['service']}", style="danger"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)
    buttons.append([btn("ᴀʟʟ sᴇʀᴠɪᴄᴇs", cb="del_svc__ALL", style="danger")])
    buttons.append([btn("ʙᴀᴄᴋ",           cb="adm_back",     style="danger")])
    return rows, mk(buttons)

async def build_delete_country_grid(service):
    if service == "ALL":
        rows = await db_fetchall(
            "SELECT country, flag, COUNT(*) AS cnt FROM numbers GROUP BY country, flag ORDER BY country"
        )
    else:
        rows = await db_fetchall(
            "SELECT country, flag, COUNT(*) AS cnt FROM numbers WHERE service=$1 "
            "GROUP BY country, flag ORDER BY country",
            service,
        )
    if not rows:
        return None, None
    buttons = []
    pair    = []
    for r in rows:
        pair.append(btn(f"{r['flag']} {sc(r['country'])}", cb=f"del_cntry__{service}__{r['country']}", style="danger"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)
    buttons.append([btn("ᴀʟʟ ᴄᴏᴜɴᴛʀɪᴇs", cb=f"del_cntry__{service}__ALL", style="danger")])
    buttons.append([btn("ʙᴀᴄᴋ",            cb="adm_delete_numbers",         style="danger")])
    return rows, mk(buttons)

def service_picker_markup():
    buttons = []
    pair    = []
    for svc in DEFAULT_SERVICES:
        pair.append(btn(sc(svc), cb=f"adm_svc__{svc}", style="primary"))
        if len(pair) == 2:
            buttons.append(pair)
            pair = []
    if pair:
        buttons.append(pair)
    buttons.append([btn("ᴄᴜsᴛᴏᴍ", cb="adm_svc_custom",    style="success")])
    buttons.append([btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state", style="danger")])
    return mk(buttons)

async def send_msg(bot, chat_id, text, reply_markup=None):
    return await bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )

async def edit_msg(query, text, reply_markup=None):
    try:
        await query.edit_message_text(
            text=text, parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except Exception:
        pass

async def notify_admins(app, text):
    for aid in ADMIN_IDS:
        try:
            await app.bot.send_message(
                chat_id=aid, text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

async def broadcast_stock_notification(app, groups: dict):
    markup = stock_notification_markup()
    for country, data in groups.items():
        flag       = data["flag"]
        service    = data["service"]
        nums       = data["numbers"]
        filename   = f"{flag} {country} — {sc(service)}.txt".replace("/", "-")
        file_bytes = "\n".join(nums).encode("utf-8")
        caption    = (
            f"┌─ ɴᴇᴡ sᴛᴏᴄᴋ ᴀᴅᴅᴇᴅ\n"
            f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country)}\n"
            f"├─❏ sᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
            f"├─❏ ɴᴜᴍʙᴇʀs  : {len(nums)}\n"
            f"└─❏"
        )
        for target in [MAIN_CHANNEL, STOCK_NOTIFY_CHANNEL_ID]:
            try:
                await app.bot.send_document(
                    chat_id=target,
                    document=InputFile(BytesIO(file_bytes), filename=filename),
                    caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup,
                )
            except Exception as e:
                logger.error(f"Channel notification error ({target}): {e}")
        await asyncio.sleep(0.5)
        all_users = await db_fetchall("SELECT user_id FROM users WHERE is_banned=FALSE")
        for row in all_users:
            if row["user_id"] in ADMIN_IDS:
                continue
            try:
                await app.bot.send_document(
                    chat_id=row["user_id"],
                    document=InputFile(BytesIO(file_bytes), filename=filename),
                    caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup,
                )
                await asyncio.sleep(0.04)
            except Exception:
                pass
        await asyncio.sleep(1)

def format_otp_message(row, otp):
    masked             = mask_number(row["number"])
    country_name, flag = get_country_info(row["number"])
    sms_txt            = (row.get("sms") or "").strip()
    service            = sc((row.get("service") or "Unknown").strip())
    text = (
        f"┌─ ➪ ɴᴇᴡ ᴏᴛᴘ ʀᴇᴄᴇɪᴠᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{masked}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {service}\n"
        f"├─❏ ᴏᴛᴘ      : <code>{otp}</code>\n"
        f"├─❏ sᴍs      : <blockquote>{sms_txt}</blockquote>\n"
        f"└─❏"
    )
    return text, otp_markup()

def solve_captcha(html):
    try:
        soup      = BeautifulSoup(html, "html.parser")
        full_text = soup.get_text(" ", strip=True)
        m = re.search(r"[Ww]hat\s+is\s+(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*[=?]", full_text)
        if not m:
            for tag in soup.find_all(True):
                m = re.search(r"(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*=\s*\?", tag.get_text(strip=True))
                if m:
                    break
        if m:
            a, op, b = int(m.group(1)), m.group(2).strip(), int(m.group(3))
            if op == "+":                    return str(a + b)
            if op == "-":                    return str(a - b)
            if op in ("*", "×", "x", "X"): return str(a * b)
            if op in ("÷", "/") and b != 0: return str(a // b)
    except Exception as e:
        logger.error(f"Captcha solve error: {e}")
    return "0"

class PanelSession:
    def __init__(self):
        self._session        = None
        self._logged_in      = False
        self._sesskey        = ""
        self._login_attempts = 0
        self._next_login_at  = 0
        self._last_activity  = 0

    async def _get_session(self):
        if self._session is None or self._session.closed:
            connector     = aiohttp.TCPConnector(ssl=True, limit=10, ttl_dns_cache=300, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"
                    ),
                    "Accept-Language":           "en-CI,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control":             "max-age=0",
                },
                timeout=aiohttp.ClientTimeout(total=60, connect=20),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
        return self._session

    async def login(self):
        now = time.time()
        if now < self._next_login_at:
            return False
        try:
            sess = await self._get_session()
            try:
                async with sess.get(
                    PANEL_LOGIN_PAGE, allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    login_html = await resp.text(errors="replace")
                    if "login" not in str(resp.url).lower() and resp.status == 200:
                        self._logged_in      = True
                        self._login_attempts = 0
                        self._next_login_at  = 0
                        self._last_activity  = time.time()
                        await self._fetch_sesskey(sess)
                        return True
            except Exception as e:
                logger.error(f"Login page fetch error: {e}")
                return False

            if not login_html:
                return False

            soup     = BeautifulSoup(login_html, "html.parser")
            etkk     = ""
            etkk_inp = soup.find("input", {"name": "etkk"})
            if etkk_inp:
                etkk = etkk_inp.get("value", "")
            if not etkk:
                for pat in (
                    r'name=["\']etkk["\'][^>]*value=["\']([^"\']+)["\']',
                    r'value=["\']([^"\']+)["\'][^>]*name=["\']etkk["\']',
                ):
                    m = re.search(pat, login_html)
                    if m:
                        etkk = m.group(1)
                        break

            capt      = solve_captcha(login_html)
            form_data = aiohttp.FormData()
            if etkk:
                form_data.add_field("etkk", etkk)
            form_data.add_field("username", PANEL_USERNAME)
            form_data.add_field("password", PANEL_PASSWORD)
            form_data.add_field("capt",     capt)

            async with sess.post(
                PANEL_SIGNIN_URL, data=form_data,
                headers={
                    "Referer":        PANEL_LOGIN_PAGE,
                    "Origin":         PANEL_BASE,
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-User": "?1",
                    "Sec-Fetch-Dest": "document",
                },
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                location = resp.headers.get("Location", "")
                if resp.status == 302 and "login" not in location.lower():
                    if location.startswith("http"):
                        redirect_url = location
                    elif location.startswith("/"):
                        redirect_url = f"{PANEL_BASE}{location}"
                    else:
                        redirect_url = PANEL_BASE + "/"
                    try:
                        async with sess.get(
                            redirect_url, allow_redirects=True,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as redir_resp:
                            if "login" in str(redir_resp.url).lower():
                                return False
                    except Exception as e:
                        logger.warning(f"Post-login redirect warning: {e}")

                    self._logged_in      = True
                    self._login_attempts = 0
                    self._next_login_at  = 0
                    self._last_activity  = time.time()
                    await self._fetch_sesskey(sess)
                    return True

                self._login_attempts += 1
                self._next_login_at   = time.time() + min(30 * (2 ** (self._login_attempts - 1)), 1800)
                return False

        except Exception as e:
            logger.error(f"Login exception: {e}")
            self._login_attempts += 1
            self._next_login_at   = time.time() + min(30 * (2 ** (self._login_attempts - 1)), 1800)
            return False

    async def _fetch_sesskey(self, sess):
        try:
            async with sess.get(
                PANEL_CDR_URL, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if "login" in str(resp.url).lower():
                    return
                html = await resp.text(errors="replace")
                for pat in (
                    r'["\']sesskey["\']\s*[,:=]\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'var\s+sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                ):
                    m = re.search(pat, html)
                    if m:
                        self._sesskey = m.group(1)
                        return
        except Exception as e:
            logger.error(f"sesskey fetch error: {e}")

    async def keepalive(self):
        try:
            sess = await self._get_session()
            async with sess.get(
                PANEL_DASHBOARD_URL, allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if "login" in str(resp.url).lower():
                    self._logged_in = False
                    return False
                self._last_activity = time.time()
                return True
        except Exception as e:
            logger.error(f"Keepalive error: {e}")
            return False

    async def fetch_cdr(self):
        try:
            sess = await self._get_session()
            now  = datetime.now()
            params = {
                "fdate1":         now.strftime("%Y-%m-%d 00:00:00"),
                "fdate2":         now.strftime("%Y-%m-%d 23:59:59"),
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
                "sColumns":       ".......",
                "iDisplayStart":  "0",
                "iDisplayLength": "25",
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
                PANEL_DATA_URL, params=params,
                headers={
                    "Referer":          PANEL_CDR_URL,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept":           "application/json, text/javascript, */*; q=0.01",
                    "Sec-Fetch-Dest":   "empty",
                    "Sec-Fetch-Mode":   "cors",
                    "Sec-Fetch-Site":   "same-origin",
                },
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if "login" in str(resp.url).lower():
                    self._logged_in = False
                    return None, "session_expired"
                text = await resp.text(errors="replace")
                if not text.strip():
                    return None, "empty_response"
                try:
                    data = json.loads(text)
                except Exception:
                    if "login" in text.lower() and len(text) < 5000:
                        self._logged_in = False
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
            logger.error(f"Fetch CDR error: {e}")
            return None, str(e)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

panel = PanelSession()

async def sms_worker(app):
    if worker_info["running"]:
        return
    worker_info["running"] = True
    keepalive_timer        = 0
    last_reset_day         = datetime.now().day

    while True:
        try:
            today = datetime.now().day
            if today != last_reset_day:
                worker_info["otps_today"] = 0
                last_reset_day            = today

            if not panel._logged_in:
                worker_info["logged_in"] = False
                if time.time() < panel._next_login_at:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                ok = await panel.login()
                if not ok:
                    worker_info["errors"] += 1
                    if panel._login_attempts == 1:
                        await notify_admins(
                            app,
                            f"┌─ ʟᴏɢɪɴ ғᴀɪʟᴇᴅ\n"
                            f"├─❏ ᴘᴀɴᴇʟ : imssms.org\n"
                            f"├─❏ ᴀᴛᴛᴇᴍᴘᴛ : #{panel._login_attempts}\n"
                            f"└─❏ ʀᴇᴛʀʏɪɴɢ...",
                        )
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                worker_info["logged_in"]  = True
                worker_info["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worker_info["errors"]     = 0
                await notify_admins(
                    app,
                    f"┌─ ɪᴍs ʟᴏɢɪɴ\n"
                    f"├─❏ sᴛᴀᴛᴜs : ᴏɴʟɪɴᴇ\n"
                    f"├─❏ ᴘᴀɴᴇʟ : imssms.org\n"
                    f"├─❏ ᴜsᴇʀ : {PANEL_USERNAME}\n"
                    f"├─❏ ᴛɪᴍᴇ : {worker_info['last_login']}\n"
                    f"└─❏ {BOT_NAME} ɪs ʟɪᴠᴇ",
                )
                startup_rows, _ = await panel.fetch_cdr()
                if startup_rows:
                    for r in startup_rows:
                        h = hashlib.md5(f"{r['date']}{r['number']}{r['sms']}".encode()).hexdigest()
                        otp_cache.add(h)
                continue

            keepalive_timer += POLL_INTERVAL
            if keepalive_timer >= KEEPALIVE_INTERVAL:
                if time.time() - panel._last_activity >= KEEPALIVE_INTERVAL:
                    await panel.keepalive()
                keepalive_timer = 0

            rows, err = await panel.fetch_cdr()

            if err == "session_expired":
                panel._logged_in         = False
                worker_info["logged_in"] = False
                await notify_admins(app, "┌─ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ\n├─❏ ʀᴇ-ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛɪɴɢ...\n└─❏")
                await asyncio.sleep(10)
                continue

            if err:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if rows:
                for row in rows:
                    try:
                        sms    = row.get("sms", "").strip()
                        number = row.get("number", "").strip()
                        date   = row.get("date", "").strip()
                        if not sms or not number:
                            continue
                        if not re.sub(r"[Xx\s\-_*]", "", sms):
                            continue
                        otp = extract_otp(sms)
                        if not otp:
                            continue
                        h = hashlib.md5(f"{date}{number}{sms}".encode()).hexdigest()
                        if h in otp_cache:
                            continue
                        existing = await db_fetchone("SELECT id FROM otp_history WHERE hash=$1", h)
                        if existing:
                            otp_cache.add(h)
                            continue
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
                            "INSERT INTO otp_history (hash, number, otp, service, sms, range_name) "
                            "VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (hash) DO NOTHING",
                            h, number, otp, row.get("service", ""), sms, row.get("range", ""),
                        )
                        await db_execute(
                            "INSERT INTO traffic (range_name, number, sms, otp, service, received_at) "
                            "VALUES ($1,$2,$3,$4,$5,$6)",
                            row.get("range", ""), number, sms, otp, row.get("service", ""), date,
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                    except Exception as row_err:
                        logger.error(f"Row error: {row_err}")
                        continue

            if len(otp_cache) > 50000:
                otp_cache.clear()
                recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
                for r in recent:
                    otp_cache.add(r["hash"])

            await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as e:
            worker_info["errors"] += 1
            logger.error(f"Worker loop error: {e}")
            if worker_info["errors"] % 5 == 0:
                await notify_admins(app, f"┌─ ᴡᴏʀᴋᴇʀ ᴇʀʀᴏʀ\n├─❏ {e}\n└─❏")
            await asyncio.sleep(15)

    worker_info["running"] = False

BANNED_TEXT = "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ."
MAINT_TEXT  = "ʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ. ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sᴏᴏɴ."
JOIN_TEXT   = f"┌─ {BOT_NAME}\n├─❏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ\n└─❏ ᴛᴀᴘ ᴠᴇʀɪғʏ ᴡʜᴇɴ ᴅᴏɴᴇ"
WELCOME_TEXT       = f"┌─ {BOT_NAME}\n├─❏ ʟɪᴠᴇ ᴏᴛᴘ ᴍᴏɴɪᴛᴏʀɪɴɢ 24/7\n└─❏"
WELCOME_ADMIN_TEXT = f"┌─ {BOT_NAME}\n├─❏ ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴀᴅᴍɪɴ\n└─❏"
GET_NUMBER_TEXT    = "┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏"

def number_display_text(number, country_name, flag, service):
    display = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴀssɪɢɴᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴏᴛᴘ..."
    )

def number_changed_text(number, country_name, flag, service):
    display = f"+{number}" if not str(number).startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴄʜᴀɴɢᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country_name)}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴏᴛᴘ..."
    )

def admin_text():
    return "┌─ ᴀᴅᴍɪɴ\n├─❏ ᴍᴀɴᴀɢᴇ ᴛʜᴇ ɴᴜᴍʙᴇʀ ᴅᴀᴛᴀʙᴀsᴇ\n└─❏"

async def numbers_db_text():
    total = await db_fetchval("SELECT COUNT(*) FROM numbers")
    avail = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE is_used=FALSE")
    used  = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE is_used=TRUE")
    return f"┌─ ɴᴜᴍʙᴇʀs\n├─❏ ᴛᴏᴛᴀʟ : {total}\n├─❏ ᴀᴠᴀɪʟ : {avail}\n├─❏ ᴜsᴇᴅ  : {used}\n└─❏"

async def status_text():
    total_users   = await db_fetchval("SELECT COUNT(*) FROM users WHERE is_banned=FALSE") or 0
    monthly_users = await get_monthly_users()
    return (
        f"┌─ sᴛᴀᴛᴜs\n"
        f"├─❏ ɪᴍs       : {'ᴏɴʟɪɴᴇ' if worker_info['logged_in'] else 'ᴏғғʟɪɴᴇ'}\n"
        f"├─❏ ᴡᴏʀᴋᴇʀ    : {'ʀᴜɴɴɪɴɢ' if worker_info['running'] else 'sᴛᴏᴘᴘᴇᴅ'}\n"
        f"├─❏ ʟᴀsᴛ ʟᴏɢɪɴ : {worker_info['last_login']}\n"
        f"├─❏ ᴏᴛᴘs ᴛᴏᴅᴀʏ : {worker_info['otps_today']}\n"
        f"├─❏ ʟᴀsᴛ ᴏᴛᴘ   : {worker_info['last_otp']}\n"
        f"├─❏ ᴇʀʀᴏʀs     : {worker_info['errors']}\n"
        f"├─❏ ᴜsᴇʀs      : {total_users}\n"
        f"├─❏ ᴍᴏɴᴛʜʟʏ    : {monthly_users}\n"
        f"├─❏ sᴛᴀʀᴛᴇᴅ    : {worker_info['started_at']}\n"
        f"└─❏"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if not is_admin(user.id):
        if await is_banned(user.id):
            await send_msg(context.bot, update.effective_chat.id, BANNED_TEXT)
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "sʟᴏᴡ ᴅᴏᴡɴ.")
            return
        if maintenance:
            await send_msg(context.bot, update.effective_chat.id, MAINT_TEXT)
            return
    joined = await check_membership(context.bot, user.id)
    if not joined:
        statuses = await check_membership_per_channel(context.bot, user.id)
        await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
        return
    welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await send_msg(context.bot, update.effective_chat.id, welcome, reply_markup=await main_menu_markup(context.bot, user.id))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    joined = await check_membership(context.bot, user.id)
    if not joined:
        statuses = await check_membership_per_channel(context.bot, user.id)
        await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
        return
    await send_msg(context.bot, update.effective_chat.id, admin_text(), reply_markup=admin_markup())

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE.pop(user.id, None)
    joined = await check_membership(context.bot, user.id)
    if not joined:
        statuses = await check_membership_per_channel(context.bot, user.id)
        await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
        return
    await send_msg(context.bot, update.effective_chat.id, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=await main_menu_markup(context.bot, user.id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data

    if not is_admin(user.id) and await is_banned(user.id) and data != "check_join":
        await query.answer(BANNED_TEXT, show_alert=True)
        return

    if data.startswith("joined_noop__"):
        await query.answer()
        return

    if data == "check_join":
        joined = await check_membership(context.bot, user.id)
        if joined:
            await query.answer()
            await register_user(user)
            welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_msg(query, welcome, reply_markup=await main_menu_markup(context.bot, user.id))
        else:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await edit_msg(query, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            await query.answer("ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ғɪʀsᴛ.", show_alert=True)
        return

    await query.answer()

    if data == "menu_back":
        joined = await check_membership(context.bot, user.id)
        if not joined:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await edit_msg(query, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            return
        welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await edit_msg(query, welcome, reply_markup=await main_menu_markup(context.bot, user.id))
        return

    if data == "menu_admin":
        if not is_admin(user.id):
            await query.answer("ᴀᴅᴍɪɴs ᴏɴʟʏ.", show_alert=True)
            return
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "menu_get_number":
        joined = await check_membership(context.bot, user.id)
        if not joined:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await edit_msg(query, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            return
        if not is_admin(user.id) and maintenance:
            await query.answer(MAINT_TEXT, show_alert=True)
            return
        _, markup = await build_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ɴᴜᴍʙᴇʀs\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sᴏᴏɴ", reply_markup=back_to_menu())
            return
        await edit_msg(query, GET_NUMBER_TEXT, reply_markup=markup)
        return

    if data.startswith("gns__"):
        service = data.replace("gns__", "")
        _, markup = await build_country_grid_for_service(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ғᴏʀ ᴛʜɪs sᴇʀᴠɪᴄᴇ.", show_alert=True)
            return
        await edit_msg(query, f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("gnc__"):
        parts   = data.split("__", 2)
        country = parts[1]
        service = parts[2] if len(parts) > 2 else "All"
        wait    = await check_number_cooldown(user.id)
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
                    await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"]
        if not is_admin(user.id):
            await set_number_cooldown(user.id)
        country_name, _ = get_country_info(number)
        await edit_msg(query, number_display_text(number, country_name, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
        return

    if data.startswith("chgn__"):
        parts   = data.split("__")
        if len(parts) < 4:
            await query.answer("ɪɴᴠᴀʟɪᴅ ʀᴇǫᴜᴇsᴛ.", show_alert=True)
            return
        old_id  = parts[-1]
        service = parts[-2]
        country = "__".join(parts[1:-2])
        wait    = await check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT id, number, flag FROM numbers WHERE country=$1 AND service=$2 AND is_used=FALSE AND id!=$3 LIMIT 1 FOR UPDATE SKIP LOCKED",
                    country, service, int(old_id) if old_id.isdigit() else -1,
                )
                if not row:
                    await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀs.", show_alert=True)
                    return
                if old_id.isdigit():
                    await conn.execute(
                        "UPDATE numbers SET is_used=FALSE, used_by=NULL, use_date=NULL WHERE id=$1 AND used_by=$2",
                        int(old_id), user.id,
                    )
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"]
        if not is_admin(user.id):
            await set_number_cooldown(user.id)
        country_name, _ = get_country_info(number)
        await edit_msg(query, number_changed_text(number, country_name, flag, service), reply_markup=number_assigned_markup(country, service, num_id))
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

    if data == "adm_status":
        await edit_msg(query, await status_text(), reply_markup=back_to_admin())
        return

    if data == "adm_numbers":
        await edit_msg(query, await numbers_db_text(), reply_markup=numbers_markup())
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_PICK_SERVICE"
        await edit_msg(query, "┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=service_picker_markup())
        return

    if data == "adm_delete_numbers":
        _, markup = await build_delete_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀs ɪɴ ᴅᴀᴛᴀʙᴀsᴇ\n└─❏", reply_markup=back_to_admin())
            return
        await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_svc__"):
        service = data.replace("del_svc__", "")
        _, markup = await build_delete_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ғᴏᴜɴᴅ.", show_alert=True)
            return
        await edit_msg(query, f"┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_cntry__"):
        parts   = data.replace("del_cntry__", "").split("__", 1)
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
        svc_label     = "ᴀʟʟ" if service == "ALL" else sc(service)
        country_label = "ᴀʟʟ" if country == "ALL" else sc(country)
        await edit_msg(
            query,
            f"┌─ ᴅᴇʟᴇᴛᴇᴅ\n├─❏ sᴇʀᴠɪᴄᴇ : {svc_label}\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country_label}\n├─❏ ʀᴇᴍᴏᴠᴇᴅ : {deleted}\n└─❏",
            reply_markup=back_to_admin(),
        )
        return

    if data.startswith("adm_svc__"):
        service = data.replace("adm_svc__", "")
        USER_STATE[user.id] = f"WAITING_FILE__{service}"
        await send_msg(
            context.bot, user.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇɴᴅ .ᴛxᴛ / .ᴄsᴠ / .xʟs / .xʟsx\n└─❏ ᴀᴜᴛᴏ ᴄᴏᴜɴᴛʀʏ ᴅᴇᴛᴇᴄᴛɪᴏɴ",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if data == "adm_svc_custom":
        USER_STATE[user.id] = "ADM_CUSTOM_SVC"
        await send_msg(
            context.bot, user.id,
            "┌─ ᴄᴜsᴛᴏᴍ sᴇʀᴠɪᴄᴇ\n├─❏ sᴇɴᴅ sᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not is_admin(user.id):
        if await is_banned(user.id):
            await send_msg(context.bot, update.effective_chat.id, BANNED_TEXT)
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "sʟᴏᴡ ᴅᴏᴡɴ.")
            return
        if maintenance:
            await send_msg(context.bot, update.effective_chat.id, MAINT_TEXT)
            return
        return
    state = USER_STATE.get(user.id)
    if not state:
        return
    if state == "ADM_CUSTOM_SVC":
        service = text.strip()
        USER_STATE[user.id] = f"WAITING_FILE__{service}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇɴᴅ .ᴛxᴛ / .ᴄsᴠ / .xʟs / .xʟsx\n└─❏ ᴀᴜᴛᴏ ᴄᴏᴜɴᴛʀʏ ᴅᴇᴛᴇᴄᴛɪᴏɴ",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    state = USER_STATE.get(user.id)
    if not state or not state.startswith("WAITING_FILE__"):
        return
    service = state.replace("WAITING_FILE__", "")
    doc     = update.message.document
    if not doc.file_name.lower().endswith((".txt", ".csv", ".xls", ".xlsx")):
        await send_msg(context.bot, update.effective_chat.id, "ɪɴᴠᴀʟɪᴅ ғɪʟᴇ. ᴜsᴇ .ᴛxᴛ, .ᴄsᴠ, .xʟs ᴏʀ .xʟsx")
        return

    status_msg = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇssɪɴɢ...")
    try:
        tg_file = await doc.get_file()
        content = bytes(await tg_file.download_as_bytearray())
        result  = await process_numbers_async(content, doc.file_name)
        groups  = result["groups"]
        total   = result["total"]

        if not groups:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="┌─ ᴇʀʀᴏʀ\n├─❏ ɴᴏ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀs ғᴏᴜɴᴅ\n└─❏",
                reply_markup=mk([[btn("ʙᴀᴄᴋ", cb="adm_numbers", style="danger")]]),
            )
            USER_STATE.pop(user.id, None)
            return

        all_rows = []
        for country, cdata in groups.items():
            for n in cdata["numbers"]:
                all_rows.append((country, cdata["flag"], n, service))

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO numbers (country, flag, number, service) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (number) DO NOTHING",
                all_rows,
            )

        inserted_after = await db_fetchall(
            "SELECT number, country, flag FROM numbers WHERE number = ANY($1::text[]) AND service=$2",
            [r[2] for r in all_rows], service,
        )
        inserted_set  = {r["number"] for r in inserted_after}
        all_input_set = {r[2] for r in all_rows}
        new_nums      = inserted_set & all_input_set

        count_added   = 0
        notify_groups = {}
        for country, cdata in groups.items():
            flag       = cdata["flag"]
            added_here = [n for n in cdata["numbers"] if n in new_nums]
            if added_here:
                count_added += len(added_here)
                notify_groups[country] = {"flag": flag, "service": service, "numbers": added_here}

        USER_STATE.pop(user.id, None)
        lines = [
            "┌─ ᴅᴏɴᴇ",
            f"├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}",
            f"├─❏ ғɪʟᴇ    : {doc.file_name}",
            f"├─❏ ᴛᴏᴛᴀʟ   : {total}",
            f"├─❏ ᴀᴅᴅᴇᴅ   : {count_added}",
            f"├─❏ ᴅᴜᴘᴇs   : {total - count_added}",
        ]
        for country, cdata in sorted(notify_groups.items(), key=lambda x: -len(x[1]["numbers"])):
            lines.append(f"├─❏ {cdata['flag']} {sc(country)} : {len(cdata['numbers'])}")
        lines.append("└─❏")

        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=mk([[btn("ʙᴀᴄᴋ", cb="adm_numbers", style="danger")]]),
            )
        except Exception:
            await send_msg(
                context.bot, update.effective_chat.id,
                "\n".join(lines),
                reply_markup=mk([[btn("ʙᴀᴄᴋ", cb="adm_numbers", style="danger")]]),
            )

        if notify_groups:
            asyncio.create_task(broadcast_stock_notification(context.application, notify_groups))

    except Exception as e:
        logger.error(f"Document handler error: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="┌─ ᴇʀʀᴏʀ\n├─❏ ғᴀɪʟᴇᴅ ᴛᴏ ᴘʀᴏᴄᴇss ғɪʟᴇ\n└─❏",
                reply_markup=mk([[btn("ʙᴀᴄᴋ", cb="adm_numbers", style="danger")]]),
            )
        except Exception:
            pass
        USER_STATE.pop(user.id, None)

async def health_handler(request):
    return web.Response(
        text=json.dumps({
            "status":     "ok",
            "bot":        BOT_NAME,
            "worker":     worker_info["running"],
            "logged_in":  worker_info["logged_in"],
            "otps_today": worker_info["otps_today"],
            "last_otp":   worker_info["last_otp"],
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
    try:
        await db_execute("ALTER TABLE numbers ADD COLUMN IF NOT EXISTS flag TEXT DEFAULT '🌐'")
    except Exception:
        pass
    recent = await db_fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
    for r in recent:
        otp_cache.add(r["hash"])
    logger.info(f"Loaded {len(otp_cache)} OTP hashes into cache")
    await application.bot.set_my_commands([
        BotCommand("start",  "start"),
        BotCommand("admin",  "admin"),
        BotCommand("cancel", "cancel"),
    ])
    app_web = web.Application()
    app_web.router.add_get("/",       health_handler)
    app_web.router.add_get("/health", health_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Health server on port {PORT}")
    application.create_task(sms_worker(application))
    logger.info(f"{BOT_NAME} is live")

if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start",  start))
    application.add_handler(CommandHandler("admin",  admin_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))
    logger.info(f"Starting {BOT_NAME}...")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
