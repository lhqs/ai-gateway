import { Copy, KeyRound, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Section, Select } from "../components/ui";
import { api, jsonPreview, parseCsv } from "../lib/api";
import type { ApiKey, Client, PageProps } from "../types/gateway";

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

function defaultClientForm(name = "client") {
  return {
    name,
    description: "Default gateway client",
    model_aliases: "*",
    provider_names: "*",
    native_paths: "*"
  };
}

function defaultKeyForm(clientId = "") {
  return {
    client_id: clientId,
    name: "full-access-key",
    model_aliases: "*",
    provider_names: "*",
    native_paths: "*"
  };
}

export function ClientsPage({ headers, setNotice }: PageProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [clientForm, setClientForm] = useState(defaultClientForm());
  const [clientFullAccess, setClientFullAccess] = useState(true);
  const [keyForm, setKeyForm] = useState(defaultKeyForm());
  const [newKey, setNewKey] = useState("");

  async function load() {
    const [clientData, keyData] = await Promise.all([
      api<Client[]>("/admin/clients", { headers }, setNotice),
      api<ApiKey[]>("/admin/api-keys", { headers }, setNotice)
    ]);
    setClients(clientData);
    setKeys(keyData);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  useEffect(() => {
    setClientForm((current) => {
      if (current.name !== "client" || clients.length === 0) return current;
      return { ...current, name: nextClientName(clients) };
    });
    setKeyForm((current) => {
      if (current.client_id || clients.length === 0) return current;
      return { ...current, client_id: String(clients[0].id) };
    });
  }, [clients]);

  async function createClient(event: React.FormEvent) {
    event.preventDefault();
    await api<Client>(
      "/admin/clients",
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: clientForm.name,
          description: clientForm.description || null,
          status: "active",
          access_config: clientFullAccess
            ? {
                model_aliases: ["*"],
                provider_names: ["*"],
                native_paths: ["*"]
              }
            : {
                model_aliases: parseCsv(clientForm.model_aliases),
                provider_names: parseCsv(clientForm.provider_names),
                native_paths: parseCsv(clientForm.native_paths)
              }
        })
      },
      setNotice
    );
    setClientForm(defaultClientForm(nextClientName([...clients, { ...clientForm, id: -1 } as Client])));
    setClientFullAccess(true);
    setNotice("Client created");
    await load();
  }

  async function createKey(event: React.FormEvent) {
    event.preventDefault();
    const result = await api<{ key: string }>(
      "/admin/api-keys",
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          client_id: Number(keyForm.client_id),
          name: keyForm.name,
          access_config: {
            model_aliases: parseCsv(keyForm.model_aliases),
            provider_names: parseCsv(keyForm.provider_names),
            native_paths: parseCsv(keyForm.native_paths)
          }
        })
      },
      setNotice
    );
    setNewKey(result.key);
    setKeyForm(defaultKeyForm(keyForm.client_id));
    setNotice("API key created");
    await load();
  }

  async function copyApiKey(value: string) {
    await navigator.clipboard.writeText(value);
    setNotice("API key copied");
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
    <div className="grid grid-cols-[1fr_420px] gap-5">
      <div className="space-y-5">
        <Section
          title="Clients"
          action={
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
          }
        >
          <DataTable
            columns={["id", "name", "status", "access"]}
            rows={clients.map((client) => [
              client.id,
              client.name,
              <Badge tone={client.status === "active" ? "good" : "bad"}>{client.status}</Badge>,
              jsonPreview(client.access_config)
            ])}
          />
        </Section>
        <Section title="API Keys">
          <DataTable
            columns={["id", "client", "name", "api key", "status", "access"]}
            rows={keys.map((key) => [
              key.id,
              key.client_id,
              key.name,
              renderApiKey(key),
              <Badge tone={key.status === "active" ? "good" : "bad"}>{key.status}</Badge>,
              jsonPreview(key.access_config)
            ])}
          />
        </Section>
      </div>
      <div className="space-y-5">
        <Section title="Create Client">
          <form onSubmit={createClient} className="space-y-3">
            <Field label="Name">
              <Input value={clientForm.name} onChange={(e) => setClientForm({ ...clientForm, name: e.target.value })} required />
            </Field>
            <Field label="Description">
              <Input value={clientForm.description} onChange={(e) => setClientForm({ ...clientForm, description: e.target.value })} />
            </Field>
            <label className="flex h-9 items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={clientFullAccess}
                onChange={(event) => setClientFullAccess(event.target.checked)}
                className="h-4 w-4 rounded border-line"
              />
              Full access
            </label>
            {!clientFullAccess && (
              <div className="space-y-3 rounded-md border border-line bg-panel p-3">
                <Field label="Model Aliases">
                  <Input placeholder="default-chat, reasoning" value={clientForm.model_aliases} onChange={(e) => setClientForm({ ...clientForm, model_aliases: e.target.value })} />
                </Field>
                <Field label="Providers">
                  <Input placeholder="openai, gemini" value={clientForm.provider_names} onChange={(e) => setClientForm({ ...clientForm, provider_names: e.target.value })} />
                </Field>
                <Field label="Native Paths">
                  <Input placeholder="v1beta/models/*" value={clientForm.native_paths} onChange={(e) => setClientForm({ ...clientForm, native_paths: e.target.value })} />
                </Field>
              </div>
            )}
            <Button type="submit">
              <Plus size={15} />
              Create Client
            </Button>
          </form>
        </Section>
        <Section title="Create API Key">
          <form onSubmit={createKey} className="space-y-3">
            <Field label="Client">
              <Select value={keyForm.client_id} onChange={(e) => setKeyForm({ ...keyForm, client_id: e.target.value })} required>
                <option value="">Select client</option>
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Name">
              <Input value={keyForm.name} onChange={(e) => setKeyForm({ ...keyForm, name: e.target.value })} required />
            </Field>
            <Field label="Allowed Model Aliases">
              <Input value={keyForm.model_aliases} onChange={(e) => setKeyForm({ ...keyForm, model_aliases: e.target.value })} />
            </Field>
            <Field label="Allowed Providers">
              <Input value={keyForm.provider_names} onChange={(e) => setKeyForm({ ...keyForm, provider_names: e.target.value })} />
            </Field>
            <Field label="Allowed Native Paths">
              <Input value={keyForm.native_paths} onChange={(e) => setKeyForm({ ...keyForm, native_paths: e.target.value })} />
            </Field>
            <Button type="submit">
              <KeyRound size={15} />
              Create Key
            </Button>
            {newKey && <pre className="overflow-auto rounded-md bg-panel p-3 text-xs">{newKey}</pre>}
          </form>
        </Section>
      </div>
    </div>
  );
}
