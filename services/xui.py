import paramiko
import time
import io
from config import SERVERS
import database as db


def _get_server(server_id: str) -> dict:
    for s in SERVERS:
        if s["id"] == server_id:
            return s
    return SERVERS[0]


def get_least_loaded_server() -> dict:
    counts = db.get_active_subs_per_server()
    best = min(SERVERS, key=lambda s: counts.get(s["id"], 0))
    return best


def _run_script(server: dict, script: str) -> str:
    key_path = server["ssh_key"]
    try:
        pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
    except Exception:
        pkey = paramiko.RSAKey.from_private_key_file(key_path)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server["ip"], username=server["ssh_user"], pkey=pkey, timeout=15)

    sftp = client.open_sftp()
    sftp.putfo(io.BytesIO(script.encode()), "/tmp/xui_script.py")
    sftp.close()

    _, stdout, stderr = client.exec_command("sudo python3 /tmp/xui_script.py")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.exec_command("rm -f /tmp/xui_script.py")
    client.close()
    return out if out else err


async def add_client(uuid: str, tg_id: int, days: int, server_id: str = None) -> bool:
    server = _get_server(server_id) if server_id else get_least_loaded_server()
    inbound_id = server["inbound_id"]
    expiry_ms = int((time.time() + days * 86400) * 1000)
    now_ms = int(time.time() * 1000)
    script = f"""
import sqlite3, time
conn = sqlite3.connect('/etc/x-ui/x-ui.db')
cur = conn.cursor()
cur.execute("DELETE FROM client_inbounds WHERE client_id IN (SELECT id FROM clients WHERE uuid=?)", ('{uuid}',))
cur.execute("DELETE FROM clients WHERE uuid=?", ('{uuid}',))
cur.execute(
    "INSERT INTO clients (email, uuid, flow, enable, tg_id, expiry_time, limit_ip, total_gb, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
    ('{tg_id}', '{uuid}', 'xtls-rprx-vision', 1, {tg_id}, {expiry_ms}, 3, 0, {now_ms}, {now_ms})
)
client_id = cur.lastrowid
cur.execute(
    "INSERT INTO client_inbounds (client_id, inbound_id, flow_override, created_at) VALUES (?,?,?,?)",
    (client_id, {inbound_id}, 'xtls-rprx-vision', {now_ms})
)
conn.commit()
conn.close()
print('ok')
"""
    try:
        result = _run_script(server, script)
        return "ok" in result
    except Exception as e:
        print(f"add_client error: {e}")
        return False


async def toggle_client(uuid: str, enable: bool, server_id: str = None) -> bool:
    server = _get_server(server_id) if server_id else SERVERS[0]
    val = 1 if enable else 0
    script = f"""
import sqlite3
conn = sqlite3.connect('/etc/x-ui/x-ui.db')
conn.execute("UPDATE clients SET enable={val} WHERE uuid=?", ('{uuid}',))
conn.commit()
conn.close()
print('ok')
"""
    try:
        result = _run_script(server, script)
        return "ok" in result
    except Exception as e:
        print(f"toggle_client error: {e}")
        return False


async def delete_client(uuid: str, server_id: str = None) -> bool:
    server = _get_server(server_id) if server_id else SERVERS[0]
    script = f"""
import sqlite3
conn = sqlite3.connect('/etc/x-ui/x-ui.db')
conn.execute("DELETE FROM client_inbounds WHERE client_id IN (SELECT id FROM clients WHERE uuid=?)", ('{uuid}',))
conn.execute("DELETE FROM clients WHERE uuid=?", ('{uuid}',))
conn.commit()
conn.close()
print('ok')
"""
    try:
        result = _run_script(server, script)
        return "ok" in result
    except Exception as e:
        print(f"delete_client error: {e}")
        return False


def build_vless_link(uuid: str, server: dict) -> str:
    return (
        f"vless://{uuid}@{server['ip']}:443"
        f"?type=tcp&security=reality&pbk={server['public_key']}"
        f"&fp=firefox&sni=www.microsoft.com&sid={server['short_id']}&flow=xtls-rprx-vision"
        f"#VPN-Bot"
    )
