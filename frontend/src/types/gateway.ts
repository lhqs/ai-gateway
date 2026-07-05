export type Tab = "dashboard" | "clients" | "providers" | "models" | "routes" | "usage";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type Dashboard = {
  total_requests: number;
  success_rate: number;
  total_tokens: number;
  avg_latency_ms: number;
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
  status: string;
  protocol_modes: string[];
  auth_type: string;
  allowed_paths: string[];
  blocked_headers: string[];
  usage_parser_type: string;
  health_status: string;
  timeout_ms: number;
  allow_streaming: boolean;
  native_rate_limit_per_minute: number | null;
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
  failover_enabled: boolean;
  max_failover_attempts: number;
  cache_enabled: boolean;
  cache_ttl_seconds: number;
  status: string;
};

export type UsageLog = {
  id: number;
  request_id: string;
  client_id: number | null;
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

export type PageProps = {
  headers: HeadersInit;
  setNotice: (value: string) => void;
};
