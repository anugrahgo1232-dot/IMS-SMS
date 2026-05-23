import sys
import os
import logging
import sqlite3
import time
import re
import threading
import hashlib
import asyncio
import json
import aiohttp
from datetime import datetime
from io import BytesIO
from bs4 import BeautifulSoup
import openpyxl
from aiohttp import web

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
BASE_ADMIN_IDS      = [8339856952]

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

DB_FILE             = "bot.db"
PORT                = int(os.environ.get("PORT", 8080))
POLL_INTERVAL       = 5
KEEPALIVE_INTERVAL  = 60
FLOOD_LIMIT         = 5
FLOOD_WINDOW        = 10
NUMBER_COOLDOWN     = 30

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

COUNTRY_CODES = {
    "1": ("USA/Canada", "🇺🇸"), "7": ("Russia", "🇷🇺"), "20": ("Egypt", "🇪🇬"),
    "27": ("South Africa", "🇿🇦"), "30": ("Greece", "🇬🇷"), "31": ("Netherlands", "🇳🇱"),
    "32": ("Belgium", "🇧🇪"), "33": ("France", "🇫🇷"), "34": ("Spain", "🇪🇸"),
    "36": ("Hungary", "🇭🇺"), "39": ("Italy", "🇮🇹"), "40": ("Romania", "🇷🇴"),
    "41": ("Switzerland", "🇨🇭"), "43": ("Austria", "🇦🇹"), "44": ("United Kingdom", "🇬🇧"),
    "45": ("Denmark", "🇩🇰"), "46": ("Sweden", "🇸🇪"), "47": ("Norway", "🇳🇴"),
    "48": ("Poland", "🇵🇱"), "49": ("Germany", "🇩🇪"), "51": ("Peru", "🇵🇪"),
    "52": ("Mexico", "🇲🇽"), "53": ("Cuba", "🇨🇺"), "54": ("Argentina", "🇦🇷"),
    "55": ("Brazil", "🇧🇷"), "56": ("Chile", "🇨🇱"), "57": ("Colombia", "🇨🇴"),
    "58": ("Venezuela", "🇻🇪"), "60": ("Malaysia", "🇲🇾"), "61": ("Australia", "🇦🇺"),
    "62": ("Indonesia", "🇮🇩"), "63": ("Philippines", "🇵🇭"), "64": ("New Zealand", "🇳🇿"),
    "65": ("Singapore", "🇸🇬"), "66": ("Thailand", "🇹🇭"), "81": ("Japan", "🇯🇵"),
    "82": ("South Korea", "🇰🇷"), "84": ("Viet Nam", "🇻🇳"), "86": ("China", "🇨🇳"),
    "90": ("Turkey", "🇹🇷"), "91": ("India", "🇮🇳"), "92": ("Pakistan", "🇵🇰"),
    "93": ("Afghanistan", "🇦🇫"), "94": ("Sri Lanka", "🇱🇰"), "95": ("Myanmar", "🇲🇲"),
    "98": ("Iran", "🇮🇷"), "211": ("South Sudan", "🇸🇸"), "212": ("Morocco", "🇲🇦"),
    "213": ("Algeria", "🇩🇿"), "216": ("Tunisia", "🇹🇳"), "218": ("Libya", "🇱🇾"),
    "220": ("Gambia", "🇬🇲"), "221": ("Senegal", "🇸🇳"), "222": ("Mauritania", "🇲🇷"),
    "223": ("Mali", "🇲🇱"), "224": ("Guinea", "🇬🇳"), "225": ("Côte d'Ivoire", "🇨🇮"),
    "226": ("Burkina Faso", "🇧🇫"), "227": ("Niger", "🇳🇪"), "228": ("Togo", "🇹🇬"),
    "229": ("Benin", "🇧🇯"), "230": ("Mauritius", "🇲🇺"), "231": ("Liberia", "🇱🇷"),
    "232": ("Sierra Leone", "🇸🇱"), "233": ("Ghana", "🇬🇭"), "234": ("Nigeria", "🇳🇬"),
    "235": ("Chad", "🇹🇩"), "236": ("Central African Republic", "🇨🇫"),
    "237": ("Cameroon", "🇨🇲"), "238": ("Cape Verde", "🇨🇻"),
    "240": ("Equatorial Guinea", "🇬🇶"), "241": ("Gabon", "🇬🇦"), "242": ("Congo", "🇨🇬"),
    "243": ("DR Congo", "🇨🇩"), "244": ("Angola", "🇦🇴"), "245": ("Guinea-Bissau", "🇬🇼"),
    "248": ("Seychelles", "🇸🇨"), "249": ("Sudan", "🇸🇩"), "250": ("Rwanda", "🇷🇼"),
    "251": ("Ethiopia", "🇪🇹"), "252": ("Somalia", "🇸🇴"), "253": ("Djibouti", "🇩🇯"),
    "254": ("Kenya", "🇰🇪"), "255": ("Tanzania", "🇹🇿"), "256": ("Uganda", "🇺🇬"),
    "257": ("Burundi", "🇧🇮"), "258": ("Mozambique", "🇲🇿"), "260": ("Zambia", "🇿🇲"),
    "261": ("Madagascar", "🇲🇬"), "263": ("Zimbabwe", "🇿🇼"), "264": ("Namibia", "🇳🇦"),
    "265": ("Malawi", "🇲🇼"), "266": ("Lesotho", "🇱🇸"), "267": ("Botswana", "🇧🇼"),
    "268": ("Eswatini", "🇸🇿"), "269": ("Comoros", "🇰🇲"), "290": ("Saint Helena", "🇸🇭"),
    "291": ("Eritrea", "🇪🇷"), "297": ("Aruba", "🇦🇼"), "298": ("Faroe Islands", "🇫🇴"),
    "299": ("Greenland", "🇬🇱"), "350": ("Gibraltar", "🇬🇮"), "351": ("Portugal", "🇵🇹"),
    "352": ("Luxembourg", "🇱🇺"), "353": ("Ireland", "🇮🇪"), "354": ("Iceland", "🇮🇸"),
    "355": ("Albania", "🇦🇱"), "356": ("Malta", "🇲🇹"), "357": ("Cyprus", "🇨🇾"),
    "358": ("Finland", "🇫🇮"), "359": ("Bulgaria", "🇧🇬"), "370": ("Lithuania", "🇱🇹"),
    "371": ("Latvia", "🇱🇻"), "372": ("Estonia", "🇪🇪"), "373": ("Moldova", "🇲🇩"),
    "374": ("Armenia", "🇦🇲"), "375": ("Belarus", "🇧🇾"), "376": ("Andorra", "🇦🇩"),
    "377": ("Monaco", "🇲🇨"), "380": ("Ukraine", "🇺🇦"), "381": ("Serbia", "🇷🇸"),
    "382": ("Montenegro", "🇲🇪"), "385": ("Croatia", "🇭🇷"), "386": ("Slovenia", "🇸🇮"),
    "387": ("Bosnia and Herzegovina", "🇧🇦"), "389": ("North Macedonia", "🇲🇰"),
    "420": ("Czech Republic", "🇨🇿"), "421": ("Slovakia", "🇸🇰"), "423": ("Liechtenstein", "🇱🇮"),
    "500": ("Falkland Islands", "🇫🇰"), "501": ("Belize", "🇧🇿"), "502": ("Guatemala", "🇬🇹"),
    "503": ("El Salvador", "🇸🇻"), "504": ("Honduras", "🇭🇳"), "505": ("Nicaragua", "🇳🇮"),
    "506": ("Costa Rica", "🇨🇷"), "507": ("Panama", "🇵🇦"), "509": ("Haiti", "🇭🇹"),
    "591": ("Bolivia", "🇧🇴"), "592": ("Guyana", "🇬🇾"), "593": ("Ecuador", "🇪🇨"),
    "595": ("Paraguay", "🇵🇾"), "597": ("Suriname", "🇸🇷"), "598": ("Uruguay", "🇺🇾"),
    "670": ("East Timor", "🇹🇱"), "673": ("Brunei", "🇧🇳"), "675": ("Papua New Guinea", "🇵🇬"),
    "676": ("Tonga", "🇹🇴"), "677": ("Solomon Islands", "🇸🇧"), "678": ("Vanuatu", "🇻🇺"),
    "679": ("Fiji", "🇫🇯"), "685": ("Samoa", "🇼🇸"), "687": ("New Caledonia", "🇳🇨"),
    "689": ("French Polynesia", "🇵🇫"), "850": ("North Korea", "🇰🇵"),
    "852": ("Hong Kong", "🇭🇰"), "853": ("Macau", "🇲🇴"), "855": ("Cambodia", "🇰🇭"),
    "856": ("Laos", "🇱🇦"), "880": ("Bangladesh", "🇧🇩"), "886": ("Taiwan", "🇹🇼"),
    "960": ("Maldives", "🇲🇻"), "961": ("Lebanon", "🇱🇧"), "962": ("Jordan", "🇯🇴"),
    "963": ("Syria", "🇸🇾"), "964": ("Iraq", "🇮🇶"), "965": ("Kuwait", "🇰🇼"),
    "966": ("Saudi Arabia", "🇸🇦"), "967": ("Yemen", "🇾🇪"), "968": ("Oman", "🇴🇲"),
    "970": ("Palestine", "🇵🇸"), "971": ("UAE", "🇦🇪"), "972": ("Israel", "🇮🇱"),
    "973": ("Bahrain", "🇧🇭"), "974": ("Qatar", "🇶🇦"), "975": ("Bhutan", "🇧🇹"),
    "976": ("Mongolia", "🇲🇳"), "977": ("Nepal", "🇳🇵"), "992": ("Tajikistan", "🇹🇯"),
    "993": ("Turkmenistan", "🇹🇲"), "994": ("Azerbaijan", "🇦🇿"), "995": ("Georgia", "🇬🇪"),
    "996": ("Kyrgyzstan", "🇰🇬"), "998": ("Uzbekistan", "🇺🇿"),
}

