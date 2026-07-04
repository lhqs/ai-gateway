ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS access_config JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE api_keys
  ADD COLUMN IF NOT EXISTS access_config JSONB NOT NULL DEFAULT '{}'::jsonb;
