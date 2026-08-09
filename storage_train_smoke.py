"""Smoke test training store on VPS from C:\\saqr cwd."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import paramiko

load_dotenv(Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\.env"), override=True)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    os.getenv("WIN_HOST").strip(),
    username=os.getenv("WIN_USER").strip(),
    password=os.getenv("WIN_PASSWORD").strip(),
    timeout=40,
    allow_agent=False,
    look_for_keys=False,
)

cmd = (
    "cmd /c "
    "cd /d C:\\saqr && "
    ".venv\\Scripts\\python.exe -c "
    "\"from app.store import ConversationStore; "
    "from app.training_rules import match_training_lesson, looks_like_teaching; "
    "s=ConversationStore(); "
    "i=s.add_training_lesson('شلون التوصيل؟ => التوصيل حسب المحافظة عيني'); "
    "u=s.add_training_utterance('اختبار ارشيف', source='smoke'); "
    "lessons=s.list_training_lessons(active_only=True, limit=20); "
    "m=match_training_lesson('شلون التوصيل؟', lessons); "
    "print('lesson', i, 'utt', u, 'match', m, 'teach', looks_like_teaching('قولي دزيلي سكرين'))\""
)
_i, o, e = c.exec_command(cmd, timeout=60)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
