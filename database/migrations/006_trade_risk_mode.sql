-- risk_mode للصفقات: standard | high_conviction
ALTER TABLE trades ADD COLUMN risk_mode TEXT NOT NULL DEFAULT 'standard';
