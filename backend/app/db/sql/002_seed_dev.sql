INSERT INTO clients (name, description, status)
VALUES ('demo-client', 'Local development client', 'active')
ON CONFLICT (name) DO NOTHING;

INSERT INTO providers (
  name,
  provider_type,
  base_url,
  encrypted_api_key,
  protocol_modes,
  auth_type,
  auth_config,
  allowed_paths,
  blocked_headers,
  usage_parser_type,
  status
)
VALUES (
  'local-openai-compatible',
  'openai_compatible',
  'https://api.openai.com',
  '',
  '["openai_compatible"]'::jsonb,
  'bearer_token',
  '{"header":"Authorization"}'::jsonb,
  '[]'::jsonb,
  '["authorization","cookie","set-cookie","host","content-length"]'::jsonb,
  'openai',
  'disabled'
)
ON CONFLICT (name) DO NOTHING;
