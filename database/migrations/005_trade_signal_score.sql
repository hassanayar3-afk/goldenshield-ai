-- قوة الإشارة عند فتح الصفقة (0–10) للاستعادة والعرض في لوحة التحكم
ALTER TABLE trades ADD COLUMN signal_score INTEGER NOT NULL DEFAULT 0;
