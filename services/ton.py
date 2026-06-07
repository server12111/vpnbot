import aiohttp
from config import TON_CENTER_API, TON_WALLET

API_URL = "https://toncenter.com/api/v2"

async def get_transactions(limit: int = 50) -> list:
    params = {
        "address": TON_WALLET,
        "limit": limit,
        "api_key": TON_CENTER_API,
    }
    async with aiohttp.ClientSession() as s:
        r = await s.get(f"{API_URL}/getTransactions", params=params)
        resp = await r.json()
        if resp.get("ok"):
            return resp.get("result", [])
        return []

async def find_transaction_by_comment(comment: str, min_amount_ton: float) -> bool:
    txs = await get_transactions(limit=100)
    for tx in txs:
        try:
            in_msg = tx.get("in_msg", {})
            msg_data = in_msg.get("msg_data", {})
            text = msg_data.get("text", "") or ""

            # Декодировать base64 комментарий если нужно
            import base64
            try:
                decoded = base64.b64decode(text).decode("utf-8", errors="ignore").strip()
            except Exception:
                decoded = text.strip()

            if comment in decoded or comment in text:
                value = int(in_msg.get("value", 0)) / 1e9  # нанотоны -> TON
                if value >= min_amount_ton * 0.95:  # 5% допуск
                    return True
        except Exception:
            continue
    return False
