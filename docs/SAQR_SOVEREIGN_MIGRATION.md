# Saqr sovereign local migration — checklist

| Step | Status |
|------|--------|
| 1. Backup `.env` outside workspace | `/tmp/saqr_secrets_backup/.env` (local VM); restore at repo root `.env` |
| 2. Purge legacy `saqr/`, mobile, PWA, tunnel scripts | Done — use `core_engine/`, `gateway_api/`, … |
| 3. `.env` at **workspace root** | Required — not committed to Git |
| 4. Sovereign folders | `core_engine/`, `risk_sentinel/`, `data_highway/`, `gateway_api/`, `terminal_control/`, `deploy_ops/` |
| 5. One-click run | `deploy_ops/run.bat` or root `SAQR_RUN.bat` |

## Web control panel

After `run.bat`: **http://localhost:8000** (same UI at `/dashboard`).

## Windows copy path

Extract ZIP → set `SAqr_ROOT` in `.env` to your folder (e.g. `C:\Saqr_Binance`) → `pip install -r requirements-saqr-local.txt` → double-click `SAQR_RUN.bat`.
