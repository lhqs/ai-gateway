import { CheckCircle2, Plus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Section, Select, TextArea } from "../components/ui";
import { api, parseCsv } from "../lib/api";
import type { JsonValue, PageProps, Provider } from "../types/gateway";

export function ProvidersPage({ headers, setNotice }: PageProps) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [form, setForm] = useState({
    name: "gemini",
    provider_type: "gemini",
    base_url: "https://generativelanguage.googleapis.com",
    encrypted_api_key: "",
    protocol_modes: "native_proxy",
    auth_type: "api_key_query",
    auth_config: '{"query_name":"key"}',
    allowed_paths: "v1beta/models/*, v1beta/models/*:generateContent, v1beta/models/*:streamGenerateContent",
    blocked_headers: "authorization, cookie",
    usage_parser_type: "gemini",
    timeout_ms: "60000",
    native_rate_limit_per_minute: "60",
    allow_streaming: true
  });

  async function load() {
    setProviders(await api<Provider[]>("/admin/providers", { headers }, setNotice));
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  async function createProvider(event: React.FormEvent) {
    event.preventDefault();
    await api<Provider>(
      "/admin/providers",
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          ...form,
          protocol_modes: parseCsv(form.protocol_modes),
          auth_config: JSON.parse(form.auth_config || "{}"),
          allowed_paths: parseCsv(form.allowed_paths),
          blocked_headers: parseCsv(form.blocked_headers),
          timeout_ms: Number(form.timeout_ms),
          native_rate_limit_per_minute: form.native_rate_limit_per_minute ? Number(form.native_rate_limit_per_minute) : null,
          status: "active"
        })
      },
      setNotice
    );
    setNotice("Provider created");
    await load();
  }

  async function testProvider(id: number) {
    const result = await api<Record<string, JsonValue>>(`/admin/providers/${id}/test`, { method: "POST", headers }, setNotice);
    setNotice(JSON.stringify(result));
    await load();
  }

  return (
    <div className="grid grid-cols-[1fr_440px] gap-5">
      <Section title="Providers" action={<Button onClick={load} variant="light"><RefreshCw size={15} />Refresh</Button>}>
        <DataTable
          columns={["id", "name", "type", "modes", "auth", "health", "stream", ""]}
          rows={providers.map((p) => [
            p.id,
            p.name,
            p.provider_type,
            p.protocol_modes.join(", "),
            p.auth_type,
            <Badge tone={p.health_status === "healthy" ? "good" : p.health_status === "unhealthy" ? "bad" : "neutral"}>{p.health_status}</Badge>,
            p.allow_streaming ? "yes" : "no",
            <Button onClick={() => testProvider(p.id)} variant="light"><CheckCircle2 size={14} />Test</Button>
          ])}
        />
      </Section>
      <Section title="Create Provider">
        <form onSubmit={createProvider} className="grid grid-cols-2 gap-3">
          <Field label="Name"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
          <Field label="Type"><Select value={form.provider_type} onChange={(e) => setForm({ ...form, provider_type: e.target.value })}><option value="gemini">gemini</option><option value="openai_compatible">openai_compatible</option></Select></Field>
          <Field label="Base URL"><Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} required /></Field>
          <Field label="API Key"><Input type="password" value={form.encrypted_api_key} onChange={(e) => setForm({ ...form, encrypted_api_key: e.target.value })} /></Field>
          <Field label="Protocol Modes"><Input value={form.protocol_modes} onChange={(e) => setForm({ ...form, protocol_modes: e.target.value })} /></Field>
          <Field label="Auth Type"><Select value={form.auth_type} onChange={(e) => setForm({ ...form, auth_type: e.target.value })}><option value="api_key_query">api_key_query</option><option value="api_key_header">api_key_header</option><option value="bearer_token">bearer_token</option></Select></Field>
          <div className="col-span-2"><Field label="Auth Config JSON"><TextArea value={form.auth_config} onChange={(e) => setForm({ ...form, auth_config: e.target.value })} /></Field></div>
          <div className="col-span-2"><Field label="Allowed Paths"><Input value={form.allowed_paths} onChange={(e) => setForm({ ...form, allowed_paths: e.target.value })} /></Field></div>
          <Field label="Blocked Headers"><Input value={form.blocked_headers} onChange={(e) => setForm({ ...form, blocked_headers: e.target.value })} /></Field>
          <Field label="Usage Parser"><Select value={form.usage_parser_type} onChange={(e) => setForm({ ...form, usage_parser_type: e.target.value })}><option value="gemini">gemini</option><option value="openai">openai</option><option value="none">none</option></Select></Field>
          <Field label="Timeout ms"><Input value={form.timeout_ms} onChange={(e) => setForm({ ...form, timeout_ms: e.target.value })} /></Field>
          <Field label="Native Rate / min"><Input value={form.native_rate_limit_per_minute} onChange={(e) => setForm({ ...form, native_rate_limit_per_minute: e.target.value })} /></Field>
          <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={form.allow_streaming} onChange={(e) => setForm({ ...form, allow_streaming: e.target.checked })} /> Allow streaming</label>
          <div className="col-span-2"><Button type="submit"><Plus size={15} />Create Provider</Button></div>
        </form>
      </Section>
    </div>
  );
}
