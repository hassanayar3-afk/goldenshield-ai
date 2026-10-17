# نشر «صقر» على اللابتوب — `C:\Users\acer\saqr`

## لماذا المجلد فارغ على Windows؟

وكيل Cursor Cloud **يعدّل مستودع Git على سيرفر بعيد** — لا يستطيع نسخ الملفات تلقائياً إلى قرص `C:\` على جهازك unless تربط SSH (WIN_HOST) أو تنفّذ النسخ بنفسك.

## الطريقة 1 — Git (مفضّلة)

```powershell
mkdir C:\Users\acer\saqr -Force
cd C:\Users\acer\saqr
git clone https://github.com/hassanayar3-afk/goldenshield-ai.git .
git checkout cursor/saqr-binance-local-dcdf
# المشروع داخل مجلد saqr داخل المستودع:
xcopy /E /I /Y saqr\* C:\Users\acer\saqr\
```

أو است clone في مكان مؤقت ثم انسخ مجلد `saqr` فقط إلى `C:\Users\acer\saqr`.

## الطريقة 2 — تنزيل ZIP من GitHub

1. افتح الفرع `cursor/saqr-binance-local-dcdf` على GitHub.
2. Code → Download ZIP.
3. فك الضغط وانسخ محتويات مجلد **`saqr`** إلى `C:\Users\acer\saqr`.

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
