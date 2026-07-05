import { Database, Network, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Modal, Pagination, Section, Select } from "../components/ui";
import { api, apiWithMeta, parseCsv } from "../lib/api";
import type { Alias, Model, PageProps, Provider, RouteRule } from "../types/gateway";

const PAGE_SIZE = 20;

type ModelForm = {
  provider_id: string;
  name: string;
  display_name: string;
  capabilities: string;
  context_window: string;
  status: string;
};

type AliasForm = {
  alias: string;
  description: string;
  primary_model_id: string;
  status: string;
};

type RemoveTarget =
  | { type: "model"; id: number; label: string }
  | { type: "alias"; id: number; label: string };

function defaultModelForm(providerId = ""): ModelForm {
  return {
    provider_id: providerId,
    name: "",
    display_name: "",
    capabilities: "chat, stream",
    context_window: "",
    status: "active"
  };
}

function defaultAliasForm(primaryModelId = ""): AliasForm {
  return { alias: "default-chat", description: "", primary_model_id: primaryModelId, status: "active" };
}

function modelFormFromModel(model: Model): ModelForm {
  return {
    provider_id: String(model.provider_id),
    name: model.name,
    display_name: model.display_name || "",
    capabilities: model.capabilities.join(", "),
    context_window: model.context_window ? String(model.context_window) : "",
    status: model.status
  };
}

function aliasFormFromAlias(alias: Alias, routeRule?: RouteRule): AliasForm {
  return {
    alias: alias.alias,
    description: alias.description || "",
    primary_model_id: routeRule ? String(routeRule.primary_model_id) : "",
    status: alias.status
  };
}

function modelPayload(form: ModelForm) {
  return {
    provider_id: Number(form.provider_id),
    name: form.name,
    display_name: form.display_name || null,
    capabilities: parseCsv(form.capabilities),
    context_window: form.context_window ? Number(form.context_window) : null,
    status: form.status
  };
}

