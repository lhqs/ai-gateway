ALTER TABLE providers
  ADD COLUMN IF NOT EXISTS failure_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_failure_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_health_error TEXT,
  ADD COLUMN IF NOT EXISTS last_health_status_code INTEGER;

CREATE INDEX IF NOT EXISTS idx_providers_health_status ON providers(health_status);
CREATE INDEX IF NOT EXISTS idx_providers_cooldown_until ON providers(cooldown_until);

ALTER TABLE usage_logs
  ADD COLUMN IF NOT EXISTS api_key_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_usage_logs_api_key_id ON usage_logs(api_key_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_api_key_created_at ON usage_logs(api_key_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_client_created_at ON usage_logs(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_provider_created_at ON usage_logs(provider_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model_created_at ON usage_logs(model_id, created_at);
