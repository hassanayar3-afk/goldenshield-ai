-- v1.3 Multi-Tier TP persistence
ALTER TABLE trades ADD COLUMN exit_tier INTEGER NOT NULL DEFAULT 0;
