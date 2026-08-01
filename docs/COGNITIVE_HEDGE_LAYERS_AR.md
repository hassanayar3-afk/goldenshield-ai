# الركائز المعرفية (Cognitive Hedge) — طبقات مضافة

هذه الطبقات تعمل فوق GoldenShield الحالي على **Binance Demo** دون تأخير الدخول.

## 1) Shadow Stress-Testing
- عند إشارة ≥90 تُسجَّل فرضية ظل موازية وتُراقب ~15 دقيقة.
- التنفيذ على Demo يستمر فوراً (Parallel Shadow).
- 3 فشلات ظلّية متتالية لنفس النمط → تبريد الزوج ساعة.

## 2) Black Box
- عند إغلاق صفقة خاسرة تُحفظ لقطة وتُرسل خلاصة على تيليجرام مع تعديل وزن مؤقت.

## 3) Order Book Gate
- يرفض الدخول عند اختلال عمق واضح ضد الاتجاه أو فخ سيولة محتمل.

## 4) Fractional Exits
- Multi-Tier تقريباً: 30% @1:1 + BE → 40% @1:2 + trail → 30% runner.
- خروج زخم استباقي اختياري عبر `MOMENTUM_PREEMPTIVE_EXIT_ENABLED`.

## 5) Adaptive Weights
- تعديل خفيف لأوزان مكوّنات التسجيل (±20% كحد).

## 6) Macro / Sentiment
- بوابة Fear&Greed + طبقة اختيارية لمناطق الحيتان من دفتر الأوامر.
- فشل المصدر = تمرير آمن (لا يوقف البوت).

## 7) Risk Committee
- قواعد افتراضية (تبريد، دفتر أوامر، تلاعب).
- LLM اختياري: `RISK_COMMITTEE_LLM_ENABLED=true` + `OPENAI_API_KEY`.

انظر `.env.cognitive.example` لمفاتيح البيئة.
