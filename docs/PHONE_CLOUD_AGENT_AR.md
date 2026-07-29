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
- `WIN_PASSWORD`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_DEMO_TRADING`
- `EXECUTION_MODE`
- `EXECUTION_BACKEND`

بدون هذه الأسرار يستطيع الوكيل تعديل الكود فقط، ولا يدير السيرفر الحي.

### 3) من Agents على الهاتف
1. افتح https://cursor.com/agents
2. اختر `goldenshield-ai`
3. اكتب مثلاً: `افحص البوت على ويندوز VPS عبر SSH وأصلح أي مشكلة`
4. انتظر انتهاء تقييد GitHub إن ظهر Rate limit ثم أعد المحاولة

## الحسابات
- GitHub: https://github.com/hassanayar3-afk/goldenshield-ai
- Cursor: نفس حساب Pro المرتبط بالإيميل على الجهاز