DEFAULT_SERVICES = [
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Google",
    "TikTok", "Twitter/X", "Snapchat", "Discord", "Line",
    "WeChat", "Viber", "Signal", "Binance", "Bybit",
    "OKX", "Bitget", "Coinbase", "Kraken", "Other",
]


class Database:
    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def fetchone(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def init(self):
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT    DEFAULT '',
                    first_name TEXT    DEFAULT '',
                    joined_at  TEXT    DEFAULT (datetime('now')),
                    is_banned  INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS otp_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash       TEXT    UNIQUE NOT NULL,
                    number     TEXT,
                    otp        TEXT,
                    service    TEXT,
                    sms        TEXT,
                    range_name TEXT,
                    added_at   TEXT    DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS traffic (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    range_name  TEXT,
                    number      TEXT,
                    sms         TEXT,
                    otp         TEXT,
                    service     TEXT,
                    received_at TEXT
                );
                CREATE TABLE IF NOT EXISTS numbers (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    country  TEXT    NOT NULL,
                    number   TEXT    NOT NULL,
                    service  TEXT    DEFAULT 'All',
                    is_used  INTEGER DEFAULT 0,
                    used_by  INTEGER DEFAULT NULL,
                    use_date TEXT    DEFAULT NULL,
                    UNIQUE(number)
                );
                CREATE TABLE IF NOT EXISTS cooldowns (
                    user_id   INTEGER PRIMARY KEY,
                    timestamp INTEGER
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_otp_hash     ON otp_history(hash);
                CREATE INDEX IF NOT EXISTS idx_otp_added    ON otp_history(added_at);
                CREATE INDEX IF NOT EXISTS idx_traffic_date ON traffic(received_at);
                CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
                CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
                CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
                CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
            """)
            self._conn.commit()
            migrations = [
                "ALTER TABLE traffic ADD COLUMN range_name TEXT",
                "ALTER TABLE traffic ADD COLUMN service TEXT",
                "ALTER TABLE otp_history ADD COLUMN range_name TEXT",
                "ALTER TABLE numbers ADD COLUMN use_date TEXT DEFAULT NULL",
                "ALTER TABLE numbers ADD COLUMN used_by INTEGER DEFAULT NULL",
            ]
            for sql in migrations:
                try:
                    self._conn.execute(sql)
                    self._conn.commit()
                except Exception:
                    pass

    def get_setting(self, key, default=""):
        row = self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


db = Database(DB_FILE)


def _btn(text, *, cb=None, url=None, style=None):
    if url is not None:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=cb)

def _markup(rows):
    return InlineKeyboardMarkup(rows)


def get_country_info(number):
    clean = re.sub(r"\D", "", str(number))
    for length in (3, 2, 1):
        prefix = clean[:length]
        if prefix in COUNTRY_CODES:
            name, flag = COUNTRY_CODES[prefix]
            return name, flag
    return "Unknown", "🌐"

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
    for pattern in (
        r"\b\d{3}[-\s]\d{3}\b",
        r"\b\d{6,8}\b",
        r"\b\d{4,5}\b",
    ):
        m = re.search(pattern, sms)
        if m:
            return m.group().strip()
    return None

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

def register_user(user):
    db.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, user.username or "", user.first_name or ""),
    )
    db.execute(
        "UPDATE users SET username=?, first_name=? WHERE user_id=?",
        (user.username or "", user.first_name or "", user.id),
    )

def is_banned(user_id):
    row = db.fetchone("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
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

def check_number_cooldown(user_id):
    row = db.fetchone("SELECT timestamp FROM cooldowns WHERE user_id=?", (user_id,))
    if row:
        elapsed = int(time.time()) - row["timestamp"]
        if elapsed < NUMBER_COOLDOWN:
            return NUMBER_COOLDOWN - elapsed
    return 0

def set_number_cooldown(user_id):
    db.execute(
        "INSERT OR REPLACE INTO cooldowns (user_id, timestamp) VALUES (?, ?)",
        (user_id, int(time.time())),
    )

def extract_numbers_from_content(content, filename):
    nums = set()
    try:
        if filename.endswith(".xlsx"):
            wb = openpyxl.load_workbook(BytesIO(bytes(content)), read_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    for cell in row:
                        if cell:
                            val = re.sub(r"\D", "", str(cell))
                            if 7 <= len(val) <= 15:
                                nums.add(val)
        else:
            text = content.decode("utf-8", errors="ignore")
            for line in text.splitlines():
                val = re.sub(r"\D", "", line.strip())
                if 7 <= len(val) <= 15:
                    nums.add(val)
    except Exception as e:
        logger.error(f"Number extraction error: {e}")
    return list(nums)


CHANNEL_LABELS = {
    "@sage_xd":  ("sᴀɢᴇ",    MAIN_CHANNEL_LINK),
    "@mr_afrix": ("ᴍʀᴀғʀɪx",  BACKUP_CHANNEL_LINK),
    "@oxellabs": ("ᴏxᴇʟʟᴀʙs", THIRD_CHANNEL_LINK),
    "@oracron":  ("ᴏʀᴀᴄʀᴏɴ",  FOURTH_CHANNEL_LINK),
}

def join_markup_static():
    return _markup([
        [
            _btn("sᴀɢᴇ",    url=MAIN_CHANNEL_LINK),
            _btn("ᴍʀᴀғʀɪx",  url=BACKUP_CHANNEL_LINK),
        ],
        [
            _btn("ᴏxᴇʟʟᴀʙs", url=THIRD_CHANNEL_LINK),
            _btn("ᴏʀᴀᴄʀᴏɴ",  url=FOURTH_CHANNEL_LINK),
        ],
        [_btn("ᴠᴇʀɪғʏ", cb="check_join")],
    ])

def join_markup_dynamic(statuses):
    rows = []
    pair = []
    for channel, (label, link) in CHANNEL_LABELS.items():
        joined = statuses.get(channel, False)
        display = label if joined else label
        btn = _btn(display, url=link) if not joined else _btn(display, cb=f"joined_noop__{channel}")
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([_btn("ᴠᴇʀɪғʏ", cb="check_join")])
    return _markup(rows)

def main_menu_markup(user_id=None):
    rows = [
        [_btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", cb="menu_get_number")],
        [
            _btn("sᴀɢᴇ",    url=MAIN_CHANNEL_LINK),
            _btn("ᴍʀᴀғʀɪx",  url=BACKUP_CHANNEL_LINK),
        ],
        [
            _btn("ᴏxᴇʟʟᴀʙs", url=THIRD_CHANNEL_LINK),
            _btn("ᴏʀᴀᴄʀᴏɴ",  url=FOURTH_CHANNEL_LINK),
        ],
    ]
    if user_id and is_admin(user_id):
        rows.append([_btn("ᴀᴅᴍɪɴ", cb="menu_admin")])
    return _markup(rows)

def otp_markup():
    return _markup([
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK),
            _btn("ᴍʀᴀғʀɪx",     url=BACKUP_CHANNEL_LINK),
        ],
        [
            _btn("ᴏxᴇʟʟᴀʙs", url=THIRD_CHANNEL_LINK),
            _btn("ᴏʀᴀᴄʀᴏɴ",  url=FOURTH_CHANNEL_LINK),
        ],
        [_btn("sᴀɢᴇ", url=MAIN_CHANNEL_LINK)],
    ])

def number_assigned_markup(country, service, num_id):
    return _markup([
        [_btn("ᴄʜᴀɴɢᴇ ɴᴜᴍʙᴇʀ", cb=f"chgn__{country}__{service}__{num_id}")],
        [_btn("ᴏᴛᴘ ɢʀᴏᴜᴘ", url=OTP_GROUP_LINK)],
        [_btn("ʙᴀᴄᴋ", cb="menu_back")],
    ])

def admin_markup():
    return _markup([
        [_btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀs", cb="adm_numbers")],
        [_btn("ʙᴀᴄᴋ", cb="menu_back")],
    ])

def back_to_menu():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="menu_back")]])

def back_to_admin():
    return _markup([[_btn("ʙᴀᴄᴋ", cb="adm_back")]])

def cancel_state_markup(back_cb="adm_back"):
    return _markup([
        [
            _btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state"),
            _btn("ʙᴀᴄᴋ", cb=back_cb),
        ]
    ])

def build_service_grid():
    rows = db.fetchall(
        "SELECT service, COUNT(*) AS cnt FROM numbers WHERE is_used=0 GROUP BY service ORDER BY service"
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        cb = f"gns__{r['service']}"
        row_buf.append(_btn(r['service'], cb=cb))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb="menu_back")])
    return rows, _markup(buttons)

def build_country_grid_for_service(service):
    rows = db.fetchall(
        "SELECT country, COUNT(*) AS cnt FROM numbers WHERE is_used=0 AND service=? "
        "GROUP BY country ORDER BY country",
        (service,),
    )
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        cb = f"gnc__{r['country']}__{service}"
        row_buf.append(_btn(r['country'], cb=cb))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb=f"gns__{service}")])
    return rows, _markup(buttons)

def _service_picker_markup(mode="file"):
    buttons = []
    row_buf = []
    for svc in DEFAULT_SERVICES:
        row_buf.append(_btn(svc, cb=f"adm_svc__{svc}"))
        if len(row_buf) == 3:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ᴄᴜsᴛᴏᴍ", cb=f"adm_svc_custom__{mode}")])
    buttons.append([_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state")])
    return _markup(buttons)


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


def format_otp_message(row, otp):
    masked             = mask_number(row["number"])
    country_name, flag = get_country_info(row["number"])
    sms_txt            = (row.get("sms") or "").strip()
    service            = (row.get("service") or "Unknown").strip()

    text = (
        f"┌─ ➪ ɴᴇᴡ ᴏᴛᴘ ʀᴇᴄᴇɪᴠᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{masked}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {country_name}\n"
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
        m = re.search(
            r"[Ww]hat\s+is\s+(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*[=?]",
            full_text,
        )
        if not m:
            for tag in soup.find_all(True):
                t = tag.get_text(strip=True)
                m = re.search(r"(\d+)\s*([\+\-*×xX÷/])\s*(\d+)\s*=\s*\?", t)
                if m:
                    break
        if m:
            a  = int(m.group(1))
            op = m.group(2).strip()
            b  = int(m.group(3))
            if op == "+":                           return str(a + b)
            if op == "-":                           return str(a - b)
            if op in ("*", "×", "x", "X"):         return str(a * b)
            if op in ("÷", "/") and b != 0:        return str(a // b)
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
            connector = aiohttp.TCPConnector(
                ssl=True,
                limit=10,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"
                    ),
                    "Accept-Language": "en-CI,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
                        "application/signed-exchange;v=b3;q=0.7"
                    ),
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0",
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

            login_html = ""
            try:
                async with sess.get(
                    PANEL_LOGIN_PAGE,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    login_html = await resp.text(errors="replace")
                    logger.info(f"Login page: status={resp.status}")
            except Exception as e:
                logger.error(f"Login page fetch error: {e}")
                return False

            if not login_html:
                return False

            soup = BeautifulSoup(login_html, "html.parser")
            etkk = ""
            etkk_inp = soup.find("input", {"name": "etkk"})
            if etkk_inp:
                etkk = etkk_inp.get("value", "")
            if not etkk:
                m = re.search(r'name=["\']etkk["\'][^>]*value=["\']([^"\']+)["\']', login_html)
                if not m:
                    m = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']etkk["\']', login_html)
                if m:
                    etkk = m.group(1)

            capt = solve_captcha(login_html)
            soup_dbg = BeautifulSoup(login_html, "html.parser")
            raw_txt  = soup_dbg.get_text(" ", strip=True)
            capt_ctx = ""
            for kw in ["what is", "What is", "captcha", "capt", "="]:
                idx = raw_txt.lower().find(kw.lower())
                if idx >= 0:
                    capt_ctx = raw_txt[max(0, idx - 10):idx + 40].strip()
                    break
            logger.info(f"etkk={'found' if etkk else 'missing'}, capt={capt}, ctx={repr(capt_ctx)}")

            form_data = aiohttp.FormData()
            if etkk:
                form_data.add_field("etkk", etkk)
            form_data.add_field("username", PANEL_USERNAME)
            form_data.add_field("password", PANEL_PASSWORD)
            form_data.add_field("capt", capt)

            async with sess.post(
                PANEL_SIGNIN_URL,
                data=form_data,
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
                logger.info(f"Signin: status={resp.status}, location={location}")

                if resp.status == 302 and "login" not in location.lower():
                    if location.startswith("http"):
                        redirect_url = location
                    elif location.startswith("/"):
                        redirect_url = f"{PANEL_BASE}{location}"
                    else:
                        redirect_url = PANEL_BASE + "/"
                    logger.info(f"Following post-login redirect to: {redirect_url}")
                    try:
                        async with sess.get(
                            redirect_url,
                            allow_redirects=True,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as redir_resp:
                            final = str(redir_resp.url)
                            logger.info(f"Post-login redirect: status={redir_resp.status}, url={final}")
                            if "login" in final.lower():
                                logger.error("Session cookie not accepted")
                                return False
                    except Exception as e:
                        logger.warning(f"Post-login redirect warning: {e}")

                    self._logged_in      = True
                    self._login_attempts = 0
                    self._next_login_at  = 0
                    self._last_activity  = time.time()
                    await self._fetch_sesskey(sess)
                    logger.info(f"Panel login OK -> sesskey={'found' if self._sesskey else 'missing'}")
                    return True

                logger.error(f"Login failed | status={resp.status} | location={location}")
                self._login_attempts += 1
                backoff = min(30 * (2 ** (self._login_attempts - 1)), 1800)
                self._next_login_at = time.time() + backoff
                logger.warning(f"Login backoff: attempt {self._login_attempts}, next in {backoff}s")
                return False

        except Exception as e:
            logger.error(f"Login exception: {type(e).__name__}: {e}")
            self._login_attempts += 1
            backoff = min(30 * (2 ** (self._login_attempts - 1)), 1800)
            self._next_login_at = time.time() + backoff
            return False

    async def _fetch_sesskey(self, sess):
        try:
            async with sess.get(
                PANEL_CDR_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                final_url = str(resp.url)
                logger.info(f"sesskey fetch: status={resp.status}, url={final_url}")
                if "login" in final_url.lower():
                    logger.warning("sesskey fetch redirected to login")
                    return
                html = await resp.text(errors="replace")
                patterns = [
                    r'["\']sesskey["\']\s*[,:=]\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'var\s+sesskey\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'data\[.sesskey.\]\s*=\s*["\']([A-Za-z0-9+/=_\-]{10,})["\']',
                    r'sesskey["\\s:=]+([A-Za-z0-9+/=_\-]{10,})',
                ]
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        self._sesskey = m.group(1)
                        logger.info(f"sesskey extracted: {self._sesskey[:12]}...")
                        return
                logger.warning("sesskey not found in CDR page")
        except Exception as e:
            logger.error(f"sesskey fetch error: {e}")

    async def keepalive(self):
        try:
            sess = await self._get_session()
            async with sess.get(
                PANEL_DASHBOARD_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                final = str(resp.url)
                if "login" in final.lower():
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
            params = {
                "draw":   "1",
                "start":  "0",
                "length": "50",
            }
            if self._sesskey:
                params["sesskey"] = self._sesskey

            async with sess.get(
                PANEL_DATA_URL,
                params=params,
                headers={
                    "Referer":          PANEL_CDR_URL,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept":           "application/json, text/javascript, */*; q=0.01",
                },
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                final_url = str(resp.url)
                if "login" in final_url.lower():
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

                aa = data.get("aaData", [])
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
    global maintenance
    if worker_info["running"]:
        logger.warning("Worker already running")
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
                logger.info("Attempting panel login...")
                ok = await panel.login()
                if not ok:
                    worker_info["errors"] += 1
                    if panel._login_attempts == 1:
                        await notify_admins(
                            app,
                            f"ᴘᴀɴᴇʟ ʟᴏɢɪɴ ғᴀɪʟᴇᴅ\nattempt #{panel._login_attempts}",
                        )
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                worker_info["logged_in"]  = True
                worker_info["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worker_info["errors"]     = 0
                await notify_admins(app, f"ᴘᴀɴᴇʟ ʟᴏɢɪɴ ᴏᴋ\n{BOT_NAME} ɪs ʟɪᴠᴇ.")
                _startup_rows, _ = await panel.fetch_cdr()
                if _startup_rows:
                    for _r in _startup_rows:
                        _h = hashlib.md5(
                            f"{str(_r['date']).strip()}{str(_r['number']).strip()}{str(_r['sms']).strip()}".encode()
                        ).hexdigest()
                        otp_cache.add(_h)
                    logger.info(f"Startup cache: {len(_startup_rows)} rows pre-cached")
                continue

            keepalive_timer += POLL_INTERVAL
            if keepalive_timer >= KEEPALIVE_INTERVAL:
                idle_secs = time.time() - panel._last_activity
                if idle_secs >= KEEPALIVE_INTERVAL:
                    alive = await panel.keepalive()
                    if not alive:
                        logger.warning("Keepalive failed")
                keepalive_timer = 0

            rows, err = await panel.fetch_cdr()

            if err == "session_expired":
                panel._logged_in         = False
                worker_info["logged_in"] = False
                logger.warning("Session expired")
                await notify_admins(app, "sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ — ʀᴇ-ᴀᴜᴛʜᴇɴᴛɪᴄᴀᴛɪɴɢ...")
                await asyncio.sleep(10)
                continue

            if err:
                logger.warning(f"Fetch warning: {err}")
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

                        h = hashlib.md5(
                            f"{str(date).strip()}{str(number).strip()}{str(sms).strip()}".encode()
                        ).hexdigest()

                        if h in otp_cache:
                            continue
                        if db.fetchone("SELECT id FROM otp_history WHERE hash=?", (h,)):
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
                        db.execute(
                            "INSERT OR IGNORE INTO otp_history "
                            "(hash, number, otp, service, sms, range_name) VALUES (?,?,?,?,?,?)",
                            (h, number, otp, row.get("service", ""), sms, row.get("range", "")),
                        )
                        db.execute(
                            "INSERT INTO traffic "
                            "(range_name, number, sms, otp, service, received_at) VALUES (?,?,?,?,?,?)",
                            (row.get("range", ""), number, sms, otp, row.get("service", ""), date),
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                        logger.info(f"OTP sent | {mask_number(number)} | {otp} | {row.get('service')}")

                    except Exception as row_err:
                        logger.error(f"Row error: {row_err}")
                        continue

            if len(otp_cache) > 50000:
                otp_cache.clear()
                rows_db = db.fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
                for r in rows_db:
                    otp_cache.add(r["hash"])

            await asyncio.sleep(POLL_INTERVAL)

        except asyncio.CancelledError:
            break
        except Exception as e:
            worker_info["errors"] += 1
            logger.error(f"Worker loop error: {e}")
            if worker_info["errors"] % 5 == 0:
                await notify_admins(app, f"ᴡᴏʀᴋᴇʀ ᴇʀʀᴏʀ\n{e}")
            await asyncio.sleep(15)

    worker_info["running"] = False


BANNED_TEXT = "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ."
MAINT_TEXT  = "ʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ. ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sᴏᴏɴ."

JOIN_TEXT = (
    f"┌─ {BOT_NAME}\n"
    f"├─❏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ\n"
    f"└─❏ ᴛᴀᴘ ᴠᴇʀɪғʏ ᴡʜᴇɴ ᴅᴏɴᴇ"
)

WELCOME_TEXT = (
    f"┌─ {BOT_NAME}\n"
    f"├─❏ ʟɪᴠᴇ ᴏᴛᴘ ᴍᴏɴɪᴛᴏʀɪɴɢ 24/7\n"
    f"└─❏"
)

WELCOME_ADMIN_TEXT = (
    f"┌─ {BOT_NAME}\n"
    f"├─❏ ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴀᴅᴍɪɴ\n"
    f"└─❏"
)

GET_NUMBER_TEXT = (
    f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n"
    f"├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n"
    f"└─❏"
)

def number_display_text(number, country_name, flag, service):
    display = f"+{number}" if not number.startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴀssɪɢɴᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {country_name}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {service}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴏᴛᴘ..."
    )

def number_changed_text(number, country_name, flag, service):
    display = f"+{number}" if not number.startswith("+") else number
    return (
        f"┌─ ɴᴜᴍʙᴇʀ ᴄʜᴀɴɢᴇᴅ\n"
        f"├─❏ ɴᴜᴍʙᴇʀ  : <code>{display}</code>\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {country_name}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {service}\n"
        f"└─❏ ᴡᴀɪᴛɪɴɢ ғᴏʀ ᴏᴛᴘ..."
    )

def admin_text():
    return (
        f"┌─ ᴀᴅᴍɪɴ\n"
        f"├─❏ ᴀᴅᴅ ɴᴜᴍʙᴇʀs ᴛᴏ ᴛʜᴇ ᴅᴀᴛᴀʙᴀsᴇ\n"
        f"└─❏"
    )

def numbers_db_text():
    total_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers")["c"]
    avail_nums = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=0")["c"]
    used_nums  = db.fetchone("SELECT COUNT(*) AS c FROM numbers WHERE is_used=1")["c"]
    return (
        f"┌─ ɴᴜᴍʙᴇʀs\n"
        f"├─❏ ᴛᴏᴛᴀʟ  : {total_nums}\n"
        f"├─❏ ᴀᴠᴀɪʟ  : {avail_nums}\n"
        f"├─❏ ᴜsᴇᴅ   : {used_nums}\n"
        f"└─❏"
    )

def numbers_markup():
    return _markup([
        [_btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀs", cb="adm_add_numbers")],
        [_btn("ʙᴀᴄᴋ", cb="adm_back")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    if not is_admin(user.id):
        if is_banned(user.id):
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
            await send_msg(
                context.bot,
                update.effective_chat.id,
                JOIN_TEXT,
                reply_markup=join_markup_dynamic(statuses),
            )
            return

    welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await send_msg(
        context.bot,
        update.effective_chat.id,
        welcome,
        reply_markup=main_menu_markup(user.id),
    )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await send_msg(
        context.bot,
        update.effective_chat.id,
        admin_text(),
        reply_markup=admin_markup(),
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USER_STATE.pop(user.id, None)
    await send_msg(
        context.bot,
        update.effective_chat.id,
        "ᴄᴀɴᴄᴇʟʟᴇᴅ.",
        reply_markup=main_menu_markup(user.id),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global maintenance
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    if not is_admin(user.id) and is_banned(user.id) and data != "check_join":
        await query.answer(BANNED_TEXT, show_alert=True)
        return

    if data.startswith("joined_noop__"):
        return

    if data == "check_join":
        joined = await check_membership(context.bot, user.id)
        if joined:
            register_user(user)
            welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
        else:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await edit_msg(query, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            await query.answer("ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ғɪʀsᴛ.", show_alert=True)
        return

    if data == "menu_back":
        welcome = WELCOME_ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
        await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
        return

    if data == "menu_admin":
        if not is_admin(user.id):
            await query.answer("ᴀᴅᴍɪɴs ᴏɴʟʏ.", show_alert=True)
            return
        await edit_msg(query, admin_text(), reply_markup=admin_markup())
        return

    if data == "menu_get_number":
        if not is_admin(user.id) and maintenance:
            await query.answer(MAINT_TEXT, show_alert=True)
            return
        _, markup = build_service_grid()
        if markup is None:
            await edit_msg(
                query,
                "┌─ ɴᴜᴍʙᴇʀs\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sᴏᴏɴ",
                reply_markup=back_to_menu(),
            )
            return
        await edit_msg(query, GET_NUMBER_TEXT, reply_markup=markup)
        return

    if data.startswith("gns__"):
        service = data.replace("gns__", "")
        _, markup = build_country_grid_for_service(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ғᴏʀ ᴛʜɪs sᴇʀᴠɪᴄᴇ.", show_alert=True)
            return
        await edit_msg(
            query,
            f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ sᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏",
            reply_markup=markup,
        )
        return

    if data.startswith("gnc__"):
        parts   = data.split("__", 2)
        country = parts[1]
        service = parts[2] if len(parts) > 2 else "All"

        wait = check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return

        row = db.fetchone(
            "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
            (country, service),
        )
        if not row:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
            return

        num_id = row["id"]
        number = row["number"]

        updated = db.execute(
            "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=? AND is_used=0",
            (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
        ).rowcount

        if updated == 0:
            row2 = db.fetchone(
                "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
                (country, service),
            )
            if not row2:
                await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
                return
            num_id = row2["id"]
            number = row2["number"]
            db.execute(
                "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=?",
                (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
            )

        if not is_admin(user.id):
            set_number_cooldown(user.id)

        country_name, flag = get_country_info(number)
        await edit_msg(
            query,
            number_display_text(number, country_name, flag, service),
            reply_markup=number_assigned_markup(country, service, num_id),
        )
        return

    if data.startswith("chgn__"):
        parts   = data.split("__", 3)
        country = parts[1]
        service = parts[2] if len(parts) > 2 else "All"
        old_id  = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

        wait = check_number_cooldown(user.id)
        if wait > 0 and not is_admin(user.id):
            await query.answer(f"ᴡᴀɪᴛ {wait}s.", show_alert=True)
            return

        row = db.fetchone(
            "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
            (country, service),
        )
        if not row:
            await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀs.", show_alert=True)
            return

        num_id = row["id"]
        number = row["number"]

        updated = db.execute(
            "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=? AND is_used=0",
            (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
        ).rowcount

        if updated == 0:
            row2 = db.fetchone(
                "SELECT id, number FROM numbers WHERE country=? AND service=? AND is_used=0 LIMIT 1",
                (country, service),
            )
            if not row2:
                await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀs.", show_alert=True)
                return
            num_id = row2["id"]
            number = row2["number"]
            db.execute(
                "UPDATE numbers SET is_used=1, used_by=?, use_date=? WHERE id=?",
                (user.id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), num_id),
            )

        if not is_admin(user.id):
            set_number_cooldown(user.id)

        country_name, flag = get_country_info(number)
        await edit_msg(
            query,
            number_changed_text(number, country_name, flag, service),
            reply_markup=number_assigned_markup(country, service, num_id),
        )
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

    if data == "adm_numbers":
        await edit_msg(query, numbers_db_text(), reply_markup=numbers_markup())
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_ADD_COUNTRY"
        await edit_msg(
            query,
            "┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇɴᴅ ᴛʜᴇ ᴄᴏᴜɴᴛʀʏ ɴᴀᴍᴇ\n└─❏ ᴇx: ɢʜᴀɴᴀ",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if data == "adm_addmethod_file":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_METHOD__"):
            country = state.replace("ADM_ADD_METHOD__", "")
            USER_STATE[user.id] = f"ADM_ADD_FILE_SVC__{country}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏",
                reply_markup=_service_picker_markup("file"),
            )
        return

    if data == "adm_addmethod_type":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_METHOD__"):
            country = state.replace("ADM_ADD_METHOD__", "")
            USER_STATE[user.id] = f"ADM_ADD_TYPE_SVC__{country}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏",
                reply_markup=_service_picker_markup("type"),
            )
        return

    if data.startswith("adm_svc__"):
        service = data.replace("adm_svc__", "")
        state   = USER_STATE.get(user.id, "")
        if state.startswith("ADM_ADD_FILE_SVC__"):
            country = state.replace("ADM_ADD_FILE_SVC__", "")
            USER_STATE[user.id] = f"WAITING_FILE__{country}__{service}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ sᴇɴᴅ .ᴛxᴛ / .ᴄsᴠ / .xʟsx\n└─❏",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        elif state.startswith("ADM_ADD_TYPE_SVC__"):
            country = state.replace("ADM_ADD_TYPE_SVC__", "")
            USER_STATE[user.id] = f"TYPING_NUMBERS__{country}__{service}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ sᴇɴᴅ ɴᴜᴍʙᴇʀs, ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ\n└─❏",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        return

    if data in ("adm_svc_custom__file", "adm_svc_custom__type"):
        mode  = "file" if "file" in data else "type"
        state = USER_STATE.get(user.id, "")
        if mode == "file" and state.startswith("ADM_ADD_FILE_SVC__"):
            country = state.replace("ADM_ADD_FILE_SVC__", "")
            USER_STATE[user.id] = f"ADM_CUSTOM_SVC_FILE__{country}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴄᴜsᴛᴏᴍ sᴇʀᴠɪᴄᴇ\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇɴᴅ sᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        elif mode == "type" and state.startswith("ADM_ADD_TYPE_SVC__"):
            country = state.replace("ADM_ADD_TYPE_SVC__", "")
            USER_STATE[user.id] = f"ADM_CUSTOM_SVC_TYPE__{country}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴄᴜsᴛᴏᴍ sᴇʀᴠɪᴄᴇ\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇɴᴅ sᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏",
                reply_markup=cancel_state_markup("adm_numbers"),
            )
        return


async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()

    if not is_admin(user.id):
        if is_banned(user.id):
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

    if state == "ADM_ADD_COUNTRY":
        country = text.strip()
        USER_STATE[user.id] = f"ADM_ADD_METHOD__{country}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ ᴄʜᴏᴏsᴇ ᴍᴇᴛʜᴏᴅ\n└─❏",
            reply_markup=_markup([
                [
                    _btn("ᴜᴘʟᴏᴀᴅ ғɪʟᴇ", cb="adm_addmethod_file"),
                    _btn("ᴛʏᴘᴇ ɴᴜᴍʙᴇʀs", cb="adm_addmethod_type"),
                ],
                [_btn("ᴄᴀɴᴄᴇʟ", cb="adm_cancel_state")],
            ]),
        )
        return

    if state and state.startswith("ADM_ADD_METHOD__"):
        await send_msg(context.bot, update.effective_chat.id, "ᴜsᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ᴀʙᴏᴠᴇ.")
        return

    if state and state.startswith("ADM_CUSTOM_SVC_FILE__"):
        country = state.replace("ADM_CUSTOM_SVC_FILE__", "")
        service = text.strip()
        USER_STATE[user.id] = f"WAITING_FILE__{country}__{service}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ sᴇɴᴅ ᴛʜᴇ ғɪʟᴇ\n└─❏",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if state and state.startswith("ADM_CUSTOM_SVC_TYPE__"):
        country = state.replace("ADM_CUSTOM_SVC_TYPE__", "")
        service = text.strip()
        USER_STATE[user.id] = f"TYPING_NUMBERS__{country}__{service}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ sᴇɴᴅ ɴᴜᴍʙᴇʀs, ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ\n└─❏",
            reply_markup=cancel_state_markup("adm_numbers"),
        )
        return

    if state and state.startswith("TYPING_NUMBERS__"):
        parts   = state.replace("TYPING_NUMBERS__", "").split("__", 1)
        country = parts[0]
        service = parts[1] if len(parts) > 1 else "All"
        nums    = [
            re.sub(r"\D", "", line)
            for line in text.splitlines()
            if re.sub(r"\D", "", line.strip())
        ]
        nums    = [n for n in nums if 7 <= len(n) <= 15]
        count, dupes = 0, 0
        for n in nums:
            try:
                db.execute(
                    "INSERT INTO numbers (country, number, service) VALUES (?, ?, ?)",
                    (country, n, service),
                )
                count += 1
            except Exception:
                dupes += 1
        USER_STATE.pop(user.id, None)
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴅᴏɴᴇ\n├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n├─❏ sᴇʀᴠɪᴄᴇ : {service}\n├─❏ ᴀᴅᴅᴇᴅ  : {count}\n├─❏ ᴅᴜᴘᴇs  : {dupes}\n└─❏",
            reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_numbers")]]),
        )
        return


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    if not is_admin(user.id):
        return
    state = USER_STATE.get(user.id)
    if not state or not state.startswith("WAITING_FILE__"):
        return
    parts   = state.replace("WAITING_FILE__", "").split("__", 1)
    country = parts[0]
    service = parts[1] if len(parts) > 1 else "All"
    doc     = update.message.document
    if not doc.file_name.endswith((".txt", ".csv", ".xlsx")):
        await send_msg(context.bot, update.effective_chat.id, "ɪɴᴠᴀʟɪᴅ ғɪʟᴇ. ᴜsᴇ .ᴛxᴛ, .ᴄsᴠ, ᴏʀ .xʟsx")
        return
    status = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇssɪɴɢ...")
    try:
        f       = await doc.get_file()
        content = await f.download_as_bytearray()
        nums    = extract_numbers_from_content(content, doc.file_name)
        count, dupes = 0, 0
        for n in nums:
            try:
                db.execute(
                    "INSERT INTO numbers (country, number, service) VALUES (?, ?, ?)",
                    (country, n, service),
                )
                count += 1
            except Exception:
                dupes += 1
        USER_STATE.pop(user.id, None)
        result = (
            f"┌─ ᴅᴏɴᴇ\n"
            f"├─❏ ᴄᴏᴜɴᴛʀʏ : {country}\n"
            f"├─❏ sᴇʀᴠɪᴄᴇ : {service}\n"
            f"├─❏ ғɪʟᴇ   : {doc.file_name}\n"
            f"├─❏ ᴀᴅᴅᴇᴅ  : {count}\n"
            f"├─❏ ᴅᴜᴘᴇs  : {dupes}\n"
            f"└─❏"
        )
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text=result,
                parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_numbers")]]),
            )
        except Exception:
            await send_msg(
                context.bot, update.effective_chat.id, result,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_numbers")]]),
            )
    except Exception as e:
        logger.error(f"Document handler error: {e}")
        await send_msg(context.bot, update.effective_chat.id, "ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ғɪʟᴇ.")
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

    saved_maint = db.get_setting("maintenance")
    if saved_maint == "1":
        maintenance = True

    extra = db.get_setting("extra_admins")
    if extra:
        for eid in extra.split(","):
            eid = eid.strip()
            if eid.isdigit():
                aid = int(eid)
                if aid not in ADMIN_IDS:
                    ADMIN_IDS.append(aid)
    logger.info(f"Admin IDs loaded: {ADMIN_IDS}")

    rows = db.fetchall("SELECT hash FROM otp_history ORDER BY id DESC LIMIT 30000")
    for r in rows:
        otp_cache.add(r["hash"])
    logger.info(f"Loaded {len(otp_cache)} OTP hashes into cache")

    commands = [
        BotCommand("start",  "start"),
        BotCommand("admin",  "admin"),
        BotCommand("cancel", "cancel"),
    ]
    await application.bot.set_my_commands(commands)

    app_web = web.Application()
    app_web.router.add_get("/",       health_handler)
    app_web.router.add_get("/health", health_handler)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health server on port {PORT}")

    application.create_task(sms_worker(application))
    logger.info(f"{BOT_NAME} is live")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    db.init()

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start",  start))
    application.add_handler(CommandHandler("admin",  admin_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))

    logger.info(f"Starting {BOT_NAME}...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
