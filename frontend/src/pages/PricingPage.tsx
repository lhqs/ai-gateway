import { DollarSign, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, DataTable, Field, Input, Modal, Pagination, Section, Select, TextArea } from "../components/ui";
import { api, apiWithMeta } from "../lib/api";
import type { Model, ModelPriceConfig, PageProps, Provider } from "../types/gateway";

const PAGE_SIZE = 20;

type PriceForm = {
  provider_id: string;
  model_id: string;
  currency_code: string;
  unit_type: string;
  unit_quantity: string;
  input_unit_price: string;
  cached_input_unit_price: string;
  output_unit_price: string;
  reasoning_output_unit_price: string;
  request_unit_price: string;
  status: string;
  effective_from: string;
  effective_to: string;
  config: string;
};

type PriceFilter = {
  search: string;
  provider_id: string;
  currency_code: string;
  status: string;
};

const defaultFilter: PriceFilter = {
  search: "",
  provider_id: "",
  currency_code: "",
  status: ""
};

const DEFAULT_CONFIG_JSON = JSON.stringify(
  {
    source: "manual",
    source_model_id: "",
    source_name: "",
    source_unit: "USD per 1M tokens",
    note: "Edit this metadata to describe where the price came from.",
    raw_pricing: {
      prompt: "",
      input_cache_read: "",
      completion: "",
      internal_reasoning: ""
    }
  },
  null,
  2
);

function defaultForm(model?: Model): PriceForm {
  return {
    provider_id: model ? String(model.provider_id) : "",
    model_id: model ? String(model.id) : "",
    currency_code: "USD",
    unit_type: "tokens",
    unit_quantity: "1000000",
    input_unit_price: "",
    cached_input_unit_price: "",
    output_unit_price: "",
    reasoning_output_unit_price: "",
    request_unit_price: "",
    status: "active",
    effective_from: "",
    effective_to: "",
    config: DEFAULT_CONFIG_JSON
  };
}

function dateInputValue(value: string | null) {
  if (!value) return "";
  return value.slice(0, 16);
}

function formFromPrice(price: ModelPriceConfig): PriceForm {
  return {
    provider_id: String(price.provider_id),
    model_id: String(price.model_id),
    currency_code: price.currency_code,
    unit_type: price.unit_type,
    unit_quantity: String(price.unit_quantity),
    input_unit_price: price.input_unit_price || "",
    cached_input_unit_price: price.cached_input_unit_price || "",
    output_unit_price: price.output_unit_price || "",
    reasoning_output_unit_price: price.reasoning_output_unit_price || "",
    request_unit_price: price.request_unit_price || "",
    status: price.status,
    effective_from: dateInputValue(price.effective_from),
    effective_to: dateInputValue(price.effective_to),
    config: JSON.stringify(price.config || {}, null, 2)
  };
}

function isoOrNull(value: string) {
  return value ? new Date(value).toISOString() : null;
}

function nullablePrice(value: string) {
  return value.trim() ? value.trim() : null;
}

function formatMoney(value: string | number | null) {
  return value === null || value === "" ? "" : String(value);
}

