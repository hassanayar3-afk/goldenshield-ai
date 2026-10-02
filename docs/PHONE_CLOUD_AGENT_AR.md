# العمل من الهاتف مع GoldenShield

هذا المستودع يحتوي **كل أكواد المشروع** اللازمة للوكيل السحابي.

## ما الموجود على GitHub
- كل ملفات Python والإعدادات والاختبارات والسكربتات والوثائق
- `.env.example` (قالب فارغ)

## ما لن يُرفع أبداً (لحمايتك)
- `.env` الحقيقي (مفاتيح Binance / Telegram / كلمات مرور السيرفر)
- قواعد البيانات والسجلات و`.venv`

## لتستطيع من الهاتف ما يشبه العمل على الحاسوب

### 1) إعداد بيئة السحابة
1. افتح: https://cursor.com/dashboard/cloud-agents
2. اضغط **Environments** / إعداد البيئة
3. اختر المستودع: `goldenshield-ai`
4. أكمل الإعداد (Install dependencies)

### 2) أضف الأسرار (Secrets) — مهم
في نفس صفحة Cloud Agents → **Secrets** أضف هذه المفاتيح بالقيم من جهازك (من ملف `.env` المحلي):

- `WIN_HOST`
- `WIN_USER`
- `WIN_PASSWORD` (أو WinRM إذا كان SSH مغلقاً)
- `WIN_SSH_PRIVATE_KEY` (**مهم**) — إذا كان SSH على VPS يقبل **مفتاحاً فقط** وليس كلمة المرور
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_DEMO_TRADING`
- `EXECUTION_MODE`
- `EXECUTION_BACKEND`

بدون هذه الأسرار يستطيع الوكيل تعديل الكود فقط، ولا يدير السيرفر الحي.

### 2.1) حل «لا يدخل الوكيل إلى السيرفر»

الوكيل يحتاج **قناة واحدة** على الأقل:

| القناة | متى تستخدمها | ما الذي تفعله على VPS (مرة واحدة) |
|--------|----------------|-------------------------------------|
| **SSH + مفتاح** | الأفضل للنشر الكامل | أنشئ زوج مفاتيح، ضع **المفتاح العام** في `C:\Users\<WIN_USER>\.ssh\authorized_keys`، وضع **المفتاح الخاص** في Cursor Secret `WIN_SSH_PRIVATE_KEY` |
| **SSH + كلمة مرور** | إذا فضّلت كلمة المرور | في `C:\ProgramData\ssh\sshd_config`: `PasswordAuthentication yes` ثم `Restart-Service sshd` |
| **WinRM** | إذا SSH محجوب | على VPS (PowerShell كمسؤول): `Enable-PSRemoting -Force`، فعّل Basic auth، وافتح المنفذ **5985** في الجدار الناري للوصول من الإنترنت |

**فحص من الوكيل بعد ضبط الأسرار:**

```bash
python3 scripts/probe_windows_remote.py
python3 scripts/deploy_to_windows.py
```

أو نشر حزمة التشغيل المرئية عبر WinRM:

```bash
python3 scripts/deploy_visible_winrm.py
```

### 3) من Agents على الهاتف
1. افتح https://cursor.com/agents
2. اختر `goldenshield-ai`
3. اكتب مثلاً: `افحص البوت على ويندوز VPS عبر SSH وأصلح أي مشكلة`
4. انتظر انتهاء تقييد GitHub إن ظهر Rate limit ثم أعد المحاولة

## الحسابات
- GitHub: https://github.com/hassanayar3-afk/goldenshield-ai
- Cursor: نفس حساب Pro المرتبط بالإيميل على الجهاز
