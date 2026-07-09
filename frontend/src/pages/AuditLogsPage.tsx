import { ListFilter, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, DataTable, Input, Pagination, Section, Select } from "../components/ui";
import { apiWithMeta, jsonPreview } from "../lib/api";
import type { AdminAuditLog, PageProps } from "../types/gateway";

const PAGE_SIZE = 20;

type AuditFilter = {
  action: string;
  resource_type: string;
  resource_id: string;
  user_id: string;
};

const defaultFilter: AuditFilter = {
  action: "",
  resource_type: "",
  resource_id: "",
  user_id: ""
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

function auditParams(page: number, filter: AuditFilter) {
  const params = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String((page - 1) * PAGE_SIZE)
  });
  Object.entries(filter).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params.toString();
}

export function AuditLogsPage({ headers, setNotice }: PageProps) {
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<AuditFilter>(defaultFilter);
  const [openId, setOpenId] = useState<number | null>(null);

  async function load(nextPage = page, nextFilter = filter) {
    const result = await apiWithMeta<AdminAuditLog[]>(
      `/admin/audit-logs?${auditParams(nextPage, nextFilter)}`,
      { headers },
      setNotice
    );
    setLogs(result.data);
    setTotal(result.total);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, page]);

  useEffect(() => {
    setPage((value) => Math.min(value, Math.max(1, Math.ceil(total / PAGE_SIZE))));
  }, [total]);

  async function applyFilters() {
    setOpenId(null);
    setPage(1);
    await load(1);
  }

  async function resetFilters() {
    setFilter(defaultFilter);
    setOpenId(null);
    setPage(1);
    await load(1, defaultFilter);
  }

  return (
    <div className="space-y-5">
      <section className="rounded-md border border-line bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex min-w-[190px] flex-1 items-center gap-2 xl:max-w-[240px]">
            <span className="text-xs font-medium text-slate-600">Action</span>
            <Input
              value={filter.action}
              onChange={(event) => setFilter({ ...filter, action: event.target.value })}
              placeholder="api_key.rotate"
            />
          </label>
          <label className="flex min-w-[190px] flex-1 items-center gap-2 xl:max-w-[240px]">
            <span className="whitespace-nowrap text-xs font-medium text-slate-600">Resource</span>
            <Select
              value={filter.resource_type}
              onChange={(event) => setFilter({ ...filter, resource_type: event.target.value })}
            >
              <option value="">Any</option>
              <option value="client">client</option>
              <option value="api_key">api_key</option>
              <option value="provider">provider</option>
              <option value="model">model</option>
              <option value="model_alias">model_alias</option>
              <option value="route_rule">route_rule</option>
              <option value="model_price_config">model_price_config</option>
            </Select>
          </label>
          <label className="flex min-w-[150px] flex-1 items-center gap-2 xl:max-w-[180px]">
            <span className="whitespace-nowrap text-xs font-medium text-slate-600">ID</span>
            <Input
              value={filter.resource_id}
              onChange={(event) => setFilter({ ...filter, resource_id: event.target.value })}
            />
          </label>
          <label className="flex min-w-[150px] flex-1 items-center gap-2 xl:max-w-[180px]">
            <span className="whitespace-nowrap text-xs font-medium text-slate-600">User</span>
            <Input
              value={filter.user_id}
              onChange={(event) => setFilter({ ...filter, user_id: event.target.value })}
            />
          </label>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            <Button onClick={applyFilters}>
              <ListFilter size={15} />
              Apply
            </Button>
            <Button onClick={resetFilters} variant="light">Reset</Button>
          </div>
        </div>
      </section>

      <Section
        title="Audit Logs"
        action={
          <Button onClick={() => load()} variant="light">
            <RefreshCw size={15} />
            Refresh
          </Button>
        }
      >
        <DataTable
          columns={["time", "action", "resource", "user", "ip", "detail", ""]}
          rows={logs.map((log) => [
            <span className="text-xs text-slate-600">{formatTime(log.created_at)}</span>,
            log.action,
            `${log.resource_type || ""}${log.resource_id ? ` #${log.resource_id}` : ""}`,
            log.user_id ?? "",
            log.ip_address || "",
            <span className="block max-w-[360px] truncate text-xs">{jsonPreview(log.detail)}</span>,
            <Button onClick={() => setOpenId(openId === log.id ? null : log.id)} variant="light">
              Details
            </Button>
          ])}
        />
        {logs.map((log) => openId === log.id && (
          <pre key={log.id} className="mt-3 max-h-[420px] overflow-auto rounded-md border border-line bg-panel p-3 text-xs leading-5">
            {JSON.stringify(log, null, 2)}
          </pre>
        ))}
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </Section>
    </div>
  );
}
