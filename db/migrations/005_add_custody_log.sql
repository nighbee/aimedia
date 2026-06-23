-- migration 005: add chain-of-custody log to jobs table
ALTER TABLE core.jobs ADD COLUMN IF NOT EXISTS custody_log JSONB;
