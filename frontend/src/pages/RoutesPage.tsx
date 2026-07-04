import { RefreshCw, Route } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Section, Select } from "../components/ui";
import { api, parseNumberCsv } from "../lib/api";
import type { Alias, Model, PageProps, RouteRule } from "../types/gateway";

export function RoutesPage({ headers, setNotice }: PageProps) {
  const [routes, setRoutes] = useState<RouteRule[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [form, setForm] = useState({
    model_alias_id: "",
    primary_model_id: "",
    fallback_model_ids: "",
    max_failover_attempts: "2",
    cache_ttl_seconds: "300",
    cache_enabled: true,
    failover_enabled: true
  });

  async function load() {
    const [r, m, a] = await Promise.all([
      api<RouteRule[]>("/admin/route-rules", { headers }, setNotice),
      api<Model[]>("/admin/models", { headers }, setNotice),
      api<Alias[]>("/admin/model-aliases", { headers }, setNotice)
    ]);
    setRoutes(r);
    setModels(m);
    setAliases(a);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  async function createRoute(event: React.FormEvent) {
    event.preventDefault();
    await api<RouteRule>(
      "/admin/route-rules",
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          model_alias_id: Number(form.model_alias_id),
          primary_model_id: Number(form.primary_model_id),
          fallback_model_ids: parseNumberCsv(form.fallback_model_ids),
          failover_enabled: form.failover_enabled,
          max_failover_attempts: Number(form.max_failover_attempts),
          cache_enabled: form.cache_enabled,
          cache_ttl_seconds: Number(form.cache_ttl_seconds),
          status: "active"
        })
      },
      setNotice
    );
    setNotice("Route rule created");
    await load();
  }

  return (
    <div className="grid grid-cols-[1fr_420px] gap-5">
      <Section title="Route Rules" action={<Button onClick={load} variant="light"><RefreshCw size={15} />Refresh</Button>}>
        <DataTable
          columns={["id", "alias", "primary", "fallbacks", "failover", "cache", "ttl", "status"]}
          rows={routes.map((r) => [
            r.id,
            aliases.find((a) => a.id === r.model_alias_id)?.alias || r.model_alias_id,
            models.find((m) => m.id === r.primary_model_id)?.name || r.primary_model_id,
            r.fallback_model_ids.join(", "),
            r.failover_enabled ? `yes / ${r.max_failover_attempts}` : "no",
            r.cache_enabled ? "yes" : "no",
            `${r.cache_ttl_seconds}s`,
            <Badge tone={r.status === "active" ? "good" : "bad"}>{r.status}</Badge>
          ])}
        />
      </Section>
      <Section title="Create Route">
        <form onSubmit={createRoute} className="space-y-3">
          <Field label="Alias">
            <Select value={form.model_alias_id} onChange={(e) => setForm({ ...form, model_alias_id: e.target.value })} required>
              <option value="">Select alias</option>
              {aliases.map((a) => <option key={a.id} value={a.id}>{a.alias}</option>)}
            </Select>
          </Field>
          <Field label="Primary Model">
            <Select value={form.primary_model_id} onChange={(e) => setForm({ ...form, primary_model_id: e.target.value })} required>
              <option value="">Select model</option>
              {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </Select>
          </Field>
          <Field label="Fallback Model IDs"><Input value={form.fallback_model_ids} onChange={(e) => setForm({ ...form, fallback_model_ids: e.target.value })} placeholder="2, 3" /></Field>
          <Field label="Max Failover Attempts"><Input value={form.max_failover_attempts} onChange={(e) => setForm({ ...form, max_failover_attempts: e.target.value })} /></Field>
          <Field label="Cache TTL Seconds"><Input value={form.cache_ttl_seconds} onChange={(e) => setForm({ ...form, cache_ttl_seconds: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.failover_enabled} onChange={(e) => setForm({ ...form, failover_enabled: e.target.checked })} /> Enable failover</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.cache_enabled} onChange={(e) => setForm({ ...form, cache_enabled: e.target.checked })} /> Enable cache</label>
          <Button type="submit"><Route size={15} />Create Route</Button>
        </form>
      </Section>
    </div>
  );
}
