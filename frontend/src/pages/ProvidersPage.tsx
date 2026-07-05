import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Pencil,
  Plus,
  RefreshCw,
  SlidersHorizontal,
  Trash2
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";

import {
  Badge,
  Button,
  DataTable,
  Field,
  Input,
  Modal,
  Pagination,
  Section,
  Select,
  TextArea
} from "../components/ui";
import { api, apiWithMeta, parseCsv } from "../lib/api";
import type { JsonValue, PageProps, Provider } from "../types/gateway";

const PAGE_SIZE = 20;

type ProviderType = "gemini" | "openai_compatible";

type ProviderForm = {
  name: string;
  provider_type: string;
  base_url: string;
  encrypted_api_key: string;
  config: string;
  protocol_modes: string;
  auth_type: string;
  auth_config: string;
  allowed_paths: string;
  blocked_headers: string;
  usage_parser_type: string;
  timeout_ms: string;
  native_rate_limit_per_minute: string;
  status: string;
  allow_streaming: boolean;
};

const PROVIDER_TEMPLATES: Record<
  ProviderType,
  Pick<
    ProviderForm,
    | "name"
    | "provider_type"
    | "base_url"
    | "config"
    | "protocol_modes"
    | "auth_type"
    | "auth_config"
    | "allowed_paths"
    | "blocked_headers"
    | "usage_parser_type"
    | "native_rate_limit_per_minute"
  > & { label: string }
> = {
  gemini: {
    label: "Gemini native proxy",
    name: "gemini",
    provider_type: "gemini",
    base_url: "https://generativelanguage.googleapis.com",
    config: "{}",
    protocol_modes: "native_proxy",
    auth_type: "api_key_query",
    auth_config: '{"query_name":"key"}',
    allowed_paths: "v1beta/models/*, v1beta/models/*:generateContent, v1beta/models/*:streamGenerateContent",
    blocked_headers: "authorization, cookie",
    usage_parser_type: "gemini",
    native_rate_limit_per_minute: "60"
  },
  openai_compatible: {
    label: "OpenAI compatible chat",
    name: "openai",
    provider_type: "openai_compatible",
    base_url: "https://api.openai.com",
    config: "{}",
    protocol_modes: "openai_compatible",
    auth_type: "bearer_token",
    auth_config: '{"header":"Authorization"}',
    allowed_paths: "",
    blocked_headers: "authorization, cookie, set-cookie, host, content-length",
    usage_parser_type: "openai",
    native_rate_limit_per_minute: ""
  }
};

function isProviderType(value: string): value is ProviderType {
  return value === "gemini" || value === "openai_compatible";
}

function providerTemplate(value: string) {
  return PROVIDER_TEMPLATES[isProviderType(value) ? value : "gemini"];
}

function defaultProviderForm(providerType: ProviderType = "gemini"): ProviderForm {
  const template = PROVIDER_TEMPLATES[providerType];
  return {
    name: template.name,
    provider_type: template.provider_type,
    base_url: template.base_url,
    encrypted_api_key: "",
    config: template.config,
    protocol_modes: template.protocol_modes,
    auth_type: template.auth_type,
    auth_config: template.auth_config,
    allowed_paths: template.allowed_paths,
    blocked_headers: template.blocked_headers,
    usage_parser_type: template.usage_parser_type,
    timeout_ms: "60000",
    native_rate_limit_per_minute: template.native_rate_limit_per_minute,
    status: "active",
    allow_streaming: true
  };
}

function applyProviderTemplate(form: ProviderForm, providerType: ProviderType): ProviderForm {
  const currentTemplate = providerTemplate(form.provider_type);
  const nextTemplate = PROVIDER_TEMPLATES[providerType];

  return {
    ...form,
    name: !form.name || form.name === currentTemplate.name ? nextTemplate.name : form.name,
    provider_type: nextTemplate.provider_type,
    base_url: !form.base_url || form.base_url === currentTemplate.base_url ? nextTemplate.base_url : form.base_url,
    config: nextTemplate.config,
    protocol_modes: nextTemplate.protocol_modes,
    auth_type: nextTemplate.auth_type,
    auth_config: nextTemplate.auth_config,
    allowed_paths: nextTemplate.allowed_paths,
    blocked_headers: nextTemplate.blocked_headers,
    usage_parser_type: nextTemplate.usage_parser_type,
    native_rate_limit_per_minute: nextTemplate.native_rate_limit_per_minute
  };
}

function providerFormFromProvider(provider: Provider): ProviderForm {
  return {
    name: provider.name,
    provider_type: provider.provider_type,
    base_url: provider.base_url,
    encrypted_api_key: provider.encrypted_api_key || "",
    config: prettyJson(provider.config || {}),
    protocol_modes: provider.protocol_modes.join(", "),
    auth_type: provider.auth_type,
    auth_config: prettyJson(provider.auth_config || {}),
    allowed_paths: provider.allowed_paths.join(", "),
    blocked_headers: provider.blocked_headers.join(", "),
    usage_parser_type: provider.usage_parser_type,
    timeout_ms: String(provider.timeout_ms),
    native_rate_limit_per_minute: provider.native_rate_limit_per_minute
      ? String(provider.native_rate_limit_per_minute)
      : "",
    status: provider.status,
    allow_streaming: provider.allow_streaming
  };
}

