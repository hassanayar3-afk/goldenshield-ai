from pathlib import Path
import os
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
token = os.getenv("TELEGRAM_TOKEN")
chat = os.getenv("TELEGRAM_CHAT_ID")
text = """طريقة أقصر (انسخ كل سطر كما هو):

1)
mkdir %USERPROFILE%\\GoldenShield

2)
cd /d %USERPROFILE%\\Downloads

3)
tar -xf goldenshield_windows_deploy.zip -C %USERPROFILE%\\GoldenShield

4)
dir %USERPROFILE%\\GoldenShield\\main.py

إذا ظهر مسار ينتهي بـ main.py اكتب هنا: موجود
"""
print(
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text},
        timeout=30,
    )
    .json()
    .get("ok")
)
