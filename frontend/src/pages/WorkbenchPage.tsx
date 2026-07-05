import { Clipboard, RefreshCw, Send } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Field, Input, Section, Select, TextArea } from "../components/ui";
import { api, apiWithMeta } from "../lib/api";
import type {
  Alias,
  ApiKey,
  Client,
  JsonValue,
  Model,
  PageProps,
  Provider,
  WorkbenchChatTestResponse
} from "../types/gateway";

type WorkbenchForm = {
  client_id: string;
  api_key_id: string;
  model: string;
  system_prompt: string;
  user_prompt: string;
  temperature: string;
  top_p: string;
  max_tokens: string;
};

type DetailTab = "summary" | "request" | "response";

const defaultForm: WorkbenchForm = {
  client_id: "",
  api_key_id: "",
  model: "",
  system_prompt: "You are a helpful assistant.",
  user_prompt: "Say hello in one sentence.",
  temperature: "0.7",
  top_p: "",
  max_tokens: "512"
};

function compactJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function assistantText(body: Record<string, JsonValue> | null) {
  const choices = body?.choices;
  if (!Array.isArray(choices) || choices.length === 0) return "";
  const first = choices[0];
  if (!first || typeof first !== "object" || Array.isArray(first)) return "";
  const message = first.message;
  if (!message || typeof message !== "object" || Array.isArray(message)) return "";
  const content = message.content;
  return typeof content === "string" ? content : compactJson(content);
}

function numericField(value: string) {
  if (!value.trim()) return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
}

function buildPayload(form: WorkbenchForm) {
  const messages = [
    ...(form.system_prompt.trim() ? [{ role: "system", content: form.system_prompt.trim() }] : []),
    { role: "user", content: form.user_prompt.trim() }
  ];
  return {
    api_key_id: Number(form.api_key_id),
    model: form.model.trim(),
    messages,
    stream: false,
    temperature: numericField(form.temperature),
    top_p: numericField(form.top_p),
    max_tokens: numericField(form.max_tokens)
  };
}

function jsonBodyFromForm(form: WorkbenchForm) {
  const { api_key_id: _apiKeyId, ...payload } = buildPayload(form);
  return compactJson(payload);
}

function valueOrDash(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "-" : value;
}

function Metric({
  label,
  value,
  emphasis = false
}: {
  label: string;
  value: React.ReactNode;
  emphasis?: boolean;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className={`mt-1 truncate ${emphasis ? "text-lg font-semibold text-ink" : "text-sm text-slate-700"}`}>
        {value}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_minmax(0,1fr)] gap-4 border-t border-line py-2 text-sm first:border-t-0">
      <div className="text-slate-500">{label}</div>
      <div className="min-w-0 break-words text-ink">{valueOrDash(value as string | number | null | undefined)}</div>
    </div>
  );
}

