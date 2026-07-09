# 阶段四：管理台配置体验优化实施总结

> 日期：2026-07-09  
> 范围：管理台 Routes、Providers、Workbench、Pricing 配置体验优化，以及对应后端校验/Schema/Workbench 流式测试接口。  
> 角色视角：AI Gateway 产品技术负责人（Platform Product Tech Lead）

## 1. 本次目标

阶段四的核心目标是减少管理员误配置，让常见配置闭环尽量通过结构化 UI 完成，而不是依赖手写 JSON、手填 ID 或事后排查。

本次重点落地四件事：

1. Route 配置保存前可验证。
2. Provider 常用配置结构化。
3. Workbench 支持真正的流式响应测试。
4. Pricing 支持筛选、状态识别和 CSV 模版导入。

## 2. 后端改动

### 2.1 Provider Config Schema API

新增接口：

```text
GET /admin/provider-config-schema/{provider_type}
```

用途：

- 前端按 provider 类型渲染常用配置字段。
- 避免所有 provider config 都只能通过 JSON 编辑。

当前支持：

- `claude`
  - `health_path`
  - `default_max_tokens`
- `gemini`
  - `health_path`
  - `forward_headers_allowlist`
- `openai_compatible`
  - `health_path`
  - `request_body_remove_fields`

主要文件：

- `backend/app/api/v1/admin/resources.py`
- `backend/app/schemas/admin.py`

### 2.2 Route Validate API

新增接口：

```text
POST /admin/route-rules/validate
```

返回：

- `valid`
- `errors`
- `warnings`
- `primary`
- `fallbacks`
- `duplicate_model_ids`
- `cross_provider`

校验内容：

- alias 是否存在。
- primary/fallback model 是否存在。
- primary 与 fallback 是否重复。
- model/provider 是否 active。
- provider health 是否 unhealthy。
- fallback 是否跨 provider。
- 当前 alias 是否已有其他 active route。

同时，`POST /admin/route-rules` 和 `PATCH /admin/route-rules/{id}` 已接入相同校验逻辑。前端预检只是体验增强，后端仍会阻止明显错误配置落库。

主要文件：

- `backend/app/api/v1/admin/resources.py`
- `backend/app/schemas/admin.py`

### 2.3 Workbench 真流式测试接口

新增接口：

```text
POST /admin/workbench/chat-test/stream
```

返回格式：

```text
application/x-ndjson
```

事件类型：

- `start`：返回 `request_id`。
- `delta`：返回可直接追加到 UI 的文本片段。
- `chunk`：返回无法解析为文本 delta 的原始 stream chunk。
- `meta`：请求结束后返回 usage log 元数据和保留的 stream chunks。
- `done`：流式请求完成。
- `error`：流式请求失败。

为什么没有继续只用 `/admin/workbench/chat-test`：

- 原接口是标准 JSON 响应，浏览器必须等后端聚合完成后才能展示。
- 用户反馈“勾选 Stream 但 Response 不是流式输出”是正确的。
- 新接口让前端通过 `ReadableStream` 逐块读取并即时渲染，才符合 Workbench 流式测试预期。

主要文件：

- `backend/app/api/v1/admin/workbench.py`

## 3. 前端改动

### 3.1 Provider 页面

主要变化：

- 新增通用 `TagInput` 组件。
- `allowed_paths` 从逗号文本框改为 tag input。
- `blocked_headers` 从逗号文本框改为 tag input。
- Provider 常用 config 字段按 schema 渲染。
- `Provider Config JSON` 仍保留在高级模式中，用于复杂配置。

主要文件：

- `frontend/src/components/ui.tsx`
- `frontend/src/pages/ProvidersPage.tsx`
- `frontend/src/types/gateway.ts`

### 3.2 Routes 页面

主要变化：

- fallback models 使用下拉选择。
- 已选 fallback 支持上移、下移、删除。
- fallback 显示 provider、model status、provider health。
- 表单内新增 `Validate` 操作。
- 保存前自动调用校验接口。
- 校验结果显示 errors、warnings、cross provider 标识。

主要文件：

- `frontend/src/pages/RoutesPage.tsx`
- `frontend/src/types/gateway.ts`

### 3.3 Workbench 页面

主要变化：

- `Stream` 勾选后调用新的 `/admin/workbench/chat-test/stream`。
- 前端使用 `fetch().body.getReader()` 逐块读取 NDJSON。
- Assistant Response 会随着 `delta` 事件即时追加内容。
- 请求结束后补齐 usage/meta。
- `Diagnostics > summary` 增加：
  - `Execution Mode`
  - `Stream Chunks`
- `Diagnostics > response` 增加 stream chunks 诊断信息。
- JSON 模式下也以页面 `Stream` 勾选框为准，避免 raw body 中的 `stream` 覆盖用户操作。

主要文件：

- `frontend/src/pages/WorkbenchPage.tsx`

