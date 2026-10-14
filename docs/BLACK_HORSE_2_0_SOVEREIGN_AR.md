# Black Horse 2.0 — دليل التنفيذ السيادي (Cursor)

تنفيذ **تصاعدي** فوق GoldenShield الحالي دون كسر `main.py` / `gs_daemon.ps1`.

## Phase 1 — Clean slate & secrets

```powershell
cd C:\GoldenShield_Binance
.\deploy_ops\Harvest-GsSecrets.ps1
.\deploy\windows\Cleanup-GsLegacy.ps1 -Aggressive
```

## Phase 2–4 — Neural matrix & engines

| مسار | دور |
|------|-----|
| `core_engine/neural_matrix.py` | PM2 GS-NeuralCore (مشرف إجماع؛ `GS_NEURAL_RUN_MAIN_BOT=true` لتشغيل البوت الكامل) |
| `core_engine/black_horse_smc.py` | SMC |
| `core_engine/zscore_flash.py` | Gold Flash |
| `core_engine/momentum_ioc.py` | Micro momentum |
| `risk_sentinel/sovereign_guard.py` | حرارة محفظة / ارتباط / elite |
| `data_highway/zero_copy_cache.py` | ذاكرة لحظية + idempotency |

## Phase 3 — Gateway

```bash
python -m pip install -r requirements.txt
python gateway_api/fast_router.py
```

## Phase 5 — نفق ثابت

`.env`:

```env
MOBILE_PUBLIC_BASE_URL=https://violafashioniq.com/
CLOUDFLARE_TUNNEL_TOKEN=<from Cloudflare Zero Trust>
GS_BAN_QUICK_TUNNEL=true
```

`trycloudflare.com` **محظور** عند `GS_BAN_QUICK_TUNNEL=true`.

## Phase 6 — PM2 (Windows)

```powershell
npm install -g pm2
cd C:\GoldenShield_Binance
pm2 start deploy_ops/pm2.ecosystem.config.cjs
pm2 save
pm2 startup
```

APK: `config/mobile_default_servers.txt` → `deploy\windows\BUILD_ANDROID_APK.ps1`
