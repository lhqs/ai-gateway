import React, { useEffect, useState } from "react";
import { ListFilter, RefreshCw } from "lucide-react";

import { Badge, Button, Field, Input, Section, Select } from "../components/ui";
import { api } from "../lib/api";
import type { PageProps, UsageLog } from "../types/gateway";

export function UsagePage({ headers, setNotice }: PageProps) {
  const [usage, setUsage] = useState<UsageLog[]>([]);
  const [filter, setFilter] = useState({ call_mode: "", status: "", native_path: "", cache_hit: "", failover_triggered: "" });
  const [openId, setOpenId] = useState<number | null>(null);

  async function load() {
    const params = new URLSearchParams();
    Object.entries(filter).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    setUsage(await api<UsageLog[]>(`/admin/usage-logs?${params.toString()}`, { headers }, setNotice));
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  return (
    <div className="space-y-5">
      <Section title="Filters" action={<Button onClick={load}><ListFilter size={15} />Apply</Button>}>
        <div className="grid grid-cols-5 gap-3">
          <Field label="Mode"><Select value={filter.call_mode} onChange={(e) => setFilter({ ...filter, call_mode: e.target.value })}><option value="">Any</option><option value="unified_chat">unified_chat</option><option value="native_proxy">native_proxy</option></Select></Field>
          <Field label="Status"><Select value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}><option value="">Any</option><option value="success">success</option><option value="failed">failed</option></Select></Field>
          <Field label="Native Path"><Input value={filter.native_path} onChange={(e) => setFilter({ ...filter, native_path: e.target.value })} /></Field>
          <Field label="Cache Hit"><Select value={filter.cache_hit} onChange={(e) => setFilter({ ...filter, cache_hit: e.target.value })}><option value="">Any</option><option value="true">true</option><option value="false">false</option></Select></Field>
          <Field label="Failover"><Select value={filter.failover_triggered} onChange={(e) => setFilter({ ...filter, failover_triggered: e.target.value })}><option value="">Any</option><option value="true">true</option><option value="false">false</option></Select></Field>
        </div>
      </Section>
      <Section title="Usage Logs" action={<Button onClick={load} variant="light"><RefreshCw size={15} />Refresh</Button>}>
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-slate-600">
            <tr>{["Request", "Mode", "Target", "Status", "Usage", "Tokens", "Latency", "Cache", "Failover", ""].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {usage.map((row) => (
              <React.Fragment key={row.id}>
                <tr className="border-t border-line">
                  <td className="px-3 py-2 font-mono text-xs">{row.request_id.slice(0, 12)}</td>
                  <td className="px-3 py-2">{row.call_mode}</td>
                  <td className="px-3 py-2">{row.model_alias || row.native_path}</td>
                  <td className="px-3 py-2"><Badge tone={row.status === "success" ? "good" : "bad"}>{row.status}</Badge></td>
                  <td className="px-3 py-2">{row.usage_status}</td>
                  <td className="px-3 py-2">{row.total_tokens}</td>
                  <td className="px-3 py-2">{row.latency_ms ?? 0} ms</td>
                  <td className="px-3 py-2">{row.cache_hit ? "yes" : "no"}</td>
                  <td className="px-3 py-2">{row.failover_triggered ? `${row.failover_attempts}` : "no"}</td>
                  <td className="px-3 py-2"><Button onClick={() => setOpenId(openId === row.id ? null : row.id)} variant="light">Details</Button></td>
                </tr>
                {openId === row.id && (
                  <tr className="border-t border-line bg-panel">
                    <td colSpan={10} className="p-3">
                      <pre className="max-h-[420px] overflow-auto rounded-md bg-white p-3 text-xs">{JSON.stringify(row, null, 2)}</pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
