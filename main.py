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

def detect_phone_column(df: pd.DataFrame) -> str:
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

    n = name.lower()
    if n.endswith((".csv", ".xlsx", ".xls")):
        try:
            df  = load_file_df(data, name)
            col = detect_phone_column(df)
            if col:
                raws = df[col].dropna().astype(str).tolist()
            else:
                raws = []
                for col2 in df.columns:
                    raws += df[col2].dropna().astype(str).tolist()
        except Exception:
            raws = data.decode("utf-8", errors="ignore").splitlines()
    elif n.endswith(".txt"):
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
                flag     TEXT    DEFAULT '🌐',
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
            CREATE INDEX IF NOT EXISTS idx_otp_added    ON otp_history(added_at);
            CREATE INDEX IF NOT EXISTS idx_users_banned ON users(is_banned);
            CREATE INDEX IF NOT EXISTS idx_nums_country ON numbers(country);
            CREATE INDEX IF NOT EXISTS idx_nums_used    ON numbers(is_used);
            CREATE INDEX IF NOT EXISTS idx_nums_service ON numbers(service);
        """)
        try:
            await conn.execute("ALTER TABLE numbers ADD COLUMN IF NOT EXISTS flag TEXT DEFAULT '🌐'")
        except Exception:
            pass
    logger.info("Database initialised")

async def get_setting(key, default=""):
    row = await db_fetchone("SELECT value FROM settings WHERE key=$1", key)
    return row["value"] if row else default

async def set_setting(key, value):
    await db_execute(
        "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
        key, value,
    )

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

def _btn(text, *, cb=None, url=None, style=None):
    if url is not None:
        return InlineKeyboardButton(text, url=url, style=style)
    return InlineKeyboardButton(text, callback_data=cb, style=style)

def _markup(rows):
    return InlineKeyboardMarkup(rows)

def join_markup_dynamic(statuses):
    rows = []
    pair = []
    for channel, (label, link) in CHANNEL_LABELS.items():
        joined = statuses.get(channel, False)
        btn    = _btn(label, cb=f"joined_noop__{channel}", style="primary") if joined else _btn(label, url=link, style="danger")
        pair.append(btn)
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([_btn("ᴠᴇʀɪғʏ", cb="check_join", style="success")])
    return _markup(rows)

def main_menu_markup(user_id=None):
    rows = [
        [_btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", cb="menu_get_number", style="success")],
        [
            _btn("sᴀɢᴇ",    url=MAIN_CHANNEL_LINK,   style="primary"),
            _btn("ᴍʀᴀғʀɪx",  url=BACKUP_CHANNEL_LINK, style="primary"),
        ],
        [
            _btn("ᴏxᴇʟʟᴀʙs", url=THIRD_CHANNEL_LINK,  style="primary"),
            _btn("ᴏʀᴀᴄʀᴏɴ",  url=FOURTH_CHANNEL_LINK, style="primary"),
        ],
    ]
    if user_id and is_admin(user_id):
        rows.append([_btn("ᴀᴅᴍɪɴ", cb="menu_admin", style="danger")])
    return _markup(rows)

def otp_markup():
    return _markup([
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,            style="success"),
            _btn("ᴍʀᴀғʀɪx",     url=BACKUP_CHANNEL_LINK, style="primary"),
        ],
        [
            _btn("ᴏxᴇʟʟᴀʙs", url=THIRD_CHANNEL_LINK,  style="primary"),
            _btn("ᴏʀᴀᴄʀᴏɴ",  url=FOURTH_CHANNEL_LINK, style="primary"),
        ],
        [_btn("sᴀɢᴇ", url=MAIN_CHANNEL_LINK, style="primary")],
    ])

def stock_markup():
    return _markup([
        [
            _btn("ɢᴇᴛ ɴᴜᴍʙᴇʀ", url=BOT_LINK,       style="success"),
            _btn("ᴏᴛᴘ ɢʀᴏᴜᴘ",   url=OTP_GROUP_LINK, style="success"),
        ],
    ])

def number_assigned_markup(country, service, num_id):
    return _markup([
        [
            _btn("ᴄʜᴀɴɢᴇ ɴᴜᴍʙᴇʀ", cb=f"chgn__{country}__{service}__{num_id}", style="success"),
            _btn("ᴏᴛᴘ ɢʀᴏᴜᴘ",     url=OTP_GROUP_LINK,                          style="primary"),
        ],
        [_btn("ʙᴀᴄᴋ", cb="menu_back", style="danger")],
    ])

def admin_markup():
    return _markup([
        [
            _btn("ᴀᴅᴅ ɴᴜᴍʙᴇʀs",    cb="adm_add_numbers",    style="success"),
            _btn("ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs", cb="adm_delete_numbers", style="danger"),
        ],
        [_btn("sᴛᴀᴛᴜs", cb="adm_status", style="primary")],
        [_btn("ʙᴀᴄᴋ",   cb="menu_back",  style="danger")],
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
            _btn("ᴜᴘʟᴏᴀᴅ ғɪʟᴇ",   cb="adm_addmethod_file", style="primary"),
            _btn("ᴛʏᴘᴇ ɴᴜᴍʙᴇʀs", cb="adm_addmethod_type", style="primary"),
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
    buttons.append([_btn("ᴄᴜsᴛᴏᴍ", cb="adm_svc_custom", style="primary")])
    buttons.append([_btn("ᴄᴀɴᴄᴇʟ",  cb="adm_cancel_state", style="danger")])
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
        row_buf.append(_btn(sc(r["service"]), cb=f"gns__{r['service']}", style="success"))
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
        label = f"{r['flag']} {sc(r['country'])}"
        row_buf.append(_btn(label, cb=f"gnc__{r['country']}__{service}", style="success"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ʙᴀᴄᴋ", cb=f"gns__{service}", style="danger")])
    return rows, _markup(buttons)

async def build_delete_service_grid():
    rows = await db_fetchall("SELECT service, COUNT(*) AS cnt FROM numbers GROUP BY service ORDER BY service")
    if not rows:
        return None, None
    buttons = []
    row_buf = []
    for r in rows:
        row_buf.append(_btn(sc(r["service"]), cb=f"del_svc__{r['service']}", style="danger"))
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
        label = f"{r['flag']} {sc(r['country'])}"
        row_buf.append(_btn(label, cb=f"del_cntry__{service}__{r['country']}", style="danger"))
        if len(row_buf) == 2:
            buttons.append(row_buf)
            row_buf = []
    if row_buf:
        buttons.append(row_buf)
    buttons.append([_btn("ᴀʟʟ ᴄᴏᴜɴᴛʀɪᴇs", cb=f"del_cntry__{service}__ALL", style="danger")])
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
        "INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) "
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
        "INSERT INTO cooldowns (user_id, ts) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET ts=$2",
        user_id, int(time.time()),
    )

def get_country_info_from_number(number):
    clean = re.sub(r"\D", "", str(number))
    _, iso, name, _ = parse_phone(clean)
    if iso:
        return name, iso_to_flag(iso)
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
        f"┌─ ɴᴇᴡ sᴛᴏᴄᴋ ᴀᴅᴅᴇᴅ\n"
        f"├─❏ ᴄᴏᴜɴᴛʀʏ  : {flag} {sc(country)}\n"
        f"├─❏ sᴇʀᴠɪᴄᴇ  : {sc(service)}\n"
        f"├─❏ ɴᴜᴍʙᴇʀs  : {count}\n"
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
        logger.error(f"Channel notify error: {e}")

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

def format_otp_message(row, otp):
    masked           = mask_number(row["number"])
    country_name, flag = get_country_info_from_number(row["number"])
    sms_txt          = (row.get("sms") or "").strip()
    service          = sc((row.get("service") or "Unknown").strip())
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
    return (
        f"┌─ ᴀᴅᴍɪɴ\n"
        f"├─❏ ᴍᴀɴᴀɢᴇ ɴᴜᴍʙᴇʀ ᴅᴀᴛᴀʙᴀsᴇ\n"
        f"└─❏"
    )

async def status_text():
    total  = await db_fetchval("SELECT COUNT(*) FROM numbers") or 0
    avail  = await db_fetchval("SELECT COUNT(*) FROM numbers WHERE is_used=FALSE") or 0
    users  = await db_fetchval("SELECT COUNT(*) FROM users") or 0
    otps   = await db_fetchval("SELECT COUNT(*) FROM otp_history") or 0
    online = "ᴏɴʟɪɴᴇ" if worker_info["logged_in"] else "ᴏғғʟɪɴᴇ"
    return (
        f"┌─ sᴛᴀᴛᴜs\n"
        f"├─❏ ᴡᴏʀᴋᴇʀ     : {online}\n"
        f"├─❏ ᴏᴛᴘs ᴛᴏᴅᴀʏ : {worker_info['otps_today']}\n"
        f"├─❏ ʟᴀsᴛ ᴏᴛᴘ   : {worker_info['last_otp']}\n"
        f"├─❏ ɴᴜᴍʙᴇʀs    : {total} ᴛᴏᴛᴀʟ / {avail} ᴀᴠᴀɪʟ\n"
        f"├─❏ ᴜsᴇʀs       : {users}\n"
        f"├─❏ ᴏᴛᴘ ʜɪsᴛᴏʀʏ : {otps}\n"
        f"├─❏ ᴇʀʀᴏʀs      : {worker_info['errors']}\n"
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
    def __init__(self):
        self._session        = None
        self._logged_in      = False
        self._sesskey        = ""
        self._login_attempts = 0
        self._next_login_at  = 0
        self._last_activity  = 0

    async def _get_session(self):
        if self._session is None or self._session.closed:
            connector    = aiohttp.TCPConnector(ssl=True, limit=10, ttl_dns_cache=300, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "User-Agent":               "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
                    "Accept-Language":          "en-CI,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control":             "max-age=0",
                },
                timeout=aiohttp.ClientTimeout(total=60, connect=20),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
        return self._session

    async def login(self):
        if time.time() < self._next_login_at:
            return False
        try:
            sess       = await self._get_session()
            login_html = ""
            async with sess.get(PANEL_LOGIN_PAGE, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                login_html = await resp.text(errors="replace")
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
            form_data.add_field("capt", capt)

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
                    redirect_url = location if location.startswith("http") else (f"{PANEL_BASE}{location}" if location.startswith("/") else f"{PANEL_BASE}/")
                    try:
                        async with sess.get(redirect_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as rr:
                            if "login" in str(rr.url).lower():
                                return False
                    except Exception as e:
                        logger.warning(f"Post-login redirect: {e}")

                    self._logged_in      = True
                    self._login_attempts = 0
                    self._next_login_at  = 0
                    self._last_activity  = time.time()
                    await self._fetch_sesskey(sess)
                    return True

                self._login_attempts += 1
                backoff = min(30 * (2 ** (self._login_attempts - 1)), 1800)
                self._next_login_at = time.time() + backoff
                return False
        except Exception as e:
            logger.error(f"Login: {e}")
            self._login_attempts += 1
            backoff = min(30 * (2 ** (self._login_attempts - 1)), 1800)
            self._next_login_at = time.time() + backoff
            return False

    async def _fetch_sesskey(self, sess):
        try:
            async with sess.get(PANEL_CDR_URL, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as resp:
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
            logger.error(f"sesskey: {e}")

    async def keepalive(self):
        try:
            sess = await self._get_session()
            async with sess.get(PANEL_DASHBOARD_URL, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if "login" in str(resp.url).lower():
                    self._logged_in = False
                    return False
                self._last_activity = time.time()
                return True
        except Exception as e:
            logger.error(f"Keepalive: {e}")
            return False

    async def fetch_cdr(self):
        try:
            sess   = await self._get_session()
            params = {
                "sEcho":         "1",
                "iColumns":      "7",
                "sColumns":      ".......",
                "iDisplayStart": "0",
                "iDisplayLength":"25",
                "mDataProp_0":   "0",
                "mDataProp_1":   "1",
                "mDataProp_2":   "2",
                "mDataProp_3":   "3",
                "mDataProp_4":   "4",
                "mDataProp_5":   "5",
                "mDataProp_6":   "6",
                "bSortable_0":   "true",
                "bSortable_1":   "true",
                "bSortable_2":   "true",
                "bSortable_3":   "true",
                "bSortable_4":   "true",
                "bSortable_5":   "true",
                "bSortable_6":   "true",
                "iSortCol_0":    "0",
                "sSortDir_0":    "desc",
                "iSortingCols":  "1",
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
                    "Sec-Fetch-Site":   "same-origin",
                    "Sec-Fetch-Mode":   "cors",
                    "Sec-Fetch-Dest":   "empty",
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
            logger.error(f"Fetch CDR: {e}")
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
                        await notify_admins(app, "ᴘᴀɴᴇʟ ʟᴏɢɪɴ ғᴀɪʟᴇᴅ")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                worker_info["logged_in"]  = True
                worker_info["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worker_info["errors"]     = 0
                await notify_admins(app, f"ᴘᴀɴᴇʟ ʟᴏɢɪɴ ᴏᴋ — {BOT_NAME} ɪs ʟɪᴠᴇ")
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
                await notify_admins(app, "sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ — ʀᴇʟᴏɢɢɪɴɢ")
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
                            "INSERT INTO otp_history (hash, number, otp, service, sms, range_name) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (hash) DO NOTHING",
                            h, number, otp, row.get("service", ""), sms, row.get("range", ""),
                        )
                        await db_execute(
                            "INSERT INTO traffic (range_name, number, sms, otp, service, received_at) VALUES ($1,$2,$3,$4,$5,$6)",
                            row.get("range", ""), number, sms, otp, row.get("service", ""), date,
                        )
                        worker_info["last_otp"]    = datetime.now().strftime("%H:%M:%S")
                        worker_info["otps_today"] += 1
                    except Exception as row_err:
                        logger.error(f"Row: {row_err}")
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
            logger.error(f"Worker: {e}")
            if worker_info["errors"] % 5 == 0:
                await notify_admins(app, f"ᴡᴏʀᴋᴇʀ ᴇʀʀᴏʀ: {e}")
            await asyncio.sleep(15)

    worker_info["running"] = False

JOIN_TEXT    = f"┌─ {BOT_NAME}\n├─❏ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ\n└─❏ ᴛᴀᴘ ᴠᴇʀɪғʏ ᴡʜᴇɴ ᴅᴏɴᴇ"
WELCOME_TEXT = f"┌─ {BOT_NAME}\n├─❏ ʟɪᴠᴇ ᴏᴛᴘ ᴍᴏɴɪᴛᴏʀɪɴɢ 24/7\n└─❏"
ADMIN_TEXT   = f"┌─ {BOT_NAME}\n├─❏ ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, ᴀᴅᴍɪɴ\n└─❏"
GET_NUM_TEXT = f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user)
    if not is_admin(user.id):
        if await is_banned_user(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ.")
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "sʟᴏᴡ ᴅᴏᴡɴ.")
            return
        if maintenance:
            await send_msg(context.bot, update.effective_chat.id, "ʙᴏᴛ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.")
            return
        joined = await check_membership(context.bot, user.id)
        if not joined:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await send_msg(context.bot, update.effective_chat.id, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            return
    welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
    await send_msg(context.bot, update.effective_chat.id, welcome, reply_markup=main_menu_markup(user.id))

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_STATE.pop(update.effective_user.id, None)
    await send_msg(context.bot, update.effective_chat.id, "ᴄᴀɴᴄᴇʟʟᴇᴅ.", reply_markup=main_menu_markup(update.effective_user.id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = query.from_user
    data  = query.data
    await query.answer()

    if not is_admin(user.id) and await is_banned_user(user.id) and data != "check_join":
        await query.answer("ʙᴀɴɴᴇᴅ.", show_alert=True)
        return

    if data.startswith("joined_noop__"):
        return

    if data == "check_join":
        joined = await check_membership(context.bot, user.id)
        if joined:
            await register_user(user)
            welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
            await edit_msg(query, welcome, reply_markup=main_menu_markup(user.id))
        else:
            statuses = await check_membership_per_channel(context.bot, user.id)
            await edit_msg(query, JOIN_TEXT, reply_markup=join_markup_dynamic(statuses))
            await query.answer("ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ғɪʀsᴛ.", show_alert=True)
        return

    if data == "menu_back":
        welcome = ADMIN_TEXT if is_admin(user.id) else WELCOME_TEXT
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
            await query.answer("ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.", show_alert=True)
            return
        _, markup = await build_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ɴᴜᴍʙᴇʀs\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ\n└─❏", reply_markup=back_to_menu())
            return
        await edit_msg(query, GET_NUM_TEXT, reply_markup=markup)
        return

    if data.startswith("gns__"):
        service = data[5:]
        _, markup = await build_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs.", show_alert=True)
            return
        await edit_msg(query, f"┌─ ɢᴇᴛ ɴᴜᴍʙᴇʀ\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
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
                    await query.answer("ɴᴏ ɴᴜᴍʙᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or "🌐"

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
                    await query.answer("ɴᴏ ᴍᴏʀᴇ ɴᴜᴍʙᴇʀs.", show_alert=True)
                    return
                await conn.execute(
                    "UPDATE numbers SET is_used=TRUE, used_by=$1, use_date=NOW() WHERE id=$2",
                    user.id, row["id"],
                )
                num_id = row["id"]
                number = row["number"]
                flag   = row["flag"] or "🌐"

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

    if data == "adm_status":
        await edit_msg(query, await status_text(), reply_markup=back_to_admin())
        return

    if data == "adm_add_numbers":
        USER_STATE[user.id] = "ADM_PICK_SERVICE"
        await edit_msg(
            query,
            "┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏",
            reply_markup=service_picker_markup(),
        )
        return

    if data == "adm_delete_numbers":
        _, markup = await build_delete_service_grid()
        if markup is None:
            await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ ɴᴏ ɴᴜᴍʙᴇʀs ɪɴ ᴅʙ\n└─❏", reply_markup=back_to_admin())
            return
        await edit_msg(query, "┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʟᴇᴄᴛ sᴇʀᴠɪᴄᴇ\n└─❏", reply_markup=markup)
        return

    if data.startswith("del_svc__"):
        service = data[9:]
        _, markup = await build_delete_country_grid(service)
        if markup is None:
            await query.answer("ɴᴏᴛʜɪɴɢ ғᴏᴜɴᴅ.", show_alert=True)
            return
        await edit_msg(query, f"┌─ ᴅᴇʟᴇᴛᴇ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service) if service != 'ALL' else 'ᴀʟʟ'}\n├─❏ sᴇʟᴇᴄᴛ ᴄᴏᴜɴᴛʀʏ\n└─❏", reply_markup=markup)
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

        await edit_msg(
            query,
            f"┌─ ᴅᴇʟᴇᴛᴇᴅ\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service) if service != 'ALL' else 'ᴀʟʟ'}\n├─❏ ᴄᴏᴜɴᴛʀʏ : {sc(country) if country != 'ALL' else 'ᴀʟʟ'}\n├─❏ ʀᴇᴍᴏᴠᴇᴅ : {deleted}\n└─❏",
            reply_markup=back_to_admin(),
        )
        return

    if data.startswith("adm_svc__"):
        service = data[9:]
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        await edit_msg(
            query,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏsᴇ ᴍᴇᴛʜᴏᴅ\n└─❏",
            reply_markup=method_picker_markup(),
        )
        return

    if data == "adm_svc_custom":
        USER_STATE[user.id] = "ADM_CUSTOM_SVC"
        await edit_msg(
            query,
            "┌─ ᴄᴜsᴛᴏᴍ sᴇʀᴠɪᴄᴇ\n├─❏ sᴇɴᴅ sᴇʀᴠɪᴄᴇ ɴᴀᴍᴇ\n└─❏",
            reply_markup=cancel_state_markup("adm_add_numbers"),
        )
        return

    if data == "adm_addmethod_file":
        state = USER_STATE.get(user.id, "")
        if state.startswith("ADM_PICK_METHOD__"):
            service = state[17:]
            USER_STATE[user.id] = f"WAITING_FILE__{service}"
            await send_msg(
                context.bot, user.id,
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇɴᴅ ғɪʟᴇ (.ᴛxᴛ .ᴄsᴠ .xʟsx .xʟs)\n└─❏ ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛs ᴄᴏᴜɴᴛʀʏ",
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
                f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ sᴇɴᴅ ɴᴜᴍʙᴇʀs, ᴏɴᴇ ᴘᴇʀ ʟɪɴᴇ\n└─❏ ᴀᴜᴛᴏ-ᴅᴇᴛᴇᴄᴛs ᴄᴏᴜɴᴛʀʏ",
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
                try:
                    r = await conn.execute(
                        "INSERT INTO numbers (country, flag, number, service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                        country, flag, num, service,
                    )
                    if r == "INSERT 0 1":
                        total_added += 1
                        added_for.append(num)
                    else:
                        total_dupes += 1
                except Exception:
                    total_dupes += 1
            if added_for:
                by_country[iso] = {"name": country, "flag": flag, "numbers": added_for}

        for num in result["unknown"]:
            try:
                r = await conn.execute(
                    "INSERT INTO numbers (country, flag, number, service) VALUES ($1,$2,$3,$4) ON CONFLICT (number) DO NOTHING",
                    "Unknown", "🌐", num, service,
                )
                if r == "INSERT 0 1":
                    total_added += 1
                else:
                    total_dupes += 1
            except Exception:
                total_dupes += 1

    return total_added, total_dupes, by_country


async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    text  = (update.message.text or "").strip()

    if not is_admin(user.id):
        if await is_banned_user(user.id):
            await send_msg(context.bot, update.effective_chat.id, "ʙᴀɴɴᴇᴅ.")
            return
        if is_flooded(user.id):
            await send_msg(context.bot, update.effective_chat.id, "sʟᴏᴡ ᴅᴏᴡɴ.")
            return
        return

    state = USER_STATE.get(user.id)
    if not state:
        return

    if state == "ADM_CUSTOM_SVC":
        service = text.strip()
        USER_STATE[user.id] = f"ADM_PICK_METHOD__{service}"
        await send_msg(
            context.bot, update.effective_chat.id,
            f"┌─ ᴀᴅᴅ ɴᴜᴍʙᴇʀs\n├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n├─❏ ᴄʜᴏᴏsᴇ ᴍᴇᴛʜᴏᴅ\n└─❏",
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

        status_msg = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇssɪɴɢ...")
        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)
        USER_STATE.pop(user.id, None)

        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}"
            for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇs ᴅᴇᴛᴇᴄᴛᴇᴅ"

        result_text = (
            f"┌─ ᴅᴏɴᴇ\n"
            f"├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n"
            f"├─❏ ᴀᴅᴅᴇᴅ   : {total_added}\n"
            f"├─❏ ᴅᴜᴘᴇs   : {total_dupes}\n"
            f"{countries_summary}\n"
            f"└─❏"
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

        for iso, v in by_country.items():
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
        await send_msg(context.bot, update.effective_chat.id, "ɪɴᴠᴀʟɪᴅ ғɪʟᴇ ᴛʏᴘᴇ. ᴜsᴇ .ᴛxᴛ .ᴄsᴠ .xʟsx .xʟs")
        return

    status_msg = await send_msg(context.bot, update.effective_chat.id, "ᴘʀᴏᴄᴇssɪɴɢ...")
    USER_STATE.pop(user.id, None)

    try:
        f       = await doc.get_file()
        content = bytes(await f.download_as_bytearray())

        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, extract_numbers_smart, content, name)

        total_added, total_dupes, by_country = await _insert_numbers_bulk(service, result)

        countries_summary = "\n".join(
            f"├─❏ {v['flag']} {sc(v['name'])} : {len(v['numbers'])}"
            for v in by_country.values()
        ) or "├─❏ ɴᴏ ᴄᴏᴜɴᴛʀɪᴇs ᴅᴇᴛᴇᴄᴛᴇᴅ"

        result_text = (
            f"┌─ ᴅᴏɴᴇ\n"
            f"├─❏ sᴇʀᴠɪᴄᴇ : {sc(service)}\n"
            f"├─❏ ғɪʟᴇ    : {name}\n"
            f"├─❏ ᴛᴏᴛᴀʟ   : {result['total']}\n"
            f"├─❏ ᴀᴅᴅᴇᴅ   : {total_added}\n"
            f"├─❏ ᴅᴜᴘᴇs   : {total_dupes}\n"
            f"{countries_summary}\n"
            f"└─❏"
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

        for iso, v in by_country.items():
            asyncio.create_task(broadcast_stock(context.application, v["name"], v["flag"], service, len(v["numbers"]), v["numbers"]))

    except Exception as e:
        logger.error(f"Document handler: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text="ᴇʀʀᴏʀ ᴘʀᴏᴄᴇssɪɴɢ ғɪʟᴇ.",
                parse_mode=ParseMode.HTML,
                reply_markup=_markup([[_btn("ʙᴀᴄᴋ", cb="adm_back", style="danger")]]),
            )
        except Exception:
            pass


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

    application.create_task(sms_worker(application))
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))

    logger.info(f"Starting {BOT_NAME}...")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