function prettyJson(value: Record<string, JsonValue>) {
  return JSON.stringify(value || {}, null, 2);
}

function providerPayload(form: ProviderForm, keepExistingApiKey: boolean) {
  const payload = {
    name: form.name.trim(),
    provider_type: form.provider_type,
    base_url: form.base_url.trim(),
    encrypted_api_key: form.encrypted_api_key || null,
    config: JSON.parse(form.config || "{}"),
    protocol_modes: parseCsv(form.protocol_modes),
    auth_type: form.auth_type,
    auth_config: JSON.parse(form.auth_config || "{}"),
    allowed_paths: parseCsv(form.allowed_paths),
    blocked_headers: parseCsv(form.blocked_headers),
    usage_parser_type: form.usage_parser_type,
    timeout_ms: Number(form.timeout_ms),
    native_rate_limit_per_minute: form.native_rate_limit_per_minute
      ? Number(form.native_rate_limit_per_minute)
      : null,
    status: form.status,
    allow_streaming: form.allow_streaming
  };

  if (keepExistingApiKey && !form.encrypted_api_key) {
    const { encrypted_api_key: _encryptedApiKey, ...payloadWithoutApiKey } = payload;
    return payloadWithoutApiKey;
  }

  return payload;
}

function ProviderAdvancedFields({
  form,
  onChange
}: {
  form: ProviderForm;
  onChange: (patch: Partial<ProviderForm>) => void;
}) {
  return (
    <div className="grid gap-3 border-t border-line p-3 md:grid-cols-2">
      <Field label="Protocol Modes">
        <Input
          value={form.protocol_modes}
          onChange={(event) => onChange({ protocol_modes: event.target.value })}
        />
      </Field>
      <Field label="Auth Type">
        <Select value={form.auth_type} onChange={(event) => onChange({ auth_type: event.target.value })}>
          <option value="api_key_query">api_key_query</option>
          <option value="api_key_header">api_key_header</option>
          <option value="bearer_token">bearer_token</option>
        </Select>
      </Field>
      <Field label="Usage Parser">
        <Select
          value={form.usage_parser_type}
          onChange={(event) => onChange({ usage_parser_type: event.target.value })}
        >
          <option value="gemini">gemini</option>
          <option value="openai">openai</option>
          <option value="none">none</option>
        </Select>
      </Field>
      <Field label="Timeout ms">
        <Input value={form.timeout_ms} onChange={(event) => onChange({ timeout_ms: event.target.value })} />
      </Field>
      <Field label="Native Rate / min">
        <Input
          value={form.native_rate_limit_per_minute}
          onChange={(event) => onChange({ native_rate_limit_per_minute: event.target.value })}
        />
      </Field>
      <Field label="Blocked Headers">
        <Input
          value={form.blocked_headers}
          onChange={(event) => onChange({ blocked_headers: event.target.value })}
        />
      </Field>
      <div className="md:col-span-2">
        <Field label="Allowed Paths">
          <Input value={form.allowed_paths} onChange={(event) => onChange({ allowed_paths: event.target.value })} />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Provider Config JSON">
          <TextArea value={form.config} onChange={(event) => onChange({ config: event.target.value })} />
        </Field>
      </div>
      <div className="md:col-span-2">
        <Field label="Auth Config JSON">
          <TextArea value={form.auth_config} onChange={(event) => onChange({ auth_config: event.target.value })} />
        </Field>
      </div>
    </div>
  );
}

