"""التحقق من هوية حساب Binance المربوط بالبوت (بدون طباعة أسرار)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
KEEP = r"C:\GoldenShield_Binance"
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"


def run(ssh, cmd, timeout=180):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace")
    print(text[-5000:].encode("ascii", "replace").decode("ascii"))
    return text


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        os.environ["WIN_HOST"],
        username=os.environ["WIN_USER"],
        password=os.environ["WIN_PASSWORD"],
        timeout=45,
        allow_agent=False,
        look_for_keys=False,
    )

    # بصمة محلية للمفتاح فقط للمقارنة (لا نطبع المفتاح)
    local_env = Path(__file__).resolve().parents[1] / ".env"
    local_key = ""
    for line in local_env.read_text(encoding="utf-8").splitlines():
        if line.startswith("BINANCE_API_KEY="):
            local_key = line.split("=", 1)[1].strip()
            break
    local_fp = hashlib.sha256(local_key.encode()).hexdigest()[:16] if local_key else "missing"
    print("LOCAL_KEY_FP", local_fp, "len", len(local_key))

    code = r'''
import hashlib, json
from config.settings import load_settings
from data.exchange_client import get_exchange, reset_exchange

s = load_settings(reload=True)
key = (s.binance_api_key or "")
sec = (s.binance_api_secret or "")
print("REMOTE_KEY_FP", hashlib.sha256(key.encode()).hexdigest()[:16] if key else "missing")
print("REMOTE_KEY_LEN", len(key))
print("REMOTE_SECRET_LEN", len(sec))
print("DEMO_FLAG", bool(s.binance_demo_trading))
print("MODE", s.execution_mode)
print("BACKEND", s.execution_backend)

reset_exchange()
ex = get_exchange()
print("API_HOST_PUBLIC", (ex.urls.get("api") or {}).get("public"))
print("API_HOST_PRIVATE", (ex.urls.get("api") or {}).get("private"))

# معلومات الحساب
info = {}
try:
    # ccxt unified
    bal = ex.fetch_balance()
    info["info_keys"] = list((bal.get("info") or {}).keys())[:40]
    raw = bal.get("info") or {}
    # حقول شائعة للهوية إن وُجدت
    for k in ("uid", "userId", "accountType", "accountTypeName", "email", "nickName", "nickname", "username", "makerCommission", "takerCommission", "canTrade", "canWithdraw", "canDeposit", "updateTime", "accountAlias"):
        if k in raw:
            info[k] = raw.get(k)
    # أحياناً داخل nested
    for nest in ("account", "data", "result"):
        if isinstance(raw.get(nest), dict):
            for k,v in raw[nest].items():
                if k.lower() in {"uid","userid","email","nickname","username","accounttype"}:
                    info[f"{nest}.{k}"] = v
    usdt = bal.get("USDT") or {}
    info["USDT_free"] = usdt.get("free")
    info["USDT_total"] = usdt.get("total")
    nonzero = sorted([(k, float(v)) for k,v in (bal.get("total") or {}).items() if v and float(v) > 0], key=lambda x: -x[1])
    info["top_assets"] = nonzero[:10]
    print("BALANCE_OK", True)
except Exception as e:
    print("BALANCE_ERR", type(e).__name__, str(e)[:300])

# محاولة endpoint إضافية للهوية إن وُجدت في ccxt
for meth in ("fapiPrivateGetAccount", "sapiGetAccountApiTradingStatus", "privateGetAccount"):
    if hasattr(ex, meth):
        try:
            fn = getattr(ex, meth)
            resp = fn()
            if isinstance(resp, dict):
                for k in ("uid","userId","email","nickName","nickname","username","accountAlias","updateTime"):
                    if k in resp and k not in info:
                        info[k] = resp.get(k)
                print("METH_OK", meth, list(resp.keys())[:20])
        except Exception as e:
            print("METH_ERR", meth, type(e).__name__, str(e)[:160])

# نص للبحث عن hassan
blob = json.dumps(info, ensure_ascii=False, default=str).lower()
print("HAS_HASSAN", "hassan" in blob)
print("HAS_AYAR", "ayar" in blob)
print("ACCOUNT_INFO", json.dumps(info, ensure_ascii=False, default=str)[:2000])
'''
    remote = KEEP + r"\_whoami_binance.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote.replace("\\", "/"), "w") as f:
        f.write(code)
    sftp.close()
    out = run(ssh, f'powershell -NoProfile -Command "Set-Location \'{KEEP}\'; $env:PYTHONIOENCODING=\'utf-8\'; & \'{PY}\' _whoami_binance.py"')

    # قارن بصمة المفتاح
    remote_fp = None
    for line in out.splitlines():
        if line.startswith("REMOTE_KEY_FP"):
            remote_fp = line.split()[-1]
    print("KEY_MATCH", local_fp == remote_fp if remote_fp else False)

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