### 3.4 Pricing 页面

主要变化：

- 支持 provider/model/search/currency/status 筛选。
- 展示价格生效窗口状态：
  - `current`
  - `future`
  - `expired`
- 支持 CSV 批量导入。
- 新增 `CSV Template` 下载按钮。
- `Import CSV` 弹窗内也提供 `Download Template`。

CSV 模版字段：

```csv
provider,model,currency_code,unit_type,unit_quantity,input_unit_price,cached_input_unit_price,output_unit_price,reasoning_output_unit_price,request_unit_price,status,effective_from,effective_to
```

导入匹配规则：

- `provider` 支持 provider name 或 provider id。
- `model` 支持 model name、display name 或 model id。
- provider 与 model 必须属于同一 provider，否则跳过该行。

主要文件：

- `frontend/src/pages/PricingPage.tsx`

## 4. 测试覆盖

新增或扩展的后端测试覆盖：

- provider config schema API。
- route validate warnings/errors。
- route create/update 后端强制校验。
- Workbench stream 聚合响应。
- Workbench 真流式 NDJSON endpoint。

测试文件：

- `backend/tests/test_app_integration.py`

已执行验证：

```bash
cd backend
uv run pytest
```

结果：

```text
46 passed
```

前端构建验证：

```bash
cd frontend
npm run build
```

结果：

```text
build succeeded
```

## 5. 手动验收重点

### 5.1 Workbench 真流式响应

1. 打开 `AI Workbench`。
2. 选择 Client、API Key、Model Alias。
3. 勾选 `Stream`。
4. 点击 `Send`。
5. 验证 Assistant Response 是否边返回边追加文本。
6. 打开 `Diagnostics > summary`，确认：
   - `Execution Mode = stream`
   - `Stream Chunks` 大于 0。

### 5.2 Pricing CSV 模版

1. 打开 `Pricing`。
2. 点击 `CSV Template`。
3. 确认下载 `model-pricing-template.csv`。
4. 点击 `Import CSV`。
5. 点击弹窗内 `Download Template`。
6. 用模版内容导入，确认可创建价格配置。

### 5.3 Route 校验

1. 打开 `Routes`。
2. 创建或编辑 route。
3. 添加 fallback models 并调整顺序。
4. 点击 `Validate`。
5. 验证跨 provider、不健康 provider、重复 model 等场景有明确提示。

### 5.4 Provider 结构化配置

1. 打开 `Providers`。
2. 新建或编辑 provider。
3. 展开 `Advanced`。
4. 验证 allowed paths、blocked headers、常用 config 字段无需手写 CSV/JSON。

## 6. 关键设计取舍

### 6.1 Route 校验采用 warnings + errors

有些配置并非绝对错误，例如跨 provider fallback 或 fallback provider unhealthy。它们可能是管理员有意为之，所以只作为 warning。

真正阻止保存的是硬错误，例如：

- 模型不存在。
- alias 不存在。
- primary 与 fallback 重复。

### 6.2 Provider schema 先做轻量内置

当前 provider 类型有限，schema 先以内置 dict 维护，避免过早引入复杂配置系统。

后续如果 provider 类型快速增长，可以考虑：

- schema 独立为模块。
- schema 与 provider adapter registry 绑定。
- 由后端返回更完整的字段类型、校验规则和默认值。

### 6.3 Workbench stream 使用 NDJSON

没有直接复用 OpenAI SSE 给前端，是因为 Workbench 需要同时输出：

- 可渲染文本 delta。
- 原始 chunks。
- 请求完成后的 usage/meta。
- 错误事件。

NDJSON 比 SSE 更容易用 `fetch().body.getReader()` 处理，也不需要额外 EventSource 兼容 POST 的问题。

### 6.4 Native Proxy Workbench 未在本次完整封装

本次没有把 native proxy 测试 UI 做成完整闭环。

原因：

- 现有 native proxy 运行路径已经由 `/proxy/...` 覆盖。
- Workbench native 测试需要构造 method/path/query/body/header，交互复杂度明显高于 chat test。
- 如果强行塞进本次改动，容易形成第二套路由/请求构造逻辑。

建议作为后续独立小迭代实现：

- Workbench 增加 `Chat / Native Proxy` 分段模式。
- Native 模式支持 provider、method、native path、query、JSON body。
- 后端尽量复用 `NativeProxyService`，避免重复转发逻辑。

## 7. 后续建议

1. 为 Workbench stream 增加前端自动化测试或 Playwright 冒烟测试。
2. Pricing CSV 导入建议后续改为后端批量接口，支持事务、预校验、错误行报告。
3. Provider config schema 建议抽到独立 service/module，避免 admin resources 文件继续膨胀。
4. Route validate 可增加 capability 校验，例如 chat/multimodal/native proxy 能力是否匹配 alias 用途。
5. Workbench native proxy 测试建议单独做一轮，不与 chat form 混在同一表单中。
