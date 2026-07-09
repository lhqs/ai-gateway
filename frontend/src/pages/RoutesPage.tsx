import { ChevronDown, ChevronUp, Pencil, Plus, RefreshCw, Route, Trash2, X } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Modal, Pagination, Section, Select } from "../components/ui";
import { api, apiWithMeta } from "../lib/api";
import type { Alias, Model, PageProps, Provider, RouteRule, RouteValidationResult } from "../types/gateway";

const PAGE_SIZE = 20;

type RouteForm = {
  model_alias_id: string;
  primary_model_id: string;
  fallback_model_ids: string[];
  max_failover_attempts: string;
  cache_ttl_seconds: string;
  status: string;
  cache_enabled: boolean;
  failover_enabled: boolean;
};

function defaultRouteForm(): RouteForm {
  return {
    model_alias_id: "",
    primary_model_id: "",
    fallback_model_ids: [],
    max_failover_attempts: "2",
    cache_ttl_seconds: "300",
    status: "active",
    cache_enabled: true,
    failover_enabled: true
  };
}

function routeFormFromRoute(routeRule: RouteRule): RouteForm {
  return {
    model_alias_id: String(routeRule.model_alias_id),
    primary_model_id: String(routeRule.primary_model_id),
    fallback_model_ids: routeRule.fallback_model_ids.map(String),
    max_failover_attempts: String(routeRule.max_failover_attempts),
    cache_ttl_seconds: String(routeRule.cache_ttl_seconds),
    status: routeRule.status,
    cache_enabled: routeRule.cache_enabled,
    failover_enabled: routeRule.failover_enabled
  };
}

function routePayload(form: RouteForm) {
  return {
    model_alias_id: Number(form.model_alias_id),
    primary_model_id: Number(form.primary_model_id),
    fallback_model_ids: form.fallback_model_ids.map(Number),
    failover_enabled: form.failover_enabled,
    max_failover_attempts: Number(form.max_failover_attempts),
    cache_enabled: form.cache_enabled,
    cache_ttl_seconds: Number(form.cache_ttl_seconds),
    status: form.status
  };
}

