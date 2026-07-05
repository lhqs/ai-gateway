WITH provider_seed (
  name,
  provider_type,
  base_url,
  protocol_modes,
  auth_type,
  auth_config,
  allowed_paths,
  blocked_headers,
  usage_parser_type,
  status
) AS (
  VALUES
  (
    'gemini',
    'gemini',
    'https://generativelanguage.googleapis.com',
    '["native_proxy"]'::jsonb,
    'api_key_query',
    '{"query_name":"key"}'::jsonb,
    '["v1beta/models/*","v1beta/models/*:generateContent","v1beta/models/*:streamGenerateContent"]'::jsonb,
    '["authorization","cookie","set-cookie","host","content-length"]'::jsonb,
    'gemini',
    'disabled'
  ),
  (
    'qwen',
    'openai_compatible',
    'https://dashscope.aliyuncs.com/compatible-mode/v1',
    '["openai_compatible"]'::jsonb,
    'bearer_token',
    '{"header":"Authorization"}'::jsonb,
    '[]'::jsonb,
    '["authorization","cookie","set-cookie","host","content-length"]'::jsonb,
    'openai',
    'disabled'
  ),
  (
    'deepseek',
    'openai_compatible',
    'https://api.deepseek.com/v1',
    '["openai_compatible"]'::jsonb,
    'bearer_token',
    '{"header":"Authorization"}'::jsonb,
    '[]'::jsonb,
    '["authorization","cookie","set-cookie","host","content-length"]'::jsonb,
    'openai',
    'disabled'
  )
)
INSERT INTO providers (
  name,
  provider_type,
  base_url,
  protocol_modes,
  auth_type,
  auth_config,
  allowed_paths,
  blocked_headers,
  usage_parser_type,
  status
)
SELECT
  name,
  provider_type,
  base_url,
  protocol_modes,
  auth_type,
  auth_config,
  allowed_paths,
  blocked_headers,
  usage_parser_type,
  status
FROM provider_seed
ON CONFLICT (name) DO NOTHING;

DROP TABLE IF EXISTS tmp_common_model_price_seed;

