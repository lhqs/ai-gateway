export type Tab = "dashboard" | "workbench" | "clients" | "providers" | "models" | "pricing" | "routes" | "usage";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type AuthUser = {
  id: number;
  email: string;
  username: string;
  display_name: string | null;
  status: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
};

export type Dashboard = {
  total_requests: number;
  success_rate: number;
  error_rate: number;
  total_tokens: number;
  avg_latency_ms: number;
  error_count: number;
  total_cost: number;
  total_cost_24h: number;
  total_cost_7d: number;
  cache_hit_rate: number;
  failover_count: number;
  failover_rate: number;
  stream_count: number;
  usage_parsed_rate: number;
  missing_price_count: number;
};

export type Client = {
  id: number;
  name: string;
  description: string | null;
  status: string;
  access_config: Record<string, JsonValue>;
};

export type PageResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type ApiKey = {
  id: number;
  client_id: number;
  name: string;
  key: string | null;
  key_prefix: string;
  status: string;
  access_config: Record<string, JsonValue>;
  last_used_at: string | null;
  expires_at: string | null;
};

export type Provider = {
  id: number;
  name: string;
  provider_type: string;
  base_url: string;
  encrypted_api_key: string | null;
  config: Record<string, JsonValue>;
  status: string;
  protocol_modes: string[];
  auth_type: string;
  auth_config: Record<string, JsonValue>;
  allowed_paths: string[];
  blocked_headers: string[];
  usage_parser_type: string;
  health_status: string;
  failure_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  cooldown_until: string | null;
  last_health_error: string | null;
  last_health_status_code: number | null;
  failure_threshold: number;
  cooldown_seconds: number;
  timeout_ms: number;
  allow_streaming: boolean;
  native_rate_limit_per_minute: number | null;
};

export type ProviderConfigField = {
  name: string;
  label: string;
  field_type: "text" | "number" | "tags" | string;
  default: JsonValue | JsonValue[] | null;
  help_text: string | null;
};

export type ProviderConfigSchema = {
  provider_type: string;
  fields: ProviderConfigField[];
  defaults: Record<string, JsonValue>;
};

export type Model = {
  id: number;
  provider_id: number;
  name: string;
  display_name: string | null;
  capabilities: string[];
  context_window: number | null;
  status: string;
};

export type ModelPriceConfig = {
  id: number;
  provider_id: number;
  model_id: number;
  model_name: string;
  currency_code: string;
  unit_type: string;
  unit_quantity: number;
  input_unit_price: string | null;
  cached_input_unit_price: string | null;
  output_unit_price: string | null;
  reasoning_output_unit_price: string | null;
  request_unit_price: string | null;
  config: Record<string, JsonValue>;
  status: string;
  effective_from: string;
  effective_to: string | null;
};

export type Alias = {
  id: number;
  alias: string;
  description: string | null;
  status: string;
};

export type RouteRule = {
  id: number;
  model_alias_id: number;
  primary_model_id: number;
  fallback_model_ids: number[];
  priority: number;
  failover_enabled: boolean;
  max_failover_attempts: number;
  cache_enabled: boolean;
  cache_ttl_seconds: number;
  status: string;
};

export type RouteValidationModel = {
  model_id: number;
  model_name: string | null;
  provider_id: number | null;
  provider_name: string | null;
  model_status: string | null;
  provider_status: string | null;
  provider_health_status: string | null;
  available: boolean;
};

export type RouteValidationResult = {
  valid: boolean;
  errors: string[];
  warnings: string[];
  primary: RouteValidationModel | null;
  fallbacks: RouteValidationModel[];
  duplicate_model_ids: number[];
  cross_provider: boolean;
};

export type UsageLog = {
  id: number;
  request_id: string;
  client_id: number | null;
  api_key_id: number | null;
  call_mode: string;
  model_alias: string | null;
  provider_id: number | null;
  model_id: number | null;
  native_path: string | null;
  native_status_code: number | null;
  status: string;
  usage_status: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  billable_input_tokens: number;
  billable_output_tokens: number;
  estimated_cost: string | number | null;
  cost_currency: string | null;
  cost_unit_type: string | null;
  cost_unit_quantity: number | null;
  input_cost: string | number | null;
  cached_input_cost: string | number | null;
  output_cost: string | number | null;
  total_cost: string | number | null;
  pricing_config_id: number | null;
  pricing_status: string;
  cost_breakdown: unknown | null;
  latency_ms: number | null;
  cache_hit: boolean;
  failover_triggered: boolean;
  failover_attempts: number;
  final_provider_id: number | null;
  final_model_id: number | null;
  failure_reason: string | null;
  prompt_content: unknown | null;
  completion_content: unknown | null;
  raw_request_body: unknown | null;
  raw_response_body: unknown | null;
  created_at: string;
};

export type UsageSummaryRow = {
  group_key: string;
  request_count: number;
  success_count: number;
  error_count: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  cached_input_tokens: number;
  total_cost: string | number | null;
  avg_latency_ms: number;
  cache_hit_count: number;
  failover_count: number;
  stream_count: number;
  parsed_usage_count: number;
  missing_price_count: number;
};

export type WorkbenchChatTestMeta = {
  usage_log_id: number | null;
  latency_ms: number | null;
  model_alias: string | null;
  provider_id: number | null;
  model_id: number | null;
  final_provider_id: number | null;
  final_model_id: number | null;
  status: string | null;
  usage_status: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_input_tokens: number;
  total_cost: string | number | null;
  cost_currency: string | null;
  pricing_status: string | null;
  cache_hit: boolean;
  failover_triggered: boolean;
  failover_attempts: number;
};

export type WorkbenchChatTestResponse = {
  request_id: string;
  body: Record<string, JsonValue>;
  meta: WorkbenchChatTestMeta;
};

export type PageProps = {
  headers: HeadersInit;
  setNotice: (value: string) => void;
};
