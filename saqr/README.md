# صقر — SAQR Engine v6.0

محرك تداول **Binance** (Rust) — مستودع مستقل على **hassanayar93/Saqr**.

## الوثائق

- **[الفهرس.md](./الفهرس.md)** — شجرة الملفات واختصاص كل ملف
- **[دليل صقر.md](./دليل%20صقر.md)** — شرح ما تم برمجته

## تشغيل سريع

```bash
cp .env.example .env
# عدّل .env (Binance, Telegram, Cloud)
cargo run --release --bin saqr
```

لوحة التحكم: `http://127.0.0.1:8787`

## Demo افتراضي

`SAQR_MODE=demo` — لا live trading حتى تغيّر الإعدادات صراحة.
