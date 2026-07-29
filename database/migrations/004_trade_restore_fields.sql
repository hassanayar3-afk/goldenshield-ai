-- مستويات الصفقة للاستعادة بعد إعادة التشغيل
ALTER TABLE trades ADD COLUMN stop_loss REAL;
ALTER TABLE trades ADD COLUMN take_profit REAL;
ALTER TABLE trades ADD COLUMN is_paper INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trades ADD COLUMN breakeven_applied INTEGER NOT NULL DEFAULT 0;
ALTER TABLE trades ADD COLUMN partial_exit_done INTEGER NOT NULL DEFAULT 0;
