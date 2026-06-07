import sqlite3
import uuid
import random
import string
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = "vpnbot.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                trial_used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                xui_uuid TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                plan TEXT NOT NULL,
                server_id TEXT DEFAULT 's1',
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                plan TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                payload TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS admins (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS referral_bonuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referee_id INTEGER NOT NULL,
                days INTEGER DEFAULT 1,
                given_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS bonus_claims (
                tg_id INTEGER PRIMARY KEY,
                last_claimed TEXT
            );
        """)
        # Миграция: добавляем колонки если их нет
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "referral_code" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        if "referred_by" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if "trial_used" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0")

        sub_cols = {row[1] for row in conn.execute("PRAGMA table_info(subscriptions)").fetchall()}
        if "server_id" not in sub_cols:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN server_id TEXT DEFAULT 's1'")

        # Выдать referral_code всем у кого нет
        users = conn.execute("SELECT tg_id FROM users WHERE referral_code IS NULL").fetchall()
        for u in users:
            code = _generate_referral_code()
            conn.execute("UPDATE users SET referral_code = ? WHERE tg_id = ?", (code, u["tg_id"]))

def get_or_create_user(tg_id: int, username: str = None, referred_by_code: str = None):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if existing:
            return existing, False  # (user, is_new)

        code = _generate_referral_code()
        # Защита от коллизий
        while conn.execute("SELECT 1 FROM users WHERE referral_code = ?", (code,)).fetchone():
            code = _generate_referral_code()

        referrer_id = None
        if referred_by_code:
            ref = conn.execute("SELECT tg_id FROM users WHERE referral_code = ?", (referred_by_code,)).fetchone()
            if ref and ref["tg_id"] != tg_id:
                referrer_id = ref["tg_id"]

        conn.execute(
            "INSERT INTO users (tg_id, username, referral_code, referred_by) VALUES (?, ?, ?, ?)",
            (tg_id, username, code, referrer_id)
        )
        user = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return user, True  # (user, is_new)

def get_user(tg_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()

def mark_trial_used(tg_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET trial_used = 1 WHERE tg_id = ?", (tg_id,))

def get_active_subscription(tg_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE tg_id = ? AND expires_at > datetime('now') ORDER BY expires_at DESC LIMIT 1",
            (tg_id,)
        ).fetchone()

def create_subscription(tg_id: int, plan: str, days: int, server_id: str = "s1") -> tuple:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, xui_uuid, expires_at, server_id FROM subscriptions WHERE tg_id = ? AND expires_at > datetime('now')",
            (tg_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE subscriptions SET expires_at = datetime(expires_at, ? || ' days'), plan = ? WHERE id = ?",
                (str(days), plan, existing["id"])
            )
            return existing["xui_uuid"], existing["server_id"]

        xui_uuid = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        conn.execute(
            "INSERT INTO subscriptions (tg_id, xui_uuid, expires_at, plan, server_id) VALUES (?, ?, ?, ?, ?)",
            (tg_id, xui_uuid, expires_at, plan, server_id)
        )
        return xui_uuid, server_id

def get_active_subs_per_server() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT server_id, COUNT(*) as cnt FROM subscriptions WHERE expires_at > datetime('now') GROUP BY server_id"
        ).fetchall()
        return {row["server_id"]: row["cnt"] for row in rows}

def save_payment(tg_id: int, amount: str, currency: str, plan: str, payload: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO payments (tg_id, amount, currency, plan, payload) VALUES (?, ?, ?, ?, ?)",
            (tg_id, amount, currency, plan, payload)
        )

def confirm_payment(payload: str):
    with get_conn() as conn:
        conn.execute("UPDATE payments SET status = 'paid' WHERE payload = ?", (payload,))

def get_pending_payment(payload: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM payments WHERE payload = ? AND status = 'pending'",
            (payload,)
        ).fetchone()

def get_expiring_soon(hours: int = 24):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE expires_at BETWEEN datetime('now') AND datetime('now', ? || ' hours')",
            (str(hours),)
        ).fetchall()

def get_all_users():
    with get_conn() as conn:
        return conn.execute("SELECT tg_id FROM users").fetchall()

def has_ever_paid(tg_id: int) -> bool:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT 1 FROM payments WHERE tg_id = ? AND status = 'paid' LIMIT 1", (tg_id,)
        ).fetchone()
        return r is not None

def give_referral_bonus(referrer_id: int, referee_id: int, days: int = 1):
    with get_conn() as conn:
        already = conn.execute(
            "SELECT 1 FROM referral_bonuses WHERE referee_id = ?", (referee_id,)
        ).fetchone()
        if already:
            return False
        conn.execute(
            "INSERT INTO referral_bonuses (referrer_id, referee_id, days) VALUES (?, ?, ?)",
            (referrer_id, referee_id, days)
        )
        conn.execute(
            "UPDATE subscriptions SET expires_at = datetime(expires_at, ? || ' days') WHERE tg_id = ? AND expires_at > datetime('now')",
            (str(days), referrer_id)
        )
        return True

def get_user_referrals_count(tg_id: int) -> int:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (tg_id,)
        ).fetchone()
        return r["cnt"] if r else 0

# --- Admins ---
def get_admin_ids() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT tg_id FROM admins").fetchall()
        return [r["tg_id"] for r in rows]

def add_admin(tg_id: int, username: str = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins (tg_id, username) VALUES (?, ?)",
            (tg_id, username)
        )

def remove_admin(tg_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE tg_id = ?", (tg_id,))

def get_all_admins():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM admins").fetchall()

# --- Settings ---
def get_setting(key: str, default: str = None) -> str:
    with get_conn() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r["value"] if r else default

def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

# --- Stats ---
def can_claim_bonus(tg_id: int) -> bool:
    with get_conn() as conn:
        r = conn.execute("SELECT tg_id FROM bonus_claims WHERE tg_id = ?", (tg_id,)).fetchone()
        return r is None  # Только один раз

def claim_bonus(tg_id: int) -> bool:
    if not can_claim_bonus(tg_id):
        return False
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO bonus_claims (tg_id, last_claimed) VALUES (?, datetime('now'))",
            (tg_id,)
        )
    return True

def get_stats() -> dict:
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        active_subs = conn.execute(
            "SELECT COUNT(*) as c FROM subscriptions WHERE expires_at > datetime('now')"
        ).fetchone()["c"]
        new_today = conn.execute(
            "SELECT COUNT(*) as c FROM users WHERE created_at >= date('now')"
        ).fetchone()["c"]
        new_week = conn.execute(
            "SELECT COUNT(*) as c FROM users WHERE created_at >= date('now', '-7 days')"
        ).fetchone()["c"]
        total_paid = conn.execute(
            "SELECT COUNT(*) as c FROM payments WHERE status = 'paid'"
        ).fetchone()["c"]

        earnings = {}
        rows = conn.execute(
            "SELECT currency, SUM(CAST(amount AS REAL)) as total FROM payments WHERE status = 'paid' GROUP BY currency"
        ).fetchall()
        for r in rows:
            earnings[r["currency"]] = round(r["total"], 2)

        total_referrals = conn.execute("SELECT COUNT(*) as c FROM referral_bonuses").fetchone()["c"]

        return {
            "total_users": total_users,
            "active_subs": active_subs,
            "new_today": new_today,
            "new_week": new_week,
            "total_paid": total_paid,
            "earnings": earnings,
            "total_referrals": total_referrals,
        }