export function WorkbenchPage({ headers, setNotice }: PageProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [form, setForm] = useState<WorkbenchForm>(defaultForm);
  const [mode, setMode] = useState<"form" | "json">("form");
  const [rawBody, setRawBody] = useState(jsonBodyFromForm(defaultForm));
  const [requestPreview, setRequestPreview] = useState("");
  const [result, setResult] = useState<WorkbenchChatTestResponse | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("summary");
  const [loading, setLoading] = useState(false);

  const clientKeys = useMemo(
    () => apiKeys.filter((key) => !form.client_id || key.client_id === Number(form.client_id)),
    [apiKeys, form.client_id]
  );
  const clientsById = useMemo(() => new Map(clients.map((client) => [client.id, client])), [clients]);
  const keysById = useMemo(() => new Map(apiKeys.map((key) => [key.id, key])), [apiKeys]);
  const providersById = useMemo(() => new Map(providers.map((provider) => [provider.id, provider])), [providers]);
  const modelsById = useMemo(() => new Map(models.map((model) => [model.id, model])), [models]);

  const selectedClient = clientsById.get(Number(form.client_id));
  const selectedKey = keysById.get(Number(form.api_key_id));
  const finalProvider = result?.meta.final_provider_id
    ? providersById.get(result.meta.final_provider_id)
    : result?.meta.provider_id
      ? providersById.get(result.meta.provider_id)
      : null;
  const finalModel = result?.meta.final_model_id
    ? modelsById.get(result.meta.final_model_id)
    : result?.meta.model_id
      ? modelsById.get(result.meta.model_id)
      : null;
  const responseText = assistantText(result?.body || null);
  const ready = Boolean(form.api_key_id && form.model && form.user_prompt.trim());
  const statusTone = result?.meta.status === "success" ? "good" : result?.meta.status === "failed" ? "bad" : "neutral";

  async function load() {
    const [clientData, keyData, aliasData, providerData, modelData] = await Promise.all([
      apiWithMeta<Client[]>("/admin/clients?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<ApiKey[]>("/admin/api-keys?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Alias[]>("/admin/model-aliases?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Provider[]>("/admin/providers?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Model[]>("/admin/models?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setClients(clientData.data);
    setApiKeys(keyData.data);
    setAliases(aliasData.data);
    setProviders(providerData.data);
    setModels(modelData.data);
    setForm((current) => {
      const clientId = current.client_id || (clientData.data[0] ? String(clientData.data[0].id) : "");
      const key = keyData.data.find((item) => item.client_id === Number(clientId)) || keyData.data[0];
      return {
        ...current,
        client_id: clientId,
        api_key_id: current.api_key_id || (key ? String(key.id) : ""),
        model: current.model || aliasData.data[0]?.alias || ""
      };
    });
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  useEffect(() => {
    if (mode === "form") {
      setRawBody(jsonBodyFromForm(form));
    }
  }, [form, mode]);

  function updateForm(patch: Partial<WorkbenchForm>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function changeClient(clientId: string) {
    const nextKey = apiKeys.find((key) => key.client_id === Number(clientId));
    updateForm({ client_id: clientId, api_key_id: nextKey ? String(nextKey.id) : "" });
  }

  function syncJson() {
    setRawBody(jsonBodyFromForm(form));
    setMode("json");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      let payload;
      try {
        payload = mode === "json"
          ? { ...JSON.parse(rawBody), api_key_id: Number(form.api_key_id), stream: false }
          : buildPayload(form);
      } catch {
        setNotice("Request body is not valid JSON");
        return;
      }
      setRequestPreview(compactJson(payload));
      const response = await api<WorkbenchChatTestResponse>(
        "/admin/workbench/chat-test",
        {
          method: "POST",
          headers,
          body: JSON.stringify(payload)
        },
        setNotice
      );
      setResult(response);
      setDetailTab("summary");
      setNotice(`Workbench request ${response.request_id.slice(0, 12)} completed`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-4">
          <Section
            title="Test Setup"
            action={
              <div className="flex items-center gap-2">
                <Button onClick={load} variant="light" title="Refresh options">
                  <RefreshCw size={15} />
                </Button>
                <Button type="submit" disabled={loading || !ready}>
                  <Send size={15} />
                  {loading ? "Sending" : "Send"}
                </Button>
              </div>
            }
          >
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-md border border-line bg-panel px-3 py-2">
                <span className="text-xs font-medium text-slate-500">Status</span>
                <Badge tone={statusTone}>{result?.meta.status || (ready ? "ready" : "setup required")}</Badge>
              </div>
              <Field label="Client">
                <Select value={form.client_id} onChange={(event) => changeClient(event.target.value)}>
                  <option value="">Select client</option>
                  {clients.map((client) => (
                    <option key={client.id} value={client.id}>
                      {client.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="API Key">
                <Select
                  value={form.api_key_id}
                  onChange={(event) => updateForm({ api_key_id: event.target.value })}
                  required
                >
                  <option value="">Select API key</option>
                  {clientKeys.map((key) => (
                    <option key={key.id} value={key.id}>
                      {key.name} / {key.key_prefix}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Model Alias">
                <Select value={form.model} onChange={(event) => updateForm({ model: event.target.value })} required>
                  <option value="">Select alias</option>
                  {aliases.map((alias) => (
                    <option key={alias.id} value={alias.alias}>
                      {alias.alias}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Temp">
                  <Input value={form.temperature} onChange={(event) => updateForm({ temperature: event.target.value })} />
                </Field>
                <Field label="Top P">
                  <Input value={form.top_p} onChange={(event) => updateForm({ top_p: event.target.value })} />
                </Field>
                <Field label="Max">
                  <Input value={form.max_tokens} onChange={(event) => updateForm({ max_tokens: event.target.value })} />
                </Field>
              </div>
            </div>
          </Section>

          <Section
            title="Prompt"
            action={
              <div className="flex items-center gap-2">
                <Button onClick={() => setMode("form")} variant={mode === "form" ? "dark" : "light"}>
                  Form
                </Button>
                <Button onClick={syncJson} variant={mode === "json" ? "dark" : "light"}>
                  JSON
                </Button>
              </div>
            }
          >
            {mode === "form" ? (
              <div className="space-y-3">
                <Field label="System">
                  <TextArea
                    value={form.system_prompt}
                    onChange={(event) => updateForm({ system_prompt: event.target.value })}
                    className="min-h-20"
                  />
                </Field>
                <Field label="User">
                  <TextArea
                    value={form.user_prompt}
                    onChange={(event) => updateForm({ user_prompt: event.target.value })}
                    className="min-h-28"
                    required
                  />
                </Field>
              </div>
            ) : (
              <TextArea value={rawBody} onChange={(event) => setRawBody(event.target.value)} className="min-h-80" />
            )}
          </Section>
        </div>

        <div className="space-y-5 lg:col-span-8">
          <Section
            title="Assistant Response"
            action={
              result ? (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>{result.meta.total_tokens} tokens</span>
                  <span>{result.meta.cache_hit ? "cache hit" : "live call"}</span>
                  <span>{result.meta.failover_triggered ? `failover ${result.meta.failover_attempts}` : "primary"}</span>
                </div>
              ) : null
            }
          >
            <div className="mb-4 grid gap-3 md:grid-cols-4">
              <Metric label="Target Alias" value={form.model || "-"} emphasis />
              <Metric label="Provider" value={finalProvider?.name || "-"} />
              <Metric label="Model" value={finalModel?.display_name || finalModel?.name || "-"} />
              <Metric label="Latency" value={result ? `${result.meta.latency_ms ?? 0} ms` : "-"} />
            </div>
            <pre className="min-h-56 max-h-[460px] overflow-auto whitespace-pre-wrap break-words rounded-md border border-line bg-panel p-4 text-sm leading-6 text-ink">
              {responseText || "Run a test to see the assistant response."}
            </pre>
          </Section>

          <Section
            title="Diagnostics"
            action={
              <div className="flex items-center gap-2">
                {(["summary", "request", "response"] as DetailTab[]).map((tab) => (
                  <Button
                    key={tab}
                    onClick={() => setDetailTab(tab)}
                    variant={detailTab === tab ? "dark" : "light"}
                  >
                    {tab}
                  </Button>
                ))}
              </div>
            }
          >
            {detailTab === "summary" && (
              <div className="grid gap-x-6 md:grid-cols-2">
                <DetailRow label="Client" value={selectedClient?.name} />
                <DetailRow label="API Key" value={selectedKey ? `${selectedKey.name} / ${selectedKey.key_prefix}` : null} />
                <DetailRow label="Request ID" value={result?.request_id} />
                <DetailRow label="Usage Log" value={result?.meta.usage_log_id} />
                <DetailRow label="Usage Status" value={result?.meta.usage_status} />
                <DetailRow label="Prompt Tokens" value={result?.meta.prompt_tokens} />
                <DetailRow label="Completion Tokens" value={result?.meta.completion_tokens} />
                <DetailRow label="Total Tokens" value={result?.meta.total_tokens} />
                <DetailRow label="Cache" value={result ? (result.meta.cache_hit ? "hit" : "miss") : null} />
                <DetailRow
                  label="Failover"
                  value={result ? (result.meta.failover_triggered ? result.meta.failover_attempts : "no") : null}
                />
              </div>
            )}
            {detailTab === "request" && (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button onClick={() => navigator.clipboard.writeText(requestPreview || rawBody)} variant="light">
                    <Clipboard size={15} />
                    Copy
                  </Button>
                </div>
                <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-panel p-3 text-xs leading-5">
                  {requestPreview || rawBody}
                </pre>
              </div>
            )}
            {detailTab === "response" && (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button onClick={() => navigator.clipboard.writeText(result ? compactJson(result) : "{}")} variant="light">
                    <Clipboard size={15} />
                    Copy
                  </Button>
                </div>
                <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-panel p-3 text-xs leading-5">
                  {result ? compactJson(result) : "{}"}
                </pre>
              </div>
            )}
          </Section>
        </div>
      </div>
    </form>
  );
}