CREATE TEMP TABLE tmp_common_model_price_seed AS
SELECT *
FROM (
  VALUES
  ('gemini', 'gemini-3.1-flash-lite', 'Google: Gemini 3.1 Flash Lite', 1048576, '["chat","multimodal"]'::jsonb, 0.25, 0.025, 1.5, 1.5, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-3.1-flash-lite","source_name":"Google: Gemini 3.1 Flash Lite","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.08333333333333334","raw_pricing":{"prompt":"0.00000025","completion":"0.0000015","image":"0.00000025","audio":"0.0000005","web_search":"0.014","internal_reasoning":"0.0000015","input_cache_read":"0.000000025","input_cache_write":"0.00000008333333333333334"}}'::jsonb),
  ('gemini', 'gemini-3.1-pro-preview', 'Google: Gemini 3.1 Pro Preview', 1048576, '["chat","multimodal"]'::jsonb, 2, 0.2, 12, 12, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-3.1-pro-preview","source_name":"Google: Gemini 3.1 Pro Preview","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.375","raw_pricing":{"prompt":"0.000002","completion":"0.000012","image":"0.000002","audio":"0.000002","web_search":"0.014","internal_reasoning":"0.000012","input_cache_read":"0.0000002","input_cache_write":"0.000000375"}}'::jsonb),
  ('gemini', 'gemini-3-flash-preview', 'Google: Gemini 3 Flash Preview', 1048576, '["chat","multimodal"]'::jsonb, 0.5, 0.05, 3, 3, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-3-flash-preview","source_name":"Google: Gemini 3 Flash Preview","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.08333333333333334","raw_pricing":{"prompt":"0.0000005","completion":"0.000003","image":"0.0000005","audio":"0.000001","web_search":"0.014","internal_reasoning":"0.000003","input_cache_read":"0.00000005","input_cache_write":"0.00000008333333333333334"}}'::jsonb),
  ('gemini', 'gemini-2.5-pro', 'Google: Gemini 2.5 Pro', 1048576, '["chat","multimodal"]'::jsonb, 1.25, 0.125, 10, 10, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-2.5-pro","source_name":"Google: Gemini 2.5 Pro","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.375","raw_pricing":{"prompt":"0.00000125","completion":"0.00001","image":"0.00000125","audio":"0.00000125","web_search":"0.014","internal_reasoning":"0.00001","input_cache_read":"0.000000125","input_cache_write":"0.000000375"}}'::jsonb),
  ('gemini', 'gemini-2.5-flash', 'Google: Gemini 2.5 Flash', 1048576, '["chat","multimodal"]'::jsonb, 0.3, 0.03, 2.5, 2.5, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-2.5-flash","source_name":"Google: Gemini 2.5 Flash","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.08333333333333334","raw_pricing":{"prompt":"0.0000003","completion":"0.0000025","image":"0.0000003","audio":"0.000001","web_search":"0.014","internal_reasoning":"0.0000025","input_cache_read":"0.00000003","input_cache_write":"0.00000008333333333333334"}}'::jsonb),
  ('gemini', 'gemini-2.5-flash-lite', 'Google: Gemini 2.5 Flash Lite', 1048576, '["chat","multimodal"]'::jsonb, 0.1, 0.01, 0.4, 0.4, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-2.5-flash-lite","source_name":"Google: Gemini 2.5 Flash Lite","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.08333333333333334","raw_pricing":{"prompt":"0.0000001","completion":"0.0000004","image":"0.0000001","audio":"0.0000003","web_search":"0.014","internal_reasoning":"0.0000004","input_cache_read":"0.00000001","input_cache_write":"0.00000008333333333333334"}}'::jsonb),
  ('gemini', 'gemini-2.0-flash-001', 'Google: Gemini 2.0 Flash', 1048576, '["chat","multimodal"]'::jsonb, 0.1, 0.025, 0.4, 0.4, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-2.0-flash-001","source_name":"Google: Gemini 2.0 Flash","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.08333333333333334","raw_pricing":{"prompt":"0.0000001","completion":"0.0000004","image":"0.0000001","audio":"0.0000007","web_search":"0.014","internal_reasoning":"0.0000004","input_cache_read":"0.000000025","input_cache_write":"0.00000008333333333333334"}}'::jsonb),
  ('gemini', 'gemini-2.0-flash-lite-001', 'Google: Gemini 2.0 Flash Lite', 1048576, '["chat","multimodal"]'::jsonb, 0.075, NULL, 0.3, 0.3, '{"source":"docs/ref/models.json","source_model_id":"google/gemini-2.0-flash-lite-001","source_name":"Google: Gemini 2.0 Flash Lite","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000075","completion":"0.0000003","image":"0.000000075","audio":"0.000000075","web_search":"0.014","internal_reasoning":"0.0000003"}}'::jsonb),
  ('qwen', 'qwen3.6-plus', 'Qwen: Qwen3.6 Plus', 1000000, '["chat","multimodal"]'::jsonb, 0.325, NULL, 1.95, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3.6-plus","source_name":"Qwen: Qwen3.6 Plus","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.40625","raw_pricing":{"prompt":"0.000000325","completion":"0.00000195","input_cache_write":"0.00000040625"}}'::jsonb),
  ('qwen', 'qwen3.6-flash', 'Qwen: Qwen3.6 Flash', 1000000, '["chat","multimodal"]'::jsonb, 0.1875, NULL, 1.125, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3.6-flash","source_name":"Qwen: Qwen3.6 Flash","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.234375","raw_pricing":{"prompt":"0.0000001875","completion":"0.000001125","input_cache_write":"0.000000234375"}}'::jsonb),
  ('qwen', 'qwen3.6-max-preview', 'Qwen: Qwen3.6 Max Preview', 262144, '["chat"]'::jsonb, 1.04, NULL, 6.24, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3.6-max-preview","source_name":"Qwen: Qwen3.6 Max Preview","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"1.3","raw_pricing":{"prompt":"0.00000104","completion":"0.00000624","input_cache_write":"0.0000013"}}'::jsonb),
  ('qwen', 'qwen3.5-plus-20260420', 'Qwen: Qwen3.5 Plus 2026-04-20', 1000000, '["chat","multimodal"]'::jsonb, 0.3, NULL, 1.8, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3.5-plus-20260420","source_name":"Qwen: Qwen3.5 Plus 2026-04-20","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.0000003","completion":"0.0000018"}}'::jsonb),
  ('qwen', 'qwen3-max', 'Qwen: Qwen3 Max', 262144, '["chat"]'::jsonb, 0.78, 0.156, 3.9, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-max","source_name":"Qwen: Qwen3 Max","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.975","raw_pricing":{"prompt":"0.00000078","completion":"0.0000039","input_cache_read":"0.000000156","input_cache_write":"0.000000975"}}'::jsonb),
  ('qwen', 'qwen3-max-thinking', 'Qwen: Qwen3 Max Thinking', 262144, '["chat"]'::jsonb, 0.78, NULL, 3.9, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-max-thinking","source_name":"Qwen: Qwen3 Max Thinking","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000078","completion":"0.0000039"}}'::jsonb),
  ('qwen', 'qwen3-coder-plus', 'Qwen: Qwen3 Coder Plus', 1000000, '["chat"]'::jsonb, 0.65, 0.13, 3.25, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-coder-plus","source_name":"Qwen: Qwen3 Coder Plus","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.8125","raw_pricing":{"prompt":"0.00000065","completion":"0.00000325","input_cache_read":"0.00000013","input_cache_write":"0.0000008125"}}'::jsonb),
  ('qwen', 'qwen3-coder-flash', 'Qwen: Qwen3 Coder Flash', 1000000, '["chat"]'::jsonb, 0.195, 0.039, 0.975, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-coder-flash","source_name":"Qwen: Qwen3 Coder Flash","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.24375","raw_pricing":{"prompt":"0.000000195","completion":"0.000000975","input_cache_read":"0.000000039","input_cache_write":"0.00000024375"}}'::jsonb),
  ('qwen', 'qwen3-coder', 'Qwen: Qwen3 Coder 480B A35B', 262144, '["chat"]'::jsonb, 0.22, NULL, 1.8, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-coder","source_name":"Qwen: Qwen3 Coder 480B A35B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000022","completion":"0.0000018"}}'::jsonb),
  ('qwen', 'qwen-plus', 'Qwen: Qwen-Plus', 1000000, '["chat"]'::jsonb, 0.26, 0.052, 0.78, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen-plus","source_name":"Qwen: Qwen-Plus","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.325","raw_pricing":{"prompt":"0.00000026","completion":"0.00000078","input_cache_read":"0.000000052","input_cache_write":"0.000000325"}}'::jsonb),
  ('qwen', 'qwen-plus-2025-07-28', 'Qwen: Qwen Plus 0728', 1000000, '["chat"]'::jsonb, 0.26, NULL, 0.78, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen-plus-2025-07-28","source_name":"Qwen: Qwen Plus 0728","source_unit":"USD per token","input_cache_write_unit_price_per_1m":"0.325","raw_pricing":{"prompt":"0.00000026","completion":"0.00000078","input_cache_write":"0.000000325"}}'::jsonb),
  ('qwen', 'qwen3-235b-a22b', 'Qwen: Qwen3 235B A22B', 131072, '["chat"]'::jsonb, 0.455, NULL, 1.82, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-235b-a22b","source_name":"Qwen: Qwen3 235B A22B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000455","completion":"0.00000182"}}'::jsonb),
  ('qwen', 'qwen3-32b', 'Qwen: Qwen3 32B', 40960, '["chat"]'::jsonb, 0.08, NULL, 0.28, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-32b","source_name":"Qwen: Qwen3 32B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000008","completion":"0.00000028"}}'::jsonb),
  ('qwen', 'qwen3-14b', 'Qwen: Qwen3 14B', 40960, '["chat"]'::jsonb, 0.1, NULL, 0.24, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-14b","source_name":"Qwen: Qwen3 14B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.0000001","completion":"0.00000024"}}'::jsonb),
  ('qwen', 'qwen3-8b', 'Qwen: Qwen3 8B', 40960, '["chat"]'::jsonb, 0.05, 0.05, 0.4, NULL, '{"source":"docs/ref/models.json","source_model_id":"qwen/qwen3-8b","source_name":"Qwen: Qwen3 8B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000005","completion":"0.0000004","input_cache_read":"0.00000005"}}'::jsonb),
  ('deepseek', 'deepseek-v4-pro', 'DeepSeek: DeepSeek V4 Pro', 1048576, '["chat"]'::jsonb, 0.435, 0.003625, 0.87, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-v4-pro","source_name":"DeepSeek: DeepSeek V4 Pro","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000435","completion":"0.00000087","input_cache_read":"0.000000003625"}}'::jsonb),
  ('deepseek', 'deepseek-v4-flash', 'DeepSeek: DeepSeek V4 Flash', 1048576, '["chat"]'::jsonb, 0.126, 0.0252, 0.252, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-v4-flash","source_name":"DeepSeek: DeepSeek V4 Flash","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000126","completion":"0.000000252","input_cache_read":"0.0000000252"}}'::jsonb),
  ('deepseek', 'deepseek-v3.2', 'DeepSeek: DeepSeek V3.2', 131072, '["chat"]'::jsonb, 0.252, 0.0252, 0.378, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-v3.2","source_name":"DeepSeek: DeepSeek V3.2","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000252","completion":"0.000000378","input_cache_read":"0.0000000252"}}'::jsonb),
  ('deepseek', 'deepseek-v3.2-speciale', 'DeepSeek: DeepSeek V3.2 Speciale', 163840, '["chat"]'::jsonb, 0.287, 0.058, 0.431, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-v3.2-speciale","source_name":"DeepSeek: DeepSeek V3.2 Speciale","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.000000287","completion":"0.000000431","input_cache_read":"0.000000058"}}'::jsonb),
  ('deepseek', 'deepseek-chat-v3.1', 'DeepSeek: DeepSeek V3.1', 163840, '["chat"]'::jsonb, 0.21, 0.13, 0.79, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-chat-v3.1","source_name":"DeepSeek: DeepSeek V3.1","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000021","completion":"0.00000079","input_cache_read":"0.00000013"}}'::jsonb),
  ('deepseek', 'deepseek-v3.1-terminus', 'DeepSeek: DeepSeek V3.1 Terminus', 163840, '["chat"]'::jsonb, 0.27, 0.13, 0.95, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-v3.1-terminus","source_name":"DeepSeek: DeepSeek V3.1 Terminus","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000027","completion":"0.00000095","input_cache_read":"0.00000013"}}'::jsonb),
  ('deepseek', 'deepseek-r1-0528', 'DeepSeek: R1 0528', 163840, '["chat"]'::jsonb, 0.5, 0.35, 2.15, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-r1-0528","source_name":"DeepSeek: R1 0528","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.0000005","completion":"0.00000215","input_cache_read":"0.00000035"}}'::jsonb),
  ('deepseek', 'deepseek-chat-v3-0324', 'DeepSeek: DeepSeek V3 0324', 163840, '["chat"]'::jsonb, 0.2, 0.135, 0.77, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-chat-v3-0324","source_name":"DeepSeek: DeepSeek V3 0324","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.0000002","completion":"0.00000077","input_cache_read":"0.000000135"}}'::jsonb),
  ('deepseek', 'deepseek-r1', 'DeepSeek: R1', 64000, '["chat"]'::jsonb, 0.7, NULL, 2.5, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-r1","source_name":"DeepSeek: R1","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.0000007","completion":"0.0000025"}}'::jsonb),
  ('deepseek', 'deepseek-chat', 'DeepSeek: DeepSeek V3', 163840, '["chat"]'::jsonb, 0.32, NULL, 0.89, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-chat","source_name":"DeepSeek: DeepSeek V3","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000032","completion":"0.00000089"}}'::jsonb),
  ('deepseek', 'deepseek-r1-distill-qwen-32b', 'DeepSeek: R1 Distill Qwen 32B', 32768, '["chat"]'::jsonb, 0.29, NULL, 0.29, NULL, '{"source":"docs/ref/models.json","source_model_id":"deepseek/deepseek-r1-distill-qwen-32b","source_name":"DeepSeek: R1 Distill Qwen 32B","source_unit":"USD per token","input_cache_write_unit_price_per_1m":null,"raw_pricing":{"prompt":"0.00000029","completion":"0.00000029"}}'::jsonb)
)
AS model_seed (
  provider_name,
  model_name,
  display_name,
  context_window,
  capabilities,
  input_unit_price,
  cached_input_unit_price,
  output_unit_price,
  reasoning_output_unit_price,
  config
);

INSERT INTO models (
  provider_id,
  name,
  display_name,
  capabilities,
  context_window,
  status
)
SELECT
  providers.id,
  model_seed.model_name,
  model_seed.display_name,
  model_seed.capabilities,
  model_seed.context_window,
  'active'
FROM tmp_common_model_price_seed AS model_seed
JOIN providers ON providers.name = model_seed.provider_name
WHERE NOT EXISTS (
  SELECT 1
  FROM models
  WHERE models.provider_id = providers.id
    AND models.name = model_seed.model_name
);

UPDATE model_price_configs AS price_config
SET
  model_name = model_seed.model_name,
  unit_type = 'tokens',
  unit_quantity = 1000000,
  input_unit_price = model_seed.input_unit_price,
  cached_input_unit_price = model_seed.cached_input_unit_price,
  output_unit_price = model_seed.output_unit_price,
  reasoning_output_unit_price = model_seed.reasoning_output_unit_price,
  config = model_seed.config,
  updated_at = now()
FROM tmp_common_model_price_seed AS model_seed
JOIN providers ON providers.name = model_seed.provider_name
JOIN models ON models.provider_id = providers.id AND models.name = model_seed.model_name
WHERE price_config.model_id = models.id
  AND price_config.currency_code = 'USD'
  AND price_config.status = 'active'
  AND price_config.effective_to IS NULL;

INSERT INTO model_price_configs (
  provider_id,
  model_id,
  model_name,
  currency_code,
  unit_type,
  unit_quantity,
  input_unit_price,
  cached_input_unit_price,
  output_unit_price,
  reasoning_output_unit_price,
  config,
  status
)
SELECT
  providers.id,
  models.id,
  model_seed.model_name,
  'USD',
  'tokens',
  1000000,
  model_seed.input_unit_price,
  model_seed.cached_input_unit_price,
  model_seed.output_unit_price,
  model_seed.reasoning_output_unit_price,
  model_seed.config,
  'active'
FROM tmp_common_model_price_seed AS model_seed
JOIN providers ON providers.name = model_seed.provider_name
JOIN models ON models.provider_id = providers.id AND models.name = model_seed.model_name
WHERE NOT EXISTS (
  SELECT 1
  FROM model_price_configs
  WHERE model_price_configs.model_id = models.id
    AND model_price_configs.currency_code = 'USD'
    AND model_price_configs.status = 'active'
    AND model_price_configs.effective_to IS NULL
);

SELECT
  (SELECT count(*) FROM tmp_common_model_price_seed) AS seeded_models,
  count(models.id) AS available_models,
  count(model_price_configs.id) AS active_usd_price_configs
FROM tmp_common_model_price_seed AS model_seed
JOIN providers ON providers.name = model_seed.provider_name
LEFT JOIN models ON models.provider_id = providers.id AND models.name = model_seed.model_name
LEFT JOIN model_price_configs
  ON model_price_configs.model_id = models.id
  AND model_price_configs.currency_code = 'USD'
  AND model_price_configs.status = 'active'
  AND model_price_configs.effective_to IS NULL;
