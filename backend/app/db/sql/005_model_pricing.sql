CREATE TABLE IF NOT EXISTS model_price_configs (
  id BIGSERIAL PRIMARY KEY,
  provider_id BIGINT NOT NULL,
  model_id BIGINT NOT NULL,
  model_name VARCHAR(128) NOT NULL,
  currency_code VARCHAR(16) NOT NULL,
  unit_type VARCHAR(32) NOT NULL DEFAULT 'tokens',
  unit_quantity INTEGER NOT NULL DEFAULT 1000000,
  input_unit_price NUMERIC(24,12),
  cached_input_unit_price NUMERIC(24,12),
  output_unit_price NUMERIC(24,12),
  reasoning_output_unit_price NUMERIC(24,12),
  request_unit_price NUMERIC(24,12),
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  effective_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_provider_id ON model_price_configs(provider_id);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_model_id ON model_price_configs(model_id);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_currency ON model_price_configs(currency_code);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_model_currency
  ON model_price_configs(model_id, currency_code, status);
CREATE INDEX IF NOT EXISTS idx_model_price_configs_effective
  ON model_price_configs(model_id, currency_code, effective_from, effective_to);

ALTER TABLE usage_logs
  ADD COLUMN IF NOT EXISTS cached_input_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS billable_input_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS billable_output_tokens INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_currency VARCHAR(16),
  ADD COLUMN IF NOT EXISTS cost_unit_type VARCHAR(32),
  ADD COLUMN IF NOT EXISTS cost_unit_quantity INTEGER,
  ADD COLUMN IF NOT EXISTS input_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS cached_input_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS output_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS total_cost NUMERIC(24,12),
  ADD COLUMN IF NOT EXISTS pricing_config_id BIGINT,
  ADD COLUMN IF NOT EXISTS pricing_status VARCHAR(32) NOT NULL DEFAULT 'not_calculated',
  ADD COLUMN IF NOT EXISTS cost_breakdown JSONB;

CREATE INDEX IF NOT EXISTS idx_usage_logs_cost_currency_created_at
  ON usage_logs(cost_currency, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_pricing_config_id ON usage_logs(pricing_config_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_pricing_status ON usage_logs(pricing_status);
