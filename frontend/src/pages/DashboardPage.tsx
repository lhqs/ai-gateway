import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { api, apiWithMeta } from "../lib/api";
import { Badge, Button, DataTable, Metric, Section } from "../components/ui";
import type { Dashboard, PageProps, UsageLog } from "../types/gateway";

export function DashboardPage({ headers, setNotice }: PageProps) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [usage, setUsage] = useState<UsageLog[]>([]);

  async function load() {
    const [dash, logs] = await Promise.all([
      api<Dashboard>("/admin/dashboard", { headers }, setNotice),
      apiWithMeta<UsageLog[]>("/admin/usage-logs?limit=8", { headers }, setNotice)
    ]);
    setDashboard(dash);
    setUsage(logs.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        <Metric label="Requests" value={dashboard?.total_requests ?? 0} />
        <Metric label="Success Rate" value={`${Math.round((dashboard?.success_rate ?? 0) * 100)}%`} />
        <Metric label="Tokens" value={dashboard?.total_tokens ?? 0} />
        <Metric label="Avg Latency" value={`${Math.round(dashboard?.avg_latency_ms ?? 0)} ms`} />
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Metric label="Errors" value={dashboard?.error_count ?? 0} />
        <Metric label="Est. Cost" value={`$${(dashboard?.total_cost ?? 0).toFixed(4)}`} />
        <Metric label="Cache Hit Rate" value={`${Math.round((dashboard?.cache_hit_rate ?? 0) * 100)}%`} />
        <Metric label="Failovers" value={dashboard?.failover_count ?? 0} />
      </div>
      <Section
        title="Recent Calls"
        action={
          <Button onClick={load} variant="light">
            <RefreshCw size={15} />
            Refresh
          </Button>
        }
      >
        <DataTable
          columns={["request", "mode", "target", "status", "tokens", "latency"]}
          rows={usage.map((row) => [
            row.request_id.slice(0, 12),
            row.call_mode,
            row.model_alias || row.native_path,
            <Badge tone={row.status === "success" ? "good" : "bad"}>{row.status}</Badge>,
            row.total_tokens,
            `${row.latency_ms ?? 0} ms`
          ])}
        />
      </Section>
    </div>
  );
}
