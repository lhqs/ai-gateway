import { Network, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Section, Select } from "../components/ui";
import { api, parseCsv } from "../lib/api";
import type { Alias, Model, PageProps, Provider } from "../types/gateway";

export function ModelsPage({ headers, setNotice }: PageProps) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [modelForm, setModelForm] = useState({
    provider_id: "",
    name: "",
    display_name: "",
    capabilities: "chat, stream",
    context_window: "",
    status: "active"
  });
  const [aliasForm, setAliasForm] = useState({ alias: "default-chat", description: "", status: "active" });

  async function load() {
    const [p, m, a] = await Promise.all([
      api<Provider[]>("/admin/providers", { headers }, setNotice),
      api<Model[]>("/admin/models", { headers }, setNotice),
      api<Alias[]>("/admin/model-aliases", { headers }, setNotice)
    ]);
    setProviders(p);
    setModels(m);
    setAliases(a);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  async function createModel(event: React.FormEvent) {
    event.preventDefault();
    await api<Model>(
      "/admin/models",
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          provider_id: Number(modelForm.provider_id),
          name: modelForm.name,
          display_name: modelForm.display_name || null,
          capabilities: parseCsv(modelForm.capabilities),
          context_window: modelForm.context_window ? Number(modelForm.context_window) : null,
          status: modelForm.status
        })
      },
      setNotice
    );
    setModelForm({ provider_id: "", name: "", display_name: "", capabilities: "chat, stream", context_window: "", status: "active" });
    setNotice("Model created");
    await load();
  }

  async function createAlias(event: React.FormEvent) {
    event.preventDefault();
    await api<Alias>("/admin/model-aliases", { method: "POST", headers, body: JSON.stringify(aliasForm) }, setNotice);
    setAliasForm({ alias: "", description: "", status: "active" });
    setNotice("Alias created");
    await load();
  }

  return (
    <div className="grid grid-cols-[1fr_420px] gap-5">
      <div className="space-y-5">
        <Section title="Models" action={<Button onClick={load} variant="light"><RefreshCw size={15} />Refresh</Button>}>
          <DataTable
            columns={["id", "provider", "name", "capabilities", "status"]}
            rows={models.map((m) => [
              m.id,
              m.provider_id,
              m.name,
              m.capabilities.join(", "),
              <Badge tone={m.status === "active" ? "good" : "bad"}>{m.status}</Badge>
            ])}
          />
        </Section>
        <Section title="Aliases">
          <DataTable
            columns={["id", "alias", "description", "status"]}
            rows={aliases.map((a) => [
              a.id,
              a.alias,
              a.description || "",
              <Badge tone={a.status === "active" ? "good" : "bad"}>{a.status}</Badge>
            ])}
          />
        </Section>
      </div>
      <div className="space-y-5">
        <Section title="Create Model">
          <form onSubmit={createModel} className="space-y-3">
            <Field label="Provider">
              <Select value={modelForm.provider_id} onChange={(e) => setModelForm({ ...modelForm, provider_id: e.target.value })} required>
                <option value="">Select provider</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Model Name"><Input value={modelForm.name} onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })} required /></Field>
            <Field label="Display Name"><Input value={modelForm.display_name} onChange={(e) => setModelForm({ ...modelForm, display_name: e.target.value })} /></Field>
            <Field label="Capabilities"><Input value={modelForm.capabilities} onChange={(e) => setModelForm({ ...modelForm, capabilities: e.target.value })} /></Field>
            <Field label="Context Window"><Input value={modelForm.context_window} onChange={(e) => setModelForm({ ...modelForm, context_window: e.target.value })} /></Field>
            <Button type="submit"><Plus size={15} />Create Model</Button>
          </form>
        </Section>
        <Section title="Create Alias">
          <form onSubmit={createAlias} className="space-y-3">
            <Field label="Alias"><Input value={aliasForm.alias} onChange={(e) => setAliasForm({ ...aliasForm, alias: e.target.value })} required /></Field>
            <Field label="Description"><Input value={aliasForm.description} onChange={(e) => setAliasForm({ ...aliasForm, description: e.target.value })} /></Field>
            <Button type="submit"><Network size={15} />Create Alias</Button>
          </form>
        </Section>
      </div>
    </div>
  );
}
