import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, ListFilter, RefreshCw } from "lucide-react";

import { Badge, Button, Input, Pagination, Section, Select } from "../components/ui";
import { apiWithMeta } from "../lib/api";
import type { ApiKey, Client, Model, PageProps, Provider, UsageLog, UsageSummaryRow } from "../types/gateway";

const PAGE_SIZE = 20;

type UsageFilter = {
  call_mode: string;
  client_id: string;
  api_key_id: string;
  provider_id: string;
  model_id: string;
  model_alias: string;
  status: string;
  native_path: string;
  usage_status: string;
  pricing_status: string;
  cache_hit: string;
  failover_triggered: string;
  created_from: string;
  created_to: string;
};

const defaultFilter: UsageFilter = {
  call_mode: "",
  client_id: "",
  api_key_id: "",
  provider_id: "",
  model_id: "",
  model_alias: "",
  status: "",
  native_path: "",
  usage_status: "",
  pricing_status: "",
  cache_hit: "",
  failover_triggered: "",
  created_from: "",
  created_to: ""
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
  const [summary, setSummary] = useState<UsageSummaryRow | null>(null);
  const [usageTotal, setUsageTotal] = useState(0);
  const [usagePage, setUsagePage] = useState(1);
  const [filter, setFilter] = useState<UsageFilter>(defaultFilter);
  const [clients, setClients] = useState<Client[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  function appendFilterParams(params: URLSearchParams, values = filter) {
    Object.entries(values).forEach(([key, value]) => {
      if (!value) return;
      params.set(key, key.startsWith("created_") ? new Date(value).toISOString() : value);
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

  function summaryParams(values = filter) {
    const params = new URLSearchParams({ group_by: "total", limit: "1" });
    appendFilterParams(params, values);
    return params.toString();
  }

  async function load(page = usagePage, values = filter) {
    const [result, summaryResult] = await Promise.all([
      apiWithMeta<UsageLog[]>(`/admin/usage-logs?${usageParams(page, values)}`, { headers }, setNotice),
      apiWithMeta<UsageSummaryRow[]>(`/admin/usage-summary?${summaryParams(values)}`, { headers }, setNotice)
    ]);
    setUsage(result.data);
    setUsageTotal(result.total);
    setSummary(summaryResult.data[0] || null);
  }

  async function loadOptions() {
    const [clientData, keyData, providerData, modelData] = await Promise.all([
      apiWithMeta<Client[]>("/admin/clients?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<ApiKey[]>("/admin/api-keys?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Provider[]>("/admin/providers?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Model[]>("/admin/models?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setClients(clientData.data);
    setApiKeys(keyData.data);
    setProviders(providerData.data);
    setModels(modelData.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, usagePage]);

  useEffect(() => {
    loadOptions().catch(() => null);
  }, [headers]);

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

  const advancedFilterCount = [
    filter.api_key_id,
    filter.model_id,
    filter.native_path,
    filter.usage_status,
    filter.pricing_status,
    filter.cache_hit,
    filter.failover_triggered,
    filter.created_from,
    filter.created_to
  ].filter(Boolean).length;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-5">
        <div className="rounded-md border border-line bg-white p-3">
          <div className="text-xs text-slate-500">Requests</div>
          <div className="mt-1 text-xl font-semibold">{summary?.request_count ?? 0}</div>
        </div>
        <div className="rounded-md border border-line bg-white p-3">
          <div className="text-xs text-slate-500">Success Rate</div>
          <div className="mt-1 text-xl font-semibold">
            {summary?.request_count ? Math.round((summary.success_count / summary.request_count) * 100) : 0}%
          </div>
        </div>
        <div className="rounded-md border border-line bg-white p-3">
          <div className="text-xs text-slate-500">Cost</div>
          <div className="mt-1 text-xl font-semibold">{summary?.total_cost ?? 0}</div>
        </div>
        <div className="rounded-md border border-line bg-white p-3">
          <div className="text-xs text-slate-500">Cache Hits</div>
          <div className="mt-1 text-xl font-semibold">{summary?.cache_hit_count ?? 0}</div>
        </div>
        <div className="rounded-md border border-line bg-white p-3">
          <div className="text-xs text-slate-500">Missing Prices</div>
          <div className="mt-1 text-xl font-semibold">{summary?.missing_price_count ?? 0}</div>
        </div>
      </div>
      <section className="rounded-md border border-line bg-white px-4 py-3">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 xl:flex-nowrap">
            <label className="flex min-w-[180px] flex-1 items-center gap-2 xl:max-w-[220px]">
              <span className="text-xs font-medium text-slate-600">Mode</span>
              <Select
                value={filter.call_mode}
                onChange={(event) => setFilter({ ...filter, call_mode: event.target.value })}
              >
                <option value="">Any</option>
                <option value="unified_chat">unified_chat</option>
                <option value="native_proxy">native_proxy</option>
              </Select>
            </label>
            <label className="flex min-w-[160px] flex-1 items-center gap-2 xl:max-w-[190px]">
              <span className="text-xs font-medium text-slate-600">Status</span>
              <Select
                value={filter.status}
                onChange={(event) => setFilter({ ...filter, status: event.target.value })}
              >
                <option value="">Any</option>
                <option value="success">success</option>
                <option value="failed">failed</option>
              </Select>
            </label>
            <label className="flex min-w-[180px] flex-1 items-center gap-2 xl:max-w-[220px]">
              <span className="text-xs font-medium text-slate-600">Client</span>
              <Select
                value={filter.client_id}
                onChange={(event) => setFilter({ ...filter, client_id: event.target.value })}
              >
                <option value="">Any</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>{client.name}</option>
                ))}
              </Select>
            </label>
            <label className="flex min-w-[180px] flex-1 items-center gap-2 xl:max-w-[220px]">
              <span className="text-xs font-medium text-slate-600">Provider</span>
              <Select
                value={filter.provider_id}
                onChange={(event) => setFilter({ ...filter, provider_id: event.target.value })}
              >
                <option value="">Any</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>{provider.name}</option>
                ))}
              </Select>
            </label>
            <label className="flex min-w-[190px] flex-1 items-center gap-2">
              <span className="whitespace-nowrap text-xs font-medium text-slate-600">Alias</span>
              <Input
                value={filter.model_alias}
                onChange={(event) => setFilter({ ...filter, model_alias: event.target.value })}
              />
            </label>
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <Button onClick={applyFilters}>
                <ListFilter size={15} />
                Apply
              </Button>
              <Button
                onClick={() => setShowAdvancedFilters((value) => !value)}
                variant="light"
              >
                {showAdvancedFilters ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                More{advancedFilterCount ? ` ${advancedFilterCount}` : ""}
              </Button>
              <Button onClick={resetFilters} variant="light">
                Reset
              </Button>
            </div>
          </div>
          {showAdvancedFilters && (
            <div className="grid gap-3 border-t border-line pt-3 md:grid-cols-2 xl:grid-cols-4">
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">API Key</span>
                <Select
                  value={filter.api_key_id}
                  onChange={(event) => setFilter({ ...filter, api_key_id: event.target.value })}
                >
                  <option value="">Any</option>
                  {apiKeys.map((key) => (
                    <option key={key.id} value={key.id}>{key.name}</option>
                  ))}
                </Select>
              </label>
              <label className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-600">Model</span>
                <Select
                  value={filter.model_id}
                  onChange={(event) => setFilter({ ...filter, model_id: event.target.value })}
                >
                  <option value="">Any</option>
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>{model.name}</option>
                  ))}
                </Select>
              </label>
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">Usage</span>
                <Select
                  value={filter.usage_status}
                  onChange={(event) => setFilter({ ...filter, usage_status: event.target.value })}
                >
                  <option value="">Any</option>
                  <option value="parsed">parsed</option>
                  <option value="estimated">estimated</option>
                  <option value="unknown">unknown</option>
                  <option value="failed">failed</option>
                </Select>
              </label>
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">Pricing</span>
                <Select
                  value={filter.pricing_status}
                  onChange={(event) => setFilter({ ...filter, pricing_status: event.target.value })}
                >
                  <option value="">Any</option>
                  <option value="calculated">calculated</option>
                  <option value="missing_price_config">missing_price_config</option>
                  <option value="usage_unknown">usage_unknown</option>
                  <option value="not_billable">not_billable</option>
                </Select>
              </label>
              <label className="flex items-center gap-2 md:col-span-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">Native Path</span>
                <Input
                  value={filter.native_path}
                  onChange={(event) => setFilter({ ...filter, native_path: event.target.value })}
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">Cache Hit</span>
                <Select
                  value={filter.cache_hit}
                  onChange={(event) => setFilter({ ...filter, cache_hit: event.target.value })}
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
                >
                  <option value="">Any</option>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </Select>
              </label>
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">From</span>
                <Input
                  type="datetime-local"
                  value={filter.created_from}
                  onChange={(event) => setFilter({ ...filter, created_from: event.target.value })}
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="whitespace-nowrap text-xs font-medium text-slate-600">To</span>
                <Input
                  type="datetime-local"
                  value={filter.created_to}
                  onChange={(event) => setFilter({ ...filter, created_to: event.target.value })}
                />
              </label>
            </div>
          )}
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
