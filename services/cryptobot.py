import aiohttp
from config import CRYPTO_BOT_TOKEN

API_URL = "https://pay.crypt.bot/api"
HEADERS = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}

async def create_invoice(amount: float, payload: str, description: str) -> dict | None:
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "payload": payload,
        "description": description,
        "allow_comments": False,
        "allow_anonymous": False,
        "expires_in": 3600,
    }
    async with aiohttp.ClientSession() as s:
        r = await s.post(f"{API_URL}/createInvoice", headers=HEADERS, json=data)
        resp = await r.json()
        if resp.get("ok"):
            return resp["result"]
        return None

async def check_invoice(payload: str) -> bool:
    async with aiohttp.ClientSession() as s:
        r = await s.get(
            f"{API_URL}/getInvoices",
            headers=HEADERS,
            params={"status": "paid"}
        )
        resp = await r.json()
        if not resp.get("ok"):
            return False
        items = resp.get("result", {}).get("items", [])
        for inv in items:
            if inv.get("payload") == payload:
                return True
        return False