export function RoutesPage({ headers, setNotice }: PageProps) {
  const [routes, setRoutes] = useState<RouteRule[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [routeTotal, setRouteTotal] = useState(0);
  const [routePage, setRoutePage] = useState(1);
  const [form, setForm] = useState<RouteForm>(defaultRouteForm());
  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [editingRouteId, setEditingRouteId] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<RouteRule | null>(null);
  const [validation, setValidation] = useState<RouteValidationResult | null>(null);

  const aliasesById = useMemo(
    () => new Map(aliases.map((alias) => [alias.id, alias.alias])),
    [aliases]
  );
  const modelsById = useMemo(
    () => new Map(models.map((model) => [model.id, model.name])),
    [models]
  );
  const providersById = useMemo(
    () => new Map(providers.map((provider) => [provider.id, provider])),
    [providers]
  );

  const fallbackOptions = useMemo(
    () =>
      models.filter(
        (model) =>
          String(model.id) !== form.primary_model_id &&
          !form.fallback_model_ids.includes(String(model.id))
      ),
    [form.fallback_model_ids, form.primary_model_id, models]
  );

  async function load() {
    const offset = (routePage - 1) * PAGE_SIZE;
    const [routeData, modelData, aliasData, providerData] = await Promise.all([
      apiWithMeta<RouteRule[]>(`/admin/route-rules?limit=${PAGE_SIZE}&offset=${offset}`, { headers }, setNotice),
      apiWithMeta<Model[]>("/admin/models?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Alias[]>("/admin/model-aliases?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Provider[]>("/admin/providers?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setRoutes(routeData.data);
    setRouteTotal(routeData.total);
    setModels(modelData.data);
    setAliases(aliasData.data);
    setProviders(providerData.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, routePage]);

  useEffect(() => {
    setRoutePage((page) => Math.min(page, Math.max(1, Math.ceil(routeTotal / PAGE_SIZE))));
  }, [routeTotal]);

  function openCreateRoute() {
    setEditingRouteId(null);
    setForm({
      ...defaultRouteForm(),
      model_alias_id: aliases[0] ? String(aliases[0].id) : "",
      primary_model_id: models[0] ? String(models[0].id) : ""
    });
    setValidation(null);
    setModalMode("create");
  }

  function openEditRoute(routeRule: RouteRule) {
    setEditingRouteId(routeRule.id);
    setForm(routeFormFromRoute(routeRule));
    setValidation(null);
    setModalMode("edit");
  }

  async function validateRoute(nextForm = form) {
    const payload = {
      ...routePayload(nextForm),
      id: modalMode === "edit" && editingRouteId !== null ? editingRouteId : null
    };
    const result = await api<RouteValidationResult>(
      "/admin/route-rules/validate",
      {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
      },
      setNotice
    );
    setValidation(result);
    return result;
  }

  async function submitRoute(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = modalMode === "edit" && editingRouteId !== null;
    const result = await validateRoute();
    if (!result.valid) {
      setNotice(result.errors[0] || "Route rule is invalid");
      return;
    }
    await api<RouteRule>(
      isEdit ? `/admin/route-rules/${editingRouteId}` : "/admin/route-rules",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(routePayload(form))
      },
      setNotice
    );
    setModalMode(null);
    setNotice(isEdit ? "Route rule updated" : "Route rule created");
    await load();
  }

  async function removeRoute() {
    if (!removeTarget) return;
    await api<unknown>(
      `/admin/route-rules/${removeTarget.id}`,
      { method: "DELETE", headers },
      setNotice
    );
    setRemoveTarget(null);
    setNotice("Route rule removed");
    await load();
  }

  function modelName(modelId: number) {
    return modelsById.get(modelId) || modelId;
  }

  function modelLabel(model: Model) {
    const provider = providersById.get(model.provider_id);
    const providerName = provider?.name || `provider ${model.provider_id}`;
    return `${model.name} / ${providerName} / ${model.status} / ${provider?.health_status || "unknown"}`;
  }

  function modelHealth(modelId: string) {
    const model = models.find((item) => String(item.id) === modelId);
    const provider = model ? providersById.get(model.provider_id) : null;
    return {
      model,
      provider,
      available: model?.status === "active" && provider?.status === "active" && provider?.health_status !== "unhealthy"
    };
  }

  function addFallbackModel(modelId: string) {
    if (!modelId || form.fallback_model_ids.includes(modelId)) return;
    setForm({ ...form, fallback_model_ids: [...form.fallback_model_ids, modelId] });
  }

  function removeFallbackModel(modelId: string) {
    setForm({
      ...form,
      fallback_model_ids: form.fallback_model_ids.filter((item) => item !== modelId)
    });
  }

  function moveFallbackModel(modelId: string, direction: -1 | 1) {
    const index = form.fallback_model_ids.indexOf(modelId);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= form.fallback_model_ids.length) return;
    const next = [...form.fallback_model_ids];
    [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
    setForm({ ...form, fallback_model_ids: next });
  }

  return (
    <div className="space-y-5">
      <Section
        title="Route Rules"
        action={
          <div className="flex items-center gap-2">
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button onClick={openCreateRoute}>
              <Plus size={15} />
              New Route
            </Button>
          </div>
        }
      >
        <DataTable
          columns={["id", "alias", "primary", "fallbacks", "failover", "cache", "ttl", "status", "actions"]}
          rows={routes.map((routeRule) => [
            routeRule.id,
            aliasesById.get(routeRule.model_alias_id) || routeRule.model_alias_id,
            modelName(routeRule.primary_model_id),
            routeRule.fallback_model_ids.map(modelName).join(", "),
            routeRule.failover_enabled ? `yes / ${routeRule.max_failover_attempts}` : "no",
            routeRule.cache_enabled ? "yes" : "no",
            `${routeRule.cache_ttl_seconds}s`,
            <Badge tone={routeRule.status === "active" ? "good" : "bad"}>{routeRule.status}</Badge>,
            <div className="flex gap-2">
              <Button onClick={() => openEditRoute(routeRule)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button onClick={() => setRemoveTarget(routeRule)} variant="light">
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination page={routePage} pageSize={PAGE_SIZE} total={routeTotal} onPageChange={setRoutePage} />
      </Section>

      <Modal
        open={modalMode !== null}
        title={modalMode === "edit" ? "Edit Route Rule" : "Create Route Rule"}
        onClose={() => setModalMode(null)}
      >
        <form onSubmit={submitRoute} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Alias">
              <Select
                value={form.model_alias_id}
                onChange={(event) => setForm({ ...form, model_alias_id: event.target.value })}
                required
              >
                <option value="">Select alias</option>
                {aliases.map((alias) => (
                  <option key={alias.id} value={alias.id}>
                    {alias.alias}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Primary Model">
              <Select
                value={form.primary_model_id}
                onChange={(event) =>
                  setForm({
                    ...form,
                    primary_model_id: event.target.value,
                    fallback_model_ids: form.fallback_model_ids.filter(
                      (modelId) => modelId !== event.target.value
                    )
                  })
                }
                required
              >
                <option value="">Select model</option>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {modelLabel(model)}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="md:col-span-2">
              <Field label="Fallback Models">
                <Select value="" onChange={(event) => addFallbackModel(event.target.value)}>
                  <option value="">Add fallback model</option>
                  {fallbackOptions.map((model) => (
                    <option key={model.id} value={model.id}>
                      {modelLabel(model)}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="mt-2 space-y-2">
                {form.fallback_model_ids.length === 0 && (
                  <div className="rounded-md border border-dashed border-line bg-panel px-3 py-2 text-sm text-slate-500">
                    No fallback models
                  </div>
                )}
                {form.fallback_model_ids.map((modelId, index) => {
                  const model = models.find((item) => String(item.id) === modelId);
                  const health = modelHealth(modelId);
                  return (
                    <div
                      key={modelId}
                      className="flex items-center justify-between gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm"
                    >
                      <div className="min-w-0">
                        <div className="truncate">{model ? modelLabel(model) : `model ${modelId}`}</div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          <Badge tone={health.available ? "good" : "bad"}>
                            {health.available ? "available" : "attention"}
                          </Badge>
                          <Badge>{health.provider?.health_status || "unknown health"}</Badge>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Button
                          onClick={() => moveFallbackModel(modelId, -1)}
                          variant="light"
                          disabled={index === 0}
                          title="Move up"
                        >
                          <ChevronUp size={14} />
                        </Button>
                        <Button
                          onClick={() => moveFallbackModel(modelId, 1)}
                          variant="light"
                          disabled={index === form.fallback_model_ids.length - 1}
                          title="Move down"
                        >
                          <ChevronDown size={14} />
                        </Button>
                        <Button
                          onClick={() => removeFallbackModel(modelId)}
                          variant="light"
                          title="Remove fallback"
                        >
                          <X size={14} />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <Field label="Max Failover Attempts">
              <Input
                value={form.max_failover_attempts}
                onChange={(event) => setForm({ ...form, max_failover_attempts: event.target.value })}
              />
            </Field>
            <Field label="Cache TTL Seconds">
              <Input
                value={form.cache_ttl_seconds}
                onChange={(event) => setForm({ ...form, cache_ttl_seconds: event.target.value })}
              />
            </Field>
            <Field label="Status">
              <Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <div className="flex h-9 items-center gap-5">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.failover_enabled}
                  onChange={(event) => setForm({ ...form, failover_enabled: event.target.checked })}
                  className="h-4 w-4 rounded border-line"
                />
                Enable failover
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.cache_enabled}
                  onChange={(event) => setForm({ ...form, cache_enabled: event.target.checked })}
                  className="h-4 w-4 rounded border-line"
                />
                Enable cache
              </label>
            </div>
            <div className="md:col-span-2">
              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={() => validateRoute()} variant="light" disabled={!form.model_alias_id || !form.primary_model_id}>
                  Validate
                </Button>
                {validation && (
                  <Badge tone={validation.valid ? "good" : "bad"}>
                    {validation.valid ? "valid" : "invalid"}
                  </Badge>
                )}
                {validation?.cross_provider && <Badge>cross provider</Badge>}
              </div>
              {validation && (validation.errors.length > 0 || validation.warnings.length > 0) && (
                <div className="mt-2 space-y-1 rounded-md border border-line bg-panel p-3 text-sm">
                  {validation.errors.map((message) => (
                    <div key={message} className="text-rose-700">{message}</div>
                  ))}
                  {validation.warnings.map((message) => (
                    <div key={message} className="text-amber-700">{message}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit" disabled={!aliases.length || !models.length}>
              {modalMode === "edit" ? <Pencil size={15} /> : <Route size={15} />}
              {modalMode === "edit" ? "Save Route" : "Create Route"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={removeTarget !== null} title="Remove Route Rule" onClose={() => setRemoveTarget(null)}>
        <div className="space-y-4">
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Remove route rule for{" "}
            <span className="font-semibold">
              {removeTarget ? aliasesById.get(removeTarget.model_alias_id) || removeTarget.model_alias_id : ""}
            </span>
            ?
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRemoveTarget(null)} variant="light">
              Cancel
            </Button>
            <Button onClick={removeRoute}>
              <Trash2 size={15} />
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
