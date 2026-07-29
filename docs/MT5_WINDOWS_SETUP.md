# تفعيل MetaTrader 5 على Windows (XM)

## لماذا Windows؟
مكتبة `MetaTrader5` الرسمية تعمل مع طرفية MT5 على **Windows فقط**.  
سيرفر Contabo الحالي (`169.58.8.253`) **Linux** — لذلك الإشارات paper هناك، والتنفيذ الحقيقي يحتاج VPS ويندوز.

## خطواتك
1. اشترِ Contabo **Windows Server** (أو أي VPS ويندوز).
2. ثبّت [MetaTrader 5](https://www.metatrader5.com/) وسجّل:
   - Login: من `.env` → `MT5_LOGIN`
   - Server: `XMGlobal-MT5 10`
   - Password: كلمة تداول الحساب
3. اترك الطرفية مفتوحة ومتصلة 24/7.
4. انسخ المشروع إلى السيرفر أو أعد النشر إليه.
5. في `.env` على Windows:

```env
EXECUTION_MODE=live
EXECUTION_BACKEND=mt5
MT5_ENABLED=true
MT5_LOGIN=345814054
MT5_SERVER=XMGlobal-MT5 10
MT5_PASSWORD=********
MANUAL_ENTRY_REQUIRED=false
AUTO_ENTRY_MIN_PERCENT=90
```

6. ثبّت الحزمة:

```powershell
pip install MetaTrader5
```

7. شغّل البوت. الدخول التلقائي من **90/100 فما فوق**.
   الإشارات 75–89 تظهر للتنبيه/الدخول اليدوي من تيليجرام.

## تحذير
- ابدأ بحساب **Demo** إن وُجد قبل التحويل للحقيقي.
- غيّر كلمة المرور لأنها ظهرت في الشات.
- لا تفعّل `MT5_ENABLED=true` على Linux Contabo — سيفشل.
