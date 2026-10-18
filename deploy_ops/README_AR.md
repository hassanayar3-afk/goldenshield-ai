# صقر — التشغيل المحلي السيادي

1. انسخ `.env.saqr.example` إلى `.env` في **جذر المستودع** وأضف مفاتيح Testnet.
2. ثبّت المتطلبات: `pip install -r requirements-saqr-local.txt`
3. شغّل: `deploy_ops\run.bat`
4. افتح: http://localhost:8000

**هيكل التشغيل:** `gateway_api` (FastAPI + WebSocket) + `core_engine/neural_matrix.py` (المحركات الثلاثة) مع SQLite WAL تحت `data_highway/`.
