# GoldenShield Terminal على Termux (Android) — بدون Windows

## 1) تثبيت (مرة واحدة)

```bash
bash deploy/termux/INSTALL_TERMUX.sh
```

أو يدوياً:

```bash
pkg update -y && pkg install -y python git curl termux-api
cd ~
git clone https://github.com/hassanayar3-afk/goldenshield-ai.git goldenshield-ai
cd goldenshield-ai
pip install -r requirements.txt
cp config/env.production.template .env
# عدّل BINANCE_* و DISCORD_* في .env
export GOLDENSHIELD_OFFICIAL_ROOT=$PWD
```

## 2) تشغيل الخلفية (Backend كامل)

```bash
cd ~/goldenshield-ai
export GOLDENSHIELD_OFFICIAL_ROOT=$PWD
bash deploy/termux/START_FULL_STACK.sh
```

## 3) التحقق من المنفذ 8790

```bash
bash deploy/termux/CHECK_API.sh
# أو:
curl http://127.0.0.1:8790/api/health
```

## 4) ربط APK (نفس الهاتف)

1. ثبّت **GoldenShield-Control.apk**
2. في حقل السيرفر اكتب بالضبط: **`http://127.0.0.1:8790`**
3. **لا تستخدم** «اكتشاف النفق» على نفس الجهاز — افتح لوحة التحكم مباشرة
4. أدخل **رمز الربط** من `.env` / `storage/runtime/mobile_api_credentials.txt` أو لوحة `/api/bootstrap`

## 5) إيقاف

```bash
bash deploy/termux/STOP_STACK.sh
```

## سجلات

- API: `storage/logs/mobile_api.log`
- Bot: `storage/logs/bot_stdout.log`

## ملاحظات

- `CLOUDFLARE_TUNNEL_ENABLED=false` على الهاتف المحلي (الافتراضي بعد INSTALL)
- Termux يجب أن يبقى مفتوحاً أو استخدم `termux-wake-lock` (مضمّن في START)
- Demo Trading: `BINANCE_DEMO_TRADING=true` في `.env`