export function ModelsPage({ headers, setNotice }: PageProps) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [modelOptions, setModelOptions] = useState<Model[]>([]);
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [routeRules, setRouteRules] = useState<RouteRule[]>([]);
  const [modelTotal, setModelTotal] = useState(0);
  const [aliasTotal, setAliasTotal] = useState(0);
  const [modelPage, setModelPage] = useState(1);
  const [aliasPage, setAliasPage] = useState(1);
  const [modelForm, setModelForm] = useState<ModelForm>(defaultModelForm());
  const [aliasForm, setAliasForm] = useState<AliasForm>(defaultAliasForm());
  const [modelModalMode, setModelModalMode] = useState<"create" | "edit" | null>(null);
  const [aliasModalMode, setAliasModalMode] = useState<"create" | "edit" | null>(null);
  const [editingModelId, setEditingModelId] = useState<number | null>(null);
  const [editingAliasId, setEditingAliasId] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<RemoveTarget | null>(null);

  const providerNamesById = useMemo(
    () => new Map(providers.map((provider) => [provider.id, provider.name])),
    [providers]
  );
  const modelsById = useMemo(
    () => new Map(modelOptions.map((model) => [model.id, model.display_name || model.name])),
    [modelOptions]
  );
  const routeRulesByAliasId = useMemo(
    () => {
      const map = new Map<number, RouteRule>();
      const sorted = [...routeRules].sort((left, right) => left.priority - right.priority || left.id - right.id);
      for (const routeRule of sorted) {
        if (!map.has(routeRule.model_alias_id)) {
          map.set(routeRule.model_alias_id, routeRule);
        }
      }
      return map;
    },
    [routeRules]
  );
  const activeRouteRulesByAliasId = useMemo(
    () => {
      const map = new Map<number, RouteRule>();
      const sorted = routeRules
        .filter((routeRule) => routeRule.status === "active")
        .sort((left, right) => left.priority - right.priority || left.id - right.id);
      for (const routeRule of sorted) {
        if (!map.has(routeRule.model_alias_id)) {
          map.set(routeRule.model_alias_id, routeRule);
        }
      }
      return map;
    },
    [routeRules]
  );
  const activeModelOptions = useMemo(
    () => modelOptions.filter((model) => model.status === "active"),
    [modelOptions]
  );

  async function load() {
    const modelOffset = (modelPage - 1) * PAGE_SIZE;
    const aliasOffset = (aliasPage - 1) * PAGE_SIZE;
    const [providerData, modelData, aliasData, modelOptionData, routeRuleData] = await Promise.all([
      apiWithMeta<Provider[]>("/admin/providers?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Model[]>(`/admin/models?limit=${PAGE_SIZE}&offset=${modelOffset}`, { headers }, setNotice),
      apiWithMeta<Alias[]>(
        `/admin/model-aliases?limit=${PAGE_SIZE}&offset=${aliasOffset}`,
        { headers },
        setNotice
      ),
      apiWithMeta<Model[]>("/admin/models?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<RouteRule[]>("/admin/route-rules?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setProviders(providerData.data);
    setModels(modelData.data);
    setModelOptions(modelOptionData.data);
    setModelTotal(modelData.total);
    setAliases(aliasData.data);
    setAliasTotal(aliasData.total);
    setRouteRules(routeRuleData.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, modelPage, aliasPage]);

  useEffect(() => {
    setModelPage((page) => Math.min(page, Math.max(1, Math.ceil(modelTotal / PAGE_SIZE))));
  }, [modelTotal]);

  useEffect(() => {
    setAliasPage((page) => Math.min(page, Math.max(1, Math.ceil(aliasTotal / PAGE_SIZE))));
  }, [aliasTotal]);

  function openCreateModel() {
    setEditingModelId(null);
    setModelForm(defaultModelForm(providers[0] ? String(providers[0].id) : ""));
    setModelModalMode("create");
  }

  function openEditModel(model: Model) {
    setEditingModelId(model.id);
    setModelForm(modelFormFromModel(model));
    setModelModalMode("edit");
  }

  function openCreateAlias() {
    setEditingAliasId(null);
    setAliasForm(defaultAliasForm(activeModelOptions[0] ? String(activeModelOptions[0].id) : ""));
    setAliasModalMode("create");
  }

  function openEditAlias(alias: Alias) {
    setEditingAliasId(alias.id);
    setAliasForm(aliasFormFromAlias(alias, routeRulesByAliasId.get(alias.id)));
    setAliasModalMode("edit");
  }

  async function submitModel(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = modelModalMode === "edit" && editingModelId !== null;
    await api<Model>(
      isEdit ? `/admin/models/${editingModelId}` : "/admin/models",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(modelPayload(modelForm))
      },
      setNotice
    );
    setModelModalMode(null);
    setNotice(isEdit ? "Model updated" : "Model created");
    await load();
  }

  async function submitAlias(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = aliasModalMode === "edit" && editingAliasId !== null;
    const alias = await api<Alias>(
      isEdit ? `/admin/model-aliases/${editingAliasId}` : "/admin/model-aliases",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify({
          alias: aliasForm.alias,
          description: aliasForm.description || null,
          status: aliasForm.status
        })
      },
      setNotice
    );

    if (aliasForm.primary_model_id) {
      const routeRule = isEdit ? routeRulesByAliasId.get(alias.id) : undefined;
      await api<RouteRule>(
        routeRule ? `/admin/route-rules/${routeRule.id}` : "/admin/route-rules",
        {
          method: routeRule ? "PATCH" : "POST",
          headers,
          body: JSON.stringify({
            model_alias_id: alias.id,
            primary_model_id: Number(aliasForm.primary_model_id),
            status: "active",
            failover_enabled: true,
            max_failover_attempts: 2,
            cache_enabled: false,
            cache_ttl_seconds: 300
          })
        },
        setNotice
      );
    }

    setAliasModalMode(null);
    setNotice(isEdit ? "Alias route updated" : "Alias route created");
    await load();
  }

  async function removeItem() {
    if (!removeTarget) return;
    const endpoint =
      removeTarget.type === "model"
        ? `/admin/models/${removeTarget.id}`
        : `/admin/model-aliases/${removeTarget.id}`;

    await api<unknown>(endpoint, { method: "DELETE", headers }, setNotice);
    setRemoveTarget(null);
    setNotice(removeTarget.type === "model" ? "Model removed" : "Alias removed");
    await load();
  }

  return (
    <div className="space-y-5">
      <Section
        title="Models"
        action={
          <div className="flex items-center gap-2">
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button onClick={openCreateModel}>
              <Plus size={15} />
              New Model
            </Button>
          </div>
        }
      >
        <DataTable
          columns={["id", "provider", "name", "display", "capabilities", "context", "status", "actions"]}
          rows={models.map((model) => [
            model.id,
            providerNamesById.get(model.provider_id) || model.provider_id,
            model.name,
            model.display_name || "",
            model.capabilities.join(", "),
            model.context_window || "",
            <Badge tone={model.status === "active" ? "good" : "bad"}>{model.status}</Badge>,
            <div className="flex gap-2">
              <Button onClick={() => openEditModel(model)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button
                onClick={() => setRemoveTarget({ type: "model", id: model.id, label: model.name })}
                variant="light"
              >
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination page={modelPage} pageSize={PAGE_SIZE} total={modelTotal} onPageChange={setModelPage} />
      </Section>

      <Section
        title="Aliases"
        action={
          <Button onClick={openCreateAlias}>
            <Network size={15} />
            New Alias Route
          </Button>
        }
      >
        <DataTable
          columns={["id", "alias", "primary model", "description", "status", "actions"]}
          rows={aliases.map((alias) => [
            alias.id,
            alias.alias,
            modelsById.get(activeRouteRulesByAliasId.get(alias.id)?.primary_model_id || 0) || "No active route",
            alias.description || "",
            <Badge tone={alias.status === "active" ? "good" : "bad"}>{alias.status}</Badge>,
            <div className="flex gap-2">
              <Button onClick={() => openEditAlias(alias)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button
                onClick={() => setRemoveTarget({ type: "alias", id: alias.id, label: alias.alias })}
                variant="light"
              >
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination page={aliasPage} pageSize={PAGE_SIZE} total={aliasTotal} onPageChange={setAliasPage} />
      </Section>

      <Modal
        open={modelModalMode !== null}
        title={modelModalMode === "edit" ? "Edit Model" : "Create Model"}
        onClose={() => setModelModalMode(null)}
      >
        <form onSubmit={submitModel} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Provider">
              <Select
                value={modelForm.provider_id}
                onChange={(event) => setModelForm({ ...modelForm, provider_id: event.target.value })}
                required
              >
                <option value="">Select provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select
                value={modelForm.status}
                onChange={(event) => setModelForm({ ...modelForm, status: event.target.value })}
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <Field label="Model Name">
              <Input
                value={modelForm.name}
                onChange={(event) => setModelForm({ ...modelForm, name: event.target.value })}
                required
              />
            </Field>
            <Field label="Display Name">
              <Input
                value={modelForm.display_name}
                onChange={(event) => setModelForm({ ...modelForm, display_name: event.target.value })}
              />
            </Field>
            <Field label="Capabilities">
              <Input
                value={modelForm.capabilities}
                onChange={(event) => setModelForm({ ...modelForm, capabilities: event.target.value })}
              />
            </Field>
            <Field label="Context Window">
              <Input
                value={modelForm.context_window}
                onChange={(event) => setModelForm({ ...modelForm, context_window: event.target.value })}
              />
            </Field>
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setModelModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit" disabled={!providers.length}>
              {modelModalMode === "edit" ? <Pencil size={15} /> : <Database size={15} />}
              {modelModalMode === "edit" ? "Save Model" : "Create Model"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={aliasModalMode !== null}
        title={aliasModalMode === "edit" ? "Edit Alias Route" : "Create Alias Route"}
        onClose={() => setAliasModalMode(null)}
      >
        <form onSubmit={submitAlias} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Alias">
              <Input
                value={aliasForm.alias}
                onChange={(event) => setAliasForm({ ...aliasForm, alias: event.target.value })}
                required
              />
            </Field>
            <Field label="Status">
              <Select
                value={aliasForm.status}
                onChange={(event) => setAliasForm({ ...aliasForm, status: event.target.value })}
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <div className="md:col-span-2">
              <Field label="Primary Model">
                <Select
                  value={aliasForm.primary_model_id}
                  onChange={(event) => setAliasForm({ ...aliasForm, primary_model_id: event.target.value })}
                  required
                >
                  <option value="">Select model</option>
                  {activeModelOptions.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.display_name || model.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="md:col-span-2">
              <Field label="Description">
                <Input
                  value={aliasForm.description}
                  onChange={(event) => setAliasForm({ ...aliasForm, description: event.target.value })}
                />
              </Field>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setAliasModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit" disabled={!activeModelOptions.length}>
              {aliasModalMode === "edit" ? <Pencil size={15} /> : <Network size={15} />}
              {aliasModalMode === "edit" ? "Save Alias Route" : "Create Alias Route"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={removeTarget !== null}
        title={removeTarget?.type === "model" ? "Remove Model" : "Remove Alias"}
        onClose={() => setRemoveTarget(null)}
      >
        <div className="space-y-4">
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Remove <span className="font-semibold">{removeTarget?.label}</span>?
            {removeTarget?.type === "model"
              ? " Route rules that depend on this model will be cleaned up."
              : " Route rules using this alias will also be removed."}
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRemoveTarget(null)} variant="light">
              Cancel
            </Button>
            <Button onClick={removeItem}>
              <Trash2 size={15} />
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