export function ProvidersPage({ headers, setNotice }: PageProps) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerTotal, setProviderTotal] = useState(0);
  const [providerPage, setProviderPage] = useState(1);
  const [form, setForm] = useState<ProviderForm>(defaultProviderForm());
  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [editingProviderId, setEditingProviderId] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Provider | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  async function load() {
    const offset = (providerPage - 1) * PAGE_SIZE;
    const result = await apiWithMeta<Provider[]>(
      `/admin/providers?limit=${PAGE_SIZE}&offset=${offset}`,
      { headers },
      setNotice
    );
    setProviders(result.data);
    setProviderTotal(result.total);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, providerPage]);

  useEffect(() => {
    setProviderPage((page) => Math.min(page, Math.max(1, Math.ceil(providerTotal / PAGE_SIZE))));
  }, [providerTotal]);

  function openCreateProvider() {
    setEditingProviderId(null);
    setForm(defaultProviderForm());
    setShowAdvanced(false);
    setModalMode("create");
  }

  function openEditProvider(provider: Provider) {
    setEditingProviderId(provider.id);
    setForm(providerFormFromProvider(provider));
    setShowAdvanced(false);
    setModalMode("edit");
  }

  function updateForm(patch: Partial<ProviderForm>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function changeProviderType(value: string) {
    if (!isProviderType(value)) return;
    setForm((current) => applyProviderTemplate(current, value));
  }

  async function submitProvider(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = modalMode === "edit" && editingProviderId !== null;
    let payload: ReturnType<typeof providerPayload>;
    try {
      payload = providerPayload(form, isEdit);
    } catch {
      setNotice("Provider/Auth JSON config is invalid");
      return;
    }

    await api<Provider>(
      isEdit ? `/admin/providers/${editingProviderId}` : "/admin/providers",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(payload)
      },
      setNotice
    );
    setModalMode(null);
    setNotice(isEdit ? "Provider updated" : "Provider created");
    await load();
  }

  async function testProvider(id: number) {
    const result = await api<Record<string, JsonValue>>(
      `/admin/providers/${id}/test`,
      { method: "POST", headers },
      setNotice
    );
    setNotice(JSON.stringify(result));
    await load();
  }

  async function removeProvider() {
    if (!removeTarget) return;
    await api<unknown>(
      `/admin/providers/${removeTarget.id}`,
      { method: "DELETE", headers },
      setNotice
    );
    setRemoveTarget(null);
    setNotice("Provider removed");
    await load();
  }

  return (
    <div className="space-y-5">
      <Section
        title="Providers"
        action={
          <div className="flex items-center gap-2">
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button onClick={openCreateProvider}>
              <Plus size={15} />
              New Provider
            </Button>
          </div>
        }
      >
        <DataTable
          columns={["id", "name", "type", "modes", "auth", "status", "health", "stream", "actions"]}
          rows={providers.map((provider) => [
            provider.id,
            provider.name,
            provider.provider_type,
            provider.protocol_modes.join(", "),
            provider.auth_type,
            <Badge tone={provider.status === "active" ? "good" : "bad"}>{provider.status}</Badge>,
            <Badge
              tone={
                provider.health_status === "healthy"
                  ? "good"
                  : provider.health_status === "unhealthy"
                    ? "bad"
                    : "neutral"
              }
            >
              {provider.health_status}
            </Badge>,
            provider.allow_streaming ? "yes" : "no",
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => testProvider(provider.id)} variant="light">
                <CheckCircle2 size={14} />
                Test
              </Button>
              <Button onClick={() => openEditProvider(provider)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button onClick={() => setRemoveTarget(provider)} variant="light">
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination
          page={providerPage}
          pageSize={PAGE_SIZE}
          total={providerTotal}
          onPageChange={setProviderPage}
        />
      </Section>

      <Modal
        open={modalMode !== null}
        title={modalMode === "edit" ? "Edit Provider" : "Create Provider"}
        onClose={() => setModalMode(null)}
      >
        <form onSubmit={submitProvider} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Provider">
              <Select value={form.provider_type} onChange={(event) => changeProviderType(event.target.value)}>
                <option value="gemini">{PROVIDER_TEMPLATES.gemini.label}</option>
                <option value="openai_compatible">{PROVIDER_TEMPLATES.openai_compatible.label}</option>
              </Select>
            </Field>
            <Field label="Name">
              <Input value={form.name} onChange={(event) => updateForm({ name: event.target.value })} required />
            </Field>
            <Field label="Base URL">
              <Input
                value={form.base_url}
                onChange={(event) => updateForm({ base_url: event.target.value })}
                required
              />
            </Field>
            <Field label="API Key">
              <Input
                value={form.encrypted_api_key}
                onChange={(event) => updateForm({ encrypted_api_key: event.target.value })}
                placeholder={modalMode === "edit" ? "Leave blank to keep current value" : ""}
              />
            </Field>
            <Field label="Status">
              <Select value={form.status} onChange={(event) => updateForm({ status: event.target.value })}>
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <label className="flex h-9 items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.allow_streaming}
                onChange={(event) => updateForm({ allow_streaming: event.target.checked })}
                className="h-4 w-4 rounded border-line"
              />
              Allow streaming
            </label>
          </div>
          <div className="overflow-hidden rounded-md border border-line bg-white">
            <button
              type="button"
              onClick={() => setShowAdvanced((value) => !value)}
              className="flex h-10 w-full items-center justify-between px-3 text-left text-sm font-medium text-ink"
            >
              <span className="inline-flex items-center gap-2">
                <SlidersHorizontal size={15} />
                Advanced
              </span>
              {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showAdvanced && <ProviderAdvancedFields form={form} onChange={updateForm} />}
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit">
              {modalMode === "edit" ? <Pencil size={15} /> : <Plus size={15} />}
              {modalMode === "edit" ? "Save Provider" : "Create Provider"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={removeTarget !== null} title="Remove Provider" onClose={() => setRemoveTarget(null)}>
        <div className="space-y-4">
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Remove <span className="font-semibold">{removeTarget?.name}</span>? This also removes its models and
            route rules that depend on those models.
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRemoveTarget(null)} variant="light">
              Cancel
            </Button>
            <Button onClick={removeProvider}>
              <Trash2 size={15} />
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
