CREATE TABLE IF NOT EXISTS clients (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  access_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  key_prefix VARCHAR(32) NOT NULL,
  key_hash VARCHAR(128) NOT NULL UNIQUE,
  key_value TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  access_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_used_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_keys_client_id ON api_keys(client_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_prefix ON api_keys(key_prefix);

CREATE TABLE IF NOT EXISTS providers (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL UNIQUE,
  provider_type VARCHAR(64) NOT NULL,
  base_url TEXT NOT NULL,
  encrypted_api_key TEXT,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  protocol_modes JSONB NOT NULL DEFAULT '[]'::jsonb,
  auth_type VARCHAR(64) NOT NULL DEFAULT 'api_key_header',
  auth_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  allowed_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
  blocked_headers JSONB NOT NULL DEFAULT '[]'::jsonb,
  usage_parser_type VARCHAR(64) NOT NULL DEFAULT 'none',
  health_status VARCHAR(32) NOT NULL DEFAULT 'healthy',
  failure_threshold INTEGER NOT NULL DEFAULT 5,
  cooldown_seconds INTEGER NOT NULL DEFAULT 60,
  timeout_ms INTEGER NOT NULL DEFAULT 60000,
  allow_streaming BOOLEAN NOT NULL DEFAULT true,
  native_rate_limit_per_minute INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_providers_type ON providers(provider_type);

CREATE TABLE IF NOT EXISTS models (
  id BIGSERIAL PRIMARY KEY,
  provider_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  display_name VARCHAR(128),
  capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
  context_window INTEGER,
  input_price NUMERIC(18,8),
  output_price NUMERIC(18,8),
  currency VARCHAR(16) NOT NULL DEFAULT 'USD',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(provider_id, name)
);
CREATE INDEX IF NOT EXISTS idx_models_provider_id ON models(provider_id);

CREATE TABLE IF NOT EXISTS model_aliases (
  id BIGSERIAL PRIMARY KEY,
  alias VARCHAR(128) NOT NULL UNIQUE,
  description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS route_rules (
  id BIGSERIAL PRIMARY KEY,
  model_alias_id BIGINT NOT NULL,
  primary_model_id BIGINT NOT NULL,
  fallback_model_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
  strategy_type VARCHAR(64) NOT NULL DEFAULT 'primary_fallback',
  strategy_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  priority INTEGER NOT NULL DEFAULT 100,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  failover_enabled BOOLEAN NOT NULL DEFAULT true,
  failover_on_status_codes JSONB NOT NULL DEFAULT '[429,500,502,503,504]'::jsonb,
  failover_on_error_types JSONB NOT NULL DEFAULT '["timeout","connection_error","rate_limit","provider_error"]'::jsonb,
  max_failover_attempts INTEGER NOT NULL DEFAULT 2,
  cache_enabled BOOLEAN NOT NULL DEFAULT false,
  cache_ttl_seconds INTEGER NOT NULL DEFAULT 300,
  cache_scope VARCHAR(64) NOT NULL DEFAULT 'client',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_route_rules_alias_id ON route_rules(model_alias_id);
CREATE INDEX IF NOT EXISTS idx_route_rules_primary_model_id ON route_rules(primary_model_id);

CREATE TABLE IF NOT EXISTS usage_logs (
  id BIGSERIAL PRIMARY KEY,
  request_id VARCHAR(64) NOT NULL,
  client_id BIGINT,
  model_alias VARCHAR(128),
  provider_id BIGINT,
  model_id BIGINT,
  stream BOOLEAN NOT NULL DEFAULT false,
  status VARCHAR(32) NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER,
  first_token_latency_ms INTEGER,
  estimated_cost NUMERIC(18,8),
  error_code VARCHAR(128),
  error_message TEXT,
  call_mode VARCHAR(32) NOT NULL DEFAULT 'unified_chat',
  native_method VARCHAR(16),
  native_path TEXT,
  native_status_code INTEGER,
  usage_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
  raw_usage JSONB,
  prompt_content JSONB,
  completion_content JSONB,
  raw_request_body JSONB,
  raw_response_body JSONB,
  cache_hit BOOLEAN NOT NULL DEFAULT false,
  cache_key TEXT,
  failover_triggered BOOLEAN NOT NULL DEFAULT false,
  failover_attempts INTEGER NOT NULL DEFAULT 0,
  initial_provider_id BIGINT,
  initial_model_id BIGINT,
  final_provider_id BIGINT,
  final_model_id BIGINT,
  failure_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_logs_request_id ON usage_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_client_id ON usage_logs(client_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model_alias ON usage_logs(model_alias);
CREATE INDEX IF NOT EXISTS idx_usage_logs_provider_id ON usage_logs(provider_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_model_id ON usage_logs(model_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON usage_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_logs_call_mode_created_at ON usage_logs(call_mode, created_at);

CREATE TABLE IF NOT EXISTS cache_entries (
  id BIGSERIAL PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,
  client_id BIGINT,
  model_alias VARCHAR(128),
  request_hash VARCHAR(128) NOT NULL,
  response_body JSONB NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cache_entries_client_id ON cache_entries(client_id);
CREATE INDEX IF NOT EXISTS idx_cache_entries_model_alias ON cache_entries(model_alias);
CREATE INDEX IF NOT EXISTS idx_cache_entries_request_hash ON cache_entries(request_hash);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at);
