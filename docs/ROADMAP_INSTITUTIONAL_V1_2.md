# GoldenShield AI — خارطة v1.2+ (نقل مؤسسي)

> **المصدر:** اقتراحات الخبراء بعد استقرار بروتوكولات الأمان (v1.1.2)  
> **القيد الحاكم:** بروتوكول التوافق الصارم + مبدأ «الاستقرار أولاً»  
> **القاعدة:** كل ميزة = طبقة مضافة · `enabled: false` افتراضياً · defaults آمنة · `try-except` · بلا نقل ملفات

---

## 0) مبدأ الاستقرار أولاً (إلزامي)

1. تشغيل النظام ببروتوكولات الأمان الحالية **أسبوع كامل بدون خطأ برمي**.
2. مراجعة `audit/` وسجلات الصفقات.
3. ثم تفعيل **ميزة واحدة فقط** حسب تشخيص السجلات:
   - خسائر في سوق عرضي → **ADX Filter**
   - خسائر بسبب تسرّع الدخول → **Partial Scaling**
   - ذعر سوقي / انهيارات جماعية → **Market Correlation / Panic Mode**
   - تآكل أرباح الجلسات المتأخرة → **Profit-Capping**
4. لا تُفعَّل كل الميزات دفعة واحدة.

---

## 1) ما يوجد مسبقاً (لا يُكسر)

| القدرة | الموقع الحالي | ملاحظة |
|--------|----------------|--------|
| Correlation بين الرموز | `execution/correlation_filter.py` | مجموعات رموز — ليس Panic على S&P/سندات |
| Scaling ضمن HC | `risk/high_conviction_protocol.py` + YAML | مختلف عن Partial Scaling العام |
| ربح/خسارة يومية في الحالة | `risk/state.py` (`daily_profit`) | أساس جيد لـ Profit-Capping |
| خدمة systemd / Docker | `deployment/` + Contabo | أساس لـ Daemonizing |
| تقارير تيليجرام | `operations/message_templates.py` | تحتاج توسيع Smart Reporting |
| Audit / Shadow | `audit/` | أساس Micro-Simulation |

---

## 2) الميزات المقترحة — طبقات مضافة (كلها OFF افتراضياً)

### أ) فلتر التذبذب — ADX Filter
- **الهدف:** منع التداول التلقائي إذا ADX < عتبة (افتراضي 20) — سوق عرضي يضر SMC.
- **الدمج المقترح:** بوابة قبل التنفيذ في مسار الإشارة (Additive gate).
- **إعدادات مقترحة (defaults):**
  - `ADX_FILTER_ENABLED=false`
  - `ADX_MIN_TREND=20`
  - `ADX_PERIOD=14`
- **مكتبات:** غالباً لا حاجة جديدة (حساب ADX من OHLCV الموجود).

### ب) فلتر الارتباط الكلي — Market Correlation / Panic Mode
- **الهدف:** مراقبة مؤشرات كبرى (S&P / عوائد سندات). في الذعر: إيقاف **Long** فقط.
- **الدمج المقترح:** طبقة فوق `correlation_filter` أو مراقب ماكرو منفصل — بدون استبدال المنطق الحالي.
- **إعدادات مقترحة:**
  - `MARKET_CORRELATION_FILTER_ENABLED=false`
  - `PANIC_MODE_BLOCK_LONG=true` (فعّال فقط إذا الميزة مفعّلة)
  - عتبات ذعر قابلة للضبط مع defaults آمنة
- **ملاحظة:** يوجد مسبقاً VIX/ماكرو في `core/macro/` — يُفضَّل البناء عليه.

### ج) الدخول المتدرج — Partial Scaling / Pyramiding
- **الهدف:** فتح 50% عند الإشارة، وإضافة 50% فقط بعد تحرّك سعري في اتجاه الربح.
- **الدمج المقترح:** طبقة في التنفيذ — لا تغيّر حجم الصفقة الكامل إلا إذا `PARTIAL_SCALING_ENABLED=true`.
- **إعدادات مقترحة:**
  - `PARTIAL_SCALING_ENABLED=false`
  - `PARTIAL_SCALING_INITIAL_PCT=50`
  - `PARTIAL_SCALING_ADD_PCT=50`
  - شرط إضافة (مثلاً كسر BE أو مسافة ATR) مع defaults

