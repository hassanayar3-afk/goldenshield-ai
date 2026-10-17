# نشر «صقر» على اللابتوب — `C:\Users\acer\saqr`

## لماذا المجلد فارغ على Windows؟

وكيل Cursor Cloud **يعدّل مستودع Git على سيرفر بعيد** — لا يستطيع نسخ الملفات تلقائياً إلى قرص `C:\` على جهازك unless تربط SSH (WIN_HOST) أو تنفّذ النسخ بنفسك.

## الطريقة 1 — مستودع «صقر» فقط (مفضّلة بعد إنشائه)

1. على GitHub: **New repository** → الاسم **`saqr`** (Private).
2. ارفع محتوى مجلد `saqr` كجذر المستودع (انظر **`STANDALONE.md`** في المشروع).

## الطريقة 2 — من مستودع GoldenShield (مؤقت فقط)

إذا كان الكود لا يزال على فرع `cursor/saqr-binance-local-dcdf` داخل `goldenshield-ai`:

- حمّل ZIP من ذلك الفرع وانسخ **محتويات مجلد `saqr` فقط** إلى `C:\Users\acer\saqr`.
- **لا** تشغّل GoldenShield ولا تدمج المجلدين — صقر وحده في `C:\Users\acer\saqr`.

## بعد النسخ

```powershell
cd C:\Users\acer\saqr
copy .env.example .env
# عدّل .env (مفاتيح Binance محلياً — لا ترفعها لـ Git)
.\run_saqr_local.bat
```

## التحقق

يجب أن ترى على الأقل:

- `gateway\main.py`
- `run_saqr_local.bat`
- `terminal_ui\index.html`
- `requirements.txt`
