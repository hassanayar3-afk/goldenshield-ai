# صقر — مشروع مستقل (ليس GoldenShield)

## لماذا ظهر داخل `goldenshield-ai` على GitHub؟

وكيل Cursor Cloud كان مربوطاً بمستودع **GoldenShield AI** في هذه الجلسة.  
كود **صقر** موجود في مجلد `saqr/` فقط — **لا يستورد** ولا يدمج كود GoldenShield (`core/`, `risk/`, …).

هذا **تجميع Git فقط**، وليس دمجاً برمجياً.

## ما الذي تريده: repo باسم «صقر» فقط

أنشئ مستودعاً جديداً على GitHub (مثلاً **`saqr`** أو **`Saqr-AI`**) **Private**، ثم ارفع محتوى هذا المجلد **كجذر** المستودع الجديد:

```powershell
cd C:\Users\acer\saqr
git init
git add .
git commit -m "Initial commit: Saqr AI local stack"
git branch -M main
git remote add origin https://github.com/hassanayar3-afk/saqr.git
git push -u origin main
```

(استبدل رابط `origin` بمستودعك الجديد بعد إنشائه من GitHub → **New repository** → اسم **saqr**.)

## على اللابتوب بدون GitHub

انسخ مجلد `saqr` كاملاً إلى `C:\Users\acer\saqr` — التشغيل **لا يحتاج** GoldenShield.

```powershell
cd C:\Users\acer\saqr
.\run_saqr_local.bat
```
