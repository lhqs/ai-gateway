import { KeyRound, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Section, Select } from "../components/ui";
import { api, jsonPreview, parseCsv } from "../lib/api";
import type { ApiKey, Client, PageProps } from "../types/gateway";

export function ClientsPage({ headers, setNotice }: PageProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [clientForm, setClientForm] = useState({
    name: "",
    description: "",
    model_aliases: "",
    provider_names: "",
    native_paths: ""
  });
  const [keyForm, setKeyForm] = useState({
    client_id: "",
    name: "",
    model_aliases: "",
    provider_names: "",
    native_paths: ""
  });
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
          access_config: {
            model_aliases: parseCsv(clientForm.model_aliases),
            provider_names: parseCsv(clientForm.provider_names),
            native_paths: parseCsv(clientForm.native_paths)
          }
        })
      },
      setNotice
    );
    setClientForm({ name: "", description: "", model_aliases: "", provider_names: "", native_paths: "" });
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
    setKeyForm({ client_id: "", name: "", model_aliases: "", provider_names: "", native_paths: "" });
    setNotice("API key created");
    await load();
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
            columns={["id", "client", "name", "prefix", "status", "access"]}
            rows={keys.map((key) => [
              key.id,
              key.client_id,
              key.name,
              key.key_prefix,
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
            <Field label="Allowed Model Aliases">
              <Input placeholder="default-chat, reasoning" value={clientForm.model_aliases} onChange={(e) => setClientForm({ ...clientForm, model_aliases: e.target.value })} />
            </Field>
            <Field label="Allowed Providers">
              <Input placeholder="openai, gemini" value={clientForm.provider_names} onChange={(e) => setClientForm({ ...clientForm, provider_names: e.target.value })} />
            </Field>
            <Field label="Allowed Native Paths">
              <Input placeholder="v1beta/models/*" value={clientForm.native_paths} onChange={(e) => setClientForm({ ...clientForm, native_paths: e.target.value })} />
            </Field>
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