export function PricingPage({ headers, setNotice }: PageProps) {
  const [prices, setPrices] = useState<ModelPriceConfig[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<PriceFilter>(defaultFilter);
  const [form, setForm] = useState<PriceForm>(defaultForm());
  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [removeTarget, setRemoveTarget] = useState<ModelPriceConfig | null>(null);

  const modelById = useMemo(() => new Map(models.map((model) => [model.id, model])), [models]);
  const providerById = useMemo(
    () => new Map(providers.map((provider) => [provider.id, provider.name])),
    [providers]
  );
  const selectedModel = modelById.get(Number(form.model_id));
  const availableModels = useMemo(
    () =>
      form.provider_id
        ? models.filter((model) => model.provider_id === Number(form.provider_id))
        : models,
    [models, form.provider_id]
  );

  function priceParams(nextPage = page, values = filter) {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String((nextPage - 1) * PAGE_SIZE)
    });
    Object.entries(values).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params.toString();
  }

  async function load(nextPage = page, values = filter) {
    const [priceData, modelData, providerData] = await Promise.all([
      apiWithMeta<ModelPriceConfig[]>(
        `/admin/model-price-configs?${priceParams(nextPage, values)}`,
        { headers },
        setNotice
      ),
      apiWithMeta<Model[]>("/admin/models?limit=1000&offset=0", { headers }, setNotice),
      apiWithMeta<Provider[]>("/admin/providers?limit=1000&offset=0", { headers }, setNotice)
    ]);
    setPrices(priceData.data);
    setTotal(priceData.total);
    setModels(modelData.data);
    setProviders(providerData.data);
  }

  useEffect(() => {
    load().catch(() => null);
  }, [headers, page]);

  useEffect(() => {
    setPage((current) => Math.min(current, Math.max(1, Math.ceil(total / PAGE_SIZE))));
  }, [total]);

  function openCreate() {
    setEditingId(null);
    setForm(defaultForm(models[0]));
    setModalMode("create");
  }

  function openEdit(price: ModelPriceConfig) {
    setEditingId(price.id);
    setForm(formFromPrice(price));
    setModalMode("edit");
  }

  function changeProvider(providerId: string) {
    const firstModel = models.find((model) => model.provider_id === Number(providerId));
    setForm({
      ...form,
      provider_id: providerId,
      model_id: firstModel ? String(firstModel.id) : ""
    });
  }

  function changeModel(modelId: string) {
    const model = modelById.get(Number(modelId));
    setForm({
      ...form,
      model_id: modelId,
      provider_id: model ? String(model.provider_id) : form.provider_id
    });
  }

  function payload() {
    const config = JSON.parse(form.config || "{}");
    return {
      provider_id: Number(form.provider_id),
      model_id: Number(form.model_id),
      model_name: selectedModel?.name || "",
      currency_code: form.currency_code,
      unit_type: form.unit_type,
      unit_quantity: Number(form.unit_quantity),
      input_unit_price: nullablePrice(form.input_unit_price),
      cached_input_unit_price: nullablePrice(form.cached_input_unit_price),
      output_unit_price: nullablePrice(form.output_unit_price),
      reasoning_output_unit_price: nullablePrice(form.reasoning_output_unit_price),
      request_unit_price: nullablePrice(form.request_unit_price),
      status: form.status,
      effective_from: isoOrNull(form.effective_from),
      effective_to: isoOrNull(form.effective_to),
      config
    };
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const isEdit = modalMode === "edit" && editingId !== null;
    await api<ModelPriceConfig>(
      isEdit ? `/admin/model-price-configs/${editingId}` : "/admin/model-price-configs",
      {
        method: isEdit ? "PATCH" : "POST",
        headers,
        body: JSON.stringify(payload())
      },
      setNotice
    );
    setModalMode(null);
    setNotice(isEdit ? "Price config updated" : "Price config created");
    await load();
  }

  async function removePrice() {
    if (!removeTarget) return;
    await api<unknown>(
      `/admin/model-price-configs/${removeTarget.id}`,
      { method: "DELETE", headers },
      setNotice
    );
    setRemoveTarget(null);
    setNotice("Price config removed");
    await load();
  }

  async function applyFilters() {
    setPage(1);
    await load(1, filter);
  }

  async function resetFilters() {
    setFilter(defaultFilter);
    setPage(1);
    await load(1, defaultFilter);
  }

  return (
    <div className="space-y-5">
      <section className="rounded-md border border-line bg-white px-4 py-3">
        <div className="overflow-x-auto">
          <div className="flex min-w-[860px] items-center gap-3">
            <label className="flex items-center gap-2">
              <span className="whitespace-nowrap text-xs font-medium text-slate-600">Model</span>
              <Input
                value={filter.search}
                onChange={(event) => setFilter({ ...filter, search: event.target.value })}
                className="w-64"
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Provider</span>
              <Select
                value={filter.provider_id}
                onChange={(event) => setFilter({ ...filter, provider_id: event.target.value })}
                className="w-44"
              >
                <option value="">Any</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </Select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-600">Currency</span>
              <Select
                value={filter.currency_code}
                onChange={(event) => setFilter({ ...filter, currency_code: event.target.value })}
                className="w-28"
              >
                <option value="">Any</option>
                <option value="USD">USD</option>
                <option value="CNY">CNY</option>
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
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </label>
            <div className="ml-auto flex items-center gap-2">
              <Button onClick={applyFilters}>Apply</Button>
              <Button onClick={resetFilters} variant="light">
                Reset
              </Button>
            </div>
          </div>
        </div>
      </section>
      <Section
        title="Model Pricing"
        action={
          <div className="flex items-center gap-2">
            <Button onClick={load} variant="light">
              <RefreshCw size={15} />
              Refresh
            </Button>
            <Button onClick={openCreate} disabled={!models.length}>
              <Plus size={15} />
              New Price
            </Button>
          </div>
        }
      >
        <DataTable
          columns={["id", "provider", "model", "currency", "unit", "input", "cached input", "output", "status", "actions"]}
          rows={prices.map((price) => [
            price.id,
            providerById.get(price.provider_id) || price.provider_id,
            modelById.get(price.model_id)?.display_name || price.model_name,
            price.currency_code,
            `${price.unit_quantity} ${price.unit_type}`,
            formatMoney(price.input_unit_price),
            formatMoney(price.cached_input_unit_price),
            formatMoney(price.output_unit_price),
            <Badge tone={price.status === "active" ? "good" : "bad"}>{price.status}</Badge>,
            <div className="flex gap-2">
              <Button onClick={() => openEdit(price)} variant="light">
                <Pencil size={14} />
                Edit
              </Button>
              <Button onClick={() => setRemoveTarget(price)} variant="light">
                <Trash2 size={14} />
                Remove
              </Button>
            </div>
          ])}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </Section>

      <Modal
        open={modalMode !== null}
        title={modalMode === "edit" ? "Edit Price Config" : "Create Price Config"}
        onClose={() => setModalMode(null)}
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Provider">
              <Select value={form.provider_id} onChange={(event) => changeProvider(event.target.value)} required>
                <option value="">Select provider</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Model">
              <Select value={form.model_id} onChange={(event) => changeModel(event.target.value)} required>
                <option value="">Select model</option>
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name || model.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Currency">
              <Select
                value={form.currency_code}
                onChange={(event) => setForm({ ...form, currency_code: event.target.value })}
              >
                <option value="USD">USD</option>
                <option value="CNY">CNY</option>
              </Select>
            </Field>
            <Field label="Status">
              <Select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </Select>
            </Field>
            <Field label="Unit Quantity">
              <Input
                value={form.unit_quantity}
                onChange={(event) => setForm({ ...form, unit_quantity: event.target.value })}
                required
              />
            </Field>
            <Field label="Unit Type">
              <Select value={form.unit_type} onChange={(event) => setForm({ ...form, unit_type: event.target.value })}>
                <option value="tokens">tokens</option>
                <option value="request">request</option>
              </Select>
            </Field>
            <Field label="Input Unit Price">
              <Input value={form.input_unit_price} onChange={(event) => setForm({ ...form, input_unit_price: event.target.value })} />
            </Field>
            <Field label="Cached Input Unit Price">
              <Input
                value={form.cached_input_unit_price}
                onChange={(event) => setForm({ ...form, cached_input_unit_price: event.target.value })}
              />
            </Field>
            <Field label="Output Unit Price">
              <Input value={form.output_unit_price} onChange={(event) => setForm({ ...form, output_unit_price: event.target.value })} />
            </Field>
            <Field label="Reasoning Output Unit Price">
              <Input
                value={form.reasoning_output_unit_price}
                onChange={(event) => setForm({ ...form, reasoning_output_unit_price: event.target.value })}
              />
            </Field>
            <Field label="Effective From">
              <Input
                type="datetime-local"
                value={form.effective_from}
                onChange={(event) => setForm({ ...form, effective_from: event.target.value })}
              />
            </Field>
            <Field label="Effective To">
              <Input
                type="datetime-local"
                value={form.effective_to}
                onChange={(event) => setForm({ ...form, effective_to: event.target.value })}
              />
            </Field>
            <div className="md:col-span-2">
              <Field label="Config JSON">
                <TextArea value={form.config} onChange={(event) => setForm({ ...form, config: event.target.value })} />
              </Field>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setModalMode(null)} variant="light">
              Cancel
            </Button>
            <Button type="submit" disabled={!form.provider_id || !form.model_id}>
              <DollarSign size={15} />
              {modalMode === "edit" ? "Save Price" : "Create Price"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={removeTarget !== null} title="Remove Price Config" onClose={() => setRemoveTarget(null)}>
        <div className="space-y-4">
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
            Remove <span className="font-semibold">{removeTarget?.model_name}</span> {removeTarget?.currency_code} price config?
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={() => setRemoveTarget(null)} variant="light">
              Cancel
            </Button>
            <Button onClick={removePrice}>
              <Trash2 size={15} />
              Remove
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
