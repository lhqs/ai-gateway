import { BookOpen, Copy, KeyRound, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import {
  Badge,
  Button,
  DataTable,
  Field,
  Input,
  Modal,
  Pagination,
  Section,
  Select
} from "../components/ui";
import { api, apiWithMeta, gatewayV1Base, jsonPreview, parseCsv } from "../lib/api";
import type { ApiKey, Client, JsonValue, PageProps } from "../types/gateway";

const PAGE_SIZE = 8;

type AccessForm = {
  model_aliases: string;
  provider_names: string;
  native_paths: string;
};

type ClientForm = AccessForm & {
  name: string;
  description: string;
  status: string;
};

type KeyForm = AccessForm & {
  client_id: string;
  name: string;
  status: string;
};

type RemoveTarget = {
  type: "client" | "key";
  id: number;
  label: string;
};

type UsageTab = "curl" | "sdk" | "env";

function nextClientName(clients: Client[]) {
  const existingNames = new Set(clients.map((client) => client.name));
  let index = 1;
  let candidate = "client";
  while (existingNames.has(candidate)) {
    index += 1;
    candidate = `client-${index}`;
  }
  return candidate;
}

function defaultClientForm(name = "client"): ClientForm {
  return {
    name,
    description: "Default gateway client",
    status: "active",
    model_aliases: "*",
    provider_names: "*",
    native_paths: "*"
  };
}

function defaultKeyForm(clientId = ""): KeyForm {
  return {
    client_id: clientId,
    name: "full-access-key",
    status: "active",
    model_aliases: "*",
    provider_names: "*",
    native_paths: "*"
  };
}

function csvValue(value: JsonValue | undefined, fallback = "*") {
  if (Array.isArray(value)) return value.join(", ");
  return typeof value === "string" ? value : fallback;
}

function accessFromConfig(accessConfig: Record<string, JsonValue>): AccessForm {
  return {
    model_aliases: csvValue(accessConfig.model_aliases),
    provider_names: csvValue(accessConfig.provider_names),
    native_paths: csvValue(accessConfig.native_paths)
  };
}

function hasFullAccess(accessConfig: Record<string, JsonValue>) {
  const access = accessFromConfig(accessConfig);
  return access.model_aliases === "*" && access.provider_names === "*" && access.native_paths === "*";
}

function accessPayload(fullAccess: boolean, form: AccessForm) {
  if (fullAccess) {
    return {
      model_aliases: ["*"],
      provider_names: ["*"],
      native_paths: ["*"]
    };
  }

  return {
    model_aliases: parseCsv(form.model_aliases),
    provider_names: parseCsv(form.provider_names),
    native_paths: parseCsv(form.native_paths)
  };
}

function clientFormFromClient(client: Client): ClientForm {
  return {
    name: client.name,
    description: client.description || "",
    status: client.status,
    ...accessFromConfig(client.access_config)
  };
}

function keyFormFromKey(key: ApiKey): KeyForm {
  return {
    client_id: String(key.client_id),
    name: key.name,
    status: key.status,
    ...accessFromConfig(key.access_config)
  };
}

function apiKeyValue(key: ApiKey) {
  return key.key || "<API_KEY>";
}

function curlSnippet(baseUrl: string, key: ApiKey) {
  return `curl ${baseUrl}/chat/completions \\
  -H "Authorization: Bearer ${apiKeyValue(key)}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "default-chat",
    "messages": [{"role": "user", "content": "Hello"}]
  }'`;
}

function sdkSnippet(baseUrl: string) {
  return `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.LHQS_API_KEY,
  baseURL: "${baseUrl}"
});

const response = await client.chat.completions.create({
  model: "default-chat",
  messages: [{ role: "user", content: "Hello" }]
});`;
}

function envSnippet(baseUrl: string, key: ApiKey) {
  return `LHQS_API_KEY=${apiKeyValue(key)}
OPENAI_BASE_URL=${baseUrl}`;
}

function AccessFields<T extends AccessForm>({
  form,
  fullAccess,
  onChange,
  onFullAccessChange
}: {
  form: T;
  fullAccess: boolean;
  onChange: (patch: Partial<T>) => void;
  onFullAccessChange: (value: boolean) => void;
}) {
  return (
    <div className="space-y-3">
      <label className="flex h-9 items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={fullAccess}
          onChange={(event) => onFullAccessChange(event.target.checked)}
          className="h-4 w-4 rounded border-line"
        />
        Full access
      </label>
      {!fullAccess && (
        <div className="grid gap-3 rounded-md border border-line bg-panel p-3 md:grid-cols-3">
          <Field label="Model Aliases">
            <Input
              placeholder="default-chat, reasoning"
              value={form.model_aliases}
              onChange={(event) => onChange({ model_aliases: event.target.value } as Partial<T>)}
            />
          </Field>
          <Field label="Providers">
            <Input
              placeholder="openai, gemini, anthropic"
              value={form.provider_names}
              onChange={(event) => onChange({ provider_names: event.target.value } as Partial<T>)}
            />
          </Field>
          <Field label="Native Paths">
            <Input
              placeholder="v1beta/models/*"
              value={form.native_paths}
              onChange={(event) => onChange({ native_paths: event.target.value } as Partial<T>)}
            />
          </Field>
        </div>
      )}
    </div>
  );
}

export function ClientsPage({ headers, setNotice }: PageProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientOptions, setClientOptions] = useState<Client[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [clientTotal, setClientTotal] = useState(0);
  const [keyTotal, setKeyTotal] = useState(0);
  const [clientForm, setClientForm] = useState<ClientForm>(defaultClientForm());
  const [keyForm, setKeyForm] = useState<KeyForm>(defaultKeyForm());
  const [clientFullAccess, setClientFullAccess] = useState(true);
  const [keyFullAccess, setKeyFullAccess] = useState(true);
  const [clientModalMode, setClientModalMode] = useState<"create" | "edit" | null>(null);
  const [keyModalMode, setKeyModalMode] = useState<"create" | "edit" | null>(null);
  const [editingClientId, setEditingClientId] = useState<number | null>(null);
  const [editingKeyId, setEditingKeyId] = useState<number | null>(null);
  const [clientPage, setClientPage] = useState(1);
  const [keyPage, setKeyPage] = useState(1);
  const [newKey, setNewKey] = useState("");
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);
  const [usageTarget, setUsageTarget] = useState<ApiKey | null>(null);
  const [usageTab, setUsageTab] = useState<UsageTab>("curl");

  const clientNamesById = useMemo(
    () => new Map(clientOptions.map((client) => [client.id, client.name])),
    [clientOptions]
  );
  const baseUrl = gatewayV1Base();

  async function load() {
    const clientOffset = (clientPage - 1) * PAGE_SIZE;
    const keyOffset = (keyPage - 1) * PAGE_SIZE;
    const [clientPageData, keyPageData, optionData] = await Promise.all([
      apiWithMeta<Client[]>(
        `/admin/clients?limit=${PAGE_SIZE}&offset=${clientOffset}`,
        { headers },
        setNotice
      ),
      apiWithMeta<ApiKey[]>(
        `/admin/api-keys?limit=${PAGE_SIZE}&offset=${keyOffset}`,
        { headers },
        setNotice
      ),
      apiWithMeta<Client[]>("/admin/clients?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setClients(clientPageData.data);
    setClientTotal(clientPageData.total);
    setKeys(keyPageData.data);
    setKeyTotal(keyPageData.total);
    setClientOptions(optionData.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, clientPage, keyPage]);

  useEffect(() => {
    setClientPage((page) => Math.min(page, Math.max(1, Math.ceil(clientTotal / PAGE_SIZE))));
  }, [clientTotal]);

  useEffect(() => {
    setKeyPage((page) => Math.min(page, Math.max(1, Math.ceil(keyTotal / PAGE_SIZE))));
  }, [keyTotal]);

  function openCreateClient() {
    setEditingClientId(null);
    setClientForm(defaultClientForm(nextClientName(clientOptions)));
    setClientFullAccess(true);
    setClientModalMode("create");
  }

  function openEditClient(client: Client) {
    setEditingClientId(client.id);
    setClientForm(clientFormFromClient(client));
    setClientFullAccess(hasFullAccess(client.access_config));
    setClientModalMode("edit");
  }

  function openCreateKey() {
    setEditingKeyId(null);
    setNewKey("");
    setKeyForm(defaultKeyForm(clientOptions[0] ? String(clientOptions[0].id) : ""));
    setKeyFullAccess(true);
    setKeyModalMode("create");
  }

  function openEditKey(key: ApiKey) {
    setEditingKeyId(key.id);
    setNewKey("");
    setKeyForm(keyFormFromKey(key));
    setKeyFullAccess(hasFullAccess(key.access_config));
    setKeyModalMode("edit");
  }

  async function submitClient(event: React.FormEvent) {
    event.preventDefault();
    const payload = {
      name: clientForm.name,
      description: clientForm.description || null,
      status: clientForm.status,
      access_config: accessPayload(clientFullAccess, clientForm)
    };
    const isEdit = clientModalMode === "edit" && editingClientId !== null;

    await api<Client>(
      isEdit ? `/admin/clients/${editingClientId}` : "/admin/clients",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(payload)
      },
      setNotice
    );
    setClientModalMode(null);
    setNotice(isEdit ? "Client updated" : "Client created");
    await load();
  }

  async function submitKey(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = keyModalMode === "edit" && editingKeyId !== null;
    const payload = {
      name: keyForm.name,
      status: keyForm.status,
      access_config: accessPayload(keyFullAccess, keyForm)
    };

    if (isEdit) {
      await api<ApiKey>(
        `/admin/api-keys/${editingKeyId}`,
        { method: "PATCH", headers, body: JSON.stringify(payload) },
        setNotice
      );
      setKeyModalMode(null);
      setNotice("API key updated");
    } else {
      const result = await api<{ key: string }>(
        "/admin/api-keys",
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            ...payload,
            client_id: Number(keyForm.client_id)
          })
        },
        setNotice
      );
      setNewKey(result.key);
      setKeyForm(defaultKeyForm(keyForm.client_id));
      setKeyFullAccess(true);
      setNotice("API key created");
    }

    await load();
  }

  async function removeItem() {
    if (!removeTarget) return;
    const endpoint =
      removeTarget.type === "client"
        ? `/admin/clients/${removeTarget.id}`
        : `/admin/api-keys/${removeTarget.id}`;

    await api<unknown>(endpoint, { method: "DELETE", headers }, setNotice);
    setRemoveTarget(null);
    setNotice(removeTarget.type === "client" ? "Client removed" : "API key removed");
    await load();
  }

  async function copyApiKey(value: string) {
    await copyText(value, "API key copied");
  }

  async function copyText(value: string, notice: string) {
    await navigator.clipboard.writeText(value);
    setNotice(notice);
  }

  function openUsage(key: ApiKey) {
    setUsageTarget(key);
    setUsageTab("curl");
  }

  function renderApiKey(key: ApiKey) {
    if (key.key) {
      return (
        <div className="flex max-w-[520px] items-start gap-2">
          <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5">{key.key}</code>
          <Button onClick={() => copyApiKey(key.key as string)} variant="light">
            <Copy size={15} />
            Copy
          </Button>
        </div>
      );
    }

    return (
      <div className="space-y-1 text-xs">
        <code className="font-mono">{key.key_prefix}</code>
        <div className="text-slate-500">Full key unavailable for older keys.</div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Section
        title="Clients"
        action={
          <div className="flex items-center gap-2">
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button onClick={openCreateClient}>
              <Plus size={15} />
              New Client
            </Button>
          </div>
        }
      >
        <DataTable
          columns={["id", "name", "description", "status", "access", "actions"]}
          rows={clients.map((client) => [
            client.id,
            client.name,
            client.description || "",
            <Badge tone={client.status === "active" ? "good" : "bad"}>{client.status}</Badge>,
            jsonPreview(client.access_config),
            <div className="flex gap-2">
              <Button onClick={() => openEditClient(client)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button
                onClick={() => setRemoveTarget({ type: "client", id: client.id, label: client.name })}
                variant="light"
              >
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination
          page={clientPage}
          pageSize={PAGE_SIZE}
          total={clientTotal}
          onPageChange={setClientPage}
        />
      </Section>

      <Section
        title="API Keys"
        action={
          <Button onClick={openCreateKey}>
            <KeyRound size={15} />
            New Key
          </Button>
        }
      >
        <DataTable
          columns={["id", "client", "name", "api key", "status", "access", "actions"]}
          rows={keys.map((key) => [
            key.id,
            clientNamesById.get(key.client_id) || key.client_id,
            key.name,
            renderApiKey(key),
            <Badge tone={key.status === "active" ? "good" : "bad"}>{key.status}</Badge>,
            jsonPreview(key.access_config),
            <div className="flex gap-2">
              <Button onClick={() => openUsage(key)} variant="light">
                <BookOpen size={14} />
                Usage
              </Button>
              <Button onClick={() => openEditKey(key)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button
                onClick={() => setRemoveTarget({ type: "key", id: key.id, label: key.name })}
                variant="light"
              >
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination
          page={keyPage}
          pageSize={PAGE_SIZE}
          total={keyTotal}
          onPageChange={setKeyPage}
        />
      </Section>

      <Modal
        open={clientModalMode !== null}
        title={clientModalMode === "edit" ? "Edit Client" : "Create Client"}
        onClose={() => setClientModalMode(null)}
      >
        <form onSubmit={submitClient} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Name">
              <Input
                value={clientForm.name}
                onChange={(event) => setClientForm({ ...clientForm, name: event.target.value })}
                required
              />
            </Field>
            <Field label="Status">
              <Select
                value={clientForm.status}
                onChange={(event) => setClientForm({ ...clientForm, status: event.target.value })}
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <div className="md:col-span-2">
              <Field label="Description">
                <Input
                  value={clientForm.description}
                  onChange={(event) => setClientForm({ ...clientForm, description: event.target.value })}
                />
              </Field>
            </div>
          </div>
          <AccessFields
            form={clientForm}
            fullAccess={clientFullAccess}
            onChange={(patch) => setClientForm({ ...clientForm, ...patch })}
            onFullAccessChange={setClientFullAccess}
          />
          <div className="flex justify-end gap-2">
            <Button onClick={() => setClientModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit">
              {clientModalMode === "edit" ? <Pencil size={15} /> : <Plus size={15} />}
              {clientModalMode === "edit" ? "Save Client" : "Create Client"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={keyModalMode !== null}
        title={keyModalMode === "edit" ? "Edit API Key" : "Create API Key"}
        onClose={() => setKeyModalMode(null)}
      >
        <form onSubmit={submitKey} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Client">
              <Select
                value={keyForm.client_id}
                onChange={(event) => setKeyForm({ ...keyForm, client_id: event.target.value })}
                disabled={keyModalMode === "edit"}
                required
              >
                <option value="">Select client</option>
                {clientOptions.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select
                value={keyForm.status}
                onChange={(event) => setKeyForm({ ...keyForm, status: event.target.value })}
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <div className="md:col-span-2">
              <Field label="Name">
                <Input
                  value={keyForm.name}
                  onChange={(event) => setKeyForm({ ...keyForm, name: event.target.value })}
                  required
                />
              </Field>
            </div>
          </div>
          <AccessFields
            form={keyForm}
            fullAccess={keyFullAccess}
            onChange={(patch) => setKeyForm({ ...keyForm, ...patch })}
            onFullAccessChange={setKeyFullAccess}
          />
          {newKey && (
            <div className="rounded-md border border-line bg-panel p-3">
              <div className="mb-2 text-xs font-medium text-slate-600">New API key</div>
              <div className="flex items-start gap-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5">{newKey}</code>
                <Button onClick={() => copyApiKey(newKey)} variant="light">
                  <Copy size={15} />
                  Copy
                </Button>
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button onClick={() => setKeyModalMode(null)} variant="light">
              {newKey ? "Done" : "Cancel"}
            </Button>
            <Button type="submit" disabled={!clientOptions.length && keyModalMode === "create"}>
              {keyModalMode === "edit" ? <Pencil size={15} /> : <KeyRound size={15} />}
              {keyModalMode === "edit" ? "Save Key" : "Create Key"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={usageTarget !== null} title="API Key Usage" onClose={() => setUsageTarget(null)}>
        {usageTarget && (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-line bg-panel p-3">
                <div className="mb-1 text-xs font-medium text-slate-600">Base URL</div>
                <div className="flex items-start gap-2">
                  <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5">
                    {baseUrl}
                  </code>
                  <Button onClick={() => copyText(baseUrl, "Base URL copied")} variant="light">
                    <Copy size={15} />
                    Copy
                  </Button>
                </div>
              </div>
              <div className="rounded-md border border-line bg-panel p-3">
                <div className="mb-1 text-xs font-medium text-slate-600">API Key</div>
                {usageTarget.key ? (
                  <div className="flex items-start gap-2">
                    <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5">
                      {usageTarget.key}
                    </code>
                    <Button onClick={() => copyApiKey(usageTarget.key as string)} variant="light">
                      <Copy size={15} />
                      Copy
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-1 text-xs">
                    <code className="font-mono">{usageTarget.key_prefix}</code>
                    <div className="text-slate-500">
                      Full key is only available when the key is created.
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {(["curl", "sdk", "env"] as UsageTab[]).map((tab) => (
                <Button
                  key={tab}
                  onClick={() => setUsageTab(tab)}
                  variant={usageTab === tab ? "dark" : "light"}
                >
                  {tab === "sdk" ? "OpenAI SDK" : tab}
                </Button>
              ))}
            </div>

            <div className="rounded-md border border-line bg-slate-950 p-3 text-slate-100">
              <div className="mb-2 flex justify-end">
                <Button
                  onClick={() =>
                    copyText(
                      usageTab === "curl"
                        ? curlSnippet(baseUrl, usageTarget)
                        : usageTab === "sdk"
                          ? sdkSnippet(baseUrl)
                          : envSnippet(baseUrl, usageTarget),
                      "Usage snippet copied"
                    )
                  }
                  variant="light"
                >
                  <Copy size={15} />
                  Copy
                </Button>
              </div>
              <pre
                className="overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-5"
              >
                {usageTab === "curl"
                  ? curlSnippet(baseUrl, usageTarget)
                  : usageTab === "sdk"
                    ? sdkSnippet(baseUrl)
                    : envSnippet(baseUrl, usageTarget)}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={removeTarget !== null}
        title={removeTarget?.type === "client" ? "Remove Client" : "Remove API Key"}
        onClose={() => setRemoveTarget(null)}
      >
        <div className="space-y-4">
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Remove <span className="font-semibold">{removeTarget?.label}</span>?
            {removeTarget?.type === "client" ? " This also removes its API keys." : ""}
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRemoveTarget(null)} variant="light">
              Cancel
            </Button>
            <Button onClick={removeItem}>
              <Trash2 size={15} />
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