### د) المحاكاة الاستباقية — Micro-Simulation
- **الهدف:** قبل صفقة حقيقية، فحص آخر N صفقات مشابهة من السجلات؛ رفض إذا نجاح < عتبة (افتراضي 50%).
- **الدمج مقترح:** بوابة قبل `TradeExecutor` تقرأ من `audit/` / DB.
- **إعدادات مقترحة:**
  - `MICRO_SIMULATION_ENABLED=false`
  - `MICRO_SIMULATION_LOOKBACK=10`
  - `MICRO_SIMULATION_MIN_WINRATE=0.50`
- عند فشل القراءة/البيانات الناقصة: **السماح بالصفقة** أو bypass آمن (لا إيقاف البوت) — يُحدَّد صراحة عند التنفيذ.

### هـ) سقف الأرباح اليومي — Profit-Capping
- **الهدف:** عند وصول ربح يومي لسقف (مثلاً 3%) يتوقف التداول التلقائي لبقية اليوم.
- **الدمج المقترح:** فحص على `risk.state.daily_profit` داخل Risk Orchestrator كطبقة إضافية.
- **إعدادات مقترحة:**
  - `PROFIT_CAP_ENABLED=false`
  - `PROFIT_CAP_DAILY_PCT=3.0`

### و) التقرير الذكي — Smart Reporting
- **الهدف:** بعد كل صفقة: سبب فني + R:R محققة + الفلاتر التي أكّدت الدخول.
- **الدمج المقترح:** توسيع قوالب التيليجرام — Additive فقط.
- **إعدادات مقترحة:**
  - `SMART_TRADE_REPORT_ENABLED=false` (أو `true` إذا رغبت لاحقاً — افتراضي false للأمان)

### ز) الاستمرارية التلقائية — Daemonizing
- **الهدف:** خدمة خلفية تعيد التشغيل ذاتياً.
- **الواقع:** يوجد مسار systemd/Docker جزئياً — تحسين/توثيق/تحقق بدل إعادة اختراع.
- **لا يغيّر منطق التداول.**

---

## 3) ترتيب التنفيذ المقترح (بعد أسبوع الاستقرار)

| الترتيب | الميزة | متى تُضاف حسب Audit Review |
|---------|--------|----------------------------|
| 1 | ADX Filter | خسائر أسواق عرضية |
| 2 | Profit-Capping | تآكل أرباح بعد هدف يومي |
| 3 | Smart Reporting | تحسين المراقبة دون تغيير التنفيذ |
| 4 | Partial Scaling | تسرّع/انزلاق عند الدخول |
| 5 | Micro-Simulation | رفض ظروف تاريخياً ضعيفة |
| 6 | Market Panic Correlation | انهيارات مرتبطة بالسوق الكلي |
| 7 | Daemon hardening | تشغيل/إعادة تشغيل السيرفر |

---

## 4) قيود بروتوكول التوافق (تُطبَّق على كل PR)

1. Defaults آمنة لكل مفتاح جديد.  
2. Additive فقط — السلوك الحالي دون تفعيل الأعلام يبقى مطابقاً لـ v1.1.2.  
3. مكتبات جديدة → `requirements.txt` + تنبيه تثبيت.  
4. `try-except` حول كل بوابة جديدة — لا إيقاف لحلقة `main.py`.  
5. لا نقل ملفات إلا بطلب صريح.

---

## 5) حالة التنفيذ

- [x] طبقات الكود مضافة (كلها `enabled: false` افتراضياً)
- [ ] أسبوع استقرار v1.1.2 بدون خطأ برمي  
- [ ] مراجعة audit  
- [ ] تفعيل ميزة واحدة حسب التشخيص (ADX / Profit Cap / …)

### ملفات الطبقات
| الميزة | الملف | العلم |
|--------|--------|--------|
| ADX Filter | `risk/adx_filter.py` + `indicators.adx` | `ADX_FILTER_ENABLED` |
| Panic Mode | `risk/panic_mode.py` | `MARKET_CORRELATION_FILTER_ENABLED` |
| Partial Scaling | `risk/partial_scaling.py` | `PARTIAL_SCALING_ENABLED` |
| Micro-Simulation | `risk/micro_simulation.py` | `MICRO_SIMULATION_ENABLED` |
| Profit Cap | `risk/profit_cap.py` | `PROFIT_CAP_ENABLED` |
| Smart Report | `operations/smart_trade_report.py` | `SMART_TRADE_REPORT_ENABLED` |
- [ ] اختيار الميزة الأولى وتفعيلها خلف flag  
- [ ] بقية الميزات تباعاً  

**لم يُنفَّذ أي كود ميزات من هذه القائمة بعد** — الوثيقة جاهزة للانطلاق عند أمرك.
