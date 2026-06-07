import os
import base64
import tempfile
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]


def _decode_key(b64: str) -> str:
    """Декодує base64 SSH ключ у тимчасовий файл, повертає шлях."""
    data = base64.b64decode(b64)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".key", mode="wb")
    tmp.write(data)
    tmp.close()
    os.chmod(tmp.name, 0o600)
    return tmp.name


SERVERS = [
    {
        "id": "s1",
        "ip": os.getenv("S1_IP"),
        "ssh_user": os.getenv("S1_SSH_USER"),
        "ssh_key": _decode_key(os.getenv("S1_SSH_KEY_B64")),
        "inbound_id": int(os.getenv("S1_INBOUND_ID", "1")),
        "public_key": os.getenv("S1_PUBLIC_KEY"),
        "short_id": os.getenv("S1_SHORT_ID"),
    },
    {
        "id": "s2",
        "ip": os.getenv("S2_IP"),
        "ssh_user": os.getenv("S2_SSH_USER"),
        "ssh_key": _decode_key(os.getenv("S2_SSH_KEY_B64")),
        "inbound_id": int(os.getenv("S2_INBOUND_ID", "1")),
        "public_key": os.getenv("S2_PUBLIC_KEY"),
        "short_id": os.getenv("S2_SHORT_ID"),
    },
]

# Тарифы
PLANS = {
    "1w": {"days": 7,   "stars": 50,   "rub": 49,   "ton": 0.5,  "usdt": 0.5,  "name": "1 неделя"},
    "1m": {"days": 30,  "stars": 120,  "rub": 119,  "ton": 1.2,  "usdt": 1.2,  "name": "1 месяц"},
    "3m": {"days": 90,  "stars": 300,  "rub": 299,  "ton": 3.0,  "usdt": 3.0,  "name": "3 месяца"},
    "1y": {"days": 365, "stars": 1000, "rub": 999,  "ton": 10.0, "usdt": 10.0, "name": "1 год"},
}

# Platega
PLATEGA_MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID", "")
PLATEGA_SECRET = os.getenv("PLATEGA_SECRET", "")

# CryptoBot
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")

# TON
TON_CENTER_API = os.getenv("TON_CENTER_API")
TON_WALLET = os.getenv("TON_WALLET")

# Реферальная система
REFERRAL_BONUS_DAYS = 1
TRIAL_DAYS = 1
