import React, { useEffect, useState } from "react";
import { ListFilter, RefreshCw } from "lucide-react";

import { Badge, Button, Input, Pagination, Section, Select } from "../components/ui";
import { apiWithMeta } from "../lib/api";
import type { PageProps, UsageLog } from "../types/gateway";

const PAGE_SIZE = 10;

type UsageFilter = {
  call_mode: string;
  status: string;
  native_path: string;
  usage_status: string;
  cache_hit: string;
  failover_triggered: string;
};

const defaultFilter: UsageFilter = {
  call_mode: "",
  status: "",
  native_path: "",
  usage_status: "",
  cache_hit: "",
  failover_triggered: ""
};

function formatLogTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

function formatCost(row: UsageLog) {
  if (row.total_cost === null || !row.cost_currency) {
    return "";
  }
  return `${row.cost_currency} ${row.total_cost}`;
}

export function UsagePage({ headers, setNotice }: PageProps) {
  const [usage, setUsage] = useState<UsageLog[]>([]);
  const [usageTotal, setUsageTotal] = useState(0);
  const [usagePage, setUsagePage] = useState(1);
  const [filter, setFilter] = useState<UsageFilter>(defaultFilter);
  const [openId, setOpenId] = useState<number | null>(null);

  function appendFilterParams(params: URLSearchParams, values = filter) {
    Object.entries(values).forEach(([key, value]) => {
      if (!value) return;
      params.set(key, value);
    });
  }

  function usageParams(page = usagePage, values = filter) {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String((page - 1) * PAGE_SIZE)
    });
    appendFilterParams(params, values);
    return params.toString();
  }

  async function load(page = usagePage, values = filter) {
    const result = await apiWithMeta<UsageLog[]>(
      `/admin/usage-logs?${usageParams(page, values)}`,
      { headers },
      setNotice
    );
    setUsage(result.data);
    setUsageTotal(result.total);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, usagePage]);

  useEffect(() => {
    setUsagePage((page) => Math.min(page, Math.max(1, Math.ceil(usageTotal / PAGE_SIZE))));
  }, [usageTotal]);

  async function applyFilters() {
    setOpenId(null);
    setUsagePage(1);
    await load(1);
  }

  async function resetFilters() {
    setFilter(defaultFilter);
    setOpenId(null);
    setUsagePage(1);
    await load(1, defaultFilter);
  }

  return (
    <div className="space-y-5">
      <section className="rounded-md border border-line bg-white px-4 py-3">
        <div className="overflow-x-auto">
          <div className="flex min-w-[1180px] items-center gap-3">
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Mode</span>
              <Select
                value={filter.call_mode}
                onChange={(event) => setFilter({ ...filter, call_mode: event.target.value })}
                className="w-40"
              >
                <option value="">Any</option>
                <option value="unified_chat">unified_chat</option>
                <option value="native_proxy">native_proxy</option>
              </Select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Status</span>
              <Select
                value={filter.status}
                onChange={(event) => setFilter({ ...filter, status: event.target.value })}
                className="w-32"
              >
                <option value="">Any</option>
                <option value="success">success</option>
                <option value="failed">failed</option>
              </Select>
            </label>
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap text-xs font-medium text-slate-600">Usage</span>
              <Select
                value={filter.usage_status}
                onChange={(event) => setFilter({ ...filter, usage_status: event.target.value })}
                className="w-32"
              >
                <option value="">Any</option>
                <option value="parsed">parsed</option>
                <option value="estimated">estimated</option>
                <option value="unknown">unknown</option>
                <option value="failed">failed</option>
              </Select>
            </label>
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap text-xs font-medium text-slate-600">Native Path</span>
              <Input
                value={filter.native_path}
                onChange={(event) => setFilter({ ...filter, native_path: event.target.value })}
                className="w-64"
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap text-xs font-medium text-slate-600">Cache Hit</span>
              <Select
                value={filter.cache_hit}
                onChange={(event) => setFilter({ ...filter, cache_hit: event.target.value })}
                className="w-28"
              >
                <option value="">Any</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </Select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Failover</span>
              <Select
                value={filter.failover_triggered}
                onChange={(event) => setFilter({ ...filter, failover_triggered: event.target.value })}
                className="w-28"
              >
                <option value="">Any</option>
                <option value="true">true</option>
                <option value="false">false</option>
              </Select>
            </label>
            <div className="ml-auto flex items-center gap-2">
              <Button onClick={applyFilters}>
                <ListFilter size={15} />
                Apply
              </Button>
              <Button onClick={resetFilters} variant="light">
                Reset
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Section
        title="Usage Logs"
        action={
          <Button onClick={() => load()} variant="light">
            <RefreshCw size={15} />
            Refresh
          </Button>
        }
      >
        <div className="max-w-full overflow-auto">
          <table className="w-full min-w-[1220px] table-fixed border-collapse text-left text-sm">
            <thead className="bg-panel text-slate-600">
              <tr>
                {["Time", "Request", "Mode", "Target", "Status", "Usage", "Tokens", "Cost", "Pricing", "Latency", "Cache", "Failover", ""].map(
                  (header) => (
                    <th key={header} className="px-3 py-2 font-medium">
                      {header}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {usage.length === 0 && (
                <tr className="border-t border-line">
                  <td className="px-3 py-5 text-slate-500" colSpan={13}>
                    No data
                  </td>
                </tr>
              )}
              {usage.map((row) => (
                <React.Fragment key={row.id}>
                  <tr className="border-t border-line">
                    <td className="px-3 py-2 align-middle text-xs text-slate-600">{formatLogTime(row.created_at)}</td>
                    <td className="px-3 py-2 align-middle font-mono text-xs">{row.request_id.slice(0, 12)}</td>
                    <td className="px-3 py-2 align-middle">{row.call_mode}</td>
                    <td className="break-words px-3 py-2 align-middle">{row.model_alias || row.native_path}</td>
                    <td className="px-3 py-2 align-middle">
                      <Badge tone={row.status === "success" ? "good" : "bad"}>{row.status}</Badge>
                    </td>
                    <td className="px-3 py-2 align-middle">{row.usage_status}</td>
                    <td className="px-3 py-2 align-middle">{row.total_tokens}</td>
                    <td className="px-3 py-2 align-middle">{formatCost(row)}</td>
                    <td className="break-words px-3 py-2 align-middle">{row.pricing_status}</td>
                    <td className="px-3 py-2 align-middle">{row.latency_ms ?? 0} ms</td>
                    <td className="px-3 py-2 align-middle">{row.cache_hit ? "yes" : "no"}</td>
                    <td className="px-3 py-2 align-middle">{row.failover_triggered ? `${row.failover_attempts}` : "no"}</td>
                    <td className="px-3 py-2 align-middle">
                      <Button onClick={() => setOpenId(openId === row.id ? null : row.id)} variant="light">
                        Details
                      </Button>
                    </td>
                  </tr>
                  {openId === row.id && (
                    <tr className="border-t border-line bg-panel">
                      <td colSpan={13} className="max-w-0 p-3">
                        <pre className="max-h-[420px] max-w-full overflow-auto whitespace-pre-wrap break-words rounded-md bg-white p-3 text-xs leading-5">
                          {JSON.stringify(row, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination page={usagePage} pageSize={PAGE_SIZE} total={usageTotal} onPageChange={setUsagePage} />
      </Section>
    </div>
  );
}
