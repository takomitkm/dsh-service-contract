# DSH 插件服务面契约（Layer A + B + C）

> **这是什么**：把 DSH（DeepSeek Harness）对外暴露的接口反向梳理成一份**显式契约**——哪些方法、什么 payload。
> 用于「一模一样」复刻 / 反代 / 外部客户端对接。DSH 没有一份统一的对外 spec 文档，但真实契约分散在源码里，
> 本文把它抽出来。

- **DSH 版本**：`0.2.2-rc.3`（tag `dsh-v0.2.2-rc.3`，commit `38a6a5c965aa99ab525161efb7cc5cf1fe62fced`）
- **来源 archive**：`C:\Users\takomi\AppData\Local\Programs\DeepSeek Harness\resources\app.asar`
- **产物树（Layer B 取源 + Layer C 交叉核对）**：`S:\apps\llm\agentwork\.tmp\dsh-asar-0.2.2-rc.3`（21717 文件）
- **交叉核对来源**：local installed app.asar extraction (@deepseek-ai/dsh-desktop-runtime 0.2.2-rc.3)
- **生成时间**：2026-11-20T15:49:17.912107+00:00
- **机器可读版**：同目录 `contract.json`

## 三层服务面（本契约覆盖 A、B、C）

| 层 | 是什么 | 谁在用 | 本契约状态 |
|---|---|---|---|
| **A. SDK / JSON-RPC** | 换行分帧的 JSON-RPC 2.0 线协议（外部客户端/反代走这条） | `dsh-sdk-client`(TS)、Python SDK、任何外部进程 | ✅ 已转录（协议 README） |
| **B. Host↔Client Remote (Typert)** | 渲染端 ↔ 主进程的命名 RPC endpoint，每个方法带 JSON Schema | DSH 自己的 renderer / 任何调 Remote 的进程 | ✅ 机器导出（39 包 / 224 endpoint / 0 错） |
| **C. 进程内 Cordis `ctx.*` 服务** | 插件在 host 进程内直接消费的服务对象 | cordis 插件包本身 | ✅ 类型化抽取（dsh-v0.2.2-rc.3 `.ts` + asar `.js` 交叉核对） |

---

# Layer A — SDK / JSON-RPC 协议

来源：`dsh-sdk-protocol/README.md (shipped in asar) + lib/index.js (transport only; types erased).`。

## A.1 传输与分帧

- **分帧**：one JSON-RPC 2.0 message per '\n'-terminated line over caller-owned byte streams
- **分派**：id+method=request; id alone=response; method alone=notification; malformed lines ignored
- **错误映射**：无 handler → `-32601`；handler 失败 → `-32603`；错误响应以 `JsonRpcResponseError` 抛出，保留 wire `code` 与可选 `data`。
- **生命周期**：start() attaches stream listeners; close() detaches them and rejects pending requests without destroying the streams
- **方法映射类型**：`HarnessSdkRequestMap`、`HarnessSdkClientRequestMap`、`HarnessSdkHostRequestMap`、`HarnessSdkNotificationMap`

## A.2 方法表（16 条）

| 方向 | 方法 | 参数 → 结果 | 类型 |
|---|---|---|---|
| client->server | `initialize` | `InitializeParams` → `InitializeResult` | request |
| client->server | `session/prompt` | `SessionPromptParams` → `SessionPromptResult` | request |
| client->server | `session/query` | `SessionQueryParams` → `SessionQueryResult` | request |
| client->server | `session/resume` | `SessionResumeParams` → `{}` | request |
| client->server | `session/wait` | `SessionWaitParams` → `{}` | request |
| client->server | `session/working-directory/get` | `SessionWorkingDirectoryParams` → `SessionWorkingDirectoryResult` | request |
| client->server | `session/working-directory/set` | `SessionWorkingDirectorySetParams` → `SessionWorkingDirectoryResult` | request |
| client->server | `shutdown` | `(none)` → `{}` | request |
| server->client | `approval/request` | `ApprovalRequestParams` → `ApprovalRequestResult` | request |
| server->client | `user-question/ask` | `SdkUserQuestionRequest` → `SdkUserQuestionResult` | request |
| server->client | `user-question.cancelled` | `SdkUserQuestionCancelled` | notification |
| server->client | `session.event` | `SessionEventNotification` | notification |
| server->client | `session.status` | `SessionStatusNotification` | notification |
| server->client | `session.query.completed` | `{sessionId, commandId, finalResponse, finishReason}` | notification |
| server->client | `subagent.started` | `SubagentStartedNotification` | notification |
| server->client | `subagent.finished` | `SubagentFinishedNotification` | notification |

### 逐方法说明

#### `initialize`  (client->server · request)
- 参数：`InitializeParams` → 结果：`InitializeResult`
- Handshake. approvalRequests:true enables approval/request; capabilities.userQuestions:true enables user-question/ask; reasoningEffort optional non-empty adapter id; maxTokens optional positive safe int; resolves the exact provider/model route and rejects session/prompt until handshake succeeds. serverInfo.name is wire-stable 'deepseek-harness-sdk-runtime'; serverInfo.version is '0.0.1' (unvalidated).

#### `session/prompt`  (client->server · request)
- 参数：`SessionPromptParams` → 结果：`SessionPromptResult`
- Queues content blocks without native slash-command routing (runtime skill recognition still applies). SessionPromptResult.messageId = the queued user message id (a durable enqueue receipt, not a model result).

#### `session/query`  (client->server · request)
- 参数：`SessionQueryParams` → 结果：`SessionQueryResult`
- Accepts {sessionId, contentBlocks: SdkPromptContentBlock[]}. Returns {kind:'prompt', messageId} for queued ordinary input, or {kind:'command', execution} after a supported command settles. A command requires one complete text block plus only encoded images; empty/all-blank text rejected; image-only allowed; strings normalize to a text block.

#### `session/resume`  (client->server · request)
- 参数：`SessionResumeParams` → 结果：`{}`
- Accepts non-empty persisted {sessionId}; restores that exact session (requires initialization + the original persistence store). Sends no new input; rejects missing/unreadable/incompatible/occupied sessions without creating a replacement.

#### `session/wait`  (client->server · request)
- 参数：`SessionWaitParams` → 结果：`{}`
- Accepts {sessionId}; returns {} after the root stays idle and progressing managed descendant work finishes; unknown ids and live Agent failures without a newer committed terminal are rejected.

#### `session/working-directory/get`  (client->server · request)
- 参数：`SessionWorkingDirectoryParams` → 结果：`SessionWorkingDirectoryResult`
- Read the session working directory.

#### `session/working-directory/set`  (client->server · request)
- 参数：`SessionWorkingDirectorySetParams` → 结果：`SessionWorkingDirectoryResult`
- Set the session working directory.

#### `shutdown`  (client->server · request)
- 参数：`(none)` → 结果：`{}`
- Shut the runtime down.

#### `approval/request`  (server->client · request)
- 参数：`ApprovalRequestParams` → 结果：`ApprovalRequestResult`
- OPT-IN: requires InitializeParams.approvalRequests == true. Params {sessionId, toolName, callId?, reason?}; Result {outcome: 'allowed-once' | 'rejected' | 'cancelled'}. Only 'allowed-once' grants exactly one operation. Cancellation discards the pending request and late responses; shutdown/transport loss fail decisions closed.

#### `user-question/ask`  (server->client · request)
- 参数：`SdkUserQuestionRequest` → 结果：`SdkUserQuestionResult`
- OPT-IN: requires InitializeParams.capabilities.userQuestions == true. Params {requestId, sessionId, questions}; Result {answers:[{id, selected, custom?}]} naming every question id exactly once, OR {cancelled:true} (dismissal -> native ASK_CANCELLED). Invalid batches -> BAD_ANSWER; host/transport failures -> PROVIDER_ERROR.

#### `user-question.cancelled`  (server->client · notification)
- 参数：`SdkUserQuestionCancelled`
- Identifies the request that stopped waiting; host cancels its own work and discards the question.

#### `session.event`  (server->client · notification)
- 参数：`SessionEventNotification`
- Every session event in the runtime, unfiltered.

#### `session.status`  (server->client · notification)
- 参数：`SessionStatusNotification`
- Whole-agent 'running'/'idle' transition.

#### `session.query.completed`  (server->client · notification)
- 参数：`{sessionId, commandId, finalResponse, finishReason}`
- Sent for the same commandId after a command query's model activity starts / state-only commands need no model turn.

#### `subagent.started`  (server->client · notification)
- 参数：`SubagentStartedNotification`
- A subagent started.

#### `subagent.finished`  (server->client · notification)
- 参数：`SubagentFinishedNotification`
- Subagent finished (in-process runs only). lastAssistantMessage = child's last non-empty assistant message, or accumulated assistant text; absent when neither exists.

## A.3 Payload 类型形状

> TS 类型在随包 `.js` 中已被编译抹除；下列形状**逐字转录自协议 README**（`Payload semantics` / 各方法段）。

- `InitializeParams` = { approvalRequests?: boolean; capabilities?: { userQuestions?: boolean }; reasoningEffort?: string (non-empty adapter-owned id); maxTokens?: positive safe int }
- `ApprovalRequestParams` = { sessionId, toolName, callId?, reason? }
- `ApprovalRequestResult` = { outcome: 'allowed-once' | 'rejected' | 'cancelled' }
- `SdkUserQuestionRequest` = { requestId, sessionId, questions }
- `SdkUserQuestionResult` = { answers: [{ id, selected, custom? }] } | { cancelled: true }
- `SessionQueryParams` = { sessionId, contentBlocks: SdkPromptContentBlock[] }
- `SessionQueryResult` = { kind: 'prompt', messageId } | { kind: 'command', execution }
- `SdkPromptContentBlock` = ordinary durable content + SdkEncodedImageBlock { type: 'image', data, mimeType } (server converts encoded images to durable refs before enqueue)
- `SessionPromptResult` = { messageId } (durable enqueue receipt)

_TypeScript types are erased in shipped .js; these shapes are transcribed verbatim from dsh-sdk-protocol/README.md (Payload semantics). Notification payloads depend on SessionEvent (dsh-session), ContentBlock (dsh-llm), SubagentStopReason (dsh-subagent)._

## A.4 已知限制

- No protocol-version negotiation (handshake carries only serverInfo.version = '0.0.1', unvalidated).
- No cancel or session-close methods; a client abandons a turn by closing the runtime process.
- Question waits are process-local; question request ids are not durable handles across a runtime restart.

---

# Layer B — Host↔Client Remote (Typert)，机器导出

每个 endpoint 都来自对应包里的生成物 `lib/typert.remote-client.js`（头注 `Generated by @deepseek-ai/dsh-typert-generator from the Host FaceModel`）。
下表里 `schema` 是**逐 endpoint 的 JSON Schema**（与 `contract.json` 内 `layerB_typert_remote` 一一对应，那里是 pretty 版）。

## B.1 概览

- **包数**：39
- **endpoint 数**：224
- **invocation 分布**：`direct`=224
- **服务（cordis service）数**：43
- **入参 schema**：56 个 endpoint 是单个 `request` 参数（其 schema 即完整入参对象），其余按参数逐个给 schema
- **参数级 schema 缺失**：1 个（`productAnalytics/report`.event → typert tool schema: unsupported never value）
- **返回 schema**：156/224 有精确 JSON Schema；68 个缺失（见下原因）
  - 31 个：void 结果（无返回体）
  - 26 个：字典/union 类型（生成器无法表达为 JSON Schema）
  - 3 个：typert tool schema: unsupported undefined value
  - 6 个：typert tool schema: selected union branches overlap or have no required discriminator
  - 2 个：typert tool schema: unsupported selected reference Uint8Array

## B.2 按包汇总

| 包 | endpoint 数 |
|---|---|
| `@deepseek-ai/dsh-action-cards` | 1 |
| `@deepseek-ai/dsh-agent-preset-registry` | 3 |
| `@deepseek-ai/dsh-agent-team` | 1 |
| `@deepseek-ai/dsh-api-job-controller` | 3 |
| `@deepseek-ai/dsh-api-remote-access` | 1 |
| `@deepseek-ai/dsh-api-session-controller` | 27 |
| `@deepseek-ai/dsh-api-settings-controller` | 8 |
| `@deepseek-ai/dsh-api-terminal-controller` | 9 |
| `@deepseek-ai/dsh-api-workspace-controller` | 14 |
| `@deepseek-ai/dsh-api-workspace-files` | 6 |
| `@deepseek-ai/dsh-client-file-upload` | 1 |
| `@deepseek-ai/dsh-client-product-analytics` | 3 |
| `@deepseek-ai/dsh-client-ui-plugin-manager` | 1 |
| `@deepseek-ai/dsh-client-ui-trajectory` | 1 |
| `@deepseek-ai/dsh-command-feedback` | 1 |
| `@deepseek-ai/dsh-commands` | 2 |
| `@deepseek-ai/dsh-cordis-host-runner` | 12 |
| `@deepseek-ai/dsh-cua` | 9 |
| `@deepseek-ai/dsh-deepseek-account` | 12 |
| `@deepseek-ai/dsh-deepseek-chat-import` | 1 |
| `@deepseek-ai/dsh-experimental-api-speech-to-text` | 6 |
| `@deepseek-ai/dsh-experimental-client-ui-cot-translation` | 2 |
| `@deepseek-ai/dsh-experimental-client-ui-forge` | 32 |
| `@deepseek-ai/dsh-experimental-liveshare` | 13 |
| `@deepseek-ai/dsh-goal` | 7 |
| `@deepseek-ai/dsh-host-plugin-inventory` | 1 |
| `@deepseek-ai/dsh-llm` | 3 |
| `@deepseek-ai/dsh-mcp-manager` | 3 |
| `@deepseek-ai/dsh-message-feedback` | 3 |
| `@deepseek-ai/dsh-office-kit` | 2 |
| `@deepseek-ai/dsh-permission-presets` | 1 |
| `@deepseek-ai/dsh-plugin-manager` | 15 |
| `@deepseek-ai/dsh-plugin-market` | 4 |
| `@deepseek-ai/dsh-plugin-recommendations` | 1 |
| `@deepseek-ai/dsh-schedule` | 9 |
| `@deepseek-ai/dsh-session-reference` | 1 |
| `@deepseek-ai/dsh-subagent` | 2 |
| `@deepseek-ai/dsh-user-questions` | 2 |
| `@deepseek-ai/dsh-web` | 1 |

## B.3 按服务（service）索引

| service | endpoints |
|---|---|
| `actionCards` | `act` |
| `agentPresets` | `list`, `read`, `select` |
| `agentTeams` | `setEnabled` |
| `commands` | `execute`, `list` |
| `cotTranslation` | `limits`, `translate` |
| `credentialsController` | `describe`, `set`, `unset` |
| `cuaAccess` | `applicationIcons`, `applications`, `enablePersistentPtc`, `openSettings`, `ptcConfiguration`, `requestPermission`, `retryApproval`, `revoke`, `systemStatus` |
| `deepseekAccount` | `cancelSignIn`, `getBalance`, `getNotificationContent`, `getNotifications`, `getProfile`, `getState`, `hasRunningAccountTasks`, `reportNotificationEvent`, `signOut`, `startSignIn`, `watch`, `watchExpiry` |
| `deepseekChatImport` | `limits` |
| `directoryPickerController` | `createDirectory`, `list`, `pick` |
| `dynamicCordisRunner` | `getClientCode`, `inventory`, `invoke`, `reportClientGuardFailure`, `reportRenderFailure`, `resolveInspectQuery`, `resolveRequestRun`, `runHostHalf`, `settleUserRun`, `stopFromPanel`, `syncInspectManifest`, `undefineFromPanel` |
| `fileUploads` | `upload` |
| `forgePanel` | `branches`, `cancelWorktree`, `changeRequestChecks`, `changeRequestCommits`, `changeRequestDiff`, `changeRequestReview`, `changeRequestReviewWrite`, `changeRequestStates`, `changeRequestText`, `changeRequestViewed`, `continueInProject`, `diffBases`, `dismiss`, `follow`, `localCommits`, `localDiff`, `localText`, `markReady`, `merge`, `refresh`, `requestReviews`, `requestWorktree`, `rerunChecks`, `restoreWorktree`, `retryWorktree`, `reviewerCandidates`, `setFileViewed`, `stopCreation`, `submitReview`, `track`, `updateBranch`, `worktreeCleanup` |
| `goals` | `clear`, `complete`, `create`, `edit`, `get`, `pause`, `resume` |
| `jobController` | `follow`, `kill`, `list` |
| `liveshareShares` | `addSessions`, `audit`, `capabilities`, `create`, `identity`, `list`, `relay`, `setCapabilities`, `setRelay`, `stop`, `testPublish`, `testRelay`, `updatePermissions` |
| `llm` | `discoverModels`, `listConfigurableProviders`, `listProviders` |
| `mcpManager` | `probe`, `restart`, `watch` |
| `messageFeedback` | `delete`, `list`, `put` |
| `officeKit` | `generation`, `render` |
| `permissionPresets` | `catalog` |
| `pluginInventory` | `list` |
| `pluginManager` | `cancelInstall`, `inspect`, `installBundle`, `listBundles`, `listPlugins`, `listVersionExemptions`, `listVersions`, `readBundleDetail`, `registries`, `removeBundle`, `setBundleEnabled`, `setPluginEnabled`, `setVersionExemption`, `updateBundle`, `waitForInstall` |
| `pluginMarket` | `listIndexes`, `readEntryDetail`, `search`, `setIndexes` |
| `pluginRecommendations` | `describe` |
| `pluginRegistryProbe` | `fastest` |
| `productAnalytics` | `enabled`, `report`, `watchPolicy` |
| `remoteAccess` | `follow` |
| `schedule` | `catalog`, `create`, `deleteInactive`, `deliveryLimits`, `edit`, `history`, `list`, `run`, `view` |
| `sessionController` | `attachment`, `canOpenWorkspacePath`, `cancel`, `control`, `create`, `events`, `follow`, `fork`, `initializeDefaultModel`, `list`, `modelCatalog`, `observeEvent`, `observeProjections`, `observeState`, `openWorkspacePath`, `page`, `projections`, `prompt`, `rename`, `search`, `selectModel`, `state`, `updateQueue`, `wait`, `workspacePathApplications` |
| `sessionFeedback` | `record` |
| `sessionFileReferences` | `list` |
| `sessionReferenceResolver` | `candidates` |
| `sessionSkillCatalog` | `list` |
| `sessionToolResults` | `watch` |
| `settingsController` | `describe`, `mutate`, `openSettingsDocument`, `replace`, `update` |
| `speechController` | `cancelPreparation`, `catalog`, `configure`, `follow`, `prepare`, `transcribe` |
| `subagents` | `interruptByUser`, `prompt` |
| `terminalController` | `attach`, `close`, `create`, `environment`, `list`, `rename`, `retain`, `shells`, `watch` |
| `userQuestions` | `answer`, `attachWait` |
| `web` | `listProviders` |
| `workspaceController` | `archiveSession`, `create`, `delete`, `follow`, `initializeDefault`, `insertBefore`, `insertSessionBefore`, `pinSession`, `rename`, `unarchiveSession`, `unpinSession` |
| `workspaceFiles` | `changes`, `list`, `read`, `readBytes`, `search`, `stat` |

## B.4 逐 endpoint 契约


### `@deepseek-ai/dsh-action-cards`

#### `@deepseek-ai/dsh-action-cards#actionCards/act`
- service: `actionCards` · invocation: `direct`
- **说明**：Apply a user action to a logged card. Shared checks run first, then the kind reconciles the card; `dismiss` is recorded here and every other verb goes to the card's kind. `dismiss` also works on an unstarted card whose kind is no longer registered. Concurrent actions on one card share one operation.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `callId` (wire `callId`, source `json`) schema=`{"type":"string"}`
  - `verb` (wire `verb`, source `json`) schema=`{"type":"string"}`
  - `payload` (wire `payload`, source `json`) schema=`{"type":"object","properties":{},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-action-cards/types#ActionCardResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"status":{"type":"string","const":"accepted"}},"required":["status"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"settled"},"decision":{"type":"object","properties":{"callId":{"type":"string"},"action":{"type":"string"},"phase":{"type":"string"},"data":{"type":"object","properties":{},"required":[],"additionalProperties":true,"description":"Kind-defined fields such as a chosen location or a created package."}},"required":["callId","action","phase"],"additionalProperties":true}},"required":["status","decision"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"refused"},"reason":{"type":"string"}},"required":["status","reason"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"unconfirmed"},"reason":{"type":"string"}},"required":["status","reason"],"additionalProperties":true}],"description":"acceptance of background work, the decision in effect, or a refusal."}`
- source: `packages/experimental/action-cards/src/index.ts:342:3`


### `@deepseek-ai/dsh-agent-preset-registry`

#### `@deepseek-ai/dsh-agent-preset-registry#agentPresets/list`
- service: `agentPresets` · invocation: `direct`
- **说明**：Read the selection roster.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-agent-preset-registry/types#AgentPresetRoster` (strict) schema=`{"type":"object","properties":{"presets":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Stable identifier; also the label's fallback."},"isDefault":{"type":"boolean","description":"Whether a session naming no preset composes this one."},"name":{"type":"string","description":"Display name the preset published."},"description":{"type":"string","description":"One sentence on what this preset is for."},"broken":{"type":"string","description":"Why this preset cannot compose a session; absent when it can."}},"required":["id","isDefault"],"additionalProperties":true},"description":"Every current declaration, including activation failures."}},"required":["presets"],"additionalProperties":true,"description":"Current presets, each marked when it is the default."}`
- source: `packages/preset/agent-preset-registry/src/index.ts:211:9`

#### `@deepseek-ai/dsh-agent-preset-registry#agentPresets/read`
- service: `agentPresets` · invocation: `direct`
- **说明**：Read one declaration's child plugin list as YAML, for viewing only.
- **参数**：
  - `agentPreset` (wire `agentPreset`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-agent-preset-registry/types#AgentPresetDocument` (strict) schema=`{"type":"object","properties":{"agentPreset":{"type":"string","description":"The preset the composition belongs to."},"content":{"type":"string","description":"The declared child plugin list as entry-list YAML, `!!js` expressions included."},"name":{"type":"string","description":"Display name the preset published."},"description":{"type":"string","description":"One sentence on what this preset is for."}},"required":["agentPreset","content"],"additionalProperties":true,"description":"The declared composition beside its published metadata."}`
- source: `packages/preset/agent-preset-registry/src/index.ts:234:3`

#### `@deepseek-ai/dsh-agent-preset-registry#agentPresets/select`
- service: `agentPresets` · invocation: `direct`
- **说明**：Select a preset before a session starts its first turn. A Session whose log records the preset and whose Agent runs its current revision keeps its composition; nothing is logged or announced.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `agentPreset` (wire `agentPreset`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-agent-preset-registry#agentPresets/select:result` (strict) schema=`{"type":"string","description":"Committed preset identity."}`
- source: `packages/preset/agent-preset-registry/src/index.ts:365:9`


### `@deepseek-ai/dsh-agent-team`

#### `@deepseek-ai/dsh-agent-team#agentTeams/setEnabled`
- service: `agentTeams` · invocation: `direct`
- **说明**：Save a root Session's Team selection without stopping children or deleting tasks. The selection takes effect before awaiting persistence. Tools resolve availability at step preparation; prompt providers read the selection when evaluated. Task mutations check the current mode when their queued operation starts; admitted operations finish.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `enabled` (wire `enabled`, source `json`) schema=`{"type":"boolean"}`
- **结果**：`@deepseek-ai/dsh-agent-team#agentTeams/setEnabled:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/team/agent-team/src/index.ts:112:9`


### `@deepseek-ai/dsh-api-job-controller`

#### `@deepseek-ai/dsh-api-job-controller#job/follow`
- service: `jobController` · invocation: `direct`
- **说明**：Stream one job's retained output from an absolute byte offset, then its terminal projection once settled and drained. Non-consuming: the model-facing cursor and notice state never observe these reads. The request's session is the fenced read's caller; the registry rejects a job the session cannot see and an unknown job.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Owning session for the fenced read. Omitted for an unowned job, which any caller may observe."},"jobId":{"type":"string"},"from":{"type":"number","description":"Absolute byte offset to resume from (a prior frame's `next`). Omitted, the stream starts at the oldest retained byte."}},"required":["jobId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-job-controller/types#JobFollowFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"opened"},"job":{"type":"object","properties":{"id":{"type":"string","description":"The registry-issued id (`<kind>-<short-uuid>`)."},"kind":{"type":"string","description":"The producer kind the job was registered with: a Host-registered `JobKind`, carried as an open string because a browser bundle or a Remote codec sees only the `JobKindMap` merges its own program compiles."},"label":{"type":"string","description":"The producer-supplied one-line label."},"owner":{"type":"string","description":"Owning session; absent for an unowned job, which every caller can see."},"outputLimitBytes":{"type":"number","description":"Producer-owned cap for complete model-facing notices and reads, in UTF-8 bytes."},"status":{"type":"string","enum":["running","stopping","completed","killed","failed"],"description":"Current lifecycle state."},"progress":{"type":"string","description":"The producer's live progress line (`3/10`, the current phase); cleared at settlement."},"detail":{"type":"string","description":"Terminal reason (`exit code: 3`); a recorded kill reason is merged in."},"startedAt":{"type":"number","description":"Epoch ms when the job was registered."},"finishedAt":{"type":"number","description":"Epoch ms when the job settled; absent while live."},"output":{"type":"object","properties":{"total":{"type":"number"},"earliest":{"type":"number"},"spillPaths":{"type":"array","items":{"type":"string"}}},"required":["total","earliest"],"additionalProperties":true,"description":"The output ring's absolute coordinates and the complete-stream files behind it. `total` is the offset the next chunk starts at (0 while nothing was written); `earliest` is the oldest retained byte, greater than zero exactly when retention dropped the head. `spillPaths` lists the spill files the job's pull sources currently keep, in source order and deduplicated, and is absent while no source keeps one: it outlives any chunk, so a reader below `earliest` can still name where the bytes went."}},"required":["id","kind","label","status","startedAt","output"],"additionalProperties":true},"from":{"type":"number","description":"Offset the first `output` frame continues from."}},"required":["type","job","from"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"output"},"chunks":{"type":"array","items":{"type":"object","properties":{"at":{"type":"number","description":"Absolute offset of the chunk's first byte; offsets never move once assigned."},"text":{"type":"string","description":"Chunk text exactly as appended (possibly tail-trimmed by retention)."},"channel":{"type":"string","enum":["stdout","stderr","log"],"description":"Stream label, when the producer supplied one."},"gapBefore":{"type":"boolean","const":true,"description":"Bytes immediately before this chunk were lost, at the producer or to retention."}},"required":["at","text"],"additionalProperties":true}},"next":{"type":"number","description":"Offset to resume from after this frame."},"lossy":{"type":"boolean","const":true,"description":"Bytes between the requested offset and `chunks` were already evicted."}},"required":["type","chunks","next"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"status"},"job":{"type":"object","properties":{"id":{"type":"string","description":"The registry-issued id (`<kind>-<short-uuid>`)."},"kind":{"type":"string","description":"The producer kind the job was registered with: a Host-registered `JobKind`, carried as an open string because a browser bundle or a Remote codec sees only the `JobKindMap` merges its own program compiles."},"label":{"type":"string","description":"The producer-supplied one-line label."},"owner":{"type":"string","description":"Owning session; absent for an unowned job, which every caller can see."},"outputLimitBytes":{"type":"number","description":"Producer-owned cap for complete model-facing notices and reads, in UTF-8 bytes."},"status":{"type":"string","enum":["running","stopping","completed","killed","failed"],"description":"Current lifecycle state."},"progress":{"type":"string","description":"The producer's live progress line (`3/10`, the current phase); cleared at settlement."},"detail":{"type":"string","description":"Terminal reason (`exit code: 3`); a recorded kill reason is merged in."},"startedAt":{"type":"number","description":"Epoch ms when the job was registered."},"finishedAt":{"type":"number","description":"Epoch ms when the job settled; absent while live."},"output":{"type":"object","properties":{"total":{"type":"number"},"earliest":{"type":"number"},"spillPaths":{"type":"array","items":{"type":"string"}}},"required":["total","earliest"],"additionalProperties":true,"description":"The output ring's absolute coordinates and the complete-stream files behind it. `total` is the offset the next chunk starts at (0 while nothing was written); `earliest` is the oldest retained byte, greater than zero exactly when retention dropped the head. `spillPaths` lists the spill files the job's pull sources currently keep, in source order and deduplicated, and is absent while no source keeps one: it outlives any chunk, so a reader below `earliest` can still name where the bytes went."}},"required":["id","kind","label","status","startedAt","output"],"additionalProperties":true}},"required":["type","job"],"additionalProperties":true}],"description":"anchor, coalesced output frames, and the terminal status."}`
- source: `packages/api/job-controller/src/index.ts:91:3`

#### `@deepseek-ai/dsh-api-job-controller#job/kill`
- service: `jobController` · invocation: `direct`
- **说明**：Kill one background job on a human's behalf. The request's session is the fenced read's caller, so the job must be one that session can see: the registry's owner fence is the only access rule, and a child session's own jobs are killable from its list like any other. The kill records `cancelled by the user` as its reason; it is not one the model requested, so the owning agent still receives the completion notice, and a shell tool waiting on that job reads the reason in its own result.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Session whose job list carries the job; the fenced lookup reads as it."},"jobId":{"type":"string"}},"required":["sessionId","jobId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-job-controller/types#JobKillValue` (strict) schema=`{"type":"object","properties":{"outcome":{"type":"string","enum":["requested","already-finished"]}},"required":["outcome"],"additionalProperties":true,"description":"the registry's admission of the kill request."}`
- source: `packages/api/job-controller/src/index.ts:110:3`

#### `@deepseek-ai/dsh-api-job-controller#job/list`
- service: `jobController` · invocation: `direct`
- **说明**：Stream the jobs one session can see — its own plus every unowned job — as whole-set frames: one on open, then one after each coalesced burst of lifecycle commits. The stream has no natural end; the carrier closes it.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-job-controller/types#JobListFrame` (strict) schema=`{"type":"object","properties":{"type":{"type":"string","const":"rows"},"jobs":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"The registry-issued id (`<kind>-<short-uuid>`)."},"kind":{"type":"string","description":"The producer kind the job was registered with: a Host-registered `JobKind`, carried as an open string because a browser bundle or a Remote codec sees only the `JobKindMap` merges its own program compiles."},"label":{"type":"string","description":"The producer-supplied one-line label."},"owner":{"type":"string","description":"Owning session; absent for an unowned job, which every caller can see."},"outputLimitBytes":{"type":"number","description":"Producer-owned cap for complete model-facing notices and reads, in UTF-8 bytes."},"status":{"type":"string","enum":["running","stopping","completed","killed","failed"],"description":"Current lifecycle state."},"progress":{"type":"string","description":"The producer's live progress line (`3/10`, the current phase); cleared at settlement."},"detail":{"type":"string","description":"Terminal reason (`exit code: 3`); a recorded kill reason is merged in."},"startedAt":{"type":"number","description":"Epoch ms when the job was registered."},"finishedAt":{"type":"number","description":"Epoch ms when the job settled; absent while live."},"output":{"type":"object","properties":{"total":{"type":"number"},"earliest":{"type":"number"},"spillPaths":{"type":"array","items":{"type":"string"}}},"required":["total","earliest"],"additionalProperties":true,"description":"The output ring's absolute coordinates and the complete-stream files behind it. `total` is the offset the next chunk starts at (0 while nothing was written); `earliest` is the oldest retained byte, greater than zero exactly when retention dropped the head. `spillPaths` lists the spill files the job's pull sources currently keep, in source order and deduplicated, and is absent while no source keeps one: it outlives any chunk, so a reader below `earliest` can still name where the bytes went."}},"required":["id","kind","label","status","startedAt","output"],"additionalProperties":true}}},"required":["type","jobs"],"additionalProperties":true,"description":"the roster frames."}`
- source: `packages/api/job-controller/src/index.ts:76:3`


### `@deepseek-ai/dsh-api-remote-access`

#### `@deepseek-ai/dsh-api-remote-access#remoteAccess/follow`
- service: `remoteAccess` · invocation: `direct`
- **说明**：Stream the calling Peer's access snapshot: one baseline, then `upsert` and `remove` frames after each `invalidate()` and each policy registration or removal that changes a grant. The owner receives only `{ owner: true }`. The generation ends when `signal` aborts or this service unloads, so a reloaded service starts every reader from a fresh baseline.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-remote-access/types#RemoteAccessFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"baseline"},"owner":{"type":"boolean","const":true}},"required":["type","owner"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"baseline"},"owner":{"type":"boolean","const":false},"grants":{"type":"array","items":{"type":"object","properties":{"resource":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"global"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"session"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"workspace"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true}]},"actions":{"type":"array","items":{"type":"string"},"description":"Endpoint actions allowed on this resource without call arguments, sorted; plain strings because Typert generates no codec for template literal types."}},"required":["resource","actions"],"additionalProperties":true}}},"required":["type","owner","grants"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"upsert"},"grant":{"type":"object","properties":{"resource":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"global"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"session"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"workspace"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true}]},"actions":{"type":"array","items":{"type":"string"},"description":"Endpoint actions allowed on this resource without call arguments, sorted; plain strings because Typert generates no codec for template literal types."}},"required":["resource","actions"],"additionalProperties":true}},"required":["type","grant"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"remove"},"resource":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"global"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"session"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"workspace"},"id":{"type":"string"}},"required":["kind","id"],"additionalProperties":true}]}},"required":["type","resource"],"additionalProperties":true}],"description":"the access frames of one generation."}`
- source: `packages/api/remote-access/src/index.ts:270:10`


### `@deepseek-ai/dsh-api-session-controller`

#### `@deepseek-ai/dsh-api-session-controller#fileReferences/list`
- service: `sessionFileReferences` · invocation: `direct`
- **说明**：List file and directory candidates for one Agent's working directory.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `query` (wire `query`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-session-controller#fileReferences/list:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"path":{"type":"string","description":"User-facing path accepted by normal prompts and filesystem tools."},"kind":{"type":"string","enum":["file","directory"],"description":"Directories keep completion open; files finish the mention."}},"required":["path","kind"],"additionalProperties":true},"description":"deterministic path-only candidates from the composed provider."}`
- source: `packages/api/session-controller/src/file-references.ts:33:3`

#### `@deepseek-ai/dsh-api-session-controller#session/attachment`
- service: `sessionController` · invocation: `direct`
- **说明**：Read one image from the attachment store after gateway authorization.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Gateway permission scope only; neither Session existence nor its image references are checked."},"attachment":{"type":"object","properties":{"attachmentId":{"type":"string","description":"Opaque storage identifier; never a filesystem path or bearer URL."},"mediaType":{"type":"string","enum":["image/png","image/jpeg","image/webp","image/gif"],"description":"Media type verified from the stored bytes."},"bytes":{"type":"number","description":"Exact encoded byte length."},"width":{"type":"number","description":"Intrinsic encoded width in pixels."},"height":{"type":"number","description":"Intrinsic encoded height in pixels."},"name":{"type":"string","description":"Optional display name stripped of local path information."},"originalDimensions":{"type":"object","properties":{"width":{"type":"number"},"height":{"type":"number"}},"required":["width","height"],"additionalProperties":true,"description":"Input dimensions after applying EXIF orientation and before normalization scaling. Present only when normalization reduced the image."}},"required":["attachmentId","mediaType","bytes","width","height"],"additionalProperties":true}},"required":["sessionId","attachment"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionAttachmentValue` (strict) schema=`{"type":"object","properties":{"attachment":{"type":"object","properties":{"attachmentId":{"type":"string","description":"Opaque storage identifier; never a filesystem path or bearer URL."},"mediaType":{"type":"string","enum":["image/png","image/jpeg","image/webp","image/gif"],"description":"Media type verified from the stored bytes."},"bytes":{"type":"number","description":"Exact encoded byte length."},"width":{"type":"number","description":"Intrinsic encoded width in pixels."},"height":{"type":"number","description":"Intrinsic encoded height in pixels."},"name":{"type":"string","description":"Optional display name stripped of local path information."},"originalDimensions":{"type":"object","properties":{"width":{"type":"number"},"height":{"type":"number"}},"required":["width","height"],"additionalProperties":true,"description":"Input dimensions after applying EXIF orientation and before normalization scaling. Present only when normalization reduced the image."}},"required":["attachmentId","mediaType","bytes","width","height"],"additionalProperties":true,"description":"Supplied reference after ID, format, byte length, and dimensions verification; display fields are preserved."},"data":{"type":"string"}},"required":["attachment","data"],"additionalProperties":true,"description":"the durable attachment reference and base64-encoded bytes."}`
- source: `packages/api/session-controller/src/index.ts:500:3`

#### `@deepseek-ai/dsh-api-session-controller#session/canOpenWorkspacePath`
- service: `sessionController` · invocation: `direct`
- **说明**：Report whether this deployment can hand a Session workspace path to a native desktop.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-session-controller#session/canOpenWorkspacePath:result` (strict) schema=`{"type":"boolean","description":"true when the matching open operation is available."}`
- source: `packages/api/session-controller/src/index.ts:353:3`

#### `@deepseek-ai/dsh-api-session-controller#session/cancel`
- service: `sessionController` · invocation: `direct`
- **说明**：Cancel one active Agent turn without dropping its pending inbox.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionCancelValue` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","const":true}},"required":["accepted"],"additionalProperties":true,"description":"acknowledgement that cancellation was requested."}`
- source: `packages/api/session-controller/src/index.ts:520:3`

#### `@deepseek-ai/dsh-api-session-controller#session/control`
- service: `sessionController` · invocation: `direct`
- **说明**：Stream a complete live-control baseline followed by replacement frames.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionControlFrame` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/session-controller/src/index.ts:631:10`

#### `@deepseek-ai/dsh-api-session-controller#session/create`
- service: `sessionController` · invocation: `direct`
- **说明**：Create one ordinary Session for a new conversation, reusing the named blank Session while it is reusable.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"workspaceId":{"type":"string","description":"Workspace the Session joins; exclusive with `cwd`."},"cwd":{"type":"string","description":"Directory the Session owns when no Workspace is named."},"sessionId":{"type":"string","description":"Blank Session to reuse while it is reusable, or the identity of a new Session when none is stored under it."},"agentPreset":{"type":"string","description":"Preset the Session runs, replacing a reused Session's recorded preset; the configured default when omitted."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionCreateValue` (strict) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"The created or reused Session, which may differ from the requested `sessionId`."},"agentPreset":{"type":"string","description":"Preset the Session runs, when the deployment composes a preset roster."}},"required":["sessionId"],"additionalProperties":true,"description":"the created or reused Session identity and its preset when configured."}`
- source: `packages/api/session-controller/src/index.ts:307:3`

#### `@deepseek-ai/dsh-api-session-controller#session/events`
- service: `sessionController` · invocation: `direct`
- **说明**：Read one cold-safe, message-aligned Session history page.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"address":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session"},"sessionId":{"type":"string"}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"subagent"},"parentSessionId":{"type":"string"},"childSessionId":{"type":"string"},"mode":{"type":"string","enum":["one-shot","continuable","unknown"]}},"required":["kind","parentSessionId","childSessionId","mode"],"additionalProperties":true}]},"throughSeq":{"type":"number","description":"Inclusive log cut; omission selects the observed log end. A follow opening reports the cut it covered so a caller can pin the same point."},"beforeSeq":{"type":"number"},"maxMessages":{"type":"number"},"turnWindow":{"type":"object","properties":{"minMessages":{"type":"number","description":"Minimum append-origin user/assistant messages; must not exceed maxMessages."},"minTurns":{"type":"number","description":"Minimum Turn starts crossed, including the partial Turn at beforeSeq."}},"required":["minMessages","minTurns"],"additionalProperties":true,"description":"Stop at a Turn start after both minima, unless maxMessages or history exhaustion wins."}},"required":["address"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionEventsPage` (strict) schema=`{"type":"object","properties":{"cursor":{"type":"number"},"records":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string","const":"event"},"event":{"type":"object","properties":{"type":{"type":"string"},"seq":{"type":"number"},"time":{"type":"number"},"data":{},"ignorable":{"type":"boolean","const":true},"sourceEventSeqs":{"description":"Earlier sources on current surface events; opaque JSON on unknown ignorable events."},"surfaceOp":{"description":"Canonical placement on current surface events; opaque JSON on unknown ignorable events."}},"required":["type","seq","time","data"],"additionalProperties":true}},"required":["type","event"],"additionalProperties":true}},"hasMore":{"type":"boolean"}},"required":["cursor","records","hasMore"],"additionalProperties":true,"description":"one chronological page with its inclusive cursor."}`
- source: `packages/api/session-controller/src/index.ts:543:3`

#### `@deepseek-ai/dsh-api-session-controller#session/follow`
- service: `sessionController` · invocation: `direct`
- **说明**：Follow one Session log from its opening or resume cursor.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"address":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session"},"sessionId":{"type":"string"}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"subagent"},"parentSessionId":{"type":"string"},"childSessionId":{"type":"string"},"mode":{"type":"string","enum":["one-shot","continuable","unknown"]}},"required":["kind","parentSessionId","childSessionId","mode"],"additionalProperties":true}]},"activate":{"type":"boolean","description":"Request background activation; omission leaves the read passive."},"assistantStream":{"type":"boolean","const":true,"description":"Include process-local assistant presentation frames for the Web client."},"maxMessages":{"type":"number"},"turnWindow":{"type":"object","properties":{"minMessages":{"type":"number","description":"Minimum append-origin user/assistant messages; must not exceed maxMessages."},"minTurns":{"type":"number","description":"Minimum Turn starts crossed, including the partial Turn at beforeSeq."}},"required":["minMessages","minTurns"],"additionalProperties":true,"description":"Stop at a Turn start after both minima, unless maxMessages or history exhaustion wins."}},"required":["address"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionFollowFrame` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/session-controller/src/index.ts:610:3`

#### `@deepseek-ai/dsh-api-session-controller#session/fork`
- service: `sessionController` · invocation: `direct`
- **说明**：Fork one cold-readable exact event prefix into a new Session. An omitted boundary selects the latest completed-turn prefix; an open cut receives synthetic fork closers.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"atSeq":{"type":"number","description":"Exact inclusive source event seq; omission selects the latest completed-turn prefix."},"allowMigration":{"type":"boolean","description":"False asks the Host to check for required migration before forking. Defaults to true."}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionForkValue` (strict) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true,"description":"the new Session identity."}`
- source: `packages/api/session-controller/src/index.ts:449:9`

#### `@deepseek-ai/dsh-api-session-controller#session/initializeDefaultModel`
- service: `sessionController` · invocation: `direct`
- **说明**：Select the first available account model after login when no provider API key is configured.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-session-controller#session/initializeDefaultModel:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/api/session-controller/src/index.ts:326:9`

#### `@deepseek-ai/dsh-api-session-controller#session/list`
- service: `sessionController` · invocation: `direct`
- **说明**：Read all visible Session rows without resuming an Agent.
- **参数**：
  - `_request` (wire `_request`, source `json`) schema=`{"type":"object","properties":{"cursor":{"type":"string"}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionListValue` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/session-controller/src/index.ts:282:9`

#### `@deepseek-ai/dsh-api-session-controller#session/modelCatalog`
- service: `sessionController` · invocation: `direct`
- **说明**：Describe every currently routable model for Host-generation selectors.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#ModelCatalog` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/session-controller/src/index.ts:344:3`

#### `@deepseek-ai/dsh-api-session-controller#session/observeEvent`
- service: `sessionController` · invocation: `direct`
- **说明**：Subscribe to Session events without reading a snapshot.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"address":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session"},"sessionId":{"type":"string"}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"subagent"},"parentSessionId":{"type":"string"},"childSessionId":{"type":"string"},"mode":{"type":"string","enum":["one-shot","continuable","unknown"]}},"required":["kind","parentSessionId","childSessionId","mode"],"additionalProperties":true}]}},"required":["address"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionEventFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"event"},"event":{"type":"object","properties":{"type":{"type":"string"},"seq":{"type":"number"},"time":{"type":"number"},"data":{},"ignorable":{"type":"boolean","const":true},"sourceEventSeqs":{"description":"Earlier sources on current surface events; opaque JSON on unknown ignorable events."},"surfaceOp":{"description":"Canonical placement on current surface events; opaque JSON on unknown ignorable events."}},"required":["type","seq","time","data"],"additionalProperties":true}},"required":["type","event"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"ready"}},"required":["type"],"additionalProperties":true}],"description":"readiness and subsequent events, without a snapshot."}`
- source: `packages/api/session-controller/src/index.ts:554:3`

#### `@deepseek-ai/dsh-api-session-controller#session/observeProjections`
- service: `sessionController` · invocation: `direct`
- **说明**：Subscribe to Session projection changes.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionProjectionFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"ready"}},"required":["type"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"projection"},"seq":{"type":"number","description":"Seq of the committed event that caused every listed change."},"changes":{"type":"array","items":{"type":"object","properties":{"key":{"type":"string"},"val":{}},"required":["key","val"],"additionalProperties":true},"description":"One entry per client-visible key whose view the event changed, in registration order without duplicate keys, with the key's new value as `val`. A key absent from `changes` is unchanged; unlike a baseline, absence does not mean an absent capability."}},"required":["type","seq","changes"],"additionalProperties":true}],"description":"readiness followed by one projection change frame per committed event."}`
- source: `packages/api/session-controller/src/index.ts:565:3`

#### `@deepseek-ai/dsh-api-session-controller#session/observeState`
- service: `sessionController` · invocation: `direct`
- **说明**：Subscribe to complete Session state replacements.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionState` (strict) schema=`{"type":"object","properties":{"cursor":{"type":"number"},"active":{"type":"boolean"},"running":{"type":"boolean"},"queue":{"oneOf":[{"type":"null","const":null},{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"placement":{"type":"string","enum":["queued","steering","context"]},"rpcId":{"type":"string"},"content":{"type":"array","items":{}}},"required":["id","placement","content"],"additionalProperties":true}}]},"pendingInput":{"type":"array","items":{"type":"string","enum":["approval","question","other"]},"description":"Pending Remote requests sampled when this state was read. A pending change alone does not trigger `observeState`; `wait` refreshes on its own interval."}},"required":["cursor","active","running","queue","pendingInput"],"additionalProperties":true,"description":"complete passive state replacements."}`
- source: `packages/api/session-controller/src/index.ts:587:3`

#### `@deepseek-ai/dsh-api-session-controller#session/openWorkspacePath`
- service: `sessionController` · invocation: `direct`
- **说明**：Verify one path through the composed filesystem and open it on the Host desktop.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"action":{"type":"string","const":"reveal","description":"File-manager navigation when requested; omission uses the default application."},"application":{"type":"string","description":"Registered application identifier; ignored for reveal. Omission preserves the operating system default."},"path":{"type":"string","description":"Path after best-effort Session workspace resolution, in Host filesystem syntax."}},"required":["path"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionOpenWorkspacePathValue` (strict) schema=`{"type":"object","properties":{"opened":{"type":"boolean","const":true}},"required":["opened"],"additionalProperties":true,"description":"confirmation after the native opener accepts the path."}`
- source: `packages/api/session-controller/src/index.ts:374:9`

#### `@deepseek-ai/dsh-api-session-controller#session/page`
- service: `sessionController` · invocation: `direct`
- **说明**：Read one cold-safe, message-aligned Session history page.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"address":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session"},"sessionId":{"type":"string"}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"subagent"},"parentSessionId":{"type":"string"},"childSessionId":{"type":"string"},"mode":{"type":"string","enum":["one-shot","continuable","unknown"]}},"required":["kind","parentSessionId","childSessionId","mode"],"additionalProperties":true}]},"throughSeq":{"type":"number","description":"Inclusive log cut; omission selects the observed log end. A follow opening reports the cut it covered so a caller can pin the same point."},"beforeSeq":{"type":"number"},"maxMessages":{"type":"number"},"turnWindow":{"type":"object","properties":{"minMessages":{"type":"number","description":"Minimum append-origin user/assistant messages; must not exceed maxMessages."},"minTurns":{"type":"number","description":"Minimum Turn starts crossed, including the partial Turn at beforeSeq."}},"required":["minMessages","minTurns"],"additionalProperties":true,"description":"Stop at a Turn start after both minima, unless maxMessages or history exhaustion wins."}},"required":["address"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionEventsPage` (strict) schema=`{"type":"object","properties":{"cursor":{"type":"number"},"records":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string","const":"event"},"event":{"type":"object","properties":{"type":{"type":"string"},"seq":{"type":"number"},"time":{"type":"number"},"data":{},"ignorable":{"type":"boolean","const":true},"sourceEventSeqs":{"description":"Earlier sources on current surface events; opaque JSON on unknown ignorable events."},"surfaceOp":{"description":"Canonical placement on current surface events; opaque JSON on unknown ignorable events."}},"required":["type","seq","time","data"],"additionalProperties":true}},"required":["type","event"],"additionalProperties":true}},"hasMore":{"type":"boolean"}},"required":["cursor","records","hasMore"],"additionalProperties":true,"description":"one chronological page with its inclusive cursor; an omitted `throughSeq` selects the observed log end."}`
- source: `packages/api/session-controller/src/index.ts:532:3`

#### `@deepseek-ai/dsh-api-session-controller#session/projections`
- service: `sessionController` · invocation: `direct`
- **说明**：Read exact projections, returning cached hints only when migration is required.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionProjectionsValue` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/session-controller/src/index.ts:621:3`

#### `@deepseek-ai/dsh-api-session-controller#session/prompt`
- service: `sessionController` · invocation: `direct`
- **说明**：Admit one prompt after explicitly resuming its Session.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"requestId":{"type":"string","description":"Client-minted identity persisted on the accepted inbox input, including empty continuation."},"sessionId":{"type":"string"},"mode":{"type":"string","enum":["queue","steer"]},"content":{"type":"array","items":{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"text"},"text":{"type":"string"}},"required":["type","text"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"image"},"mediaType":{"type":"string","enum":["image/png","image/jpeg","image/webp","image/gif"]},"data":{"type":"string"},"name":{"type":"string"}},"required":["type","mediaType","data"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"file"},"receiptId":{"type":"string"}},"required":["type","receiptId"],"additionalProperties":true}]},"description":"Non-whitespace text or attachments; an empty array continues an eligible failed idle Session."},"clientTimeZone":{"type":"string"}},"required":["requestId","sessionId","mode","content"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionPromptValue` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","const":true}},"required":["accepted"],"additionalProperties":true,"description":"acknowledgement that the Agent accepted the prompt."}`
- source: `packages/api/session-controller/src/index.ts:468:9`

#### `@deepseek-ai/dsh-api-session-controller#session/rename`
- service: `sessionController` · invocation: `direct`
- **说明**：Rename one Session after explicitly resuming it.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"title":{"type":"string"}},"required":["sessionId","title"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionRenameValue` (strict) schema=`{"type":"object","properties":{"title":{"type":"string"},"seq":{"type":"number"}},"required":["title","seq"],"additionalProperties":true,"description":"the accepted title and durable event sequence."}`
- source: `packages/api/session-controller/src/index.ts:437:3`

#### `@deepseek-ai/dsh-api-session-controller#session/search`
- service: `sessionController` · invocation: `direct`
- **说明**：Search visible Session content without resuming an Agent. A non-owner receives only the hits whose Session `allows()` admits; `hasMore` describes the bounded result before that filtering.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"query":{"type":"string"}},"required":["query"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionSearchValue` (strict) schema=`{"type":"object","properties":{"items":{"type":"array","items":{"type":"object","properties":{"sessionId":{"type":"string"},"snippet":{"type":"string"}},"required":["sessionId","snippet"],"additionalProperties":true}},"hasMore":{"type":"boolean"}},"required":["items","hasMore"],"additionalProperties":true,"description":"authorized bounded Session search results."}`
- source: `packages/api/session-controller/src/index.ts:296:9`

#### `@deepseek-ai/dsh-api-session-controller#session/selectModel`
- service: `sessionController` · invocation: `direct`
- **说明**：Select one Session-local model after explicitly resuming the Session; save the default in the background.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"provider":{"type":"string"},"model":{"type":"string"},"reasoningEffort":{"type":"string"}},"required":["sessionId","provider","model"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionSelectModelValue` (strict) schema=`{"type":"object","properties":{"selected":{"type":"object","properties":{"provider":{"type":"string"},"model":{"type":"string"},"reasoningEffort":{"type":"string"}},"required":["provider","model"],"additionalProperties":true}},"required":["selected"],"additionalProperties":true,"description":"the normalized selection installed for the Session, without waiting for default persistence."}`
- source: `packages/api/session-controller/src/index.ts:317:3`

#### `@deepseek-ai/dsh-api-session-controller#session/state`
- service: `sessionController` · invocation: `direct`
- **说明**：Read passive Session state.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionState` (strict) schema=`{"type":"object","properties":{"cursor":{"type":"number"},"active":{"type":"boolean"},"running":{"type":"boolean"},"queue":{"oneOf":[{"type":"null","const":null},{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"placement":{"type":"string","enum":["queued","steering","context"]},"rpcId":{"type":"string"},"content":{"type":"array","items":{}}},"required":["id","placement","content"],"additionalProperties":true}}]},"pendingInput":{"type":"array","items":{"type":"string","enum":["approval","question","other"]},"description":"Pending Remote requests sampled when this state was read. A pending change alone does not trigger `observeState`; `wait` refreshes on its own interval."}},"required":["cursor","active","running","queue","pendingInput"],"additionalProperties":true,"description":"current passive state."}`
- source: `packages/api/session-controller/src/index.ts:576:3`

#### `@deepseek-ai/dsh-api-session-controller#session/updateQueue`
- service: `sessionController` · invocation: `direct`
- **说明**：Mutate one still-pending queue occurrence, resuming a cold Agent first.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"itemId":{"type":"string"},"action":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"edit"},"content":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string","const":"text"},"text":{"type":"string"}},"required":["type","text"],"additionalProperties":true},"description":"Non-empty text-only replacement content."}},"required":["kind","content"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"remove"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"steer"}},"required":["kind"],"additionalProperties":true}]}},"required":["sessionId","itemId","action"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionUpdateQueueValue` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","const":true}},"required":["accepted"],"additionalProperties":true,"description":"acknowledgement that the queue mutation was applied."}`
- source: `packages/api/session-controller/src/index.ts:510:3`

#### `@deepseek-ai/dsh-api-session-controller#session/wait`
- service: `sessionController` · invocation: `direct`
- **说明**：Wait for Session quiescence or pending input with bounded assistant output.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"timeoutMs":{"type":"number"},"afterSeq":{"type":"number","description":"Exclusive output cursor; omission includes all available assistant records."},"maxMessages":{"type":"number","description":"Positive assistant-record limit; omission uses the history message budget."},"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SessionWaitValue` (strict) schema=`{"type":"object","properties":{"reason":{"type":"string","enum":["idle","input-required","timeout"]},"state":{"type":"object","properties":{"cursor":{"type":"number"},"active":{"type":"boolean"},"running":{"type":"boolean"},"queue":{"oneOf":[{"type":"null","const":null},{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"placement":{"type":"string","enum":["queued","steering","context"]},"rpcId":{"type":"string"},"content":{"type":"array","items":{}}},"required":["id","placement","content"],"additionalProperties":true}}]},"pendingInput":{"type":"array","items":{"type":"string","enum":["approval","question","other"]},"description":"Pending Remote requests sampled when this state was read. A pending change alone does not trigger `observeState`; `wait` refreshes on its own interval."}},"required":["cursor","active","running","queue","pendingInput"],"additionalProperties":true},"output":{"type":"object","properties":{"records":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string","const":"event"},"event":{"type":"object","properties":{"type":{"type":"string"},"seq":{"type":"number"},"time":{"type":"number"},"data":{},"ignorable":{"type":"boolean","const":true},"sourceEventSeqs":{"description":"Earlier sources on current surface events; opaque JSON on unknown ignorable events."},"surfaceOp":{"description":"Canonical placement on current surface events; opaque JSON on unknown ignorable events."}},"required":["type","seq","time","data"],"additionalProperties":true}},"required":["type","event"],"additionalProperties":true}},"truncated":{"type":"boolean","description":"More eligible assistant messages exist in the selected interval."}},"required":["records","truncated"],"additionalProperties":true}},"required":["reason","state","output"],"additionalProperties":true,"description":"stopping state and bounded assistant output."}`
- source: `packages/api/session-controller/src/index.ts:598:3`

#### `@deepseek-ai/dsh-api-session-controller#session/workspacePathApplications`
- service: `sessionController` · invocation: `direct`
- **说明**：Query current file handlers on the serving desktop without activating an Agent.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller#session/workspacePathApplications:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"OS application identifier; callers must revalidate it against the file's current handlers before opening."},"name":{"type":"string"},"default":{"type":"boolean"},"icon":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"PNG or SVG data URL, or null when the desktop supplies no icon."}},"required":["id","name","default","icon"],"additionalProperties":true},"description":"OS application names, icons, and default selection; empty when desktop opening is unavailable."}`
- source: `packages/api/session-controller/src/index.ts:404:9`

#### `@deepseek-ai/dsh-api-session-controller#skills/list`
- service: `sessionSkillCatalog` · invocation: `direct`
- **说明**：List the user-invocable skills visible to one Session composition.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-session-controller/types#SkillListValue` (strict) schema=`{"type":"object","properties":{"skills":{"type":"array","items":{"type":"object","properties":{"path":{"type":"string","description":"Absolute SKILL.md path when supplied by a filesystem provider."},"name":{"type":"string","description":"Kebab-case identifier referenced as `/name`."},"description":{"type":"string","description":"Short routing description."},"whenToUse":{"type":"string","description":"Optional extra routing guidance."},"modelInvocable":{"type":"boolean","description":"Whether the same skill is also advertised to the model."}},"required":["name","description","modelInvocable"],"additionalProperties":true}}},"required":["skills"],"additionalProperties":true,"description":"user-invocable skill metadata without loading skill bodies."}`
- source: `packages/api/session-controller/src/skill-catalog.ts:36:9`


### `@deepseek-ai/dsh-api-settings-controller`

#### `@deepseek-ai/dsh-api-settings-controller#credentials/describe`
- service: `credentialsController` · invocation: `direct`
- **说明**：Describe several references for one configuration surface. Batched because a settings page describes every reference its rows name at once, and one round trip keeps those rows from settling separately.
- **参数**：
  - `refs` (wire `refs`, source `json`) schema=`{"type":"array","items":{"type":"string"}}`
- **结果**：`@deepseek-ai/dsh-api-settings-controller#credentials/describe:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/api/settings-controller/src/credentials.ts:84:9`

#### `@deepseek-ai/dsh-api-settings-controller#credentials/set`
- service: `credentialsController` · invocation: `direct`
- **说明**：Store one value from a configuration surface. The value crosses the wire in this direction only: no read path returns it.
- **参数**：
  - `ref` (wire `ref`, source `json`) schema=`{"type":"string"}`
  - `value` (wire `value`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-settings-controller#credentials/set:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/api/settings-controller/src/credentials.ts:101:9`

#### `@deepseek-ai/dsh-api-settings-controller#credentials/unset`
- service: `credentialsController` · invocation: `direct`
- **说明**：Remove one reference from a configuration surface.
- **参数**：
  - `ref` (wire `ref`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-settings-controller#credentials/unset:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/api/settings-controller/src/credentials.ts:114:9`

#### `@deepseek-ai/dsh-api-settings-controller#settings/describe`
- service: `settingsController` · invocation: `direct`
- **说明**：Describe every registered namespace for a configuration page: redacted layered values plus the serialized schema the page renders its form from.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-settings/types#SettingsDescribeValue` (strict) schema=`{"type":"object","properties":{"writable":{"type":"boolean","description":"Whether the profile accepts writes; `false` disables every write control."},"hasDocument":{"type":"boolean","description":"Whether the configuration editor owns a local document, without exposing its Host path."},"namespaces":{"type":"array","items":{"type":"object","properties":{"autoGenerate":{"type":"boolean","description":"Generate a page if no custom page is registered for this instance."},"ns":{"type":"string","description":"Namespace key (`llm-deepseek`, `llm-pi-ai`, …)."},"schema":{"description":"Serialized schemastery schema envelope (`schema.toJSON()`); rehydrate with `new Schema(json)`."},"value":{"description":"Redacted resolved value (schema defaults → composition base → user layer)."},"base":{"description":"Redacted composition base layer, with defaults resolved."},"user":{"description":"Redacted raw user section, when one exists; a field's presence here marks it user-overridden."},"applies":{"type":"string","const":"live","description":"When the owner applies changes."},"secrets":{"type":"array","items":{"type":"object","properties":{"path":{"type":"array","items":{"type":"string"},"description":"Path from the section root to the removed field."},"set":{"type":"boolean","description":"Whether the slot currently holds a value; the value itself never rides."}},"required":["path","set"],"additionalProperties":true},"description":"Every schema-declared secret slot with its configured state."},"revision":{"type":"number","description":"Monotonic revision of the raw entry configuration this view was read at. Send it back as `expectedRevision` on a write so a stale editor is refused rather than silently overwriting a concurrent change."}},"required":["autoGenerate","ns","schema","value","applies","secrets","revision"],"additionalProperties":true},"description":"One view per profile plugin entry."}},"required":["writable","hasDocument","namespaces"],"additionalProperties":true,"description":"provider writability, local-document presence, and one view per namespace."}`
- source: `packages/api/settings-controller/src/index.ts:98:3`

#### `@deepseek-ai/dsh-api-settings-controller#settings/mutate`
- service: `settingsController` · invocation: `direct`
- **说明**：Apply path-addressed edits to one namespace's user section, resolved against the section as stored rather than against whatever the caller last read, then answer with that namespace's new redacted view.
- **参数**：
  - `ns` (wire `ns`, source `json`) schema=`{"type":"string"}`
  - `ops` (wire `ops`, source `json`) schema=`{"type":"array","items":{"oneOf":[{"type":"object","properties":{"op":{"type":"string","const":"set"},"path":{"type":"array","items":{"type":"string"}},"value":{}},"required":["op","path","value"],"additionalProperties":true},{"type":"object","properties":{"op":{"type":"string","const":"unset"},"path":{"type":"array","items":{"type":"string"}}},"required":["op","path"],"additionalProperties":true}]}}`
  - `expectedRevision` (wire `expectedRevision`, source `json`) schema=`{"type":"number"}`
- **结果**：`@deepseek-ai/dsh-settings/types#SettingsNamespaceView` (strict) schema=`{"type":"object","properties":{"autoGenerate":{"type":"boolean","description":"Generate a page if no custom page is registered for this instance."},"ns":{"type":"string","description":"Namespace key (`llm-deepseek`, `llm-pi-ai`, …)."},"schema":{"description":"Serialized schemastery schema envelope (`schema.toJSON()`); rehydrate with `new Schema(json)`."},"value":{"description":"Redacted resolved value (schema defaults → composition base → user layer)."},"base":{"description":"Redacted composition base layer, with defaults resolved."},"user":{"description":"Redacted raw user section, when one exists; a field's presence here marks it user-overridden."},"applies":{"type":"string","const":"live","description":"When the owner applies changes."},"secrets":{"type":"array","items":{"type":"object","properties":{"path":{"type":"array","items":{"type":"string"},"description":"Path from the section root to the removed field."},"set":{"type":"boolean","description":"Whether the slot currently holds a value; the value itself never rides."}},"required":["path","set"],"additionalProperties":true},"description":"Every schema-declared secret slot with its configured state."},"revision":{"type":"number","description":"Monotonic revision of the raw entry configuration this view was read at. Send it back as `expectedRevision` on a write so a stale editor is refused rather than silently overwriting a concurrent change."}},"required":["autoGenerate","ns","schema","value","applies","secrets","revision"],"additionalProperties":true,"description":"the namespace's redacted view after the write."}`
- source: `packages/api/settings-controller/src/index.ts:152:9`

#### `@deepseek-ai/dsh-api-settings-controller#settings/openSettingsDocument`
- service: `settingsController` · invocation: `direct`
- **说明**：Materialize the provider-owned settings document and open it in a native text editor.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-settings-controller/types#SettingsDocumentOpenValue` (strict) schema=`{"type":"object","properties":{"opened":{"type":"boolean","const":true}},"required":["opened"],"additionalProperties":true,"description":"confirmation after the native opener accepts the document."}`
- source: `packages/api/settings-controller/src/index.ts:167:9`

#### `@deepseek-ai/dsh-api-settings-controller#settings/replace`
- service: `settingsController` · invocation: `direct`
- **说明**：Replace one namespace's stored user section wholesale.
- **参数**：
  - `ns` (wire `ns`, source `json`) schema=`{"type":"string"}`
  - `section` (wire `section`, source `json`) schema=`{"type":"object","properties":{},"required":[],"additionalProperties":true}`
  - `expectedRevision` (wire `expectedRevision`, source `json`) schema=`{"type":"number"}`
- **结果**：`@deepseek-ai/dsh-settings/types#SettingsNamespaceView` (strict) schema=`{"type":"object","properties":{"autoGenerate":{"type":"boolean","description":"Generate a page if no custom page is registered for this instance."},"ns":{"type":"string","description":"Namespace key (`llm-deepseek`, `llm-pi-ai`, …)."},"schema":{"description":"Serialized schemastery schema envelope (`schema.toJSON()`); rehydrate with `new Schema(json)`."},"value":{"description":"Redacted resolved value (schema defaults → composition base → user layer)."},"base":{"description":"Redacted composition base layer, with defaults resolved."},"user":{"description":"Redacted raw user section, when one exists; a field's presence here marks it user-overridden."},"applies":{"type":"string","const":"live","description":"When the owner applies changes."},"secrets":{"type":"array","items":{"type":"object","properties":{"path":{"type":"array","items":{"type":"string"},"description":"Path from the section root to the removed field."},"set":{"type":"boolean","description":"Whether the slot currently holds a value; the value itself never rides."}},"required":["path","set"],"additionalProperties":true},"description":"Every schema-declared secret slot with its configured state."},"revision":{"type":"number","description":"Monotonic revision of the raw entry configuration this view was read at. Send it back as `expectedRevision` on a write so a stale editor is refused rather than silently overwriting a concurrent change."}},"required":["autoGenerate","ns","schema","value","applies","secrets","revision"],"additionalProperties":true,"description":"the namespace's redacted view after the write."}`
- source: `packages/api/settings-controller/src/index.ts:133:3`

#### `@deepseek-ai/dsh-api-settings-controller#settings/update`
- service: `settingsController` · invocation: `direct`
- **说明**：Merge a patch into one namespace's stored user section.
- **参数**：
  - `ns` (wire `ns`, source `json`) schema=`{"type":"string"}`
  - `patch` (wire `patch`, source `json`) schema=`{"type":"object","properties":{},"required":[],"additionalProperties":true}`
  - `expectedRevision` (wire `expectedRevision`, source `json`) schema=`{"type":"number"}`
- **结果**：`@deepseek-ai/dsh-settings/types#SettingsNamespaceView` (strict) schema=`{"type":"object","properties":{"autoGenerate":{"type":"boolean","description":"Generate a page if no custom page is registered for this instance."},"ns":{"type":"string","description":"Namespace key (`llm-deepseek`, `llm-pi-ai`, …)."},"schema":{"description":"Serialized schemastery schema envelope (`schema.toJSON()`); rehydrate with `new Schema(json)`."},"value":{"description":"Redacted resolved value (schema defaults → composition base → user layer)."},"base":{"description":"Redacted composition base layer, with defaults resolved."},"user":{"description":"Redacted raw user section, when one exists; a field's presence here marks it user-overridden."},"applies":{"type":"string","const":"live","description":"When the owner applies changes."},"secrets":{"type":"array","items":{"type":"object","properties":{"path":{"type":"array","items":{"type":"string"},"description":"Path from the section root to the removed field."},"set":{"type":"boolean","description":"Whether the slot currently holds a value; the value itself never rides."}},"required":["path","set"],"additionalProperties":true},"description":"Every schema-declared secret slot with its configured state."},"revision":{"type":"number","description":"Monotonic revision of the raw entry configuration this view was read at. Send it back as `expectedRevision` on a write so a stale editor is refused rather than silently overwriting a concurrent change."}},"required":["autoGenerate","ns","schema","value","applies","secrets","revision"],"additionalProperties":true,"description":"the namespace's redacted view after the write."}`
- source: `packages/api/settings-controller/src/index.ts:116:3`


### `@deepseek-ai/dsh-api-terminal-controller`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/attach`
- service: `terminalController` · invocation: `direct`
- **说明**：Attach terminal input and output to one physical Remote stream.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller/types#TerminalFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"snapshot"},"sequence":{"type":"number"},"screen":{"type":"string"},"info":{"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"shell":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"cwd":{"type":"string","description":"Initial working directory; shell directory changes do not update this field."},"cols":{"type":"number"},"rows":{"type":"number"},"state":{"type":"string","enum":["running","failed","exited"]},"exitCode":{"oneOf":[{"type":"null","const":null},{"type":"number"}]},"error":{"type":"string"},"origin":{"type":"string","enum":["user","agent"],"description":"Party that created the terminal."},"control":{"type":"string","enum":["user","agent"],"description":"Input owner; an agent terminal passes to the user on the user's first typed input and never returns."},"sandboxMode":{"type":"string","enum":["read-only","workspace-write","danger-full-access"],"description":"Sandbox mode an agent terminal started under; user terminals run with system-user permissions and omit it."}},"required":["id","title","shell","cwd","cols","rows","state","exitCode","origin","control"],"additionalProperties":true},"writable":{"type":"boolean"},"inputWindow":{"type":"object","properties":{"maxBytes":{"type":"number","description":"Maximum complete encoded frame bytes waiting for the Host consumer."},"frameOverheadBytes":{"type":"number","description":"UTF-8 envelope bytes added to a compact JSON item with a present value field."}},"required":["maxBytes","frameOverheadBytes"],"additionalProperties":true}},"required":["type","sequence","screen","info","writable"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"output"},"sequence":{"type":"number"},"data":{"type":"string"}},"required":["type","sequence","data"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"state"},"info":{"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"shell":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"cwd":{"type":"string","description":"Initial working directory; shell directory changes do not update this field."},"cols":{"type":"number"},"rows":{"type":"number"},"state":{"type":"string","enum":["running","failed","exited"]},"exitCode":{"oneOf":[{"type":"null","const":null},{"type":"number"}]},"error":{"type":"string"},"origin":{"type":"string","enum":["user","agent"],"description":"Party that created the terminal."},"control":{"type":"string","enum":["user","agent"],"description":"Input owner; an agent terminal passes to the user on the user's first typed input and never returns."},"sandboxMode":{"type":"string","enum":["read-only","workspace-write","danger-full-access"],"description":"Sandbox mode an agent terminal started under; user terminals run with system-user permissions and omit it."}},"required":["id","title","shell","cwd","cols","rows","state","exitCode","origin","control"],"additionalProperties":true},"writable":{"type":"boolean"}},"required":["type","info","writable"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"ack"},"sequence":{"type":"number"},"refusal":{"type":"string","enum":["read-only","not-running"]}},"required":["type","sequence"],"additionalProperties":true}],"description":"screen recovery, output, writable state and provider-acceptance acknowledgements."}`
- source: `packages/api/terminal-controller/src/index.ts:329:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/close`
- service: `terminalController` · invocation: `direct`
- **说明**：Close an identity to future creation and kill its process range; repeated closes succeed.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller#terminal/close:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/api/terminal-controller/src/index.ts:354:9`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/create`
- service: `terminalController` · invocation: `direct`
- **说明**：Allocate a user shell once for a caller-generated identity, without Agent sandbox or approval restrictions.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shellPath":{"type":"string","description":"A path returned by shell discovery; absent selects the execution default."},"id":{"type":"string"},"cols":{"type":"number"},"rows":{"type":"number"}},"required":["id","cols","rows"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller/types#WebTerminalInfo` (strict) schema=`{"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"shell":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"cwd":{"type":"string","description":"Initial working directory; shell directory changes do not update this field."},"cols":{"type":"number"},"rows":{"type":"number"},"state":{"type":"string","enum":["running","failed","exited"]},"exitCode":{"oneOf":[{"type":"null","const":null},{"type":"number"}]},"error":{"type":"string"},"origin":{"type":"string","enum":["user","agent"],"description":"Party that created the terminal."},"control":{"type":"string","enum":["user","agent"],"description":"Input owner; an agent terminal passes to the user on the user's first typed input and never returns."},"sandboxMode":{"type":"string","enum":["read-only","workspace-write","danger-full-access"],"description":"Sandbox mode an agent terminal started under; user terminals run with system-user permissions and omit it."}},"required":["id","title","shell","cwd","cols","rows","state","exitCode","origin","control"],"additionalProperties":true,"description":"the existing or newly committed terminal."}`
- source: `packages/api/terminal-controller/src/index.ts:193:9`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/environment`
- service: `terminalController` · invocation: `direct`
- **说明**：Read the Session's current directory and terminal limits without filesystem validation or shell lookup.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller/types#TerminalEnvironment` (strict) schema=`{"type":"object","properties":{"cwd":{"type":"string","description":"Logged current directory, read without filesystem validation."},"maxInputBytes":{"type":"number"},"maxBufferedBytes":{"type":"number","description":"Maximum complete encoded Client input bytes retained until acknowledgement."},"maxCols":{"type":"number"},"maxRows":{"type":"number"},"scrollback":{"type":"number"}},"required":["cwd","maxInputBytes","maxBufferedBytes","maxCols","maxRows","scrollback"],"additionalProperties":true,"description":"the logged current directory and terminal limits; retained terminals keep their own process directories."}`
- source: `packages/api/terminal-controller/src/index.ts:153:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/list`
- service: `terminalController` · invocation: `direct`
- **说明**：List retained terminals without resolving or activating an Agent.
- **参数**：
  - `sessionId` (wire `sessionId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller#terminal/list:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"shell":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"cwd":{"type":"string","description":"Initial working directory; shell directory changes do not update this field."},"cols":{"type":"number"},"rows":{"type":"number"},"state":{"type":"string","enum":["running","failed","exited"]},"exitCode":{"oneOf":[{"type":"null","const":null},{"type":"number"}]},"error":{"type":"string"},"origin":{"type":"string","enum":["user","agent"],"description":"Party that created the terminal."},"control":{"type":"string","enum":["user","agent"],"description":"Input owner; an agent terminal passes to the user on the user's first typed input and never returns."},"sandboxMode":{"type":"string","enum":["read-only","workspace-write","danger-full-access"],"description":"Sandbox mode an agent terminal started under; user terminals run with system-user permissions and omit it."}},"required":["id","title","shell","cwd","cols","rows","state","exitCode","origin","control"],"additionalProperties":true},"description":"terminals retained for this Host lifetime."}`
- source: `packages/api/terminal-controller/src/index.ts:179:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/rename`
- service: `terminalController` · invocation: `direct`
- **说明**：Rename a terminal without changing its shell.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
  - `title` (wire `title`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller#terminal/rename:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/api/terminal-controller/src/index.ts:342:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/retain`
- service: `terminalController` · invocation: `direct`
- **说明**：Retain an existing terminal for a window without activating its Agent or taking input control.
- **参数**：
  - `sessionId` (wire `sessionId`, source `json`) schema=`{"type":"string"}`
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller/types#TerminalRetentionFrame` (strict) schema=`{"type":"object","properties":{"type":{"type":"string","const":"retained"}},"required":["type"],"additionalProperties":true,"description":"a hold acknowledgement followed by an open lifetime stream."}`
- source: `packages/api/terminal-controller/src/index.ts:312:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/shells`
- service: `terminalController` · invocation: `direct`
- **说明**：Discover installed shells in the Session's execution environment.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller#terminal/shells:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"description":"verified profiles, with the configured or system default first."}`
- source: `packages/api/terminal-controller/src/index.ts:168:3`

#### `@deepseek-ai/dsh-api-terminal-controller#terminal/watch`
- service: `terminalController` · invocation: `direct`
- **说明**：Stream the Session's retained terminals as whole sets, without resolving or activating an Agent.
- **参数**：
  - `sessionId` (wire `sessionId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-terminal-controller#terminal/watch:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"shell":{"type":"object","properties":{"path":{"type":"string"},"args":{"type":"array","items":{"type":"string"}},"name":{"type":"string"}},"required":["path","args","name"],"additionalProperties":true},"cwd":{"type":"string","description":"Initial working directory; shell directory changes do not update this field."},"cols":{"type":"number"},"rows":{"type":"number"},"state":{"type":"string","enum":["running","failed","exited"]},"exitCode":{"oneOf":[{"type":"null","const":null},{"type":"number"}]},"error":{"type":"string"},"origin":{"type":"string","enum":["user","agent"],"description":"Party that created the terminal."},"control":{"type":"string","enum":["user","agent"],"description":"Input owner; an agent terminal passes to the user on the user's first typed input and never returns."},"sandboxMode":{"type":"string","enum":["read-only","workspace-write","danger-full-access"],"description":"Sandbox mode an agent terminal started under; user terminals run with system-user permissions and omit it."}},"required":["id","title","shell","cwd","cols","rows","state","exitCode","origin","control"],"additionalProperties":true},"description":"the current set, then a new set after creation, removal or any published state change."}`
- source: `packages/api/terminal-controller/src/index.ts:278:10`


### `@deepseek-ai/dsh-api-workspace-controller`

#### `@deepseek-ai/dsh-api-workspace-controller#directoryPicker/createDirectory`
- service: `directoryPickerController` · invocation: `direct`
- **说明**：Create one child directory for a Remote caller's in-app browser.
- **参数**：
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller#directoryPicker/createDirectory:result` (strict) schema=`{"type":"string","description":"the created directory's absolute path."}`
- source: `packages/api/workspace-controller/src/directory-picker.ts:88:9`

#### `@deepseek-ai/dsh-api-workspace-controller#directoryPicker/list`
- service: `directoryPickerController` · invocation: `direct`
- **说明**：List one directory level for a Remote caller's in-app browser.
- **参数**：
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-host-directory-picker/types#DirectoryListing` (strict) schema=`{"type":"object","properties":{"path":{"type":"string","description":"Absolute path of the listed directory."},"home":{"type":"string","description":"The host account's home directory (breadcrumb \"Home\" rooting)."},"crumbs":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"Base name shown in a browser row (a root crumb carries its full path)."},"path":{"type":"string","description":"Absolute host path — clients never join path segments themselves."},"hidden":{"type":"boolean","description":"Hidden by the host platform's convention (dot-prefixed on POSIX); the client owns whether to show it."}},"required":["name","path","hidden"],"additionalProperties":true},"description":"Ancestor chain from the filesystem root to the listed directory inclusive; every crumb is a jump target (crumb `hidden` is always false)."},"entries":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"Base name shown in a browser row (a root crumb carries its full path)."},"path":{"type":"string","description":"Absolute host path — clients never join path segments themselves."},"hidden":{"type":"boolean","description":"Hidden by the host platform's convention (dot-prefixed on POSIX); the client owns whether to show it."}},"required":["name","path","hidden"],"additionalProperties":true},"description":"Direct child directories, name-sorted; symlinks to directories included."},"truncated":{"type":"boolean","description":"True when the backend cut `entries` at its complete-result bound: the level has more child directories than reported, and the missing rows are the name-sorted tail (hidden rows count toward the bound)."}},"required":["path","home","crumbs","entries","truncated"],"additionalProperties":true,"description":"the level's listing with its ancestry."}`
- source: `packages/api/workspace-controller/src/directory-picker.ts:72:9`

#### `@deepseek-ai/dsh-api-workspace-controller#directoryPicker/pick`
- service: `directoryPickerController` · invocation: `direct`
- **说明**：Open the host's OS chooser for a Remote caller.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-workspace-controller#directoryPicker/pick:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"the chosen absolute path, or null when the operator cancels."}`
- source: `packages/api/workspace-controller/src/directory-picker.ts:55:9`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/archiveSession`
- service: `workspaceController` · invocation: `direct`
- **说明**：Hide one known Session from Workspace grouping surfaces.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"stopActivity":{"type":"boolean","description":"Stop the Session's running work — its turn, subagent descendants, owned background jobs, and active schedules — instead of refusing the archive as `workspace/session-active`. The stops are requested before the archive write and are not awaited; the response arrives once the archive set is durable."}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceArchiveValue` (strict) schema=`{"type":"object","properties":{"archivedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["archivedSessionIds"],"additionalProperties":true,"description":"the complete resulting archive set."}`
- source: `packages/api/workspace-controller/src/index.ts:160:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/create`
- service: `workspaceController` · invocation: `direct`
- **说明**：Create or idempotently resolve one Workspace over an existing directory.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceCreateValue` (strict) schema=`{"type":"object","properties":{"workspace":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true},"created":{"type":"boolean"}},"required":["workspace","created"],"additionalProperties":true,"description":"the Workspace and whether this call created it."}`
- source: `packages/api/workspace-controller/src/index.ts:91:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/delete`
- service: `workspaceController` · invocation: `direct`
- **说明**：Remove one Workspace registration while retaining files and Sessions.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"workspaceId":{"type":"string"}},"required":["workspaceId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceDeleteValue` (strict) schema=`{"type":"object","properties":{"deleted":{"type":"boolean","const":true}},"required":["deleted"],"additionalProperties":true,"description":"deletion confirmation."}`
- source: `packages/api/workspace-controller/src/index.ts:130:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/follow`
- service: `workspaceController` · invocation: `direct`
- **说明**：Stream a complete Workspace baseline followed by ordered increments. A non-owner receives only the Workspaces and Sessions `allows()` admits. When a delivered Workspace is no longer admitted at its next change or the next order change, the stream sends a `replace` frame with the complete filtered state instead of a `remove`, because a Client never resurrects a removed Workspace; a `remove` frame reports a deletion and reaches only a Client that received that Workspace.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceFollowFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"baseline"},"value":{"type":"object","properties":{"items":{"type":"array","items":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true}},"archivedSessionIds":{"type":"array","items":{"type":"string"}},"pinnedSessionIds":{"type":"array","items":{"type":"string"},"description":"Registry-global pin set, most recently pinned first."}},"required":["items","archivedSessionIds","pinnedSessionIds"],"additionalProperties":true}},"required":["type","value"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"replace"},"value":{"type":"object","properties":{"items":{"type":"array","items":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true}},"archivedSessionIds":{"type":"array","items":{"type":"string"}},"pinnedSessionIds":{"type":"array","items":{"type":"string"},"description":"Registry-global pin set, most recently pinned first."}},"required":["items","archivedSessionIds","pinnedSessionIds"],"additionalProperties":true}},"required":["type","value"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"upsert"},"workspace":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true}},"required":["type","workspace"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"remove"},"workspaceId":{"type":"string"}},"required":["type","workspaceId"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"order"},"workspaceIds":{"type":"array","items":{"type":"string"}}},"required":["type","workspaceIds"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"archived"},"archivedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["type","archivedSessionIds"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"pinned"},"pinnedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["type","pinnedSessionIds"],"additionalProperties":true}],"description":"baseline followed by ordered Workspace increments."}`
- source: `packages/api/workspace-controller/src/index.ts:206:10`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/initializeDefault`
- service: `workspaceController` · invocation: `direct`
- **说明**：Initialize or reuse the default Workspace during first-use startup. The directory name is fixed, so the Host never renames or relocates an existing default; its initial title is that same name, which browser consumers label in the reader's language.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-api-workspace-controller#workspace/initializeDefault:result` (strict) — schema 不可用：typert tool schema: unsupported undefined value
- source: `packages/api/workspace-controller/src/index.ts:104:9`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/insertBefore`
- service: `workspaceController` · invocation: `direct`
- **说明**：Move one Workspace within the registry display order.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"workspaceId":{"type":"string"},"beforeWorkspaceId":{"type":"string"}},"required":["workspaceId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceOrderValue` (strict) schema=`{"type":"object","properties":{"workspaceIds":{"type":"array","items":{"type":"string"}}},"required":["workspaceIds"],"additionalProperties":true,"description":"the complete resulting Workspace order."}`
- source: `packages/api/workspace-controller/src/index.ts:140:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/insertSessionBefore`
- service: `workspaceController` · invocation: `direct`
- **说明**：Move one accounted Session within a Workspace.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"workspaceId":{"type":"string"},"sessionId":{"type":"string"},"beforeSessionId":{"type":"string"}},"required":["workspaceId","sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceValue` (strict) schema=`{"type":"object","properties":{"workspace":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true}},"required":["workspace"],"additionalProperties":true,"description":"the updated Workspace projection."}`
- source: `packages/api/workspace-controller/src/index.ts:150:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/pinSession`
- service: `workspaceController` · invocation: `direct`
- **说明**：Surface one known unarchived Session ahead of unpinned Sessions.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspacePinValue` (strict) schema=`{"type":"object","properties":{"pinnedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["pinnedSessionIds"],"additionalProperties":true,"description":"the complete resulting pin set, most recently pinned first."}`
- source: `packages/api/workspace-controller/src/index.ts:180:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/rename`
- service: `workspaceController` · invocation: `direct`
- **说明**：Rename one Workspace to a unique non-blank title.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"workspaceId":{"type":"string"},"title":{"type":"string"}},"required":["workspaceId","title"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceValue` (strict) schema=`{"type":"object","properties":{"workspace":{"type":"object","properties":{"workspaceId":{"type":"string"},"path":{"type":"string","description":"Canonical host directory path."},"title":{"type":"string","description":"User-visible title."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions accounted to this Workspace in manual order."},"createdAt":{"type":"string","description":"ISO-8601 creation instant."},"updatedAt":{"type":"string","description":"ISO-8601 last-mutation instant."}},"required":["workspaceId","path","title","sessionIds","createdAt","updatedAt"],"additionalProperties":true}},"required":["workspace"],"additionalProperties":true,"description":"the updated Workspace projection."}`
- source: `packages/api/workspace-controller/src/index.ts:120:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/unarchiveSession`
- service: `workspaceController` · invocation: `direct`
- **说明**：Restore one archived Session to Workspace grouping surfaces.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspaceArchiveValue` (strict) schema=`{"type":"object","properties":{"archivedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["archivedSessionIds"],"additionalProperties":true,"description":"the complete resulting archive set."}`
- source: `packages/api/workspace-controller/src/index.ts:170:3`

#### `@deepseek-ai/dsh-api-workspace-controller#workspace/unpinSession`
- service: `workspaceController` · invocation: `direct`
- **说明**：Remove one Session's pin without changing its saved Session order.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-controller/types#WorkspacePinValue` (strict) schema=`{"type":"object","properties":{"pinnedSessionIds":{"type":"array","items":{"type":"string"}}},"required":["pinnedSessionIds"],"additionalProperties":true,"description":"the complete resulting pin set, most recently pinned first."}`
- source: `packages/api/workspace-controller/src/index.ts:190:3`


### `@deepseek-ai/dsh-api-workspace-files`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/changes`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：Watch one file or a directory's direct entries in the Session's filesystem. Files use the backend's read authority; directories remain workspace-scoped.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceFileWatchFrame` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/api/workspace-files/src/index.ts:400:3`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/list`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：List the direct children of one directory inside the Session's workspace.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceDirectoryListing` (strict) schema=`{"type":"object","properties":{"path":{"type":"string","description":"The listed directory as a workspace path, relative to the workspace root and empty for the root itself. A child's path is this value joined with {@link WorkspaceDirectoryEntry.name} by `/`."},"entries":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"Basename inside the listed directory."},"type":{"type":"string","enum":["file","directory","other"],"description":"What the child resolves to. A symlink reports the type of its destination, and `other` covers everything that is neither a regular file nor a directory; `read` still refuses a symlink, so `file` here is a listing fact, not a promise that the content is readable."},"size":{"type":"number","description":"Byte size, present only for a regular file whose backend reports it."}},"required":["name","type"],"additionalProperties":true},"description":"Direct children in the backend's stable name order, cut to the configured entry cap. Presentation order is the caller's choice."},"truncated":{"type":"boolean","description":"Whether the entry cap dropped children from {@link entries}."}},"required":["path","entries","truncated"],"additionalProperties":true,"description":"the directory's children in the backend's stable name order, bounded by the entry cap."}`
- source: `packages/api/workspace-files/src/index.ts:317:9`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/read`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：Read one page of lines from a UTF-8 file readable by the filesystem backend.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
  - `range` (wire `range`, source `json`) schema=`{"type":"object","properties":{"offset":{"type":"number","description":"First line of the page. Defaults to 1."},"limit":{"type":"number","description":"Largest number of lines on the page. Defaults to, and may not exceed, the configured `maxLines`."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceFileText` (strict) schema=`{"type":"object","properties":{"offset":{"type":"number","description":"First line of the page, as requested."},"text":{"type":"string","description":"The page's lines joined by `\\n`, without a terminator after the last one. Empty for a page past the file's last line and for a page holding one empty line; `lines` tells them apart."},"lines":{"type":"number","description":"How many lines the page holds; `0` when `offset` lies past the file's last line."},"eof":{"type":"boolean","description":"Whether the page includes the file's last line."},"absolutePath":{"type":"string","description":"Absolute path of the file in the filesystem's execution world, symlinks resolved: `/`-separated on POSIX, drive-rooted with the platform separator on Windows. What a `dsh-resource://file/absolute/…` address carries, and what a `dsh-resource://file/session/<sessionId>/…` address's workspace-relative path resolves to against that Session's root."},"version":{"type":"string","description":"Opaque freshness token at the time of the stat; never parsed."},"bytes":{"type":"number","description":"Byte size of the complete file, when the backend reports it."}},"required":["offset","text","lines","eof","absolutePath","version"],"additionalProperties":true,"description":"the page, the file's version at the stat before it, and whether it reaches the last line."}`
- source: `packages/api/workspace-files/src/index.ts:247:9`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/readBytes`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：Read a complete regular file or one byte range without text decoding.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"range":{"type":"object","properties":{"offset":{"type":"number","description":"First byte of the window. Defaults to 0."},"length":{"type":"number","description":"Largest number of bytes in the window. Defaults to, and may not exceed, the configured `maxBytes`."}},"required":[],"additionalProperties":true,"description":"Byte window; omit to read the complete file under the configured `maxFileBytes` cap."},"baseFile":{"type":"string","description":"Base file, absolute or workspace-relative; resolve the relative target from its directory."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceFileBytes` (strict) — schema 不可用：typert tool schema: unsupported selected reference Uint8Array
- source: `packages/api/workspace-files/src/index.ts:271:9`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/search`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：Search files and their inferred ancestor directories with packaged ripgrep. Native ignore rules apply unless disabled; VCS metadata, symlinks and empty directories are absent. Within the bounded set of listed files, matches sort by depth, then workspace-relative path.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"query":{"type":"string","description":"Case-insensitive substring to find. Surrounding whitespace is trimmed, and an empty result is refused. Without `/` it matches entry names; with `/` it matches `/`-joined workspace-relative paths."},"excludedPaths":{"type":"array","items":{"type":"string"},"description":"Literal exclusions passed as escaped rg globs. A value without `/` excludes that name at any depth; a value with `/` excludes the exact path rooted at the workspace. Glob metacharacters in names are not interpreted as patterns."},"includeHidden":{"type":"boolean","description":"Whether rg includes hidden files and directories; VCS metadata remains excluded."},"respectGitignore":{"type":"boolean","description":"Whether native rg ignore rules apply, including repository detection, nested and parent `.gitignore`, `.git/info/exclude`, global Git excludes and `.ignore`. The service does not read `core.ignorecase`; false passes `--no-ignore`."}},"required":["query","excludedPaths","includeHidden","respectGitignore"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceFileSearchResult` (strict) schema=`{"type":"object","properties":{"matches":{"type":"array","items":{"type":"object","properties":{"path":{"type":"string","description":"`/`-joined path relative to the workspace root, never empty."},"type":{"type":"string","enum":["file","directory","other"],"description":"What the entry resolves to, as {@link WorkspaceDirectoryEntry.type} reports it."}},"required":["path","type"],"additionalProperties":true},"description":"Matching files and inferred ancestor directories from the bounded set of listed files, sorted by depth then workspace-relative path and cut to the configured result cap."},"truncated":{"type":"boolean","description":"Whether matches exceeded the result cap after scanning the bounded file set."},"incomplete":{"type":"boolean","description":"Whether rg listed more files than the file cap and was terminated early, or exited with code 2 to report partial discovery."}},"required":["matches","truncated","incomplete"],"additionalProperties":true,"description":"matches capped by search.maxResults; incomplete marks excess rg files or exit 2."}`
- source: `packages/api/workspace-files/src/index.ts:359:9`

#### `@deepseek-ai/dsh-api-workspace-files#workspaceFiles/stat`
- service: `workspaceFiles` · invocation: `direct`
- **说明**：Report one regular file's identity, version, and size without its content.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-api-workspace-files/types#WorkspaceFileStat` (strict) schema=`{"type":"object","properties":{"absolutePath":{"type":"string","description":"Absolute path of the file in the filesystem's execution world, symlinks resolved: `/`-separated on POSIX, drive-rooted with the platform separator on Windows. What a `dsh-resource://file/absolute/…` address carries, and what a `dsh-resource://file/session/<sessionId>/…` address's workspace-relative path resolves to against that Session's root."},"version":{"type":"string","description":"Opaque freshness token at the time of the stat; never parsed."},"bytes":{"type":"number","description":"Byte size of the complete file, when the backend reports it."}},"required":["absolutePath","version"],"additionalProperties":true,"description":"the file's absolute path, current version, and byte size."}`
- source: `packages/api/workspace-files/src/index.ts:304:9`


### `@deepseek-ai/dsh-client-file-upload`

#### `@deepseek-ai/dsh-client-file-upload#fileUploads/upload`
- service: `fileUploads` · invocation: `direct`
- **说明**：Persist one encoded upload and stage it under the Agent receiver selected by Typert.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"data":{"type":"string","description":"Canonical base64 encoding of the exact file bytes."},"name":{"type":"string","description":"Optional display name; the Host sanitizes it into the stored leaf name."}},"required":["data"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-client-file-upload/types#FileUploadValue` (strict) schema=`{"type":"object","properties":{"receiptId":{"type":"string","description":"Per-upload authority accepted only inside the receiving Agent scope."},"file":{"type":"object","properties":{"attachmentId":{"type":"string","description":"Opaque content-addressed storage identifier; never a filesystem path or bearer URL."},"name":{"type":"string","description":"Sanitized display filename, also the stored object's leaf name."},"bytes":{"type":"number","description":"Exact byte length."}},"required":["attachmentId","name","bytes"],"additionalProperties":true}},"required":["receiptId","file"],"additionalProperties":true,"description":"the staged receipt and durable file reference."}`
- source: `packages/client/file-upload/src/index.ts:113:9`


### `@deepseek-ai/dsh-client-product-analytics`

#### `@deepseek-ai/dsh-client-product-analytics#productAnalytics/enabled`
- service: `productAnalytics` · invocation: `direct`
- **说明**：Read the collection policy.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-client-product-analytics#productAnalytics/enabled:result` (strict) schema=`{"type":"boolean","description":"whether this Host currently accepts Desktop analytics."}`
- source: `packages/client/product-analytics/src/index.ts:67:3`

#### `@deepseek-ai/dsh-client-product-analytics#productAnalytics/report`
- service: `productAnalytics` · invocation: `direct`
- **说明**：Submit selected Desktop fields with cached static environment and fresh identity. The first intake waits for bounded environment queries; concurrent intakes share them. Missing identity is omitted; failed environment fields carry fixed reasons.
- **参数**：
  - `event` (wire `event`, source `json`) — `@deepseek-ai/dsh-client-product-analytics/types#ProductEvent` schema 不可用：typert tool schema: unsupported never value
- **结果**：`@deepseek-ai/dsh-client-product-analytics#productAnalytics/report:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/client/product-analytics/src/index.ts:100:9`

#### `@deepseek-ai/dsh-client-product-analytics#productAnalytics/watchPolicy`
- service: `productAnalytics` · invocation: `direct`
- **说明**：Stream the effective policy initially and after live configuration edits.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-client-product-analytics#productAnalytics/watchPolicy:result` (strict) schema=`{"type":"boolean","description":"current policy values until cancellation or service disposal."}`
- source: `packages/client/product-analytics/src/index.ts:75:10`


### `@deepseek-ai/dsh-client-ui-plugin-manager`

#### `@deepseek-ai/dsh-client-ui-plugin-manager#pluginRegistryProbe/fastest`
- service: `pluginRegistryProbe` · invocation: `direct`
- **说明**：Race npm and npmmirror HTTPS ping responses through the Host's fetch proxy. Concurrent readers share a probe; a winner cancels and awaits the other request.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-client-ui-plugin-manager#pluginRegistryProbe/fastest:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"the first registry with a successful response, or null when disabled or neither responds successfully; results are cached."}`
- source: `packages/client/ui-plugin-manager/src/index.ts:51:9`


### `@deepseek-ai/dsh-client-ui-trajectory`

#### `@deepseek-ai/dsh-client-ui-trajectory#toolResults/watch`
- service: `sessionToolResults` · invocation: `direct`
- **说明**：Observe one committed result without loading a Session or reading its history. Values disappear on count eviction or when the exact Session instance leaves the registry. A cold read stays unavailable; opening a new stream observes the current instance. Inspection does not extend a result's retention.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"seq":{"type":"number"}},"required":["sessionId","seq"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-client-ui-trajectory/types#SessionToolResultValue` (strict) schema=`{"oneOf":[{"type":"object","properties":{"available":{"type":"boolean","const":false}},"required":["available"],"additionalProperties":true},{"type":"object","properties":{"available":{"type":"boolean","const":true},"value":{}},"required":["available","value"],"additionalProperties":true}],"description":"Current availability and changes until cancellation or service disposal."}`
- source: `packages/client/ui-trajectory/src/index.ts:106:10`


### `@deepseek-ai/dsh-command-feedback`

#### `@deepseek-ai/dsh-command-feedback#sessionFeedback/record`
- service: `sessionFeedback` · invocation: `direct`
- **说明**：Record one remark on a live Session.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Live Session the remark describes."},"text":{"type":"string","description":"Free-text remark; blank text is recorded as absent."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Category the human filed the remark under."}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-command-feedback/types#SessionFeedbackRecordResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"value":{"type":"object","properties":{"recorded":{"type":"boolean","const":true,"description":"The remark is appended to the Session log; flushing follows the Session's own schedule."}},"required":["recorded"],"additionalProperties":true}},"required":["ok","value"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"error":{"type":"object","properties":{"code":{"type":"string","const":"session-not-found"},"sessionId":{"type":"string"}},"required":["code","sessionId"],"additionalProperties":true}},"required":["ok","error"],"additionalProperties":true}],"description":"the recorded postcondition, or `session-not-found` when no live Session carries the id."}`
- source: `packages/feedback/command-feedback/src/index.ts:102:3`


### `@deepseek-ai/dsh-commands`

#### `@deepseek-ai/dsh-commands#commands/execute`
- service: `commands` · invocation: `direct`
- **说明**：Parse and execute a known command without sending it to the model. A resolved command's lifecycle is logged: `command/run` is appended before the handler is invoked and `command/done` after settlement (a thrown or aborted handler settles as `kind: 'error'`). Both are direct log-only appends — no turn wraps them, and persistence drains them at ordinary checkpoints. Admission misses (syntax or unknown name) log nothing — they never entered a handler. A `command/run` append failure fails the execution loud; a `command/done` append failure on the handler-failure path is contained so the handler's own error stays the reported failure. Attachment admission is enforced here, not in the composer: attachments sent to a command that does not declare `input.attachments`, an absent attachment store, and an exceeded image limit each settle as an error result before the handler runs. Validation rejection starts no attachment writes; a storage failure can leave only unreachable content-addressed objects for deferred collection.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `line` (wire `line`, source `json`) schema=`{"type":"string"}`
  - `submittedAttachments` (wire `submittedAttachments`, source `json`) schema=`{"type":"array","items":{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"image"},"mediaType":{"type":"string","enum":["image/png","image/jpeg","image/webp","image/gif"],"description":"Declared media type, verified against the decoded bytes during admission."},"data":{"type":"string","description":"Canonical base64 encoding of the image bytes."},"name":{"type":"string","description":"Optional display name; it is never interpreted as a path."}},"required":["type","mediaType","data"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"file"},"receiptId":{"type":"string"}},"required":["type","receiptId"],"additionalProperties":true}]}}`
- **结果**：`@deepseek-ai/dsh-commands#commands/execute:result` (strict) — schema 不可用：typert tool schema: unsupported undefined value
- source: `packages/interaction/commands/src/index.ts:361:9`

#### `@deepseek-ai/dsh-commands#commands/list`
- service: `commands` · invocation: `direct`
- **说明**：List the effective immutable command descriptors for one agent.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-commands#commands/list:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"definitionId":{"type":"string","description":"Stable plugin-owned identity; absent for definitions without identity-based client behavior."},"name":{"type":"string","description":"Lowercase command name without the leading slash."},"description":{"type":"string","description":"Human-readable summary used in discovery UI."},"input":{"type":"object","properties":{"hint":{"type":"string","description":"Placeholder shown before the user supplies free-form input."},"attachments":{"type":"boolean","description":"Whether composer attachments may accompany an invocation. Absent or false = the executor rejects an invocation carrying attachments and capable composers refuse the submission before dispatch. A declaring command's handler receives the admitted durable blocks and owns every further grammar decision, including rejecting sub-commands that cannot use them."}},"required":["hint"],"additionalProperties":true,"description":"Optional free-form input hint advertised to capable clients."}},"required":["name","description"],"additionalProperties":true},"description":"name-sorted descriptors after scoped shadowing."}`
- source: `packages/interaction/commands/src/index.ts:315:3`


### `@deepseek-ai/dsh-cordis-host-runner`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/getClientCode`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Fetch Client code for the exact active run.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `pluginRunId` (wire `pluginRunId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisClientSource` (strict) schema=`{"type":"object","properties":{"code":{"type":"string","description":"Browser JavaScript body."},"name":{"type":"string","description":"Package label."},"pluginId":{"type":"string","description":"Stable plugin instance."},"packageId":{"type":"string","description":"Immutable source version."},"pluginRunId":{"type":"string","description":"Exact activation the source belongs to."}},"required":["code","name","pluginId","packageId","pluginRunId"],"additionalProperties":true,"description":"Client source and its Plugin, Package, and run identities."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:402:3`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/inventory`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Frame-wide inventory, grouped as one row per stable Plugin.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/inventory:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"pluginId":{"type":"string","description":"Stable plugin instance."},"agentId":{"type":"string","description":"Session that owns this plugin."},"packages":{"type":"array","items":{"type":"object","properties":{"packageId":{"type":"string","description":"Immutable package version."},"name":{"type":"string","description":"Package label."},"purpose":{"type":"string","description":"User-facing purpose."},"hasHostHalf":{"type":"boolean","description":"Whether this version contains Host code."},"hasClientHalf":{"type":"boolean","description":"Whether this version contains Client code."}},"required":["packageId","name","purpose","hasHostHalf","hasClientHalf"],"additionalProperties":true},"description":"Immutable versions in define order."},"currentPackageId":{"type":"string","description":"Last package that completed activation successfully."},"nextPackageId":{"type":"string","description":"Package selected for a failed or in-progress transition."},"activeRun":{"type":"object","properties":{"pluginRunId":{"type":"string"},"packageId":{"type":"string"}},"required":["pluginRunId","packageId"],"additionalProperties":true,"description":"Current activation, absent while stopped."},"latestRun":{"type":"object","properties":{"pluginRunId":{"type":"string","description":"Exact attempt identity."},"packageId":{"type":"string","description":"Target Package."},"mode":{"type":"string","enum":["run","update"],"description":"Explicit run/update intent."},"status":{"type":"string","enum":["running","failed","rejected","awaiting-approval","cancelled","starting-host","client-pending","waiting","stopped"],"description":"Current attempt state."},"approvalRequestId":{"type":"string","description":"Pending Client activation request; it represents approval only when `requiresApproval` is true."},"requiresApproval":{"type":"boolean","description":"Whether the pending Client activation requires a user decision."},"host":{"type":"object","properties":{"status":{"type":"string","enum":["running","failed","pending","waiting","stopped","absent"],"description":"Lifecycle state of this half."},"waitingFor":{"type":"array","items":{"type":"string"},"description":"Services still needed by a successfully created Fiber."},"error":{"type":"string","description":"Failure text for this half."}},"required":["status","waitingFor"],"additionalProperties":true,"description":"Host-half state."},"client":{"type":"object","properties":{"status":{"type":"string","enum":["running","failed","pending","waiting","stopped","absent"],"description":"Lifecycle state of this half."},"waitingFor":{"type":"array","items":{"type":"string"},"description":"Services still needed by a successfully created Fiber."},"error":{"type":"string","description":"Failure text for this half."}},"required":["status","waitingFor"],"additionalProperties":true,"description":"Client-half state."},"error":{"type":"object","properties":{"phase":{"type":"string","enum":["approval","host-load","host-apply","client-load","client-apply","client-render"],"description":"Stage that failed."},"message":{"type":"string","description":"Original failure text."},"stack":{"type":"string","description":"Original failure stack when available."},"pluginId":{"type":"string","description":"Stable Plugin identity."},"packageId":{"type":"string","description":"Immutable Package identity."},"pluginRunId":{"type":"string","description":"Exact attempt identity."}},"required":["phase","message","pluginId","packageId","pluginRunId"],"additionalProperties":true,"description":"Most recent failure."}},"required":["pluginRunId","packageId","mode","status","host","client"],"additionalProperties":true,"description":"Latest activation attempt, including pending approval and diagnostics."}},"required":["pluginId","agentId","packages"],"additionalProperties":true},"description":"Source-free metadata for every process-local Plugin."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:544:3`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/invoke`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Invoke an active Host method while rejecting stale Client runs.
- **参数**：
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `pluginRunId` (wire `pluginRunId`, source `json`) schema=`{"type":"string"}`
  - `method` (wire `method`, source `json`) schema=`{"type":"string"}`
  - `args` (wire `args`, source `json`) schema=`{}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisInvokeResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"value":{}},"required":["ok","value"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"code":{"type":"string","enum":["plugin-not-running","stale-run","method-not-found","handler-error"]},"message":{"type":"string","description":"Original error message."},"stack":{"type":"string","description":"Original stack when the thrown value supplied one."}},"required":["ok","code","message"],"additionalProperties":true}],"description":"The JSON result or a typed invocation failure."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:760:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/reportClientGuardFailure`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Report a Client guard rejection that happened after the Package completed activation.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `pluginRunId` (wire `pluginRunId`, source `json`) schema=`{"type":"string"}`
  - `failure` (wire `failure`, source `json`) schema=`{"type":"object","properties":{"message":{"type":"string","description":"Original error message."},"stack":{"type":"string","description":"Original stack when the thrown value supplied one."}},"required":["message"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/reportClientGuardFailure:result` (strict) schema=`{"type":"null","const":null,"description":"Null after reporting or ignoring a stale/startup failure."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:737:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/reportRenderFailure`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Record a post-load render failure for the exact active run.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `pluginRunId` (wire `pluginRunId`, source `json`) schema=`{"type":"string"}`
  - `failure` (wire `failure`, source `json`) schema=`{"type":"object","properties":{"slot":{"type":"string","description":"Slot whose component failed."},"message":{"type":"string","description":"Render failure text."},"stack":{"type":"string","description":"Original render failure stack when available."},"abdicated":{"type":"boolean","description":"Whether the failing contribution relinquished its slot."}},"required":["slot","message","abdicated"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/reportRenderFailure:result` (strict) schema=`{"type":"null","const":null,"description":"Null after recording or ignoring a stale report."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:703:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/resolveInspectQuery`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Submit a Client inspect result or failure for a pending query.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `requestId` (wire `requestId`, source `json`) schema=`{"type":"string"}`
  - `resolution` (wire `resolution`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"data":{}},"required":["ok","data"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","enum":["cancelled","provider-missing","method-missing","invalid-input","provider-error"]},"message":{"type":"string"}},"required":["ok","reason","message"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#CordisInspectResolveAck` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","description":"True only for a valid success that settles the query; false for retained failures and unknown, timed out, cancelled, or late answers."}},"required":["accepted"],"additionalProperties":true,"description":"acknowledgement with accepted true only for a valid success that settles the query; pending-query failures return { accepted: false } and retain only the first diagnostic."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:530:3`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/resolveRequestRun`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Resolve one model-driven Client activation request.
- **参数**：
  - `requestId` (wire `requestId`, source `json`) schema=`{"type":"string"}`
  - `resolution` (wire `resolution`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"pluginRunId":{"type":"string"},"waitingFor":{"type":"array","items":{"type":"string"}}},"required":["ok","pluginRunId"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","enum":["rejected","host-half-failed","client-half-failed"]},"pluginRunId":{"type":"string","description":"Activation that failed; absent for a refusal before activation."},"startedHere":{"type":"boolean","description":"Whether this page created the failed activation instead of attaching to it."},"message":{"type":"string"},"stack":{"type":"string"}},"required":["ok","reason"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisResolveAck` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","description":"False for late, unknown, or stale answers."}},"required":["accepted"],"additionalProperties":true,"description":"Whether the still-pending request accepted this resolution."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:431:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/runHostHalf`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Start Host code for an approved request or a direct panel gesture.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `packageId` (wire `packageId`, source `json`) schema=`{"type":"string"}`
  - `mode` (wire `mode`, source `json`) schema=`{"type":"string","enum":["run","update"]}`
  - `requestId` (wire `requestId`, source `json`) schema=`{"oneOf":[{"type":"null","const":null},{"type":"string"}]}`
  - `approveFutureVersions` (wire `approveFutureVersions`, source `json`) schema=`{"type":"boolean"}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisHostHalfResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"pluginId":{"type":"string"},"packageId":{"type":"string"},"pluginRunId":{"type":"string"},"waitingFor":{"type":"array","items":{"type":"string"}},"startedHere":{"type":"boolean","description":"False when a panel merely attaches this page to an already active run."}},"required":["ok","pluginId","packageId","pluginRunId","waitingFor","startedHere"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"message":{"type":"string","description":"Original error message."},"stack":{"type":"string","description":"Original stack when the thrown value supplied one."}},"required":["ok","message"],"additionalProperties":true}],"description":"The exact Host activation or a failure message."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:343:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/settleUserRun`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Settle a direct panel run after this page loaded or failed its Client half.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
  - `resolution` (wire `resolution`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"pluginRunId":{"type":"string"},"waitingFor":{"type":"array","items":{"type":"string"}}},"required":["ok","pluginRunId"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","enum":["rejected","host-half-failed","client-half-failed"]},"pluginRunId":{"type":"string","description":"Activation that failed; absent for a refusal before activation."},"startedHere":{"type":"boolean","description":"Whether this page created the failed activation instead of attaching to it."},"message":{"type":"string"},"stack":{"type":"string"}},"required":["ok","reason"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisRunResponse` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"status":{"type":"string","enum":["running","awaiting-approval","starting"],"description":"Whether activation completed synchronously, is starting in a Client, or awaits user approval."},"pluginId":{"type":"string"},"packageId":{"type":"string"},"pluginRunId":{"type":"string"},"waitingFor":{"type":"array","items":{"type":"string"},"description":"Missing Host services; a parked Fiber is a successful activation."},"clientWaitingFor":{"type":"array","items":{"type":"string"},"description":"Missing Client services reported by the approving page."},"currentPackageId":{"type":"string","description":"Last fully successful Package."},"nextPackageId":{"type":"string","description":"Selected transition target."},"mode":{"type":"string","enum":["run","update"],"description":"Explicit lifecycle intent."}},"required":["ok","status","pluginId","packageId","pluginRunId","waitingFor","mode"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","enum":["not-running","plugin-missing","rejected","host-half-failed","client-half-failed","package-missing","invalid-mode","transition-in-flight","cancelled"]},"message":{"type":"string"},"stack":{"type":"string","description":"Original failure stack when available."}},"required":["ok","reason","message"],"additionalProperties":true}],"description":"The committed activation or its failure."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:456:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/stopFromPanel`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Stop a Plugin from the user panel and queue the resulting state change for the model's next step.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisStopResponse` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true}},"required":["ok"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","enum":["not-running","plugin-missing"]},"message":{"type":"string"}},"required":["ok","reason","message"],"additionalProperties":true}],"description":"Success or the reason no run was stopped."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:498:9`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/syncInspectManifest`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Replace the Host mirror of the Client inspect provider directory.
- **参数**：
  - `providers` (wire `providers`, source `json`) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Provider identity, unique within one platform."},"description":{"type":"string","description":"Capability described by this provider."},"methods":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"Method name, unique within its provider."},"description":{"type":"string","description":"What the query returns and when to use it."},"inputSchema":{"description":"JSON Schema accepted by the query."},"outputSchema":{"description":"JSON Schema produced by the query."}},"required":["name","description","inputSchema","outputSchema"],"additionalProperties":true},"description":"Explicit read-only queries."}},"required":["id","description","methods"],"additionalProperties":true}}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/syncInspectManifest:result` (strict) schema=`{"type":"null","const":null,"description":"null after accepting the manifest."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:516:3`

#### `@deepseek-ai/dsh-cordis-host-runner#dynamicCordisRunner/undefineFromPanel`
- service: `dynamicCordisRunner` · invocation: `direct`
- **说明**：Remove a Plugin from the user panel and queue the resulting state change for the model's next step.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `pluginId` (wire `pluginId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cordis-host-runner/types#DynamicCordisUndefineReceipt` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"wasRunning":{"type":"boolean"}},"required":["ok","wasRunning"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"reason":{"type":"string","const":"plugin-missing"},"message":{"type":"string"}},"required":["ok","reason","message"],"additionalProperties":true}],"description":"Whether removal succeeded and whether it stopped an active run."}`
- source: `packages/extensions/cordis-host-runner/src/index.ts:245:9`


### `@deepseek-ai/dsh-cua`

#### `@deepseek-ai/dsh-cua#cuaAccess/applicationIcons`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Load presentation icons separately from application decisions.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/applicationIcons:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/experimental/cua/src/access.ts:96:9`

#### `@deepseek-ai/dsh-cua#cuaAccess/applications`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Read fresh stored application decisions without issuing a native request.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cua/types#CuaApplicationState` (strict) schema=`{"type":"object","properties":{"allowedApps":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Native identity digest admitted from the helper or validated profile configuration."},"name":{"type":"string","description":"Application label presented when the decision was made."},"executablePath":{"type":"string","description":"Canonical executable path for display and icons; absent when the operating system cannot provide it."}},"required":["id","name"],"additionalProperties":true}},"blockedApps":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Native identity digest admitted from the helper or validated profile configuration."},"name":{"type":"string","description":"Application label presented when the decision was made."},"executablePath":{"type":"string","description":"Canonical executable path for display and icons; absent when the operating system cannot provide it."}},"required":["id","name"],"additionalProperties":true},"description":"Refusals from any session, excluding saved grants; other sessions may still hold session access."},"persistentAvailable":{"type":"boolean"}},"required":["allowedApps","blockedApps","persistentAvailable"],"additionalProperties":true,"description":"Saved grants, refused applications and durable-storage availability."}`
- source: `packages/experimental/cua/src/access.ts:80:3`

#### `@deepseek-ai/dsh-cua#cuaAccess/enablePersistentPtc`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Persist in-memory PTC execution through the existing profile editor and Loader lifecycle.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/enablePersistentPtc:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/cua/src/access.ts:67:9`

#### `@deepseek-ai/dsh-cua#cuaAccess/openSettings`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Open the macOS privacy pane selected by the user.
- **参数**：
  - `permission` (wire `permission`, source `json`) schema=`{"type":"string","enum":["accessibility","screenRecording"]}`
  - `locale` (wire `locale`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/openSettings:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/cua/src/access.ts:122:9`

#### `@deepseek-ai/dsh-cua#cuaAccess/ptcConfiguration`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Read PTC execution state separately from native permission checks.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/ptcConfiguration:result` (strict) schema=`{"type":"object","properties":{"persistent":{"type":"boolean"},"writable":{"type":"boolean"}},"required":["persistent","writable"],"additionalProperties":true,"description":"Whether the shared runtime retains memory and has an editable profile entry."}`
- source: `packages/experimental/cua/src/access.ts:55:3`

#### `@deepseek-ai/dsh-cua#cuaAccess/requestPermission`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Request the selected system privilege through the native provider.
- **参数**：
  - `permission` (wire `permission`, source `json`) schema=`{"type":"string","enum":["accessibility","screenRecording"]}`
  - `locale` (wire `locale`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cua/types#CuaSystemPermissionState` (strict) schema=`{"oneOf":[{"type":"object","properties":{"platform":{"type":"string","const":"darwin"},"accessibility":{"type":"boolean"},"screenRecording":{"type":"boolean"},"helper":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true},"parent":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true},"launchApplication":{"type":"object","properties":{"name":{"type":"string"},"path":{"type":"string"},"icon":{"type":"string"}},"required":["name","path"],"additionalProperties":true,"description":"Application macOS reports as responsible for the helper, captured at startup; absent when it cannot be identified."}},"required":["platform","accessibility","screenRecording","helper","parent"],"additionalProperties":true},{"type":"object","properties":{"platform":{"type":"string","const":"win32"},"sessionLocked":{"oneOf":[{"type":"null","const":null},{"type":"boolean","enum":[false,true]}]},"captureAvailable":{"type":"boolean"},"elevated":{"type":"boolean"},"helper":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true}},"required":["platform","sessionLocked","captureAvailable","elevated","helper"],"additionalProperties":true}],"description":"Current permission observations; requesting does not establish consent."}`
- source: `packages/experimental/cua/src/access.ts:110:9`

#### `@deepseek-ai/dsh-cua#cuaAccess/retryApproval`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Clear this application's refusals across sessions so each session may ask for access again.
- **参数**：
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/retryApproval:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/cua/src/access.ts:141:9`

#### `@deepseek-ai/dsh-cua#cuaAccess/revoke`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Remove saved and session access and join affected operations.
- **参数**：
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-cua#cuaAccess/revoke:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/cua/src/access.ts:133:3`

#### `@deepseek-ai/dsh-cua#cuaAccess/systemStatus`
- service: `cuaAccess` · invocation: `direct`
- **说明**：Inspect system privileges independently of application decisions and icons.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-cua/types#CuaSystemPermissionState` (strict) schema=`{"oneOf":[{"type":"object","properties":{"platform":{"type":"string","const":"darwin"},"accessibility":{"type":"boolean"},"screenRecording":{"type":"boolean"},"helper":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true},"parent":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true},"launchApplication":{"type":"object","properties":{"name":{"type":"string"},"path":{"type":"string"},"icon":{"type":"string"}},"required":["name","path"],"additionalProperties":true,"description":"Application macOS reports as responsible for the helper, captured at startup; absent when it cannot be identified."}},"required":["platform","accessibility","screenRecording","helper","parent"],"additionalProperties":true},{"type":"object","properties":{"platform":{"type":"string","const":"win32"},"sessionLocked":{"oneOf":[{"type":"null","const":null},{"type":"boolean","enum":[false,true]}]},"captureAvailable":{"type":"boolean"},"elevated":{"type":"boolean"},"helper":{"type":"object","properties":{"pid":{"type":"number"},"path":{"type":"string"},"name":{"type":"string"}},"required":["pid"],"additionalProperties":true}},"required":["platform","sessionLocked","captureAvailable","elevated","helper"],"additionalProperties":true}],"description":"Platform-tagged access observations and native process metadata."}`
- source: `packages/experimental/cua/src/access.ts:87:9`


### `@deepseek-ai/dsh-deepseek-account`

#### `@deepseek-ai/dsh-deepseek-account#account/cancelSignIn`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Cancel only the named attempt; committing attempts settle before returning.
- **参数**：
  - `attemptId` (wire `attemptId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-deepseek-account/types#AccountView` (strict) schema=`{"type":"object","properties":{"status":{"type":"string","enum":["signed-out","credential-stored"]},"links":{"type":"object","properties":{"usageUrl":{"type":"string"},"topUpUrl":{"type":"string"}},"required":["usageUrl","topUpUrl"],"additionalProperties":true},"attempt":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"phase":{"type":"string","enum":["failed","cancelled","initializing","waiting-browser","exchanging","committing","succeeded","expired"]},"authorizeUrl":{"type":"string"},"expiresAt":{"type":"number"},"errorCode":{"type":"string","enum":["expired","no-response","network","protocol","storage"]}},"required":["id","phase"],"additionalProperties":true}]}},"required":["status","links","attempt"],"additionalProperties":true,"description":"state after cancellation or an already-started commit."}`
- source: `packages/credentials/deepseek-account/src/index.ts:534:9`

#### `@deepseek-ai/dsh-deepseek-account#account/getBalance`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Query Platform recharge and bonus wallet balances independently of profile data.
- **参数**：
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/getBalance:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"status":{"type":"string","const":"ready"},"value":{"type":"array","items":{"type":"object","properties":{"currency":{"type":"string","enum":["CNY","USD"]},"balance":{"type":"string"}},"required":["currency","balance"],"additionalProperties":true}},"bonusWallets":{"type":"array","items":{"type":"object","properties":{"currency":{"type":"string","enum":["CNY","USD"]},"balance":{"type":"string"}},"required":["currency","balance"],"additionalProperties":true}}},"required":["status","value","bonusWallets"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"failed"}},"required":["status"],"additionalProperties":true}],"description":"balance outcome, or null if signed out or the grant changed during the query."}`
- source: `packages/credentials/deepseek-account/src/index.ts:247:3`

#### `@deepseek-ai/dsh-deepseek-account#account/getNotificationContent`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Query localized content of a notification, including one already consumed.
- **参数**：
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/getNotificationContent:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"createdAt":{"type":"string"},"displayUntil":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Display deadline; null means the notification never expires."},"title":{"type":"string"},"body":{"type":"string"},"actions":{"type":"array","items":{"type":"object","properties":{"label":{"type":"string"},"style":{"type":"string","enum":["primary","secondary"]},"target":{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"app_route"},"name":{"type":"string","const":"account"}},"required":["type","name"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"dismiss"}},"required":["type"],"additionalProperties":true}]}},"required":["label","style","target"],"additionalProperties":true}},"data":{"description":"Optional business data, retained independently of the localized copy."}},"required":["id","createdAt","displayUntil","title","body","actions"],"additionalProperties":true}],"description":"content without changing consumption, or null if signed out or the grant changed."}`
- source: `packages/credentials/deepseek-account/src/index.ts:283:9`

#### `@deepseek-ai/dsh-deepseek-account#account/getNotifications`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Query unconsumed account notifications in server order without reading profile data.
- **参数**：
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/getNotifications:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"nextPollAfterSeconds":{"type":"number","description":"Positive delay in seconds before querying again, within the browser timer range."},"notifications":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"createdAt":{"type":"string"},"displayUntil":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Display deadline; null means the notification never expires."},"title":{"type":"string"},"body":{"type":"string"},"actions":{"type":"array","items":{"type":"object","properties":{"label":{"type":"string"},"style":{"type":"string","enum":["primary","secondary"]},"target":{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"app_route"},"name":{"type":"string","const":"account"}},"required":["type","name"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"dismiss"}},"required":["type"],"additionalProperties":true}]}},"required":["label","style","target"],"additionalProperties":true}},"data":{"description":"Optional business data, retained independently of the localized copy."}},"required":["id","createdAt","displayUntil","title","body","actions"],"additionalProperties":true}}},"required":["nextPollAfterSeconds","notifications"],"additionalProperties":true}],"description":"notifications with their next query delay, or null if signed out or the grant changed during the query."}`
- source: `packages/credentials/deepseek-account/src/index.ts:257:9`

#### `@deepseek-ai/dsh-deepseek-account#account/getProfile`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Query Platform profile independently of wallet balances. A ready result whose stable profile ID first becomes available or changes notifies identity-enabled watch consumers, so they re-read getPlatformSession; repeated IDs stay silent.
- **参数**：
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/getProfile:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"status":{"type":"string","const":"ready"},"value":{"type":"object","properties":{"id":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"name":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"contact":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"avatarUrl":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Profile image URL supplied by Platform, absent when no picture is configured."}},"required":["id","name","contact"],"additionalProperties":true}},"required":["status","value"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"failed"}},"required":["status"],"additionalProperties":true}],"description":"profile outcome, or null if signed out or the grant changed during the query."}`
- source: `packages/credentials/deepseek-account/src/index.ts:228:9`

#### `@deepseek-ai/dsh-deepseek-account#account/getState`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Read stored-account presence and the latest login attempt.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-deepseek-account/types#AccountView` (strict) schema=`{"type":"object","properties":{"status":{"type":"string","enum":["signed-out","credential-stored"]},"links":{"type":"object","properties":{"usageUrl":{"type":"string"},"topUpUrl":{"type":"string"}},"required":["usageUrl","topUpUrl"],"additionalProperties":true},"attempt":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"phase":{"type":"string","enum":["failed","cancelled","initializing","waiting-browser","exchanging","committing","succeeded","expired"]},"authorizeUrl":{"type":"string"},"expiresAt":{"type":"number"},"errorCode":{"type":"string","enum":["expired","no-response","network","protocol","storage"]}},"required":["id","phase"],"additionalProperties":true}]}},"required":["status","links","attempt"],"additionalProperties":true,"description":"a snapshot without credentials or PKCE secrets."}`
- source: `packages/credentials/deepseek-account/src/index.ts:206:9`

#### `@deepseek-ai/dsh-deepseek-account#account/hasRunningAccountTasks`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Inspect running work before sign-out.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/hasRunningAccountTasks:result` (strict) schema=`{"type":"boolean","description":"whether a running task's latest request uses the account route; false when the optional agents service is absent."}`
- source: `packages/credentials/deepseek-account/src/index.ts:578:3`

#### `@deepseek-ai/dsh-deepseek-account#account/reportNotificationEvent`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Report a notification interaction; the backend decides consumption.
- **参数**：
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
  - `event` (wire `event`, source `json`) schema=`{"type":"string","enum":["displayed","cta_clicked","dismissed"]}`
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/reportNotificationEvent:result` (strict) schema=`{"type":"boolean","description":"true once the server accepts the event; false if signed out or credentials changed during the call."}`
- source: `packages/credentials/deepseek-account/src/index.ts:311:9`

#### `@deepseek-ai/dsh-deepseek-account#account/signOut`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Remove the local grant while retaining API keys; the provider revokes it in the background.
- **参数**：
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-deepseek-account/types#AccountView` (strict) schema=`{"type":"object","properties":{"status":{"type":"string","enum":["signed-out","credential-stored"]},"links":{"type":"object","properties":{"usageUrl":{"type":"string"},"topUpUrl":{"type":"string"}},"required":["usageUrl","topUpUrl"],"additionalProperties":true},"attempt":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"phase":{"type":"string","enum":["failed","cancelled","initializing","waiting-browser","exchanging","committing","succeeded","expired"]},"authorizeUrl":{"type":"string"},"expiresAt":{"type":"number"},"errorCode":{"type":"string","enum":["expired","no-response","network","protocol","storage"]}},"required":["id","phase"],"additionalProperties":true}]}},"required":["status","links","attempt"],"additionalProperties":true,"description":"the signed-out state after local removal; remote failures never restore the grant."}`
- source: `packages/credentials/deepseek-account/src/index.ts:552:3`

#### `@deepseek-ai/dsh-deepseek-account#account/startSignIn`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Join an active attempt or start browser authorization.
- **参数**：
  - `client` (wire `client`, source `json`) schema=`{"type":"object","properties":{"version":{"type":"string"},"locale":{"type":"string","description":"Active UI language; only its primary subtag selects the Platform wire locale."},"timezoneOffsetSeconds":{"type":"number","description":"Offset from UTC in seconds, positive east of Greenwich."}},"required":["version","locale","timezoneOffsetSeconds"],"additionalProperties":true}`
  - `callbackOrigin` (wire `callbackOrigin`, source `json`) schema=`{"type":"string"}`
  - `loginSource` (wire `loginSource`, source `json`) schema=`{"type":"string","enum":["web","desktop"]}`
- **结果**：`@deepseek-ai/dsh-deepseek-account/types#AccountView` (strict) schema=`{"type":"object","properties":{"status":{"type":"string","enum":["signed-out","credential-stored"]},"links":{"type":"object","properties":{"usageUrl":{"type":"string"},"topUpUrl":{"type":"string"}},"required":["usageUrl","topUpUrl"],"additionalProperties":true},"attempt":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"phase":{"type":"string","enum":["failed","cancelled","initializing","waiting-browser","exchanging","committing","succeeded","expired"]},"authorizeUrl":{"type":"string"},"expiresAt":{"type":"number"},"errorCode":{"type":"string","enum":["expired","no-response","network","protocol","storage"]}},"required":["id","phase"],"additionalProperties":true}]}},"required":["status","links","attempt"],"additionalProperties":true,"description":"the initial snapshot without waiting for browser approval."}`
- source: `packages/credentials/deepseek-account/src/index.ts:480:9`

#### `@deepseek-ai/dsh-deepseek-account#account/watch`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Stream account state without the Host-only identity subscription option.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-deepseek-account/types#AccountUpdate` (strict) schema=`{"type":"object","properties":{"type":{"type":"string","enum":["snapshot","credentials-changed"],"description":"Initial state and progress use snapshot; credential writes and removal use credentials-changed."},"state":{"type":"object","properties":{"status":{"type":"string","enum":["signed-out","credential-stored"]},"links":{"type":"object","properties":{"usageUrl":{"type":"string"},"topUpUrl":{"type":"string"}},"required":["usageUrl","topUpUrl"],"additionalProperties":true},"attempt":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string"},"phase":{"type":"string","enum":["failed","cancelled","initializing","waiting-browser","exchanging","committing","succeeded","expired"]},"authorizeUrl":{"type":"string"},"expiresAt":{"type":"number"},"errorCode":{"type":"string","enum":["expired","no-response","network","protocol","storage"]}},"required":["id","phase"],"additionalProperties":true}]}},"required":["status","links","attempt"],"additionalProperties":true}},"required":["type","state"],"additionalProperties":true,"description":"initial state, login progress, and credential-change updates."}`
- source: `packages/credentials/deepseek-account/src/index.ts:622:3`

#### `@deepseek-ai/dsh-deepseek-account#account/watchExpiry`
- service: `deepseekAccount` · invocation: `direct`
- **说明**：Subscribe to live credential expiry without replay.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-deepseek-account#account/watchExpiry:result` (strict) schema=`{"type":"string","const":"session-expired","description":"expiry notifications emitted during the subscription."}`
- source: `packages/credentials/deepseek-account/src/index.ts:588:10`


### `@deepseek-ai/dsh-deepseek-chat-import`

#### `@deepseek-ai/dsh-deepseek-chat-import#deepseekChatImport/limits`
- service: `deepseekChatImport` · invocation: `direct`
- **说明**：Report the limits the browser checks before uploading. Only the owner may import, so every other principal is refused.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-deepseek-chat-import/types#DeepseekChatImportLimits` (strict) schema=`{"type":"object","properties":{"maxUploadBytes":{"type":"number","description":"Largest export archive, in bytes, one upload may carry."}},"required":["maxUploadBytes"],"additionalProperties":true,"description":"the largest accepted archive size."}`
- source: `packages/experimental/deepseek-chat-import/src/index.ts:112:3`


### `@deepseek-ai/dsh-experimental-api-speech-to-text`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/cancelPreparation`
- service: `speechController` · invocation: `direct`
- **说明**：Explicitly cancel resource preparation.
- **参数**：
  - `providerId` (wire `providerId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-api-speech-to-text#speech/cancelPreparation:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/api-speech-to-text/src/index.ts:80:3`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/catalog`
- service: `speechController` · invocation: `direct`
- **说明**：Read provider choices without preparing a recognizer.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-api-speech-to-text/types#SpeechCatalog` (strict) schema=`{"type":"object","properties":{"maxAudioBytes":{"type":"number"},"maxDurationSeconds":{"type":"number"},"providers":{"type":"array","items":{"type":"object","properties":{"preparation":{"oneOf":[{"type":"object","properties":{"phase":{"type":"string","enum":["ready","cancelled","unprepared","standby"]},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","const":"downloading"},"resource":{"type":"string"},"completedBytes":{"type":"number"},"totalBytes":{"type":"number"},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","resource","completedBytes"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","enum":["checking","loading","waking","cancelling"]},"startedAt":{"type":"number"},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","startedAt"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","const":"failed"},"message":{"type":"string"},"download":{"type":"object","properties":{"resource":{"type":"string"},"source":{"type":"string"},"reason":{"type":"string","enum":["unknown","timeout","network","storage","dns","certificate","http","integrity"]},"code":{"type":"string"},"status":{"type":"number"}},"required":["resource","source","reason"],"additionalProperties":true},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","message"],"additionalProperties":true}]},"id":{"type":"string"},"name":{"type":"string"},"location":{"type":"string","enum":["host-local","cloud"]},"languages":{"type":"array","items":{"type":"string"},"description":"Accepted language hints, including automatic detection when supported."},"setupEstimate":{"type":"object","properties":{"recommendedDiskBytes":{"type":"number"},"expectedMemoryBytes":{"type":"number"},"minimumMinutes":{"type":"number"},"maximumMinutes":{"type":"number"}},"required":["recommendedDiskBytes","expectedMemoryBytes","minimumMinutes","maximumMinutes"],"additionalProperties":true},"downloadSources":{"type":"array","items":{"type":"string"},"description":"Origins offered for an explicit preparation download; omitted or empty when no choice applies."}},"required":["preparation","id","name","location","languages"],"additionalProperties":true}},"selection":{"type":"object","properties":{"providerId":{"type":"string"},"language":{"type":"string"}},"required":["providerId","language"],"additionalProperties":true}},"required":["maxAudioBytes","maxDurationSeconds","providers","selection"],"additionalProperties":true,"description":"available providers, resolved default, and recording limits."}`
- source: `packages/experimental/api-speech-to-text/src/index.ts:44:3`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/configure`
- service: `speechController` · invocation: `direct`
- **说明**：Persist the user's recognition preferences.
- **参数**：
  - `patch` (wire `patch`, source `json`) schema=`{"type":"object","properties":{"providerId":{"type":"string"},"language":{"type":"string"}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-api-speech-to-text#speech/configure:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/api-speech-to-text/src/index.ts:64:3`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/follow`
- service: `speechController` · invocation: `direct`
- **说明**：Follow provider readiness independently of Session and preparation lifetimes.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-api-speech-to-text/types#SpeechCatalog` (strict) schema=`{"type":"object","properties":{"maxAudioBytes":{"type":"number"},"maxDurationSeconds":{"type":"number"},"providers":{"type":"array","items":{"type":"object","properties":{"preparation":{"oneOf":[{"type":"object","properties":{"phase":{"type":"string","enum":["ready","cancelled","unprepared","standby"]},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","const":"downloading"},"resource":{"type":"string"},"completedBytes":{"type":"number"},"totalBytes":{"type":"number"},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","resource","completedBytes"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","enum":["checking","loading","waking","cancelling"]},"startedAt":{"type":"number"},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","startedAt"],"additionalProperties":true},{"type":"object","properties":{"phase":{"type":"string","const":"failed"},"message":{"type":"string"},"download":{"type":"object","properties":{"resource":{"type":"string"},"source":{"type":"string"},"reason":{"type":"string","enum":["unknown","timeout","network","storage","dns","certificate","http","integrity"]},"code":{"type":"string"},"status":{"type":"number"}},"required":["resource","source","reason"],"additionalProperties":true},"step":{"type":"string","enum":["check","model","vad","verify","load"]},"steps":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["check","model","vad","verify","load"]},"status":{"type":"string","enum":["running","failed","pending","complete","cancelled"]},"startedAt":{"type":"number"}},"required":["kind","status"],"additionalProperties":true}}},"required":["phase","message"],"additionalProperties":true}]},"id":{"type":"string"},"name":{"type":"string"},"location":{"type":"string","enum":["host-local","cloud"]},"languages":{"type":"array","items":{"type":"string"},"description":"Accepted language hints, including automatic detection when supported."},"setupEstimate":{"type":"object","properties":{"recommendedDiskBytes":{"type":"number"},"expectedMemoryBytes":{"type":"number"},"minimumMinutes":{"type":"number"},"maximumMinutes":{"type":"number"}},"required":["recommendedDiskBytes","expectedMemoryBytes","minimumMinutes","maximumMinutes"],"additionalProperties":true},"downloadSources":{"type":"array","items":{"type":"string"},"description":"Origins offered for an explicit preparation download; omitted or empty when no choice applies."}},"required":["preparation","id","name","location","languages"],"additionalProperties":true}},"selection":{"type":"object","properties":{"providerId":{"type":"string"},"language":{"type":"string"}},"required":["providerId","language"],"additionalProperties":true}},"required":["maxAudioBytes","maxDurationSeconds","providers","selection"],"additionalProperties":true,"description":"initial and subsequent complete readiness snapshots."}`
- source: `packages/experimental/api-speech-to-text/src/index.ts:54:10`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/prepare`
- service: `speechController` · invocation: `direct`
- **说明**：Start or join one Host-owned preparation task.
- **参数**：
  - `providerId` (wire `providerId`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"downloadSource":{"type":"string","description":"One advertised origin; providers reject unavailable sources and use a manual choice without fallback."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-api-speech-to-text#speech/prepare:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/api-speech-to-text/src/index.ts:72:3`

#### `@deepseek-ai/dsh-experimental-api-speech-to-text#speech/transcribe`
- service: `speechController` · invocation: `direct`
- **说明**：Validate and transcribe one recording through the explicit provider selection.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"audioBase64":{"type":"string"},"providerId":{"type":"string"},"language":{"type":"string"}},"required":["audioBase64"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-speech-to-text/types#Transcript` (strict) schema=`{"type":"object","properties":{"text":{"type":"string"},"audioSeconds":{"type":"number"},"inferenceSeconds":{"type":"number"}},"required":["text","audioSeconds","inferenceSeconds"],"additionalProperties":true,"description":"final transcript without adding a Session event."}`
- source: `packages/experimental/api-speech-to-text/src/index.ts:89:9`


### `@deepseek-ai/dsh-experimental-client-ui-cot-translation`

#### `@deepseek-ai/dsh-experimental-client-ui-cot-translation#cotTranslation/limits`
- service: `cotTranslation` · invocation: `direct`
- **说明**：Read accepted translation preferences and the current request limit without sending text.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-cot-translation/types#CotTranslationSnapshot` (strict) schema=`{"type":"object","properties":{"maxTextChars":{"type":"number","description":"Maximum UTF-16 text length accepted by one translation request."},"preferences":{"type":"object","properties":{"provider":{"type":"string","enum":["google","bing","deepseek-account","deepseek-official"],"description":"Explicit provider selection; requests never fall back to another provider."},"targetLanguage":{"type":"string","description":"BCP 47 language code, or auto to follow the UI language."}},"required":["provider","targetLanguage"],"additionalProperties":true,"description":"Current accepted provider and target-language preferences."},"availableProviders":{"type":"array","items":{"type":"string","enum":["google","bing","deepseek-account","deepseek-official"]},"description":"Anonymous endpoints and native paid routes currently eligible for translation."}},"required":["maxTextChars","preferences","availableProviders"],"additionalProperties":true,"description":"authoritative preferences, eligible routes, and maximum UTF-16 text length per request."}`
- source: `packages/experimental/client-ui-cot-translation/src/index.ts:47:9`

#### `@deepseek-ai/dsh-experimental-client-ui-cot-translation#cotTranslation/translate`
- service: `cotTranslation` · invocation: `direct`
- **说明**：Translate one displayed fragment through the reader's selected provider.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"text":{"type":"string","description":"Complete text submitted to the selected provider."},"targetLanguage":{"type":"string","description":"Destination language; common Chinese locale tags are normalized per provider."},"sourceLanguage":{"type":"string","description":"Source language; omission uses automatic detection."},"provider":{"type":"string","enum":["google","bing","deepseek-account","deepseek-official"],"description":"Endpoint selection; omission uses the service's configured provider."},"sessionId":{"type":"string","description":"Existing Session for durable results; a cache miss requires it to be active. Omission keeps the call stateless."}},"required":["text","targetLanguage"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-cot-translation#cotTranslation/translate:result` (strict) schema=`{"type":"string","description":"translated text; an uncached inactive Session joins ordinary GUI activation before retry. Failures omit the source and provider response. Cancellation stops this caller's wait, not shared activation."}`
- source: `packages/experimental/client-ui-cot-translation/src/index.ts:64:9`


### `@deepseek-ai/dsh-experimental-client-ui-forge`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/branches`
- service: `forgePanel` · invocation: `direct`
- **说明**：List the local branches that can start a worktree of the Session's current checkout.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeBranches` (strict) schema=`{"type":"object","properties":{"current":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Checked-out branch, or null when HEAD is detached."},"branches":{"type":"array","items":{"type":"string"},"description":"Local branch names, `current` first and then most recently committed first, at most `maxBranches`."}},"required":["current","branches"],"additionalProperties":true,"description":"the checked-out branch and at most `maxBranches` local branches, the checked-out one first."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:222:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/cancelWorktree`
- service: `forgePanel` · invocation: `direct`
- **说明**：Withdraw the open worktree request of a Session with its failed attempt, which lets a waiting message go on in the current checkout; without a request the Session is unchanged. Withdrawing needs no worktree service.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/cancelWorktree:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:748:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestChecks`
- service: `forgePanel` · invocation: `direct`
- **说明**：Load complete checks for the change request whose list the user opened.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `headSha` (wire `headSha`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-forge/types#ChangeRequestSnapshot` (strict) schema=`{"type":"object","properties":{"ref":{"type":"object","properties":{"repository":{"type":"object","properties":{"forge":{"type":"string","description":"Provider family that serves the repository, such as `github`."},"host":{"type":"string","description":"Lowercase host name, such as `github.com`."},"owner":{"type":"string","description":"Owner or namespace path as the host spells it."},"name":{"type":"string","description":"Repository name as the host spells it."}},"required":["forge","host","owner","name"],"additionalProperties":true,"description":"Repository that holds the change request."},"number":{"type":"number","description":"Host-assigned change request number."}},"required":["repository","number"],"additionalProperties":true,"description":"Change request the snapshot describes."},"url":{"type":"string","description":"Web page of the change request."},"title":{"type":"string","description":"Title as the author wrote it."},"state":{"type":"string","enum":["open","closed","merged"],"description":"Lifecycle state."},"draft":{"type":"boolean","description":"Whether the author marked the change request as a draft."},"author":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Author login, or null when the host hides it."},"headBranch":{"type":"string","description":"Branch that carries the proposed commits."},"headSha":{"type":"string","description":"Commit object name at the head of the change request."},"baseBranch":{"type":"string","description":"Branch the change request merges into."},"baseSha":{"type":"string","description":"Base commit the host recorded with `headSha`, whose merge base with the head starts the change request's diff; omitted when the provider does not report it."},"additions":{"type":"number","description":"Lines the change request adds."},"deletions":{"type":"number","description":"Lines the change request deletes."},"mergeability":{"type":"string","enum":["unknown","mergeable","conflicting"],"description":"Merge conflict status; `unknown` while the host computes it."},"mergeReady":{"type":"boolean","description":"Whether the host would merge the change request now for the signed-in user: open, not a draft, and meeting the base branch's merge rules."},"mergeMethods":{"type":"array","items":{"type":"string","enum":["merge","squash","rebase"]},"description":"Merge methods the repository accepts, the signed-in user's usual one first."},"branchUpdates":{"type":"array","items":{"type":"string","enum":["merge","rebase"]},"description":"Ways the signed-in user can bring the base branch's new commits into the head branch now; empty while the head is up to date, while the branches conflict, when the user cannot update the head branch, or when the provider cannot, so a head behind its base cannot be told apart from a current one for a user without the right to update it."},"reviewDecision":{"type":"string","enum":["none","approved","changes-requested","review-required"],"description":"Aggregate review outcome."},"reviewers":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["user","bot","team"],"description":"Whether the reviewer is a person's account, an app or bot account, or a team."},"login":{"type":"string","description":"Login, or `organization/slug` for a team."},"avatarUrl":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Avatar image URL, or null when the host reports none."},"requested":{"type":"boolean","description":"Whether a review from the reviewer is requested now."},"codeOwner":{"type":"boolean","description":"Whether the host requested the review because the reviewer owns changed paths."},"verdict":{"oneOf":[{"type":"null","const":null},{"type":"string","enum":["dismissed","approved","changes-requested","commented"]}],"description":"Outcome of the reviewer's latest submitted review, or null before the first."},"reviewedSha":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Commit the latest submitted review was on, or null before the first or when the host reports none."}},"required":["kind","login","avatarUrl","requested","codeOwner","verdict","reviewedSha"],"additionalProperties":true},"description":"Reviewers whose review is requested, in host order, then other accounts that reviewed, each once; the author is never listed."},"reviewersTruncated":{"type":"boolean","description":"Whether the host reported more review requests or reviews than the provider read, so `reviewers` may be incomplete."},"canRequestReviews":{"type":"boolean","description":"Whether the signed-in user may request reviews of the change request through its provider."},"checks":{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"Check name as the host displays it."},"state":{"type":"string","enum":["pending","neutral","success","cancelled","failure","skipped"],"description":"Normalized check outcome."},"url":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Web page for the check, or null when the host reports none."},"workflow":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Workflow that produced the check, or null when the host reports none."},"startedAt":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"ISO 8601 time the check started, or null before it starts and when the host reports none."},"completedAt":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"ISO 8601 time the check completed, or null while it runs and when the host reports none."},"rerun":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Identity a rerun of this check names, or null when the provider cannot rerun it, as for a commit status. Checks that name one identity rerun together, and their failed checks can be rerun once none of them is pending."}},"required":["name","state","url","workflow","startedAt","completedAt","rerun"],"additionalProperties":true},"description":"Checks on the head commit in host order."},"checksRollup":{"type":"string","enum":["pending","success","none","failure"],"description":"Combined check outcome."},"checksTruncated":{"type":"boolean","description":"Whether the host reported more checks than `checks` contains."},"canRerunChecks":{"type":"boolean","description":"Whether the signed-in user may rerun the failed checks that name a `rerun`."},"unresolvedThreads":{"type":"number","description":"Number of counted review threads that are not resolved."},"threadsTruncated":{"type":"boolean","description":"Whether the change request has more review threads than the provider counted, so `unresolvedThreads` is a lower bound."},"closingIssues":{"type":"array","items":{"type":"object","properties":{"repository":{"type":"object","properties":{"forge":{"type":"string","description":"Provider family that serves the repository, such as `github`."},"host":{"type":"string","description":"Lowercase host name, such as `github.com`."},"owner":{"type":"string","description":"Owner or namespace path as the host spells it."},"name":{"type":"string","description":"Repository name as the host spells it."}},"required":["forge","host","owner","name"],"additionalProperties":true,"description":"Repository that holds the issue."},"number":{"type":"number","description":"Host-assigned issue number."},"title":{"type":"string","description":"Title as the author wrote it."},"state":{"type":"string","enum":["open","closed"],"description":"Whether the issue is still open."},"url":{"type":"string","description":"Web page of the issue."}},"required":["repository","number","title","state","url"],"additionalProperties":true},"description":"Issues linked to the change request, which the host closes once it merges, in host order."},"closingIssuesTruncated":{"type":"boolean","description":"Whether the host reported more closing issues than `closingIssues` holds."},"updatedAt":{"type":"string","description":"ISO 8601 time of the host's last update to the change request."},"closedAt":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"ISO 8601 time the change request was merged or closed, or null while it is open."}},"required":["ref","url","title","state","draft","author","headBranch","headSha","baseBranch","additions","deletions","mergeability","mergeReady","mergeMethods","branchUpdates","reviewDecision","reviewers","reviewersTruncated","canRequestReviews","checks","checksRollup","checksTruncated","canRerunChecks","unresolvedThreads","threadsTruncated","closingIssues","closingIssuesTruncated","updatedAt","closedAt"],"additionalProperties":true,"description":"the complete snapshot at the displayed head."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:364:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestCommits`
- service: `forgePanel` · invocation: `direct`
- **说明**：List the commits of a change request of a Session at its current head, which the changes view can show one or several of instead of the whole change request.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestCommits:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the list was read at."},"commits":{"type":"array","items":{"type":"object","properties":{"sha":{"type":"string","description":"Full commit object name."},"parent":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Full object name of the first parent, or null for a root commit."},"title":{"type":"string","description":"First line of the commit message."},"author":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Author name or login as the host reports it, or null when it reports none."},"authoredAt":{"type":"string","description":"ISO 8601 time the commit was authored."}},"required":["sha","parent","title","author","authoredAt"],"additionalProperties":true},"description":"Commits oldest first, ending with the head commit unless `truncated`."},"truncated":{"type":"boolean","description":"Whether the change request has more commits than the provider lists; the listed ones are the oldest."}},"required":["headSha","commits","truncated"],"additionalProperties":true}],"description":"the commits oldest first with the head they were read at, or null when the provider does not read commits."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:384:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestDiff`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read the changes of a change request of a Session as its code host computes them, with each file's layer following the root `.gitattributes` of the commit the diff ends at. Without `commits` the diff covers the change request at the head commit of its latest status; a patch already read at the same head commit and base branch is reused from memory with its attributes, for any Session, until `maxCachedDiffBytes` evicts it. With `commits`, it covers those commits, from the first one's first parent to the last, and is read every time.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `commits` (wire `commits`, source `json`) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"from":{"type":"string","description":"First, oldest commit shown."},"to":{"type":"string","description":"Last, newest commit shown; equal to `from` for one commit."}},"required":["from","to"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeChangeRequestDiff` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/experimental/client-ui-forge/src/index.ts:413:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestReview`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read the review threads of a change request of a Session at the head commit of its displayed diff. Threads read at the same head commit and update time are reused from memory, for any Session, until they are `reviewRefreshMs` old, `maxCachedReviewBytes` evicts them, or a review write through this panel drops them; a read again after that age, or a `fresh` read, shows threads resolved elsewhere since, which do not change a GitHub pull request's update time.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `headSha` (wire `headSha`, source `json`) schema=`{"type":"string"}`
  - `fresh` (wire `fresh`, source `json`) schema=`{"type":"boolean"}`
- **结果**：`@deepseek-ai/dsh-experimental-forge/types#ForgeReviewData` (strict) schema=`{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the threads were read at; `current` positions number its files."},"viewer":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Login of the signed-in user the provider read as, or null when the host does not name one."},"threads":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Host identity of the thread."},"path":{"type":"string","description":"Repository-relative path the thread is on."},"side":{"type":"string","enum":["L","R"],"description":"Old (`L`) or new (`R`) side of the diff the lines number."},"subject":{"type":"string","enum":["file","line"],"description":"Whether the thread is on lines or on the whole file."},"current":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"commit":{"type":"string","description":"Full object name of the commit the diff's new side shows: new-side (`R`) lines number this commit's file, and old-side (`L`) lines number the file at the diff's base."},"startLine":{"type":"number","description":"First line, inclusive."},"endLine":{"type":"number","description":"Last line, inclusive."}},"required":["commit","startLine","endLine"],"additionalProperties":true}],"description":"Lines in the diff that ends at the head commit of the read, whose `commit` is that head; null for an outdated or file thread."},"original":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"commit":{"type":"string","description":"Full object name of the commit the diff's new side shows: new-side (`R`) lines number this commit's file, and old-side (`L`) lines number the file at the diff's base."},"startLine":{"type":"number","description":"First line, inclusive."},"endLine":{"type":"number","description":"Last line, inclusive."}},"required":["commit","startLine","endLine"],"additionalProperties":true}],"description":"Lines in the diff that ended at the commit the thread was written on; null for a file thread."},"diffHunk":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Diff hunk the host recorded when the thread was written, ending at its last line; null when it recorded none."},"resolved":{"type":"boolean","description":"Whether the thread is marked resolved."},"viewerCanReply":{"type":"boolean","description":"Whether the signed-in user can reply to the thread through `writeReview`; false for a provider without it."},"viewerCanResolve":{"type":"boolean","description":"Whether the signed-in user can mark the thread resolved, or unresolved when `resolved`, through `writeReview`; false for a provider without it."},"comments":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Host identity of the comment."},"author":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"login":{"type":"string","description":"Login as the host spells it."},"avatarUrl":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Avatar image URL, or null when the host reports none."},"bot":{"type":"boolean","description":"Whether the account is an app or bot rather than a person."}},"required":["login","avatarUrl","bot"],"additionalProperties":true}],"description":"Author, or null when the account no longer exists."},"body":{"type":"string","description":"Markdown source as the author wrote it; it may contain raw HTML, which readers must not render as HTML."},"createdAt":{"type":"string","description":"ISO 8601 time the comment was created."},"pending":{"type":"boolean","description":"Whether the comment belongs to the signed-in user's review that is not submitted yet, which only that user sees."},"url":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Web page of the comment, or null when the host reports none."},"viewerCanEdit":{"type":"boolean","description":"Whether the signed-in user can replace the comment's text through `writeReview`; false for a provider without it."},"viewerCanDelete":{"type":"boolean","description":"Whether the signed-in user can delete the comment through `writeReview`; false for a provider without it."}},"required":["id","author","body","createdAt","pending","url","viewerCanEdit","viewerCanDelete"],"additionalProperties":true},"description":"Comments oldest first; the first starts the thread."}},"required":["id","path","side","subject","current","original","diffHunk","resolved","viewerCanReply","viewerCanResolve","comments"],"additionalProperties":true},"description":"Threads in host order, at most the provider's limit."},"truncated":{"type":"boolean","description":"Whether the change request has more threads than `threads` holds."},"pendingReview":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"id":{"type":"string","description":"Host identity of the review."},"comments":{"type":"number","description":"Comments the review holds."}},"required":["id","comments"],"additionalProperties":true}],"description":"The signed-in user's pending review, or null without one."},"viewerCanReview":{"type":"boolean","description":"Whether the signed-in user can add comments to a pending review and submit or discard it through `writeReview`; false for a provider without it."}},"required":["headSha","viewer","threads","truncated","pendingReview","viewerCanReview"],"additionalProperties":true,"description":"the threads at `headSha`, with `current` positions numbering the files of that diff."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:527:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestReviewWrite`
- service: `forgePanel` · invocation: `direct`
- **说明**：Write to the review threads or the pending review of a change request of a Session while its head is still the head the user saw. The threads kept for the change request are dropped once the host answers, so the next read shows the write, which a resolve does not show through a GitHub pull request's update time.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `write` (wire `write`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"reply"},"thread":{"type":"string"},"body":{"type":"string"},"pending":{"type":"boolean"}},"required":["headSha","kind","thread","body","pending"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"resolve"},"thread":{"type":"string"},"resolved":{"type":"boolean"}},"required":["headSha","kind","thread","resolved"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"edit-comment"},"comment":{"type":"string"},"body":{"type":"string"}},"required":["headSha","kind","comment","body"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"delete-comment"},"comment":{"type":"string"}},"required":["headSha","kind","comment"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"add-pending"},"comment":{"type":"object","properties":{"path":{"type":"string"},"side":{"type":"string","enum":["L","R"]},"startLine":{"type":"number"},"endLine":{"type":"number"},"body":{"type":"string"}},"required":["path","side","startLine","endLine","body"],"additionalProperties":true}},"required":["headSha","kind","comment"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"submit-pending"},"review":{"type":"string"},"event":{"type":"string","enum":["comment","approve","request-changes"]},"body":{"type":"string"}},"required":["headSha","kind","review","event","body"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit the user saw; providers check it before writing and refuse with `stale` once the head is another commit."},"kind":{"type":"string","const":"discard-pending"},"review":{"type":"string"}},"required":["headSha","kind","review"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-experimental-forge/types#ForgeReviewWriteResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true}},"required":["ok"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"code":{"type":"string","enum":["failed","unknown","stale","unsupported"]},"message":{"type":"string"}},"required":["ok","code","message"],"additionalProperties":true}],"description":"whether the host took the write; `stale` once the head moved, which polls the change request again, and `unknown` when the outcome must be checked on the host before the write is tried again."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:586:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestStates`
- service: `forgePanel` · invocation: `direct`
- **说明**：Stream the last known state of every change request that a listed Session the caller may read binds: the stored states first, then each state a poll changes or a new binding reveals. Listing reads no Session log: loaded Sessions report their bindings, others the cached Session summary, and a Session without one shows nothing until it is opened. Closed requests are polled at the idle cadence so reopening is observed. The stream ends when `signal` aborts or the Remote stops.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeChangeRequestStatesFrame` (strict) schema=`{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"baseline"},"states":{"type":"array","items":{"type":"object","properties":{"title":{"type":"string","description":"Title as the author wrote it."},"state":{"type":"string","enum":["open","closed","merged"],"description":"Lifecycle state."},"url":{"type":"string","description":"Web page of the change request."},"draft":{"type":"boolean","description":"Whether the author marked the change request as a draft."},"checksRollup":{"type":"string","enum":["pending","success","none","failure"],"description":"Combined check outcome."},"reviewDecision":{"type":"string","enum":["none","approved","changes-requested","review-required"],"description":"Aggregate review outcome."},"mergeability":{"type":"string","enum":["unknown","mergeable","conflicting"],"description":"Merge conflict status; `unknown` while the host computes it."},"number":{"type":"number","description":"Change request number on its code host."}},"required":["title","state","url","draft","checksRollup","reviewDecision","mergeability","number"],"additionalProperties":true}}},"required":["type","states"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"changed"},"states":{"type":"array","items":{"type":"object","properties":{"title":{"type":"string","description":"Title as the author wrote it."},"state":{"type":"string","enum":["open","closed","merged"],"description":"Lifecycle state."},"url":{"type":"string","description":"Web page of the change request."},"draft":{"type":"boolean","description":"Whether the author marked the change request as a draft."},"checksRollup":{"type":"string","enum":["pending","success","none","failure"],"description":"Combined check outcome."},"reviewDecision":{"type":"string","enum":["none","approved","changes-requested","review-required"],"description":"Aggregate review outcome."},"mergeability":{"type":"string","enum":["unknown","mergeable","conflicting"],"description":"Merge conflict status; `unknown` while the host computes it."},"number":{"type":"number","description":"Change request number on its code host."}},"required":["title","state","url","draft","checksRollup","reviewDecision","mergeability","number"],"additionalProperties":true}}},"required":["type","states"],"additionalProperties":true}],"description":"frames in publication order."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:198:10`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestText`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read one file of a change request's repository at a commit, which supplies the unchanged lines between the hunks of its diff.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `commit` (wire `commit`, source `json`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestText:result` (strict) schema=`{"type":"string","description":"the text."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:458:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestViewed`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read the signed-in user's viewed marks on the files of a change request of a Session, which the host keeps for the whole change request.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `headSha` (wire `headSha`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/changeRequestViewed:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/experimental/client-ui-forge/src/index.ts:478:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/continueInProject`
- service: `forgePanel` · invocation: `direct`
- **说明**：Move a Session from its created worktree to the source checkout the worktree came from; the Session no longer works in the worktree. Runs as Agent maintenance, inside the wait of a message that waits for the removed worktree, which then goes on.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/continueInProject:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:829:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/diffBases`
- service: `forgePanel` · invocation: `direct`
- **说明**：List the branches the `branch` scope of the Session's current checkout can compare with.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `query` (wire `query`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeBaseBranches` (strict) schema=`{"type":"object","properties":{"automatic":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"name":{"type":"string","description":"The created worktree's base branch or abbreviated base commit, or the default branch of the code host remote."},"worktree":{"type":"boolean","description":"Whether the fork point is the base commit of the worktree the Session created rather than a merge base."}},"required":["name","worktree"],"additionalProperties":true}],"description":"The fork point used while no base branch is chosen, whatever the query; null without one."},"remote":{"type":"array","items":{"type":"object","properties":{"ref":{"type":"string","description":"Full ref name: `refs/heads/<branch>` or `refs/remotes/<remote>/<branch>`."},"name":{"type":"string","description":"The ref without `refs/heads/` or `refs/remotes/`, such as `master` or `origin/master`."}},"required":["ref","name"],"additionalProperties":true},"description":"Remote-tracking branches without symbolic refs such as `origin/HEAD`, most recently committed first, at most `maxBranches`."},"local":{"type":"array","items":{"type":"object","properties":{"ref":{"type":"string","description":"Full ref name: `refs/heads/<branch>` or `refs/remotes/<remote>/<branch>`."},"name":{"type":"string","description":"The ref without `refs/heads/` or `refs/remotes/`, such as `master` or `origin/master`."}},"required":["ref","name"],"additionalProperties":true},"description":"Local branches other than the checked-out one, most recently committed first, at most `maxBranches`."}},"required":["automatic","remote","local"],"additionalProperties":true,"description":"the automatic fork point and at most `maxBranches` remote-tracking and local branches each, most recently committed first, without the checked-out branch."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:236:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/dismiss`
- service: `forgePanel` · invocation: `direct`
- **说明**：Hide a visible binding of a Session; other URLs leave the Session unchanged.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/dismiss:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:268:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/follow`
- service: `forgePanel` · invocation: `direct`
- **说明**：Stream the panel state of a Session: the current state first, then each later state. Intermediate states may be skipped when the reader is slower than the updates. The stream ends when `signal` aborts or the Remote stops.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgePanelState` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/experimental/client-ui-forge/src/index.ts:181:10`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/localCommits`
- service: `forgePanel` · invocation: `direct`
- **说明**：List the commits of the `branch` scope of the Session's current checkout, which the changes view can show one or several of instead of the whole scope.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `base` (wire `base`, source `json`) schema=`{"oneOf":[{"type":"null","const":null},{"type":"string"}]}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeLocalCommits` (strict) schema=`{"type":"object","properties":{"headSha":{"type":"string","description":"HEAD commit the list was read at."},"commits":{"type":"array","items":{"type":"object","properties":{"sha":{"type":"string","description":"Full commit object name."},"parent":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Full object name of the first parent, or null for a root commit."},"title":{"type":"string","description":"First line of the commit message."},"author":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Author name or login as the host reports it, or null when it reports none."},"authoredAt":{"type":"string","description":"ISO 8601 time the commit was authored."}},"required":["sha","parent","title","author","authoredAt"],"additionalProperties":true},"description":"Commits oldest first, ending with HEAD's commit."},"truncated":{"type":"boolean","description":"Whether the branch has more commits than `maxCommits`; the listed ones are the newest."}},"required":["headSha","commits","truncated"],"additionalProperties":true,"description":"the newest `maxCommits` commits between the fork point and HEAD, oldest first, and HEAD's commit."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:323:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/localDiff`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read the changes one scope covers in the checkout of the Session's current directory, with Git using the Session's sandbox policy.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `scope` (wire `scope`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"branch"},"base":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"commits":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"from":{"type":"string","description":"First, oldest commit shown."},"to":{"type":"string","description":"Last, newest commit shown; equal to `from` for one commit."}},"required":["from","to"],"additionalProperties":true}]}},"required":["kind","base","commits"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"uncommitted"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"unstaged"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"staged"}},"required":["kind"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge/types#ForgeLocalDiff` (strict) schema=`{"type":"object","properties":{"base":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Ref or abbreviated commit the `branch` scope compares with, such as `origin/master`; null for other scopes."},"files":{"type":"array","items":{"type":"object","properties":{"path":{"type":"string","description":"Path relative to the repository root after the change, or before it for a deleted file."},"previousPath":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Path before a rename, else null."},"status":{"type":"string","enum":["deleted","added","modified","renamed"],"description":"How the file changed."},"binary":{"type":"boolean","description":"Whether the content is binary, which carries no hunks."},"oversized":{"type":"boolean","description":"Whether an untracked file exceeds `maxDiffBytes`, so it carries no hunks."},"untracked":{"type":"boolean","description":"Whether Git does not track the file yet; only local diffs list such files."},"additions":{"type":"number","description":"Lines added."},"deletions":{"type":"number","description":"Lines deleted."},"hunks":{"type":"array","items":{"type":"object","properties":{"oldStart":{"type":"number","description":"First old line the hunk covers, or the old line it comes before when it covers none."},"oldLines":{"type":"number","description":"Old lines the hunk covers."},"newStart":{"type":"number","description":"First new line the hunk covers, or the new line it comes before when it covers none."},"newLines":{"type":"number","description":"New lines the hunk covers."},"lines":{"type":"array","items":{"type":"string"},"description":"Lines in patch form: a leading space for context, `+` for added, `-` for deleted, and `\\` for a missing final newline."}},"required":["oldStart","oldLines","newStart","newLines","lines"],"additionalProperties":true},"description":"Hunks in file order; none for a binary file or a change of mode or name only."},"layer":{"type":"string","enum":["interface","implementation","test"],"description":"Review layer the path falls in."},"digest":{"type":"string","description":"Digest of the file's change: its paths, status, and hunks, plus the blob names of a binary change, or the content of an untracked binary file. Equal digests describe the same change; reading the same comparison again keeps it."}},"required":["path","previousPath","status","binary","oversized","untracked","additions","deletions","hunks","layer","digest"],"additionalProperties":true},"description":"Changed files in Git's path order, untracked files last."},"omitted":{"type":"number","description":"Untracked files left out beyond `maxUntrackedFiles`."}},"required":["base","files","omitted"],"additionalProperties":true,"description":"the files, the base of the `branch` scope, and the untracked files left out."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:301:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/localText`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read the new side of one changed file in a scope, which supplies the unchanged lines between its hunks: the index for `staged`, the last chosen commit for chosen commits of the `branch` scope, else the working tree.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `scope` (wire `scope`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"branch"},"base":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"commits":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"from":{"type":"string","description":"First, oldest commit shown."},"to":{"type":"string","description":"Last, newest commit shown; equal to `from` for one commit."}},"required":["from","to"],"additionalProperties":true}]}},"required":["kind","base","commits"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"uncommitted"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"unstaged"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"staged"}},"required":["kind"],"additionalProperties":true}]}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/localText:result` (strict) schema=`{"type":"string","description":"the text."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:347:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/markReady`
- service: `forgePanel` · invocation: `direct`
- **说明**：Mark a draft change request of a Session ready for review; the change request is polled again once the host answers.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/markReady:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:610:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/merge`
- service: `forgePanel` · invocation: `direct`
- **说明**：Merge a change request of a Session while its head is still `headSha`; the change request is polled again once the host answers.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `method` (wire `method`, source `json`) schema=`{"type":"string","enum":["merge","squash","rebase"]}`
  - `headSha` (wire `headSha`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/merge:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:629:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/refresh`
- service: `forgePanel` · invocation: `direct`
- **说明**：Reinspect a followed Session's checkout, probe sign-in again, and poll its change requests at once; an unfollowed Session is unchanged.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/refresh:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:281:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/requestReviews`
- service: `forgePanel` · invocation: `direct`
- **说明**：Request reviews of a change request of a Session from more reviewers; the change request is polled again once the host answers.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `reviewers` (wire `reviewers`, source `json`) schema=`{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string","enum":["user","bot","team"],"description":"Whether the reviewer is a person's account, an app or bot account, or a team."},"login":{"type":"string","description":"Login, or `organization/slug` for a team."}},"required":["kind","login"],"additionalProperties":true}}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/requestReviews:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:666:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/requestWorktree`
- service: `forgePanel` · invocation: `direct`
- **说明**：Ask for a new worktree before the Session's first turn, replacing an open request and forgetting a failed attempt. While the next message waits in the inbox, or else at the first step proposal, the panel creates a branch from `from`, or from HEAD of the current checkout when it is null, and enters its checkout. A message that already waits after a failed or stopped attempt keeps waiting for {@link ForgePanelController.retryWorktree}.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `from` (wire `from`, source `json`) schema=`{"oneOf":[{"type":"null","const":null},{"type":"string"}]}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/requestWorktree:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:729:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/rerunChecks`
- service: `forgePanel` · invocation: `direct`
- **说明**：Rerun the failed checks of a change request of a Session while its head is still the commit whose checks the user saw; the change request is polled again once the host answers.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"headSha":{"type":"string","description":"Head commit whose checks the user saw; the provider refuses with `stale` once the head is another commit."}},"required":["headSha"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/rerunChecks:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:648:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/restoreWorktree`
- service: `forgePanel` · invocation: `direct`
- **说明**：Check out the created worktree of a Session again at its recorded directory when that directory is gone: its branch when the branch still exists, otherwise a new branch of the same name at the base commit. Changes that were never committed are not recovered. Runs as Agent maintenance, inside the wait of a message that waits for the restoration, which then goes on; without a missing directory the Session is unchanged.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/restoreWorktree:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:798:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/retryWorktree`
- service: `forgePanel` · invocation: `direct`
- **说明**：Make another attempt, with a new branch name, at the worktree a message of the Session waits for after a failed or stopped attempt.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/retryWorktree:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:777:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/reviewerCandidates`
- service: `forgePanel` · invocation: `direct`
- **说明**：List accounts a review of a change request of a Session can be requested from.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `query` (wire `query`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/reviewerCandidates:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"login":{"type":"string","description":"Login as the host spells it."},"name":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Display name, or null when the account shows none."},"avatarUrl":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Avatar image URL, or null when the host reports none."},"suggested":{"type":"boolean","description":"Whether the host suggests the account for this change request, as from the history of its changed files."}},"required":["login","name","avatarUrl","suggested"],"additionalProperties":true},"description":"the accounts, the host's suggestions first."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:687:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/setFileViewed`
- service: `forgePanel` · invocation: `direct`
- **说明**：Set or clear the signed-in user's viewed mark on one file of a change request of a Session.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"path":{"type":"string","description":"Repository-relative path of the changed file."},"viewed":{"type":"boolean","description":"Whether the file is viewed."},"headSha":{"type":"string","description":"Head commit whose changes the user saw; the provider refuses with `stale` once the head is another commit."}},"required":["path","viewed","headSha"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/setFileViewed:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:500:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/stopCreation`
- service: `forgePanel` · invocation: `direct`
- **说明**：Stop the creation a message of the Session waits for; the message keeps waiting with the request still open. Without such a creation the Session is unchanged.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/stopCreation:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:764:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/submitReview`
- service: `forgePanel` · invocation: `direct`
- **说明**：Publish a line comment or completed review for a visible Session binding. The threads kept for the change request are dropped once the host answers, so the next read shows the comments.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"headSha":{"type":"string","description":"Commit the user reviewed; providers must check it before writing and address that commit explicitly."},"kind":{"type":"string","const":"comment"},"comment":{"type":"object","properties":{"path":{"type":"string"},"side":{"type":"string","enum":["L","R"]},"startLine":{"type":"number"},"endLine":{"type":"number"},"body":{"type":"string"}},"required":["path","side","startLine","endLine","body"],"additionalProperties":true}},"required":["headSha","kind","comment"],"additionalProperties":true},{"type":"object","properties":{"headSha":{"type":"string","description":"Commit the user reviewed; providers must check it before writing and address that commit explicitly."},"kind":{"type":"string","const":"review"},"event":{"type":"string","enum":["comment","approve","request-changes"]},"body":{"type":"string"},"comments":{"type":"array","items":{"type":"object","properties":{"path":{"type":"string"},"side":{"type":"string","enum":["L","R"]},"startLine":{"type":"number"},"endLine":{"type":"number"},"body":{"type":"string"}},"required":["path","side","startLine","endLine","body"],"additionalProperties":true}}},"required":["headSha","kind","event","body","comments"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-experimental-forge/types#ForgeReviewResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"url":{"type":"string"}},"required":["ok","url"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"code":{"type":"string","enum":["failed","unknown","stale","unsupported"]},"message":{"type":"string"}},"required":["ok","code","message"],"additionalProperties":true}],"description":"confirmed publication or a typed failure; unknown outcomes require reconciliation on the host."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:558:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/track`
- service: `forgePanel` · invocation: `direct`
- **说明**：Bind a change request to a Session by URL, or restore a dismissed binding.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/track:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:253:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/updateBranch`
- service: `forgePanel` · invocation: `direct`
- **说明**：Bring the base branch's new commits into the head branch of a change request of a Session while its head is still `headSha`; the change request is polled again once the host answers.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `method` (wire `method`, source `json`) schema=`{"type":"string","enum":["merge","rebase"]}`
  - `headSha` (wire `headSha`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/updateBranch:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/experimental/client-ui-forge/src/index.ts:708:9`

#### `@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/worktreeCleanup`
- service: `forgePanel` · invocation: `direct`
- **说明**：Read or await the worktree service's archive cleanup of the Session's checkout.
- **参数**：
  - `session` (wire `sessionId`, source `lookup`) schema=`{"type":"string"}`
  - `revision` (wire `revision`, source `json`) schema=`{"oneOf":[{"type":"null","const":null},{"type":"number"}]}`
- **结果**：`@deepseek-ai/dsh-experimental-client-ui-forge#forgePanel/worktreeCleanup:result` (strict) schema=`{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"revision":{"type":"number","description":"Monotonic attempt number within this Host lifetime; a Remote waits on a specific one."},"status":{"type":"string","enum":["failed","retained","scheduled","removed"],"description":"`scheduled` until the background inspection ends; `retained` when a use, policy, or Git state keeps the checkout; `removed` after `git worktree remove`; `failed` when removal threw and may have left a partial directory."}},"required":["revision","status"],"additionalProperties":true}],"description":"the cleanup state, or null without a worktree service, an attempt, or a current revision."}`
- source: `packages/experimental/client-ui-forge/src/index.ts:210:9`


### `@deepseek-ai/dsh-experimental-liveshare`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/addSessions`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Add source Sessions to one share this host already publishes.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions to add; ids already served by the share are ignored."}},"required":["shareId","sessionIds"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#ShareSessions` (strict) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"sessionIds":{"type":"array","items":{"type":"string"}}},"required":["shareId","sessionIds"],"additionalProperties":true,"description":"The source Sessions the share now serves."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:67:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/audit`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Read the Liveshare server's durable audit trail for one share.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shareId":{"type":"string"}},"required":["shareId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#ShareAudit` (strict) schema=`{"type":"object","properties":{"events":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string"},"action":{"type":"string"},"createdAt":{"type":"string"},"actor":{"type":"string"},"detail":{}},"required":["id","action","createdAt"],"additionalProperties":true}}},"required":["events"],"additionalProperties":true,"description":"The audit events, or a structured failure when the Liveshare server cannot answer."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:144:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/capabilities`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Read the endpoints plugins currently offer.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#ShareCapabilityOffers` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/experimental/liveshare/src/host/share-remote.ts:111:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/create`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Publish one Session and store the share.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"},"sessionTitle":{"type":"string","description":"Display title; the Session id is used when this is absent or empty."},"accessMode":{"type":"string","enum":["open","selected"],"description":"Access mode to store with the share. Legacy and direct-API use only: the shipped Share dialog creates `open` shares and sends no access mode, while stored `selected` records and callers that invoke this Remote directly still set it."},"ttlMinutes":{"type":"number","description":"Lifetime in minutes; absent means the share never expires."},"allowedSubjectIds":{"type":"array","items":{"type":"string"},"description":"Viewers named on a `selected` share, stored beside the deployment's allowed subjects. Legacy and direct-API use only: the shipped Share dialog creates `open` shares and sends no subjects."},"allowsFork":{"type":"boolean"},"sessionMode":{"type":"string","enum":["write","view"]}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#CreatedShare` (strict) schema=`{"type":"object","properties":{"link":{"type":"string"},"shareId":{"type":"string"},"sessionId":{"type":"string","description":"Primary source Session, for callers that predate `sessionIds`; derived from its first entry."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Every source Session this share serves, primary first; the authoritative list."},"sessionMode":{"type":"string","enum":["write","view"]},"access":{"type":"object","properties":{"mode":{"type":"string","enum":["open","selected"]},"selected":{"type":"array","items":{"type":"object","properties":{"providerId":{"type":"string"},"tenantId":{"type":"string"},"subjectId":{"type":"string"},"identityKey":{"type":"string"}},"required":["providerId","tenantId","subjectId","identityKey"],"additionalProperties":true}},"deploymentAllowedSubjectIds":{"type":"array","items":{"type":"string"}},"shareAllowedSubjectIds":{"type":"array","items":{"type":"string"}},"broadenedByDeploymentSubjects":{"type":"boolean"},"identityKeyAcl":{"type":"boolean","const":true}},"required":["mode","selected","deploymentAllowedSubjectIds","shareAllowedSubjectIds","broadenedByDeploymentSubjects","identityKeyAcl"],"additionalProperties":true}},"required":["link","shareId","sessionId","sessionIds","sessionMode","access"],"additionalProperties":true,"description":"The created share's link and stored values."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:59:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/identity`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Report this host's owner identity for one Liveshare server address.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"relay":{"type":"string"}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#OwnerIdentityStatus` (strict) schema=`{"type":"object","properties":{"state":{"type":"string","enum":["expired","verified","unverified","relay-unsupported"]},"relay":{"type":"string","description":"Relay base URL the credential is bound to. A host keeps one credential per Relay address and never presents it to another, so a viewer of this field compares it with the active address."},"displayName":{"type":"string","description":"Provider display name, when the credential carries one."},"subjectId":{"type":"string","description":"Verified subject id, which a client may show as the identity label."},"avatarUrl":{"type":"string","description":"Provider-issued avatar URL the credential carried, when it carried one."},"expiresAt":{"type":"string","description":"ISO expiry of the credential currently held."},"renewed":{"type":"boolean","description":"True when this report followed a renewal that pushed the expiry out."},"claim":{"type":"object","properties":{"claimed":{"type":"number","description":"Shares the Relay bound to this identity."},"skipped":{"type":"number","description":"Shares already bound to this identity, so the Relay left them untouched."}},"required":["claimed","skipped"],"additionalProperties":true,"description":"Automatic claim result, present once this host has run a claim pass."}},"required":["state","relay"],"additionalProperties":true,"description":"The owner identity status, without the credential."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:134:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/list`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Refresh titles and Liveshare server authority, then list this host's shares.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#OwnerShareList` (strict) schema=`{"type":"object","properties":{"shares":{"type":"array","items":{"type":"object","properties":{"shareId":{"type":"string"},"sessionId":{"type":"string","description":"Primary source Session, for callers that predate `sessionIds`; derived from its first entry."},"sessionIds":{"type":"array","items":{"type":"string"},"description":"Every source Session this share serves, primary first; the authoritative list."},"sessionTitle":{"type":"string"},"link":{"type":"string"},"createdAt":{"type":"string"},"expiresAt":{"type":"string","description":"ISO time after which the Relay denies viewers; absent means the share never expires."},"allowsFork":{"type":"boolean"},"sessionMode":{"type":"string","enum":["write","view"]},"viewerPluginAccess":{"type":"string","enum":["none","all","custom"],"description":"Global switch over every installed plugin's methods; absent reads as none."},"viewerPlugins":{"type":"array","items":{"type":"object","properties":{"plugin":{"type":"string","description":"Plugin namespace this policy applies to."},"mode":{"type":"string","enum":["none","selected","all"],"description":"Whether the share exposes every offered endpoint, none, or the explicit subset."},"endpoints":{"type":"array","items":{"type":"string"},"description":"Subset for `selected`; absent or empty exposes nothing."}},"required":["plugin","mode"],"additionalProperties":true},"description":"Per-plugin endpoint policies this share carries; an empty list means none."},"online":{"type":"boolean"},"access":{"type":"object","properties":{"mode":{"type":"string","enum":["open","selected"]},"selected":{"type":"array","items":{"type":"object","properties":{"providerId":{"type":"string"},"tenantId":{"type":"string"},"subjectId":{"type":"string"},"identityKey":{"type":"string"}},"required":["providerId","tenantId","subjectId","identityKey"],"additionalProperties":true}},"deploymentAllowedSubjectIds":{"type":"array","items":{"type":"string"}},"shareAllowedSubjectIds":{"type":"array","items":{"type":"string"}},"broadenedByDeploymentSubjects":{"type":"boolean"},"identityKeyAcl":{"type":"boolean","const":true}},"required":["mode","selected","deploymentAllowedSubjectIds","shareAllowedSubjectIds","broadenedByDeploymentSubjects","identityKeyAcl"],"additionalProperties":true,"description":"Confirmed ACL scope, absent on records written before it was recorded."}},"required":["shareId","sessionId","sessionIds","sessionTitle","link","createdAt","allowsFork","sessionMode","viewerPlugins","online"],"additionalProperties":true}}},"required":["shares"],"additionalProperties":true,"description":"Every share this host publishes."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:76:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/relay`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Read the Liveshare server address the owner saved.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#OwnerRelayState` (strict) schema=`{"type":"object","properties":{"configured":{"type":"string","description":"Address a deployment configures directly. Retained so an older Host that still reports one can be read; this build never sets it, because the owner's saved address is the only one in force."},"override":{"type":"string","description":"Address the owner saved."},"effective":{"type":"string","description":"Address new shares publish to; absent while no address is saved."}},"required":[],"additionalProperties":true,"description":"The current Liveshare server state, with both address fields absent while none is saved."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:118:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/setCapabilities`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Replace one share's exposed plugin endpoints.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"viewerPluginAccess":{"type":"string","enum":["none","all","custom"],"description":"Global switch; absent keeps the stored value."},"viewerPlugins":{"type":"array","items":{"type":"object","properties":{"plugin":{"type":"string","description":"Plugin namespace this policy applies to."},"mode":{"type":"string","enum":["none","selected","all"],"description":"Whether the share exposes every offered endpoint, none, or the explicit subset."},"endpoints":{"type":"array","items":{"type":"string"},"description":"Subset for `selected`; absent or empty exposes nothing."}},"required":["plugin","mode"],"additionalProperties":true},"description":"Per-plugin policies; absent keeps the stored value."}},"required":["shareId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#ShareCapabilities` (strict) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"viewerPluginAccess":{"type":"string","enum":["none","all","custom"]},"viewerPlugins":{"type":"array","items":{"type":"object","properties":{"plugin":{"type":"string","description":"Plugin namespace this policy applies to."},"mode":{"type":"string","enum":["none","selected","all"],"description":"Whether the share exposes every offered endpoint, none, or the explicit subset."},"endpoints":{"type":"array","items":{"type":"string"},"description":"Subset for `selected`; absent or empty exposes nothing."}},"required":["plugin","mode"],"additionalProperties":true}}},"required":["shareId","viewerPluginAccess","viewerPlugins"],"additionalProperties":true,"description":"The capability selection the share now carries."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:102:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/setRelay`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Choose the Liveshare server address later shares publish to.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"relayUrl":{"oneOf":[{"type":"null","const":null},{"type":"string"}]}},"required":["relayUrl"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#OwnerRelayState` (strict) schema=`{"type":"object","properties":{"configured":{"type":"string","description":"Address a deployment configures directly. Retained so an older Host that still reports one can be read; this build never sets it, because the owner's saved address is the only one in force."},"override":{"type":"string","description":"Address the owner saved."},"effective":{"type":"string","description":"Address new shares publish to; absent while no address is saved."}},"required":[],"additionalProperties":true,"description":"The Liveshare server state after the change."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:126:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/stop`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Stop one share locally, revoke its forks, and delete its row on the Liveshare server when reachable.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shareId":{"type":"string"}},"required":["shareId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#StopShareResult` (strict) schema=`{"type":"object","properties":{"ok":{"type":"boolean","const":true},"relay":{"type":"string","const":"unreachable"}},"required":["ok"],"additionalProperties":true,"description":"Whether the row on the Liveshare server still needs a retry."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:84:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/testPublish`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Register one throwaway share to check whether this host may publish.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string"}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#RelayPublishView` (strict) schema=`{"type":"object","properties":{"ok":{"type":"boolean"},"blocking":{"type":"boolean"},"error":{"type":"string"}},"required":["ok","blocking"],"additionalProperties":true,"description":"The Liveshare server's decision about this host's credential."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:159:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/testRelay`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Check that the effective Liveshare server answers at all.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#RelayConnectivityView` (strict) schema=`{"type":"object","properties":{"ok":{"type":"boolean"},"httpReachable":{"type":"boolean","description":"True when the address answered at all, including with a refusal an anonymous request gets."},"blocking":{"type":"boolean"},"error":{"type":"string"}},"required":["ok","httpReachable","blocking"],"additionalProperties":true,"description":"The anonymous connectivity result."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:151:3`

#### `@deepseek-ai/dsh-experimental-liveshare#liveshareShares/updatePermissions`
- service: `liveshareShares` · invocation: `direct`
- **说明**：Change one share's tier, fork switch, or both.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"sessionMode":{"type":"string","enum":["write","view"]},"allowsFork":{"type":"boolean"},"ttlMinutes":{"oneOf":[{"type":"null","const":null},{"type":"number"}],"description":"New lifetime in minutes; null clears the deadline and means the share never expires."}},"required":["shareId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-experimental-liveshare/types#SharePermissions` (strict) schema=`{"type":"object","properties":{"shareId":{"type":"string"},"sessionMode":{"type":"string","enum":["write","view"]},"allowsFork":{"type":"boolean"},"expiresAt":{"type":"string","description":"New deadline; absent means the share never expires."}},"required":["shareId","sessionMode","allowsFork"],"additionalProperties":true,"description":"The permissions the share now carries."}`
- source: `packages/experimental/liveshare/src/host/share-remote.ts:92:3`


### `@deepseek-ai/dsh-goal`

#### `@deepseek-ai/dsh-goal#goals/clear`
- service: `goals` · invocation: `direct`
- **说明**：Clear the current goal while retaining a durable tombstone and history.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `ref` (wire `ref`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#GoalRef` (strict) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true,"description":"the tombstone ref whose revision is one past the cleared snapshot."}`
- source: `packages/goal/goal/src/index.ts:435:3`

#### `@deepseek-ai/dsh-goal#goals/complete`
- service: `goals` · invocation: `direct`
- **说明**：Mark a current non-complete goal complete and disarm it.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `ref` (wire `ref`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#GoalView` (strict) schema=`{"type":"object","properties":{"roundsStarted":{"type":"number","description":"Highest admitted round number for this goal."},"createdAt":{"type":"number","description":"Epoch milliseconds of the create mutation."},"updatedAt":{"type":"number","description":"Epoch milliseconds of the latest mutation."},"activation":{"type":"string","enum":["armed","disarmed"],"description":"Process-local continuation eligibility; never persisted."},"objective":{"type":"string","description":"Human-requested completion objective."},"phase":{"type":"string","enum":["active","paused","blocked","complete"],"description":"Durable lifecycle phase."},"blockedReason":{"type":"object","properties":{"code":{"type":"string","description":"Stable lower-kebab-case classification chosen by the blocking policy."},"message":{"type":"string","description":"Non-empty explanation shown to humans and models."}},"required":["code","message"],"additionalProperties":true,"description":"Present exactly while `phase` is `blocked`."},"maxGoalRounds":{"type":"number","description":"Total admitted goal-round cap."},"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["roundsStarted","createdAt","updatedAt","activation","objective","phase","maxGoalRounds","id","revision"],"additionalProperties":true,"description":"the completed view."}`
- source: `packages/goal/goal/src/index.ts:393:3`

#### `@deepseek-ai/dsh-goal#goals/create`
- service: `goals` · invocation: `direct`
- **说明**：Create one Goal through the remote boundary.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"objective":{"type":"string"},"maxGoalRounds":{"type":"number"}},"required":["objective"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#CreateGoalResult` (strict) schema=`{"type":"object","properties":{"ref":{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}},"required":["ref"],"additionalProperties":true,"description":"the created Goal identity."}`
- source: `packages/goal/goal/src/index.ts:646:3`

#### `@deepseek-ai/dsh-goal#goals/edit`
- service: `goals` · invocation: `direct`
- **说明**：Edit objective and/or round cap without changing phase.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `ref` (wire `ref`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"objective":{"type":"string"},"maxGoalRounds":{"type":"number"}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#GoalView` (strict) schema=`{"type":"object","properties":{"roundsStarted":{"type":"number","description":"Highest admitted round number for this goal."},"createdAt":{"type":"number","description":"Epoch milliseconds of the create mutation."},"updatedAt":{"type":"number","description":"Epoch milliseconds of the latest mutation."},"activation":{"type":"string","enum":["armed","disarmed"],"description":"Process-local continuation eligibility; never persisted."},"objective":{"type":"string","description":"Human-requested completion objective."},"phase":{"type":"string","enum":["active","paused","blocked","complete"],"description":"Durable lifecycle phase."},"blockedReason":{"type":"object","properties":{"code":{"type":"string","description":"Stable lower-kebab-case classification chosen by the blocking policy."},"message":{"type":"string","description":"Non-empty explanation shown to humans and models."}},"required":["code","message"],"additionalProperties":true,"description":"Present exactly while `phase` is `blocked`."},"maxGoalRounds":{"type":"number","description":"Total admitted goal-round cap."},"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["roundsStarted","createdAt","updatedAt","activation","objective","phase","maxGoalRounds","id","revision"],"additionalProperties":true,"description":"the edited view."}`
- source: `packages/goal/goal/src/index.ts:331:3`

#### `@deepseek-ai/dsh-goal#goals/get`
- service: `goals` · invocation: `direct`
- **说明**：Read the current goal for one exact live agent.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-goal#goals/get:result` (strict) — schema 不可用：typert tool schema: unsupported undefined value
- source: `packages/goal/goal/src/index.ts:279:3`

#### `@deepseek-ai/dsh-goal#goals/pause`
- service: `goals` · invocation: `direct`
- **说明**：Pause an active goal and disarm automatic continuation.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `ref` (wire `ref`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#GoalView` (strict) schema=`{"type":"object","properties":{"roundsStarted":{"type":"number","description":"Highest admitted round number for this goal."},"createdAt":{"type":"number","description":"Epoch milliseconds of the create mutation."},"updatedAt":{"type":"number","description":"Epoch milliseconds of the latest mutation."},"activation":{"type":"string","enum":["armed","disarmed"],"description":"Process-local continuation eligibility; never persisted."},"objective":{"type":"string","description":"Human-requested completion objective."},"phase":{"type":"string","enum":["active","paused","blocked","complete"],"description":"Durable lifecycle phase."},"blockedReason":{"type":"object","properties":{"code":{"type":"string","description":"Stable lower-kebab-case classification chosen by the blocking policy."},"message":{"type":"string","description":"Non-empty explanation shown to humans and models."}},"required":["code","message"],"additionalProperties":true,"description":"Present exactly while `phase` is `blocked`."},"maxGoalRounds":{"type":"number","description":"Total admitted goal-round cap."},"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["roundsStarted","createdAt","updatedAt","activation","objective","phase","maxGoalRounds","id","revision"],"additionalProperties":true,"description":"the paused view."}`
- source: `packages/goal/goal/src/index.ts:354:3`

#### `@deepseek-ai/dsh-goal#goals/resume`
- service: `goals` · invocation: `direct`
- **说明**：Resume and arm a stopped goal, or rearm an active goal after a session-start edge, while its round budget still has capacity.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `ref` (wire `ref`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["id","revision"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-goal/client#GoalView` (strict) schema=`{"type":"object","properties":{"roundsStarted":{"type":"number","description":"Highest admitted round number for this goal."},"createdAt":{"type":"number","description":"Epoch milliseconds of the create mutation."},"updatedAt":{"type":"number","description":"Epoch milliseconds of the latest mutation."},"activation":{"type":"string","enum":["armed","disarmed"],"description":"Process-local continuation eligibility; never persisted."},"objective":{"type":"string","description":"Human-requested completion objective."},"phase":{"type":"string","enum":["active","paused","blocked","complete"],"description":"Durable lifecycle phase."},"blockedReason":{"type":"object","properties":{"code":{"type":"string","description":"Stable lower-kebab-case classification chosen by the blocking policy."},"message":{"type":"string","description":"Non-empty explanation shown to humans and models."}},"required":["code","message"],"additionalProperties":true,"description":"Present exactly while `phase` is `blocked`."},"maxGoalRounds":{"type":"number","description":"Total admitted goal-round cap."},"id":{"type":"string","description":"Stable goal identity."},"revision":{"type":"number","description":"Positive revision; every durable mutation increments it."}},"required":["roundsStarted","createdAt","updatedAt","activation","objective","phase","maxGoalRounds","id","revision"],"additionalProperties":true,"description":"the active view."}`
- source: `packages/goal/goal/src/index.ts:366:3`


### `@deepseek-ai/dsh-host-plugin-inventory`

#### `@deepseek-ai/dsh-host-plugin-inventory#pluginInventory/list`
- service: `pluginInventory` · invocation: `direct`
- **说明**：Read the Loader directly on every call. Cordis's internal plugin/status events already maintain Entry.fiber and Fiber.state, so a second cache would only add another lifecycle truth to keep synchronized. When an agent-preset roster is composed, the snapshot also carries each preset's composition rows, because those rows — not the Loader's own entries — are where a deployment that mounts the roster runs its model-facing plugins.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-host-plugin-inventory/types#PluginInventorySnapshot` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/host/plugin-inventory/src/index.ts:71:9`


### `@deepseek-ai/dsh-llm`

#### `@deepseek-ai/dsh-llm#llm/discoverModels`
- service: `llm` · invocation: `direct`
- **说明**：Remote adapter for one draft provider interrogation.
- **参数**：
  - `settingsNs` (wire `settingsNs`, source `json`) schema=`{"type":"string"}`
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"provider":{"type":"string","description":"Route the draft is editing, when it edits an existing one. A route whose adapter already knows its models answers from that knowledge instead of asking the endpoint — the adapter's own registry is the better answer, and it costs no network call."},"baseURL":{"type":"string","description":"Endpoint to interrogate. Optional because a route the adapter already describes needs none; a route it does not must supply one."},"api":{"type":"string","description":"Wire protocol the endpoint speaks, when the draft names one."},"apiKey":{"type":"string","description":"Credential for this interrogation alone; the harness never stores it."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-llm#llm/discoverModels:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Model id the endpoint accepts."},"name":{"type":"string","description":"Human-readable name when the endpoint supplies one."},"contextWindow":{"type":"number","description":"Maximum combined request and response context, when disclosed."},"maxTokens":{"type":"number","description":"Maximum output tokens, when disclosed."},"inputModalities":{"type":"array","items":{"type":"string","enum":["text","image"]},"description":"Accepted input types when disclosed by the catalog or endpoint; absent means unknown."}},"required":["id"],"additionalProperties":true},"description":"advertised models in endpoint order."}`
- source: `packages/llm/llm/src/index.ts:658:9`

#### `@deepseek-ai/dsh-llm#llm/listConfigurableProviders`
- service: `llm` · invocation: `direct`
- **说明**：List every declared configurable provider, registered or dormant.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-llm#llm/listConfigurableProviders:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"provider":{"type":"string","description":"Provider route key this entry activates when configured."},"displayName":{"type":"string","description":"Human-readable provider name for configuration surfaces."},"settingsNs":{"type":"string","description":"User-settings namespace whose section configures this provider."},"settingsPath":{"type":"array","items":{"type":"string"},"description":"Path from that namespace's section root to this provider's profile object; empty when the whole section is the profile."},"declared":{"type":"boolean","description":"Whether the owning adapter knows this route only because configuration declared it — a gateway or self-hosted server it ships nothing about. Absent means the adapter draws no such distinction; false means it does and this route is one of its own. Only the adapter can answer: a stored profile is how a user-added route AND a corrected shipped one both look from outside."},"defaultBaseURL":{"type":"string","description":"Route endpoint the adapter uses when the profile sets no `baseURL`; the adapter may still send an individual model to that model's own endpoint. Absent when the route has no fixed endpoint."},"baseURLEnv":{"type":"array","items":{"type":"string"},"description":"Environment variables used to construct a provider endpoint; absent when none are reported."},"nativeAuth":{"type":"object","properties":{"env":{"type":"array","items":{"type":"string"},"description":"Environment variables the route's authentication reads, in lookup order; empty when it reads none."},"oauth":{"type":"boolean","description":"Whether a stored OAuth sign-in can authenticate the route."}},"required":["env","oauth"],"additionalProperties":true,"description":"Authentication the adapter performs when the profile names no credential reference; absent when it reports none."},"error":{"type":"string","description":"Configuration diagnostic for repair; unaffected models may remain serviceable."}},"required":["provider","displayName","settingsNs","settingsPath"],"additionalProperties":true},"description":"detached directory entries in declaration order."}`
- source: `packages/llm/llm/src/index.ts:570:3`

#### `@deepseek-ai/dsh-llm#llm/listProviders`
- service: `llm` · invocation: `direct`
- **说明**：Describe provider routes with a registered adapter.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-llm#llm/listProviders:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"Provider route key used by {@link GenerateOptions.provider}."},"name":{"type":"string","description":"Human-readable provider name for selectors and diagnostics."}},"required":["id","name"],"additionalProperties":true},"description":"detached provider metadata in registration order."}`
- source: `packages/llm/llm/src/index.ts:498:3`


### `@deepseek-ai/dsh-mcp-manager`

#### `@deepseek-ai/dsh-mcp-manager#mcpManager/probe`
- service: `mcpManager` · invocation: `direct`
- **说明**：Probe one server for a management surface; see {@link McpServerManager.probe}.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-mcp-client/types#McpProbeResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"serverInfo":{"type":"object","properties":{"name":{"type":"string"},"version":{"type":"string"}},"required":["name","version"],"additionalProperties":true,"description":"Server-reported identity from `initialize`, when the SDK captured one."},"toolNames":{"type":"array","items":{"type":"string"},"description":"Advertised raw tool names, capped at the resolved `maxToolNames`."},"truncated":{"type":"boolean","description":"Whether the advertised list was longer than the returned `toolNames`."},"durationMs":{"type":"number","description":"Wall-clock duration of negotiation and listing, excluding cleanup, in milliseconds."},"closeConfirmed":{"type":"boolean","description":"Transport closure is confirmed, or no transport was created; unfinished negotiation remains unconfirmed."},"cleanupError":{"type":"string","description":"Cleanup failed or exceeded its budget, including after confirmed transport closure."}},"required":["ok","toolNames","truncated","durationMs","closeConfirmed"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"stage":{"type":"string","enum":["connect","list"]},"message":{"type":"string","description":"Diagnostic text of the failure."},"durationMs":{"type":"number","description":"Wall-clock duration until the failure in milliseconds."},"closeConfirmed":{"type":"boolean","description":"Transport closure is confirmed, or no transport was created; unfinished negotiation remains unconfirmed."},"cleanupError":{"type":"string","description":"Cleanup failed or exceeded its budget, including after confirmed transport closure."}},"required":["ok","stage","message","durationMs","closeConfirmed"],"additionalProperties":true}],"description":"the stage-classified probe outcome and independent cleanup result."}`
- source: `packages/mcp/mcp-manager/src/index.ts:364:3`

#### `@deepseek-ai/dsh-mcp-manager#mcpManager/restart`
- service: `mcpManager` · invocation: `direct`
- **说明**：Rebuild one server from its current entry: dispose the live instance (if any) and mount a fresh one with a fresh reconnect budget. Incomplete cleanup blocks replacement until the Host restarts.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-mcp-manager#mcpManager/restart:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/mcp/mcp-manager/src/index.ts:348:9`

#### `@deepseek-ai/dsh-mcp-manager#mcpManager/watch`
- service: `mcpManager` · invocation: `direct`
- **说明**：Stream server views for a management surface: the current list on subscription, then the complete list again after each status or entry change.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-mcp-manager#mcpManager/watch:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"name":{"type":"string","description":"The configured `servers` key or registered name; also the instance's `serverName` tool namespace."},"configured":{"type":"boolean","description":"Whether a configured or registered entry still exists; false for retained cleanup failures after removal."},"status":{"oneOf":[{"type":"object","properties":{"state":{"type":"string","const":"closed"},"result":{"type":"object","properties":{"closeConfirmed":{"type":"boolean","description":"Transport closure is confirmed, or no transport was created; unfinished negotiation remains unconfirmed."},"cleanupError":{"type":"string","description":"Cleanup failed or exceeded its budget, including after confirmed transport closure."}},"required":["closeConfirmed"],"additionalProperties":true}},"required":["state","result"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"waiting-credentials"},"lastError":{"type":"string"}},"required":["state","lastError"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"connecting","description":"A connection attempt is in flight."},"attempt":{"type":"number","description":"Consecutive failed attempts in the current outage before this one; `0` on the first-ever attempt."}},"required":["state","attempt"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"connected","description":"Connected with the current tool generation registered."},"toolCount":{"type":"number","description":"Registered tools in the live generation."},"connectedAt":{"type":"number","description":"Epoch milliseconds when connect plus initial tool sync completed."}},"required":["state","toolCount","connectedAt"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"reconnecting","description":"Waiting out the backoff delay before the next reconnect attempt."},"attempt":{"type":"number","description":"Consecutive failed attempts in the current outage."},"maxAttempts":{"type":"number","description":"Attempt budget per outage from the resolved reconnect policy."},"nextRetryAtMs":{"type":"number","description":"Epoch milliseconds when the next attempt fires."},"lastError":{"type":"string","description":"Most recent connection failure, as diagnostic text."}},"required":["state","attempt","maxAttempts","nextRetryAtMs","lastError"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"failed","description":"The supervisor stopped automatic attempts. `gave-up` exhausted the per-outage attempt budget and unregistered the tools; `reconnect-disabled` lost (or never made) the connection with reconnect off; `unclosed-generation` blocks replacement because transport closure or local cleanup is incomplete."},"reason":{"type":"string","enum":["gave-up","reconnect-disabled","unclosed-generation"],"description":"Which supervisor stop produced this terminal state."},"lastError":{"type":"string","description":"Most recent connection failure, when one was observed."}},"required":["state","reason"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"disabled"}},"required":["state"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"failed"},"reason":{"type":"string","const":"load"},"lastError":{"type":"string"}},"required":["state","reason","lastError"],"additionalProperties":true},{"type":"object","properties":{"state":{"type":"string","const":"failed"},"reason":{"type":"string","const":"cleanup"},"result":{"type":"object","properties":{"closeConfirmed":{"type":"boolean","description":"Transport closure is confirmed, or no transport was created; unfinished negotiation remains unconfirmed."},"cleanupError":{"type":"string","description":"Cleanup failed or exceeded its budget, including after confirmed transport closure."}},"required":["closeConfirmed"],"additionalProperties":true}},"required":["state","reason","result"],"additionalProperties":true}],"description":"Current runtime status."}},"required":["name","configured","status"],"additionalProperties":true},"description":"coalesced server lists until the subscriber or the manager stops."}`
- source: `packages/mcp/mcp-manager/src/index.ts:314:10`


### `@deepseek-ai/dsh-message-feedback`

#### `@deepseek-ai/dsh-message-feedback#messageFeedback/delete`
- service: `messageFeedback` · invocation: `direct`
- **说明**：Delete one item after checking its version; absence succeeds without an event.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Session that owns the feedback."},"messageId":{"type":"string","description":"Message whose feedback should be absent after this operation."},"ifVersion":{"type":"string","description":"Observed item version; ignored when the item is already absent."}},"required":["sessionId","messageId","ifVersion"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-message-feedback/types#MessageFeedbackDeleteResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"value":{"type":"object","properties":{"absent":{"type":"boolean","const":true,"description":"Stable postcondition shared by the first deletion and every retry."}},"required":["absent"],"additionalProperties":true}},"required":["ok","value"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"error":{"oneOf":[{"type":"object","properties":{"code":{"type":"string","const":"session-not-found"},"sessionId":{"type":"string"}},"required":["code","sessionId"],"additionalProperties":true},{"type":"object","properties":{"code":{"type":"string","const":"version-conflict"},"current":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"messageId":{"type":"string","description":"Stable identity of the assistant message inside the owning Session."},"rating":{"type":"string","enum":["positive","negative"],"description":"Overall positive or negative judgment."},"note":{"type":"string","description":"Optional explanation, preserved verbatim after validation."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Category the human filed the judgment under."},"version":{"type":"string","description":"Equality-only token replaced by every material create or update."},"createdAt":{"type":"number","description":"Host-assigned creation time in Unix epoch milliseconds."},"updatedAt":{"type":"number","description":"Host-assigned time of the most recent material update."}},"required":["messageId","rating","version","createdAt","updatedAt"],"additionalProperties":true}],"description":"Authoritative current item, or `null` when it does not exist."}},"required":["code","current"],"additionalProperties":true}]}},"required":["ok","error"],"additionalProperties":true}],"description":"the stable absent postcondition or an explicit failure."}`
- source: `packages/feedback/message-feedback/src/index.ts:207:3`

#### `@deepseek-ai/dsh-message-feedback#messageFeedback/list`
- service: `messageFeedback` · invocation: `direct`
- **说明**：Read current feedback from the canonical log.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Session whose feedback events should be read."}},"required":["sessionId"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-message-feedback/types#MessageFeedbackListResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"value":{"type":"object","properties":{"items":{"type":"array","items":{"type":"object","properties":{"messageId":{"type":"string","description":"Stable identity of the assistant message inside the owning Session."},"rating":{"type":"string","enum":["positive","negative"],"description":"Overall positive or negative judgment."},"note":{"type":"string","description":"Optional explanation, preserved verbatim after validation."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Category the human filed the judgment under."},"version":{"type":"string","description":"Equality-only token replaced by every material create or update."},"createdAt":{"type":"number","description":"Host-assigned creation time in Unix epoch milliseconds."},"updatedAt":{"type":"number","description":"Host-assigned time of the most recent material update."}},"required":["messageId","rating","version","createdAt","updatedAt"],"additionalProperties":true},"description":"Fresh immutable item snapshots."}},"required":["items"],"additionalProperties":true}},"required":["ok","value"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"error":{"type":"object","properties":{"code":{"type":"string","const":"session-not-found"},"sessionId":{"type":"string"}},"required":["code","sessionId"],"additionalProperties":true}},"required":["ok","error"],"additionalProperties":true}],"description":"immutable items or a definite persistence miss."}`
- source: `packages/feedback/message-feedback/src/index.ts:155:3`

#### `@deepseek-ai/dsh-message-feedback#messageFeedback/put`
- service: `messageFeedback` · invocation: `direct`
- **说明**：Create or replace feedback after checking its current version. Matching no-ops retain the version and append no event.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"sessionId":{"type":"string","description":"Persisted Session that owns the target message."},"messageId":{"type":"string","description":"Target assistant-message identity."},"rating":{"type":"string","enum":["positive","negative"],"description":"Desired overall judgment."},"note":{"type":"string","description":"Optional non-blank explanation."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Optional category; absent keeps the item uncategorized."},"ifVersion":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"Observed item version, or `null` to require that no item exists."}},"required":["sessionId","messageId","rating","ifVersion"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-message-feedback/types#MessageFeedbackPutResult` (strict) schema=`{"oneOf":[{"type":"object","properties":{"ok":{"type":"boolean","const":true},"value":{"type":"object","properties":{"messageId":{"type":"string","description":"Stable identity of the assistant message inside the owning Session."},"rating":{"type":"string","enum":["positive","negative"],"description":"Overall positive or negative judgment."},"note":{"type":"string","description":"Optional explanation, preserved verbatim after validation."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Category the human filed the judgment under."},"version":{"type":"string","description":"Equality-only token replaced by every material create or update."},"createdAt":{"type":"number","description":"Host-assigned creation time in Unix epoch milliseconds."},"updatedAt":{"type":"number","description":"Host-assigned time of the most recent material update."}},"required":["messageId","rating","version","createdAt","updatedAt"],"additionalProperties":true}},"required":["ok","value"],"additionalProperties":true},{"type":"object","properties":{"ok":{"type":"boolean","const":false},"error":{"oneOf":[{"type":"object","properties":{"code":{"type":"string","const":"session-not-found"},"sessionId":{"type":"string"}},"required":["code","sessionId"],"additionalProperties":true},{"type":"object","properties":{"code":{"type":"string","const":"target-not-found"},"sessionId":{"type":"string"},"messageId":{"type":"string"}},"required":["code","sessionId","messageId"],"additionalProperties":true},{"type":"object","properties":{"code":{"type":"string","const":"version-conflict"},"current":{"oneOf":[{"type":"null","const":null},{"type":"object","properties":{"messageId":{"type":"string","description":"Stable identity of the assistant message inside the owning Session."},"rating":{"type":"string","enum":["positive","negative"],"description":"Overall positive or negative judgment."},"note":{"type":"string","description":"Optional explanation, preserved verbatim after validation."},"category":{"type":"string","enum":["other","task-result","instruction-following","product-interaction","service-stability","resource-cost","security-privacy-permission"],"description":"Category the human filed the judgment under."},"version":{"type":"string","description":"Equality-only token replaced by every material create or update."},"createdAt":{"type":"number","description":"Host-assigned creation time in Unix epoch milliseconds."},"updatedAt":{"type":"number","description":"Host-assigned time of the most recent material update."}},"required":["messageId","rating","version","createdAt","updatedAt"],"additionalProperties":true}],"description":"Authoritative current item, or `null` when it does not exist."}},"required":["code","current"],"additionalProperties":true},{"type":"object","properties":{"code":{"type":"string","const":"note-blank"}},"required":["code"],"additionalProperties":true},{"type":"object","properties":{"code":{"type":"string","const":"note-too-large"},"maxBytes":{"type":"number"},"actualBytes":{"type":"number"}},"required":["code","maxBytes","actualBytes"],"additionalProperties":true}]}},"required":["ok","error"],"additionalProperties":true}],"description":"the durable item or an explicit business failure."}`
- source: `packages/feedback/message-feedback/src/index.ts:167:3`


### `@deepseek-ai/dsh-office-kit`

#### `@deepseek-ai/dsh-office-kit#officeKit/generation`
- service: `officeKit` · invocation: `direct`
- **说明**：Read the current rendering generation before reusing a Client PDF.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-office-kit/types#OfficeKitGeneration` (strict) schema=`{"type":"string","description":"provider lifetime, replaced with rendering, font, or engine configuration."}`
- source: `packages/document/office-kit/src/index.ts:276:3`

#### `@deepseek-ai/dsh-office-kit#officeKit/render`
- service: `officeKit` · invocation: `direct`
- **说明**：Read and convert one Office file using the Session's ordinary filesystem authorization.
- **参数**：
  - `workspaceFileScope` (wire `workspaceFileScopeId`, source `lookup`) schema=`{"type":"string"}`
  - `path` (wire `path`, source `json`) schema=`{"type":"string"}`
  - `priority` (wire `priority`, source `json`) schema=`{"type":"string","enum":["foreground","background"]}`
- **结果**：`@deepseek-ai/dsh-office-kit/types#RenderedDocumentBytes` (strict) — schema 不可用：typert tool schema: unsupported selected reference Uint8Array
- source: `packages/document/office-kit/src/index.ts:261:9`


### `@deepseek-ai/dsh-permission-presets`

#### `@deepseek-ai/dsh-permission-presets#permissionPresets/catalog`
- service: `permissionPresets` · invocation: `direct`
- **说明**：Read the complete process-level catalog exposed to current-session UI.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-permission-presets/client#PermissionCatalog` (strict) schema=`{"type":"object","properties":{"options":{"type":"array","items":{"type":"object","properties":{"value":{"type":"string","description":"Stable option value: a configured preset key, live `auto`, or derived `custom`."},"name":{"type":"string","description":"The display label."},"description":{"type":"string","description":"One user-facing sentence on what the value means; omitted when not configured."}},"required":["value","name"],"additionalProperties":true},"description":"Every currently selectable preset, in contribution order."},"defaultOptions":{"type":"array","items":{"type":"object","properties":{"value":{"type":"string","description":"Stable option value: a configured preset key, live `auto`, or derived `custom`."},"name":{"type":"string","description":"The display label."},"description":{"type":"string","description":"One user-facing sentence on what the value means; omitted when not configured."}},"required":["value","name"],"additionalProperties":true},"description":"Configured presets eligible as defaults for future sessions."},"defaultPreset":{"type":"string","description":"Effective default when the Config field is omitted."}},"required":["options","defaultOptions","defaultPreset"],"additionalProperties":true,"description":"every currently selectable preset in contribution order."}`
- source: `packages/interaction/permission-presets/src/index.ts:292:3`


### `@deepseek-ai/dsh-plugin-manager`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/cancelInstall`
- service: `pluginManager` · invocation: `direct`
- **说明**：Stop an installation this manager owns and wait until its files are back.
- **参数**：
  - `requestId` (wire `requestId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#PluginInstallCancellation` (strict) schema=`{"type":"object","properties":{"status":{"type":"string","enum":["not-running","cancelled","too-late"]}},"required":["status"],"additionalProperties":true,"description":"`cancelled` once the Git check or pnpm exited and the files are restored, `too-late` once the bundle is being applied, `not-running` for any other id."}`
- source: `packages/boot/plugin-manager/src/index.ts:1131:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/inspect`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read what a spec names before installing it.
- **参数**：
  - `spec` (wire `spec`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The registry asked first; absent, the configured one."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#PluginSpecInspection` (strict) schema=`{"oneOf":[{"type":"object","properties":{"status":{"type":"string","const":"accepted"},"kind":{"type":"string","enum":["registry","git","path","tarball"]},"name":{"type":"string"},"version":{"type":"string"},"description":{"type":"string","description":"`description` of the package manifest."},"bundle":{"oneOf":[{"type":"null","const":null},{"type":"boolean","enum":[false,true]}],"description":"Whether the package declares a bundle patch; null when the spec's form does not say."},"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The registry that answered for a name, and for the other forms the one an install of the spec asks first."},"host":{"type":"string","description":"The host a git spec or a tarball URL is fetched from, which no registry stands in for."}},"required":["status","kind","bundle","registry"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"refused"},"problem":{"type":"string","enum":["unknown","network","not-found","invalid-spec","already-installed","not-a-package","not-a-bundle"]},"reason":{"type":"string","description":"What pnpm, the registry, or the file system said."},"registries":{"type":"array","items":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"description":"The registries asked, in order, when the refusal came from asking them; `reason` is the last one's."}},"required":["status","problem","reason"],"additionalProperties":true}],"description":"The package the spec names, or why it is refused."}`
- source: `packages/boot/plugin-manager/src/index.ts:620:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/installBundle`
- service: `pluginManager` · invocation: `direct`
- **说明**：Install a package using the same pnpm implementation as dsh plugin. GitHub repositories get a connection check bounded by githubConnectionTimeoutMs before pnpm starts; only network failures or timeouts stop installation, and a stop streams the check's diagnostic as the installation's install-log run under its request id, while pnpm owns authentication and transport fallback. An HTTP(S) Git URL on another host is installed over SSH instead when access probes bounded by gitTransportTimeoutMs find that only SSH can read it. A run that fails, is cancelled, or adds a package without a bundle patch restores `package.json` and `pnpm-lock.yaml` as they were; downloaded files can stay.
- **参数**：
  - `spec` (wire `spec`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"enabled":{"type":"boolean"},"saveExact":{"type":"boolean","description":"Save the resolved dependency version without a range; applies to any bundle installation."},"requestId":{"type":"string"},"approvedBuilds":{"type":"array","items":{"type":"string"},"description":"Explicitly allow these pending packages' scripts for this profile, then install; a name no longer pending refuses the call."},"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The registry asked first; absent, the configured one. The configured fallbacks follow while a registry is unreachable or stale."},"expected":{"type":"object","properties":{"name":{"type":"string"},"version":{"type":"string"}},"required":["name","version"],"additionalProperties":true,"description":"The package and manifest version the spec must install. An installation that leaves this package missing or at another version, or that adds or changes another direct dependency, is undone with its profile files and modules before its bundle loads, and fails with `unexpected-package`; one whose package declares no bundle is undone the same way and fails with `not-bundle`, and one whose bundle patches cannot load fails as an operation error."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#ChangeResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:969:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/listBundles`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read installed, installation-provided, and offline Official catalog bundles, plus selected non-bundle names. A dependency without a bundle patch is listed, as a `not-bundle` problem, only while it is selected.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-plugin-manager#pluginManager/listBundles:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:500:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/listPlugins`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read current plugins, including why a row cannot be changed through the profile patch.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-plugin-manager#pluginManager/listPlugins:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:476:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/listVersionExemptions`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read exact plugin-version exemptions saved in this profile.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-plugin-manager#pluginManager/listVersionExemptions:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:452:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/listVersions`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read the published versions newer than an installed registry package's version, from the first registry that answers. Official bundles follow the DSH version and are not listed.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The registry asked first; absent, the one this process last installed the package from, else the configured one."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#PluginVersionList` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:680:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/readBundleDetail`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read a bundle's long description: the Markdown file its locale `meta.detail` names in `language`, otherwise its README. An installed bundle is read from its directory without network access; an official bundle the installation offers before it is installed is read from the npm file CDNs at its offered version. Nothing is cached.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
  - `language` (wire `language`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"npmFileSources":{"type":"array","items":{"type":"string","enum":["jsdelivr","unpkg","npmmirror"]}}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#BundleDetail` (strict) schema=`{"oneOf":[{"type":"object","properties":{"status":{"type":"string","const":"found"},"origin":{"type":"string","enum":["locale","readme"],"description":"`locale` for the file locale `meta.detail` names, `readme` for the package's README."},"path":{"type":"string","description":"`/`-separated path of the document inside the package."},"markdown":{"type":"string","description":"Markdown text without a byte order mark or a leading YAML front matter block."}},"required":["status","origin","path","markdown"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"none"}},"required":["status"],"additionalProperties":true}],"description":"the document with its origin and path, or `none`."}`
- source: `packages/boot/plugin-manager/src/index.ts:416:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/registries`
- service: `pluginManager` · invocation: `direct`
- **说明**：Read the registries this manager asks: the configured first one, its fallbacks in order, and what pnpm's own configuration names.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#PluginRegistries` (strict) schema=`{"type":"object","properties":{"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}]},"fallbackRegistries":{"type":"array","items":{"type":"string"}},"resolved":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The URL pnpm's own configuration names in the profile, read from pnpm; null when it could not be read."}},"required":["registry","fallbackRegistries","resolved"],"additionalProperties":true,"description":"The registries in pnpm's comparison form; null is the one pnpm's own configuration names, `resolved` as pnpm reads it now."}`
- source: `packages/boot/plugin-manager/src/index.ts:604:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/removeBundle`
- service: `pluginManager` · invocation: `direct`
- **说明**：Unload and remove a profile-owned bundle dependency through dsh plugin's pnpm path; a selected name no dependency holds is only deselected.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#ChangeResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:1148:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/setBundleEnabled`
- service: `pluginManager` · invocation: `direct`
- **说明**：Select or remove a bundle layer while retaining installed dependencies.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
  - `enabled` (wire `enabled`, source `json`) schema=`{"type":"boolean"}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#ChangeResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:947:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/setPluginEnabled`
- service: `pluginManager` · invocation: `direct`
- **说明**：Persist a plugin entry's desired enablement and apply it on live profiles.
- **参数**：
  - `id` (wire `id`, source `json`) schema=`{"type":"string"}`
  - `enabled` (wire `enabled`, source `json`) schema=`{"type":"boolean"}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#ChangeResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:929:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/setVersionExemption`
- service: `pluginManager` · invocation: `direct`
- **说明**：Grant or revoke one exact plugin/runtime exemption and reevaluate live plugins.
- **参数**：
  - `packageVersion` (wire `packageVersion`, source `json`) schema=`{"type":"string"}`
  - `runtimeVersion` (wire `runtimeVersion`, source `json`) schema=`{"type":"string"}`
  - `enabled` (wire `enabled`, source `json`) schema=`{"type":"boolean"}`
  - `acceptRisk` (wire `acceptRisk`, source `json`) schema=`{"type":"boolean","enum":[false,true]}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#ChangeResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:465:3`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/updateBundle`
- service: `pluginManager` · invocation: `direct`
- **说明**：Replace an installed bundle with a newer version. A registry copy updates to `name@version`, checked on the registry first: it must exist, declare a bundle, and accept the running DSH version, or nothing changes. A Git copy updates to the Git spec `options.spec` names, which must pin a full commit of the repository directory the copy came from; with HMR, a network failure or timeout reaching its repository stops the update before anything changes. pnpm reads a Git package only while installing it, so its bundle and compatibility are checked then. Either target installation is undone, profile files and modules included, before its bundle loads unless it installs `name` at `version`. With HMR the installed version is removed, so its plugins stop, and the target is installed with the same selection; when that installation fails or is cancelled, the removed version is installed again: a registry copy from the registry it came from, a Git copy from its saved spec. Without HMR the target is installed over the running version and the result reports the restart.
- **参数**：
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
  - `version` (wire `version`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"registry":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"The registry asked first, normally the one that answered `listVersions`; absent, as for `listVersions`."},"spec":{"type":"string","description":"The Git spec of the target version: required for a bundle listed with `update: 'git'`, where it must pin a full commit of the installed copy's repository directory, and refused for any other."},"requestId":{"type":"string","description":"Names the update's progress and the target installation's logs; `cancelInstall` stops only that installation."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-manager/types#PluginUpdateResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:738:9`

#### `@deepseek-ai/dsh-plugin-manager#pluginManager/waitForInstall`
- service: `pluginManager` · invocation: `direct`
- **说明**：Recover the result of an active installation without cancelling it.
- **参数**：
  - `requestId` (wire `requestId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-plugin-manager#pluginManager/waitForInstall:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-manager/src/index.ts:1121:9`


### `@deepseek-ai/dsh-plugin-market`

#### `@deepseek-ai/dsh-plugin-market#pluginMarket/listIndexes`
- service: `pluginMarket` · invocation: `direct`
- **说明**：List the configured index sources without fetching them.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-plugin-market#pluginMarket/listIndexes:result` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-market/src/index.ts:180:3`

#### `@deepseek-ai/dsh-plugin-market#pluginMarket/readEntryDetail`
- service: `pluginMarket` · invocation: `direct`
- **说明**：Read the long description of one listed version of a plugin market entry, from the version's source: the npm file CDNs for a public npm version, or its pinned Git commit. The Markdown file the package's locale `meta.detail` names in `language` comes first, then the package's README, then the README of the entry's `repository`, or for an npm version without one, of its `package.json` `repository`, at the default branch. An npm version from another registry has no readable package files, so only the entry's `repository` is read.
- **参数**：
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `name` (wire `name`, source `json`) schema=`{"type":"string"}`
  - `version` (wire `version`, source `json`) schema=`{"type":"string"}`
  - `language` (wire `language`, source `json`) schema=`{"type":"string"}`
  - `options` (wire `options`, source `json`) schema=`{"type":"object","properties":{"refresh":{"type":"boolean"},"npmFileSources":{"type":"array","items":{"type":"string","enum":["jsdelivr","unpkg","npmmirror"]}}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-market/types#PluginDetail` (strict) schema=`{"oneOf":[{"type":"object","properties":{"status":{"type":"string","const":"found"},"origin":{"type":"string","enum":["locale","readme","repository"]},"markdown":{"type":"string","description":"Markdown text, decoded as UTF-8."},"document":{"type":"string","description":"Relative image paths of the document resolve beside it through `GET /api/plugin-market/detail-file`."}},"required":["status","origin","markdown","document"],"additionalProperties":true},{"type":"object","properties":{"status":{"type":"string","const":"none"}},"required":["status"],"additionalProperties":true}],"description":"the document with its origin and image document id, or `none`."}`
- source: `packages/boot/plugin-market/src/index.ts:286:9`

#### `@deepseek-ai/dsh-plugin-market#pluginMarket/search`
- service: `pluginMarket` · invocation: `direct`
- **说明**：Return one page of the plugins of a configured index that match a query. Concurrent reads of a URL share one fetch; a successful document is reused for `cacheTtlMs` unless `refresh` is set. Matching and ordering read only the document; installation status and compatibility are computed for the returned page on every call.
- **参数**：
  - `url` (wire `url`, source `json`) schema=`{"type":"string"}`
  - `query` (wire `query`, source `json`) schema=`{"type":"object","properties":{"text":{"type":"string","description":"Fuzzy text matched against the package name, author, keywords, and every language of the title, description, and category and label titles. Every word must match a word in some field, as a prefix or within an edit distance of at most 2. Text without letters or digits matches every plugin."},"category":{"type":"string","description":"Category id the plugin must have."},"labels":{"type":"array","items":{"type":"string"},"description":"Label ids the plugin must all have."},"sort":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"index"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"relevance"}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"published"},"direction":{"type":"string","enum":["asc","desc"]}},"required":["kind","direction"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"key"},"id":{"type":"string"},"direction":{"type":"string","enum":["asc","desc"]}},"required":["kind","id","direction"],"additionalProperties":true}]},"offset":{"type":"number","description":"Number of matching plugins to skip; a non-negative integer."},"limit":{"type":"number","description":"Largest number of plugins returned; an integer from 1 to 100."},"refresh":{"type":"boolean","description":"Fetch again instead of using a cached document."},"fetchedAt":{"type":"number","description":"`fetchedAt` of an earlier page: answer from that document while it is still cached, even after `cacheTtlMs`, so later pages continue the same results. Without `refresh`, a replaced document is answered as without this field."}},"required":["sort","offset","limit"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-plugin-market/types#MarketSearchResult` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/boot/plugin-market/src/index.ts:229:9`

#### `@deepseek-ai/dsh-plugin-market#pluginMarket/setIndexes`
- service: `pluginMarket` · invocation: `direct`
- **说明**：Replace the configured index sources through Settings, without remounting this service. `plugin-market/changed` announces the committed list. A URL already configured is kept as written, so a client can add or remove sources beside one that `listIndexes` reports as unusable.
- **参数**：
  - `urls` (wire `urls`, source `json`) schema=`{"type":"array","items":{"type":"string"}}`
- **结果**：`@deepseek-ai/dsh-plugin-market#pluginMarket/setIndexes:result` (strict) — schema 不可用：typert tool schema: unsupported void value
- source: `packages/boot/plugin-market/src/index.ts:201:9`


### `@deepseek-ai/dsh-plugin-recommendations`

#### `@deepseek-ai/dsh-plugin-recommendations#pluginRecommendations/describe`
- service: `pluginRecommendations` · invocation: `direct`
- **说明**：Read the current catalog text for a logged card.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `callId` (wire `callId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-plugin-recommendations/types#RecommendationDetails` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/experimental/plugin-recommendations/src/index.ts:88:9`


### `@deepseek-ai/dsh-schedule`

#### `@deepseek-ai/dsh-schedule#schedule/catalog`
- service: `schedule` · invocation: `direct`
- **说明**：Read every Host task without a page bound or Session activation.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-schedule#schedule/catalog:result` (strict) schema=`{"type":"array","items":{"oneOf":[{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"after","description":"Rule discriminator for a delayed one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"afterSeconds":{"type":"number","description":"Positive safe-integer delay accepted at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","afterSeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"at","description":"Rule discriminator for an absolute one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"every","description":"Rule discriminator for a fixed-rate recurring reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"everySeconds":{"type":"number","description":"Fixed safe-integer interval, never below one minute."},"scheduledAt":{"type":"string","description":"Next anchor-aligned occurrence while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","everySeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"daily","description":"Rule discriminator for a daily wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"weekly","description":"Rule discriminator for a weekly wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit canonical IANA zone; equivalent timing edits retain the stored spelling."},"weekdays":{"type":"array","items":{"type":"number"},"description":"Unique ascending ISO weekdays, Monday 1 through Sunday 7."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","weekdays","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"cron","description":"Rule discriminator for a five-field cron wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"expression":{"type":"string","description":"Canonical five-field cron expression: minute hour day-of-month month day-of-week."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","expression","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"rrule"},"id":{"type":"string","description":"Host-generated canonical identity."},"title":{"type":"string","description":"Task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed instruction sent when an occurrence becomes due."},"rrule":{"type":"string","description":"One normalized DTSTART line and one RRULE line."},"scheduledAt":{"type":"string","description":"Next unaccepted occurrence while active, or the final accepted occurrence when ended."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["kind","id","title","prompt","rrule","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true}]},"description":"All tasks, active first, with target and execution metadata."}`
- source: `packages/schedule/schedule/src/index.ts:441:9`

#### `@deepseek-ai/dsh-schedule#schedule/create`
- service: `schedule` · invocation: `direct`
- **说明**：Create one task with a Host-generated identity for a human Remote caller.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"title":{"type":"string","description":"Task name of at most 120 characters, non-empty after trimming."},"prompt":{"type":"string","description":"Instruction sent at each occurrence; non-empty after trimming."},"timing":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"after"},"after_seconds":{"type":"number"}},"required":["kind","after_seconds"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"at"},"at":{"oneOf":[{"type":"string"},{"type":"object","properties":{"date":{"type":"string","description":"Four-digit ISO calendar date."},"time":{"type":"string","description":"Local wall-clock time with optional one-to-three digit milliseconds."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["date","time","time_zone"],"additionalProperties":true}]}},"required":["kind","at"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"every"},"every_seconds":{"type":"number"}},"required":["kind","every_seconds"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"daily"},"daily":{"type":"object","properties":{"time":{"type":"string","description":"Local HH:mm:ss time with optional one-to-three fractional digits."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["time","time_zone"],"additionalProperties":true}},"required":["kind","daily"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"weekly"},"weekly":{"type":"object","properties":{"time":{"type":"string","description":"Local HH:mm:ss time with optional one-to-three fractional digits."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."},"weekdays":{"type":"array","items":{"type":"number"},"description":"Non-empty ISO weekday set, Monday 1 through Sunday 7, without repetitions."}},"required":["time","time_zone","weekdays"],"additionalProperties":true}},"required":["kind","weekly"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"cron"},"cron":{"type":"object","properties":{"expression":{"type":"string","description":"Five-field Vixie cron expression: minute hour day-of-month month day-of-week."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["expression","time_zone"],"additionalProperties":true}},"required":["kind","cron"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"rrule"},"rrule":{"type":"string"}},"required":["kind","rrule"],"additionalProperties":true}],"description":"Authoritative typed timing with at least one future occurrence."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Deliver to one existing Session that is not a delegated child."},"sessionId":{"type":"string","description":"Existing Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"Create one Session at the first delivery."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Creation values; omission uses the Host defaults."}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Create a fresh Session at each delivery."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Creation values; omission uses the Host defaults."}},"required":["kind"],"additionalProperties":true}],"description":"Delivery destination; omission creates one Session at first delivery and reuses it."}},"required":["title","prompt","timing"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleCatalogEntry` (strict) schema=`{"oneOf":[{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"after","description":"Rule discriminator for a delayed one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"afterSeconds":{"type":"number","description":"Positive safe-integer delay accepted at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","afterSeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"at","description":"Rule discriminator for an absolute one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"every","description":"Rule discriminator for a fixed-rate recurring reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"everySeconds":{"type":"number","description":"Fixed safe-integer interval, never below one minute."},"scheduledAt":{"type":"string","description":"Next anchor-aligned occurrence while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","everySeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"daily","description":"Rule discriminator for a daily wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"weekly","description":"Rule discriminator for a weekly wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit canonical IANA zone; equivalent timing edits retain the stored spelling."},"weekdays":{"type":"array","items":{"type":"number"},"description":"Unique ascending ISO weekdays, Monday 1 through Sunday 7."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","weekdays","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"cron","description":"Rule discriminator for a five-field cron wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"expression":{"type":"string","description":"Canonical five-field cron expression: minute hour day-of-month month day-of-week."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","expression","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"rrule"},"id":{"type":"string","description":"Host-generated canonical identity."},"title":{"type":"string","description":"Task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed instruction sent when an occurrence becomes due."},"rrule":{"type":"string","description":"One normalized DTSTART line and one RRULE line."},"scheduledAt":{"type":"string","description":"Next unaccepted occurrence while active, or the final accepted occurrence when ended."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["kind","id","title","prompt","rrule","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true}],"description":"The stored task. Cancellation does not roll back an in-flight write."}`
- source: `packages/schedule/schedule/src/index.ts:363:9`

#### `@deepseek-ai/dsh-schedule#schedule/deleteInactive`
- service: `schedule` · invocation: `direct`
- **说明**：Delete every ended Host task, leaving active tasks armed. Ended tasks never schedule another delivery, so the removal changes no pending target and no timer is recomputed. Rows are enumerated and removed in one FIFO slot, so a delivery ordered behind this call ends its task after the enumeration rather than during it. The batch is one domain write: a normal failure rejects with every listed row still stored, while a backend `unknown-state` failure may have removed rows and quarantines the Host domain, so later schedule operations reject until the domain is reopened. A successful nonempty batch emits `schedule/changed` without Agent notices. A rejected batch announces `schedule/changed` because it does not establish which rows landed, and clients then re-read the catalog.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleDeleteInactiveResult` (strict) schema=`{"type":"object","properties":{"deleted":{"type":"number","description":"Ended task rows this call removed; zero when the Host held none."}},"required":["deleted"],"additionalProperties":true,"description":"Count of removed rows; zero when the Host held no ended task."}`
- source: `packages/schedule/schedule/src/index.ts:520:9`

#### `@deepseek-ai/dsh-schedule#schedule/deliveryLimits`
- service: `schedule` · invocation: `direct`
- **说明**：Read effective delivery limits without loading or activating a task.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-schedule#schedule/deliveryLimits:result` (strict) schema=`{"type":"object","properties":{"newSessionIntervalSeconds":{"type":"number"}},"required":["newSessionIntervalSeconds"],"additionalProperties":true,"description":"The configured minimum spacing between deliveries that each create a Session, in seconds."}`
- source: `packages/schedule/schedule/src/index.ts:352:3`

#### `@deepseek-ai/dsh-schedule#schedule/edit`
- service: `schedule` · invocation: `direct`
- **说明**：Update or delete one task for a human Remote caller; an invalid patch rejects with `schedule/input-invalid`.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"oneOf":[{"type":"object","properties":{"id":{"type":"string","description":"Task to change."},"action":{"type":"string","const":"update","description":"Apply `patch` as one atomic change."},"patch":{"type":"object","properties":{"title":{"type":"string","description":"Replacement task name."},"prompt":{"type":"string","description":"Replacement instruction."},"timing":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"after"},"after_seconds":{"type":"number"}},"required":["kind","after_seconds"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"at"},"at":{"oneOf":[{"type":"string"},{"type":"object","properties":{"date":{"type":"string","description":"Four-digit ISO calendar date."},"time":{"type":"string","description":"Local wall-clock time with optional one-to-three digit milliseconds."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["date","time","time_zone"],"additionalProperties":true}]}},"required":["kind","at"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"every"},"every_seconds":{"type":"number"}},"required":["kind","every_seconds"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"daily"},"daily":{"type":"object","properties":{"time":{"type":"string","description":"Local HH:mm:ss time with optional one-to-three fractional digits."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["time","time_zone"],"additionalProperties":true}},"required":["kind","daily"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"weekly"},"weekly":{"type":"object","properties":{"time":{"type":"string","description":"Local HH:mm:ss time with optional one-to-three fractional digits."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."},"weekdays":{"type":"array","items":{"type":"number"},"description":"Non-empty ISO weekday set, Monday 1 through Sunday 7, without repetitions."}},"required":["time","time_zone","weekdays"],"additionalProperties":true}},"required":["kind","weekly"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"cron"},"cron":{"type":"object","properties":{"expression":{"type":"string","description":"Five-field Vixie cron expression: minute hour day-of-month month day-of-week."},"time_zone":{"type":"string","description":"Explicit UTC or IANA Area/Location zone."}},"required":["expression","time_zone"],"additionalProperties":true}},"required":["kind","cron"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"rrule"},"rrule":{"type":"string"}},"required":["kind","rrule"],"additionalProperties":true}],"description":"Replacement timing; a changed rule recomputes the next occurrence."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Deliver to one existing Session that is not a delegated child."},"sessionId":{"type":"string","description":"Existing Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"Create one Session at the first delivery."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Creation values; omission uses the Host defaults."}},"required":["kind"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Create a fresh Session at each delivery."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Creation values; omission uses the Host defaults."}},"required":["kind"],"additionalProperties":true}],"description":"Replacement destination."},"active":{"type":"boolean","description":"`false` pauses the task; `true` resumes a recurrence from its first future occurrence."}},"required":[],"additionalProperties":true,"description":"Fields to change; at least one member is required."},"expectedUpdatedAt":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"`updatedAt` value that the editor read; a different stored value returns `schedule_conflict`."}},"required":["id","action","patch"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Task to remove."},"action":{"type":"string","const":"delete","description":"Remove the task and its saved deliveries."},"expectedUpdatedAt":{"oneOf":[{"type":"null","const":null},{"type":"string"}],"description":"`updatedAt` value that the editor read; a different stored value returns `schedule_conflict`."}},"required":["id","action"],"additionalProperties":true}]}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleEditResult` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/schedule/schedule/src/index.ts:537:9`

#### `@deepseek-ai/dsh-schedule#schedule/history`
- service: `schedule` · invocation: `direct`
- **说明**：Remote form of the target-based {@link ScheduleService.history}; an invalid limit rejects with `schedule/input-invalid`.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Task whose saved deliveries are read."},"limit":{"type":"number","description":"Required safe-integer page size from 1 through 100."},"before":{"type":"string","description":"Message identity of the oldest entry in the previous page; excluded from this page."}},"required":["id","limit"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleDeliveryHistoryResult` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/schedule/schedule/src/index.ts:478:9`

#### `@deepseek-ai/dsh-schedule#schedule/list`
- service: `schedule` · invocation: `direct`
- **说明**：Remote form of the shared Host-wide list.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"active":{"type":"boolean","description":"`true` lists only active tasks; `false` lists only paused and ended tasks; omission lists all tasks."},"limit":{"type":"number","description":"Page size from 1 through 500; the default is 100."},"offset":{"type":"number","description":"Number of sorted tasks to skip; the default is 0."}},"required":[],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleListResult` (strict) schema=`{"type":"object","properties":{"items":{"type":"array","items":{"oneOf":[{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"after","description":"Rule discriminator for a delayed one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"afterSeconds":{"type":"number","description":"Positive safe-integer delay accepted at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","afterSeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"at","description":"Rule discriminator for an absolute one-shot reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"scheduledAt":{"type":"string","description":"Four-digit-year RFC 3339 UTC target."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"every","description":"Rule discriminator for a fixed-rate recurring reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"everySeconds":{"type":"number","description":"Fixed safe-integer interval, never below one minute."},"scheduledAt":{"type":"string","description":"Next anchor-aligned occurrence while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","everySeconds","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"daily","description":"Rule discriminator for a daily wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"weekly","description":"Rule discriminator for a weekly wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"time":{"type":"string","description":"Local time normalized to HH:mm:ss.SSS."},"timeZone":{"type":"string","description":"Explicit canonical IANA zone; equivalent timing edits retain the stored spelling."},"weekdays":{"type":"array","items":{"type":"number"},"description":"Unique ascending ISO weekdays, Monday 1 through Sunday 7."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","time","timeZone","weekdays","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"id":{"type":"string","description":"Globally unique task identity."},"kind":{"type":"string","const":"cron","description":"Rule discriminator for a five-field cron wall-clock reminder."},"title":{"type":"string","description":"Required stored task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed reminder content supplied at creation."},"expression":{"type":"string","description":"Canonical five-field cron expression: minute hour day-of-month month day-of-week."},"timeZone":{"type":"string","description":"Explicit IANA zone; equivalent timing edits retain the stored spelling."},"scheduledAt":{"type":"string","description":"Committed next UTC instant while active, or final occurrence when inactive."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["id","kind","title","prompt","expression","timeZone","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"rrule"},"id":{"type":"string","description":"Host-generated canonical identity."},"title":{"type":"string","description":"Task name; already trimmed, non-empty, and at most 120 characters."},"prompt":{"type":"string","description":"Trimmed instruction sent when an occurrence becomes due."},"rrule":{"type":"string","description":"One normalized DTSTART line and one RRULE line."},"scheduledAt":{"type":"string","description":"Next unaccepted occurrence while active, or the final accepted occurrence when ended."},"target":{"oneOf":[{"type":"object","properties":{"kind":{"type":"string","const":"session","description":"Every occurrence goes to one existing Session."},"sessionId":{"type":"string","description":"Session that receives each delivery."}},"required":["kind","sessionId"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new_once","description":"The first delivery creates one Session; later deliveries go to that Session."},"sessionId":{"type":"string","description":"Reserved at creation; the first delivery creates it and the target becomes `session`."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create the reserved Session."}},"required":["kind","sessionId","create"],"additionalProperties":true},{"type":"object","properties":{"kind":{"type":"string","const":"new","description":"Every delivery creates a fresh Session."},"create":{"type":"object","properties":{"cwd":{"type":"string","description":"Project directory of the created Session, which joins the Workspace registered there; omission uses the Host project directory."},"agentPreset":{"type":"string","description":"Agent preset of the created Session; omission uses the default preset."}},"required":[],"additionalProperties":true,"description":"Values used to create each Session."}},"required":["kind","create"],"additionalProperties":true}],"description":"Destination of the next delivery."},"involvedSessionIds":{"type":"array","items":{"type":"string"},"description":"Sessions told about later changes while their Agent is live: the creating and editing Agent Sessions and each existing or reserved target Session. Sessions created by a `new` target are excluded."},"status":{"type":"string","enum":["active","paused","ended"],"description":"Only `active` tasks have a timer obligation; `paused` and `ended` tasks stay visible."},"createdAt":{"type":"string","description":"Canonical UTC creation time."},"updatedAt":{"type":"string","description":"Canonical UTC time of the latest stored change; editors send it back as `expectedUpdatedAt`."},"executionActive":{"type":"boolean","const":true,"description":"The latest delivery is queued or running in its reused target Session; a `new` target, whose deliveries run beside one another, never sets it."},"deliveryFloorEndsAt":{"type":"string","description":"End of the minimum delivery interval, present while it remains in the future."},"lastDelivery":{"type":"object","properties":{"scheduledAt":{"type":"string","description":"Canonical UTC target of the delivered occurrence."},"deliveredAt":{"type":"string","description":"Canonical UTC time sampled after Session persistence acknowledged delivery."},"messageId":{"type":"string","description":"Identity of the delivered message, shared by tasks in one recurring batch."},"targetSessionId":{"type":"string","description":"Session that durably accepted the delivered message."}},"required":["scheduledAt","deliveredAt","messageId","targetSessionId"],"additionalProperties":true,"description":"Most recent durably acknowledged inbox delivery, when available."}},"required":["kind","id","title","prompt","rrule","scheduledAt","target","involvedSessionIds","status"],"additionalProperties":true}]},"description":"Tasks in this page."},"shown":{"type":"number","description":"Number of tasks in this page."},"total":{"type":"number","description":"Number of tasks that match the filter."},"limit":{"type":"number","description":"Applied page size."},"offset":{"type":"number","description":"Applied offset."}},"required":["items","shown","total","limit","offset"],"additionalProperties":true,"description":"The requested page and total matching task count."}`
- source: `packages/schedule/schedule/src/index.ts:428:9`

#### `@deepseek-ai/dsh-schedule#schedule/run`
- service: `schedule` · invocation: `direct`
- **说明**：Deliver one task now without consuming or moving its scheduled occurrence; an archived destination Session rejects with `schedule/target-archived`.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Task to run now."}},"required":["id"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleRunResult` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/schedule/schedule/src/index.ts:495:9`

#### `@deepseek-ai/dsh-schedule#schedule/view`
- service: `schedule` · invocation: `direct`
- **说明**：Read one task without activating its target Sessions.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"id":{"type":"string","description":"Task to read."}},"required":["id"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-schedule/client#ScheduleViewResult` (strict) — schema 不可用：typert tool schema: selected union branches overlap or have no required discriminator
- source: `packages/schedule/schedule/src/index.ts:451:9`


### `@deepseek-ai/dsh-session-reference`

#### `@deepseek-ai/dsh-session-reference#sessionReferenceResolver/candidates`
- service: `sessionReferenceResolver` · invocation: `direct`
- **说明**：Remote face of {@link listCandidates}: the configured candidate limit applies, and every candidate carries the canonical mention a host inserts into the prompt draft.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `query` (wire `query`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-session-reference#sessionReferenceResolver/candidates:result` (strict) schema=`{"type":"array","items":{"type":"object","properties":{"mention":{"type":"string","description":"Canonical `@[label](dsh-session:…)` mention serialized into the prompt draft."},"sessionId":{"type":"string","description":"Opaque source session identity."},"label":{"type":"string","description":"Latest log-backed title, falling back to the opaque session id."},"displayTitle":{"type":"string","description":"Display and canonical-mention text, preferring a subagent's durable creation label over {@link label}."},"cwd":{"type":"string","description":"Source session working directory, when recorded."},"sameWorkspace":{"type":"boolean","description":"True when {@link SessionReferenceCandidate.cwd} is recorded and equals the requesting agent's. Hosts that only surface a distinguishing location read this instead of comparing paths they never received."},"createdAt":{"type":"number","description":"Source session creation time in Unix epoch milliseconds."}},"required":["mention","sessionId","label","sameWorkspace","createdAt"],"additionalProperties":true},"description":"mention-carrying candidates in rank order."}`
- source: `packages/context/session-reference/src/index.ts:282:9`


### `@deepseek-ai/dsh-subagent`

#### `@deepseek-ai/dsh-subagent#subagents/interruptByUser`
- service: `subagents` · invocation: `direct`
- **说明**：Remote face of {@link interrupt}, authorized on the target Session by the Gateway. No catalog, history, persistence, or parent Agent lookup runs. Absent, idle, and already-completed targets are accepted no-ops there.
- **参数**：
  - `childSessionId` (wire `childSessionId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-subagent/client#SubagentInterruptReceipt` (strict) schema=`{"type":"object","properties":{"accepted":{"type":"boolean","const":true}},"required":["accepted"],"additionalProperties":true,"description":"acknowledgement that the cancel signal was admitted, not that the target is quiescent."}`
- source: `packages/subagent/subagent/src/index.ts:504:3`

#### `@deepseek-ai/dsh-subagent#subagents/prompt`
- service: `subagents` · invocation: `direct`
- **说明**：Deliver one browser-authored message to a continuable child through its live subagent tree root, retaining the caller-minted request identity and validated browser zone on the accepted message. Success identifies the message the child's inbox accepted; later execution is independent of this call. Queue delivery targets a later turn; steer delivery targets the nearest step and retains the Agent loop's best-effort fallback semantics. Image parts are admitted and persisted through the attachment store before delivery, and the child's model must accept image input. Cold resume at capacity rejects with `subagent/delivery-unavailable`. Access is checked on the target Session before attachment admission or restoration.
- **参数**：
  - `request` (wire `request`, source `json`) schema=`{"type":"object","properties":{"requestId":{"type":"string","description":"Identity persisted on the accepted message, minted before the call."},"childSessionId":{"type":"string"},"delivery":{"type":"string","enum":["queue","steer"],"description":"Whether this message queues a later turn or targets the nearest step."},"content":{"type":"array","items":{"oneOf":[{"type":"object","properties":{"type":{"type":"string","const":"text"},"text":{"type":"string"}},"required":["type","text"],"additionalProperties":true},{"type":"object","properties":{"type":{"type":"string","const":"image"},"mediaType":{"type":"string","enum":["image/png","image/jpeg","image/webp","image/gif"]},"data":{"type":"string"},"name":{"type":"string"}},"required":["type","mediaType","data"],"additionalProperties":true}]},"description":"Browser prompt parts delivered as the child's user message. The Host admits and persists image parts before delivery, so the wire never carries a durable attachment reference the caller could fabricate."},"clientTimeZone":{"type":"string","description":"Optional browser zone sampled for this exact human prompt."}},"required":["requestId","childSessionId","delivery","content"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-subagent/client#SubagentPromptReceipt` (strict) schema=`{"type":"object","properties":{"messageId":{"type":"string"}},"required":["messageId"],"additionalProperties":true,"description":"the accepted message's inbox identity."}`
- source: `packages/subagent/subagent/src/index.ts:451:9`


### `@deepseek-ai/dsh-user-questions`

#### `@deepseek-ai/dsh-user-questions#userQuestions/answer`
- service: `userQuestions` · invocation: `direct`
- **说明**：Answer a continued question. The reply is steered into the agent as a user message whose source names the call; that message is also the record that closes the question in the projection.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `callId` (wire `callId`, source `json`) schema=`{"type":"string"}`
  - `answer` (wire `answer`, source `json`) schema=`{"type":"object","properties":{"answers":{"type":"array","items":{"type":"object","properties":{"id":{"type":"string","description":"The answered question id."},"selected":{"type":"array","items":{"type":"string"},"description":"Selected option labels. May accompany custom text for a multi-select question."},"custom":{"type":"string","description":"Optional free-text \"Other\" answer."}},"required":["id","selected"],"additionalProperties":true},"description":"Structured answers keyed by question id."}},"required":["answers"],"additionalProperties":true}`
- **结果**：`@deepseek-ai/dsh-user-questions#userQuestions/answer:result` (strict) schema=`{"type":"boolean","description":"Whether the question is still continued; an accepted reply stays queued until the agent admits its user message."}`
- source: `packages/interaction/user-questions/src/index.ts:170:3`

#### `@deepseek-ai/dsh-user-questions#userQuestions/attachWait`
- service: `userQuestions` · invocation: `direct`
- **说明**：Let one answer UI hold a live timed wait. Closing the stream releases its claim.
- **参数**：
  - `agent` (wire `agentId`, source `lookup`) schema=`{"type":"string"}`
  - `callId` (wire `callId`, source `json`) schema=`{"type":"string"}`
- **结果**：`@deepseek-ai/dsh-user-questions#userQuestions/attachWait:result` (strict) schema=`{"type":"object","properties":{"remainingMs":{"type":"number"}},"required":["remainingMs"],"additionalProperties":true,"description":"One Host-computed remaining duration, or no frames once the wait ended."}`
- source: `packages/interaction/user-questions/src/index.ts:221:10`


### `@deepseek-ai/dsh-web`

#### `@deepseek-ai/dsh-web#web/listProviders`
- service: `web` · invocation: `direct`
- **说明**：List every registered search and fetch provider for provider pickers. Availability does not filter the lists.
- **参数**：无
- **结果**：`@deepseek-ai/dsh-web/types#WebProviderList` (strict) — schema 不可用：typert tool schema: selected dictionaries require string keys and unconstrained JSON values
- source: `packages/web/web/src/index.ts:152:3`

---

# Layer C — 进程内 Cordis `ctx.*` 服务面

> **来源**：`deepseek-ai/deepseek-harness` 在 tag `dsh-v0.2.2-rc.3`（commit `38a6a5c965aa99ab525161efb7cc5cf1fe62fced`）的公开 TypeScript 源码。
> 用 `extract_layerc.py` 从 `S:\apps\llm\agentwork\.tmp\dsh-src-0.2.2-rc.3` 的 `packages/**` + `vendor/**` 的 `.ts` 抽取
> （5888 个 `.ts` 文件），并交叉核对本机安装的 DSH 桌面 app.asar 解包树的编译后 `.js`（1270 个 `.js` 文件）。
>
> **不是反推**：npm 不发 `.ts` 源码、同一包的 `.d.ts` 在随包产物里也缺失；
> Layer C 的每个服务键的提供类型直接读公开仓库的 `.ts` 声明合并（`declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }`），
> 运行期注册再拿本机安装的 DSH 桌面 app.asar 解包树的 `.js` 交叉核对。npm 上的 `.d.ts` 仅作参考。

## C.1 机制（类型化声明合并，非反推）

- **框架**：`@deepseek-ai/cordis`。
- **声明惯用法**：`declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }`。
- **注册惯用法**：`ctx.provide(name, value)`、`ctx.reflect.provide(name, self, check)`、`TypertRemoteService: super(ctx, key, { namespace })`。
- **依赖惯用法**：`static inject = [...]`、`const inject = [...]`、`exports.inject = inject`、`ctx.get(name) for optional service reads`。
- **说明**：ctx.<key> is a typed, declaration-merged property; strict inject reads the global service store, ctx.get reads optionally.

## C.2 覆盖度

- 生产服务键：**151** 个；测试夹具里声明的键（非生产）：**14** 个。
- 有提供方的：141；有消费方的：112。
- 方法签名：解析出 **131** 个服务、共 **1367** 个方法。
- 交叉核对（本机安装的 DSH 桌面 app.asar 解包树）：114 / 151 个生产键在编译后 `.js` 里可见。

## C.3 服务目录（生产键，151 行）

| 服务键 | 包 | 提供类型 | 提供方 | 消费方 | 方法 | asar |
|---|---|---|---|---|---|---|
| `accountUi` | `@deepseek-ai/dsh-client-ui-settings-account` | `AccountUi` | 1 | 1 | 2 | — |
| `actionCards` | `@deepseek-ai/dsh-action-cards` | `ActionCards` | 2 | 4 | 14 | ✅ |
| `agentDefaultModel` | `@deepseek-ai/dsh-agent-default-model` | `AgentDefaultModelConfig` | 0 | 4 | 2 | ✅ |
| `agentLoop` | `@deepseek-ai/dsh-agent-loop` | `AgentLoop` | 1 | 0 | 20 | ✅ |
| `agentPresets` | `@deepseek-ai/dsh-agent-preset-registry` | `AgentPresetRegistry` | 1 | 15 | 22 | ✅ |
| `agentTeams` | `@deepseek-ai/dsh-agent-team` | `TeamService` | 1 | 1 | 6 | ✅ |
| `agents` | `@deepseek-ai/dsh-agent` | `AgentRegistry` | 1 | 63 | 26 | ✅ |
| `appExit` | `@deepseek-ai/dsh-cmdline` | `AppExit` | 1 | 3 | 0 | ✅ |
| `appReady` | `@deepseek-ai/dsh-cmdline` | `AppReady` | 1 | 1 | 1 | ✅ |
| `approval` | `@deepseek-ai/dsh-user-approval` | `ApprovalService` | 1 | 12 | 10 | ✅ |
| `attachments` | `@deepseek-ai/dsh-attachment` | `AttachmentStore` | 1 | 20 | 15 | ✅ |
| `authorization` | `@deepseek-ai/dsh-authorization` | `AuthorizationService` | 1 | 1 | 11 | ✅ |
| `browserUse` | `@deepseek-ai/dsh-browser-use` | `BrowserUseRegistry` | 1 | 3 | 1 | — |
| `chatFileMentions` | `@deepseek-ai/dsh-client-ui-chat` | `ChatFileMentions` | 1 | 1 | 1 | — |
| `claudeCodeMods` | `@deepseek-ai/dsh-experimental-claude-code-mods` | `ClaudeCodeMods` | 1 | 0 | 12 | — |
| `clientModules` | `@deepseek-ai/dsh-client-modules` | `ClientModuleRegistry` | 1 | 2 | 28 | ✅ |
| `cmdlineArgs` | `@deepseek-ai/dsh-cmdline` | `CmdlineArgs` | 1 | 7 | 1 | ✅ |
| `commandUi` | `@deepseek-ai/dsh-client-ui-commands` | `CommandUiRuntime` | 1 | 3 | 20 | — |
| `commands` | `@deepseek-ai/dsh-commands` | `CommandRuntime` | 1 | 8 | 10 | ✅ |
| `compaction` | `@deepseek-ai/dsh-compaction` | `CompactionEngine` | 1 | 1 | 3 | ✅ |
| `computerUse` | `@deepseek-ai/dsh-computer-use` | `ComputerUseRegistry` | 1 | 3 | 1 | ✅ |
| `configEditor` | `@deepseek-ai/dsh-config-editor` | `ConfigEditor` | 0 | 4 | 5 | ✅ |
| `configForms` | `@deepseek-ai/dsh-client-ui-settings` | `ConfigForms` | 1 | 20 | 6 | — |
| `configuredAgentIdentities` | `@deepseek-ai/dsh-agent-loop` | `ConfiguredAgentIdentities` | 0 | 0 | 0 | — |
| `connection` | `@deepseek-ai/dsh-client-connection` | `HostConnectionHandle` | 2 | 26 | 7 | ✅ |
| `conversation` | `@deepseek-ai/dsh-client-ui-conversation` | `import('./service.ts').IConversation` | 1 | 4 | 0 | — |
| `cordisInspect` | `@deepseek-ai/dsh-cordis-client-runner` | `ClientCordisInspectRegistry` | 2 | 2 | 5 | ✅ |
| `cotTranslation` | `@deepseek-ai/dsh-experimental-client-ui-cot-translation` | `CotTranslationController` | 1 | 0 | 0 | ✅ |
| `credentials` | `@deepseek-ai/dsh-credentials` | `CredentialProvider` | 1 | 16 | 13 | ✅ |
| `credentialsController` | `@deepseek-ai/dsh-api-settings-controller` | `CredentialsController` | 1 | 0 | 5 | ✅ |
| `cuaAccess` | `@deepseek-ai/dsh-cua` | `CuaAccess` | 1 | 0 | 9 | ✅ |
| `deepseekAccount` | `@deepseek-ai/dsh-deepseek-account` | `DeepSeekAccount` | 1 | 4 | 33 | ✅ |
| `deepseekChatImport` | `@deepseek-ai/dsh-deepseek-chat-import` | `DeepseekChatImportService` | 1 | 0 | 0 | ✅ |
| `deepseekLlmApiExtensions` | `@deepseek-ai/dsh-deepseek-llm-api-extensions` | `DeepSeekLlmApiExtensionRegistry` | 1 | 4 | 2 | ✅ |
| `directoryPicker` | `@deepseek-ai/dsh-host-directory-picker` | `DirectoryPicker` | 1 | 1 | 1 | ✅ |
| `directoryPickerController` | `@deepseek-ai/dsh-api-workspace-controller` | `DirectoryPickerController` | 1 | 0 | 4 | ✅ |
| `documentPreviews` | `@deepseek-ai/dsh-client-ui-sidebar-documentpreview` | `DocumentPreviewRegistry` | 1 | 0 | 4 | — |
| `dshHomePath` | `@deepseek-ai/dsh-app-boot` | `typeof dshHomePath` | 1 | 0 | 0 | ✅ |
| `dynamicCordisRunner` | `@deepseek-ai/dsh-cordis-client-runner` | `CordisRunnerFace` | 2 | 1 | 7 | ✅ |
| `feedbackUi` | `@deepseek-ai/dsh-client-ui-message-feedback` | `FeedbackUi` | 1 | 1 | 1 | — |
| `fileDrag` | `@deepseek-ai/dsh-client-ui-file-drag` | `FileDragService` | 1 | 3 | 0 | — |
| `fileReferences` | `@deepseek-ai/dsh-file-reference` | `FileReferenceService` | 1 | 1 | 1 | ✅ |
| `fileUpload` | `@deepseek-ai/dsh-client-file-upload` | `FileUploadService` | 2 | 2 | 2 | ✅ |
| `fileUploads` | `@deepseek-ai/dsh-client-file-upload` | `FileUploads` | 1 | 1 | 13 | ✅ |
| `forge` | `@deepseek-ai/dsh-experimental-forge` | `ForgeService` | 1 | 3 | 39 | ✅ |
| `forgePanel` | `@deepseek-ai/dsh-experimental-client-ui-forge` | `ForgePanelController` | 1 | 0 | 47 | ✅ |
| `forgeSession` | `@deepseek-ai/dsh-experimental-forge-session` | `ForgeSessionService` | 1 | 1 | 16 | ✅ |
| `fs` | `@deepseek-ai/dsh-fs` | `FileSystem` | 1 | 24 | 18 | ✅ |
| `goals` | `@deepseek-ai/dsh-goal` | `GoalService` | 1 | 4 | 25 | ✅ |
| `headlessStartup` | `@deepseek-ai/dsh-headless` | `HeadlessStartupValues` | 0 | 1 | 0 | — |
| `hmr` | `@deepseek-ai/dsh-hmr` | `Hmr` | 1 | 0 | 23 | ✅ |
| `inputTriggers` | `@deepseek-ai/dsh-client-ui-input-trigger` | `import('./contract.ts').InputTriggerServiceContract` | 1 | 7 | 0 | — |
| `inspector` | `@deepseek-ai/dsh-experimental-inspector` | `InspectorService` | 2 | 0 | 0 | ✅ |
| `invocation` | `@deepseek-ai/dsh-typert-protocol` | `RemoteInvocation \| undefined` | 0 | 0 | 1 | — |
| `jobController` | `@deepseek-ai/dsh-api-job-controller` | `JobController` | 1 | 0 | 3 | ✅ |
| `jobs` | `@deepseek-ai/dsh-api-job-controller` | `IJobs` | 2 | 7 | 3 | ✅ |
| `launchEnvironment` | `@deepseek-ai/dsh-launch-environment` | `LaunchEnvironmentSnapshot` | 0 | 0 | 2 | — |
| `launcherSessionQueryPath` | `@deepseek-ai/dsh-session-query-sqlite` | `string` | 0 | 0 | 0 | — |
| `layout` | `@deepseek-ai/dsh-client-ui-layout` | `import('./service.ts').ILayout` | 1 | 5 | 0 | — |
| `liveshareShares` | `@deepseek-ai/dsh-experimental-liveshare` | `LiveshareShares` | 1 | 0 | 13 | ✅ |
| `llm` | `@deepseek-ai/dsh-llm` | `LlmRuntime` | 1 | 29 | 32 | ✅ |
| `locale` | `@deepseek-ai/dsh-client-locale` | `LocaleRuntime` | 1 | 67 | 19 | — |
| `lsp` | `@deepseek-ai/dsh-lsp` | `LspService` | 1 | 2 | 2 | — |
| `mcpManager` | `@deepseek-ai/dsh-mcp-manager` | `McpServerManager` | 1 | 0 | 0 | ✅ |
| `mcpResources` | `@deepseek-ai/dsh-mcp-resources` | `McpResourceRuntime` | 1 | 0 | 5 | ✅ |
| `messageFeedback` | `@deepseek-ai/dsh-message-feedback` | `MessageFeedbackService` | 1 | 0 | 8 | ✅ |
| `modelDirectories` | `@deepseek-ai/dsh-client-ui-model-selection` | `ModelDirectoryResolver` | 1 | 0 | 1 | — |
| `modules` | `@deepseek-ai/dsh-client-modules` | `ClientModuleLoader` | 1 | 5 | 4 | — |
| `officeKit` | `@deepseek-ai/dsh-office-kit` | `OfficeKit` | 1 | 1 | 20 | ✅ |
| `otel` | `@deepseek-ai/dsh-otel` | `OTel` | 1 | 2 | 0 | ✅ |
| `permissionPresets` | `@deepseek-ai/dsh-permission-presets` | `PermissionPresetService` | 1 | 5 | 18 | ✅ |
| `planMode` | `@deepseek-ai/dsh-plan-mode` | `PlanModeController` | 1 | 0 | 9 | ✅ |
| `pluginChanges` | `@deepseek-ai/dsh-client-ui-plugin-manager` | `{ /** * Observe whether a bundle or one of its rows is being changed. * @param packageName Bundle package name. * @returns A snapshot source whose subscriptions belong to the caller. */ bundle(packageName: string): HostObservable<boolean> }` | 1 | 0 | 0 | — |
| `pluginManager` | `@deepseek-ai/dsh-plugin-manager` | `PluginManager` | 1 | 5 | 47 | ✅ |
| `pluginMarket` | `@deepseek-ai/dsh-plugin-market` | `PluginMarket` | 1 | 0 | 0 | ✅ |
| `pluginNavigation` | `@deepseek-ai/dsh-client-ui-plugin-manager` | `{ /** * Open a bundle's details without changing the current Session. * An absent bundle displays the plugin list after loading. * @param packageName - npm package name of the bundle. */ openBundle(packageName: string): void /** Open the Plugins main list without opening a dialog or changing the current Session. */ openList(): void }` | 1 | 3 | 0 | — |
| `pluginPackages` | `@deepseek-ai/dsh-app-boot` | `PluginPackages` | 1 | 8 | 4 | ✅ |
| `pluginRecommendations` | `@deepseek-ai/dsh-plugin-recommendations` | `PluginRecommendations` | 1 | 0 | 7 | ✅ |
| `pluginRegistryProbe` | `@deepseek-ai/dsh-client-ui-plugin-manager` | `PluginRegistryProbe` | 1 | 0 | 0 | ✅ |
| `productAnalytics` | `@deepseek-ai/dsh-client-product-analytics` | `DesktopAnalytics` | 2 | 18 | 2 | ✅ |
| `productTelemetry` | `@deepseek-ai/dsh-host-product-telemetry-otel` | `ProductTelemetry` | 1 | 1 | 0 | ✅ |
| `profileContext` | `@deepseek-ai/dsh-app-boot` | `ProfileContext` | 0 | 9 | 0 | ✅ |
| `ptcRuntime` | `@deepseek-ai/dsh-ptc-runtime` | `PtcRuntime` | 1 | 7 | 3 | ✅ |
| `remote` | `@deepseek-ai/dsh-api-gateway` | `ClientRemote` | 2 | 55 | 1 | ✅ |
| `remoteAccess` | `@deepseek-ai/dsh-api-remote-access` | `ClientRemoteAccess` | 3 | 15 | 3 | ✅ |
| `resources` | `@deepseek-ai/dsh-client-resources` | `Resources` | 1 | 4 | 3 | ✅ |
| `sandbox` | `@deepseek-ai/dsh-sandbox` | `SandboxProvider` | 1 | 8 | 1 | ✅ |
| `sandboxPolicy` | `@deepseek-ai/dsh-sandbox-policy` | `SandboxPolicyService` | 1 | 26 | 5 | ✅ |
| `schedule` | `@deepseek-ai/dsh-schedule` | `ScheduleService` | 1 | 0 | 29 | ✅ |
| `sessionController` | `@deepseek-ai/dsh-api-session-controller` | `SessionController` | 1 | 4 | 29 | ✅ |
| `sessionFeedback` | `@deepseek-ai/dsh-command-feedback` | `SessionFeedbackService` | 1 | 0 | 2 | ✅ |
| `sessionFileReferences` | `@deepseek-ai/dsh-api-session-controller` | `SessionFileReferences` | 1 | 0 | 1 | ✅ |
| `sessionLogDeepSeek` | `@deepseek-ai/dsh-session-log-deepseek` | `SessionLogDeepSeekService` | 1 | 0 | 1 | ✅ |
| `sessionLogDownload` | `@deepseek-ai/dsh-session-log-export` | `SessionLogDownloadController` | 1 | 0 | 5 | — |
| `sessionPersistence` | `@deepseek-ai/dsh-session-persistence` | `SessionPersistence` | 1 | 21 | 5 | ✅ |
| `sessionProjectionCache` | `@deepseek-ai/dsh-session-projection-cache` | `SessionProjectionCache` | 1 | 8 | 15 | ✅ |
| `sessionProjections` | `@deepseek-ai/dsh-session-projection` | `SessionProjectionRegistry` | 1 | 32 | 30 | ✅ |
| `sessionQuery` | `@deepseek-ai/dsh-session-query` | `SessionQueryEngine` | 1 | 13 | 20 | ✅ |
| `sessionReferenceResolver` | `@deepseek-ai/dsh-session-reference` | `SessionReferenceResolver` | 1 | 0 | 9 | ✅ |
| `sessionSkillCatalog` | `@deepseek-ai/dsh-api-session-controller` | `SessionSkillCatalog` | 1 | 0 | 2 | ✅ |
| `sessionTelemetry` | `@deepseek-ai/dsh-session-telemetry` | `SessionTelemetryBackend` | 1 | 0 | 2 | ✅ |
| `sessionTitle` | `@deepseek-ai/dsh-session-title` | `SessionTitleService` | 1 | 6 | 27 | ✅ |
| `sessions` | `@deepseek-ai/dsh-api-session-controller` | `import('./contract/sessions.ts').ISessions` | 2 | 77 | 0 | ✅ |
| `settings` | `@deepseek-ai/dsh-settings` | `SettingsForms` | 0 | 4 | 12 | — |
| `settingsController` | `@deepseek-ai/dsh-api-settings-controller` | `SettingsController` | 1 | 0 | 7 | ✅ |
| `settingsSchema` | `@deepseek-ai/dsh-client-ui-settings` | `SettingsSchemaService` | 1 | 2 | 7 | — |
| `shell` | `@deepseek-ai/dsh-shell` | `ShellExecutor` | 1 | 6 | 2 | ✅ |
| `shellEnv` | `@deepseek-ai/dsh-shell-env` | `ShellEnvRegistry` | 1 | 2 | 4 | ✅ |
| `shortcuts` | `@deepseek-ai/dsh-client-shortcuts` | `Shortcuts` | 1 | 9 | 7 | — |
| `sidebarRight` | `@deepseek-ai/dsh-client-ui-sidebar-right` | `SidebarRightController` | 1 | 12 | 42 | — |
| `sidebarRightTabs` | `@deepseek-ai/dsh-client-ui-sidebar-right` | `SidebarRightTabRegistry` | 1 | 11 | 12 | — |
| `skills` | `@deepseek-ai/dsh-skill` | `SkillRegistry` | 1 | 7 | 20 | ✅ |
| `slots` | `@deepseek-ai/dsh-client-ui-renderer` | `SlotRegistry` | 1 | 73 | 34 | ✅ |
| `speechController` | `@deepseek-ai/dsh-experimental-api-speech-to-text` | `SpeechController` | 1 | 0 | 0 | ✅ |
| `speechToText` | `@deepseek-ai/dsh-experimental-speech-to-text` | `SpeechToText` | 1 | 2 | 0 | ✅ |
| `spillStore` | `@deepseek-ai/dsh-spill` | `SpillStore` | 1 | 3 | 1 | ✅ |
| `ssh` | `@deepseek-ai/dsh-ssh` | `SshConnection` | 1 | 3 | 11 | — |
| `storage` | `@deepseek-ai/dsh-storage` | `Storage` | 1 | 3 | 2 | ✅ |
| `storageDomain` | `@deepseek-ai/dsh-storage-domain` | `DomainFacility` | 0 | 7 | 3 | ✅ |
| `subagentModelSelection` | `@deepseek-ai/dsh-tool-subagent` | `SubagentModelSelectionConfig` | 1 | 0 | 2 | ✅ |
| `subagents` | `@deepseek-ai/dsh-subagent` | `SubagentRuntime` | 1 | 23 | 25 | ✅ |
| `subprocess` | `@deepseek-ai/dsh-subprocess` | `SubprocessRuntime` | 1 | 22 | 4 | ✅ |
| `systemPrompt` | `@deepseek-ai/dsh-system-prompt` | `SystemPrompt` | 1 | 30 | 10 | ✅ |
| `terminalController` | `@deepseek-ai/dsh-api-terminal-controller` | `TerminalController` | 1 | 1 | 26 | ✅ |
| `terminals` | `@deepseek-ai/dsh-terminal` | `TerminalSessionService` | 1 | 5 | 25 | ✅ |
| `theme` | `@deepseek-ai/dsh-client-ui-theme` | `ThemeRuntime` | 1 | 4 | 14 | — |
| `tokenMeter` | `@deepseek-ai/dsh-token-meter` | `TokenMeter` | 1 | 4 | 10 | ✅ |
| `toolResultPruner` | `@deepseek-ai/dsh-compaction-tool-result-pruner` | `ToolResultPruner` | 1 | 2 | 3 | ✅ |
| `tools` | `@deepseek-ai/dsh-tools` | `ToolsService` | 1 | 58 | 15 | ✅ |
| `translator` | `@deepseek-ai/dsh-experimental-translator` | `Translator` | 1 | 1 | 0 | ✅ |
| `typert` | `@deepseek-ai/dsh-typert-protocol` | `TypertRegistryContract` | 1 | 17 | 0 | ✅ |
| `typertGateway` | `@deepseek-ai/dsh-api-gateway` | `TypertGateway` | 1 | 5 | 5 | ✅ |
| `uiConversation` | `@deepseek-ai/dsh-client-ui-conversation` | `import('./conversation/assembly.ts').UiConversation` | 1 | 15 | 0 | — |
| `uiRenderer` | `@deepseek-ai/dsh-client-ui-renderer` | `UiRendererService` | 1 | 1 | 0 | — |
| `uiSession` | `@deepseek-ai/dsh-client-ui-session` | `UiSession` | 1 | 7 | 29 | — |
| `uiWorkspace` | `@deepseek-ai/dsh-client-ui-workspace` | `UiWorkspace` | 1 | 12 | 13 | — |
| `userQuestionPanels` | `@deepseek-ai/dsh-client-ui-tool` | `UserQuestionPanels` | 1 | 2 | 2 | — |
| `userQuestions` | `@deepseek-ai/dsh-user-questions` | `UserQuestionService` | 1 | 6 | 7 | ✅ |
| `web` | `@deepseek-ai/dsh-web` | `WebRuntime` | 1 | 4 | 14 | ✅ |
| `webApp` | `@deepseek-ai/dsh-web-app` | `WebApp` | 1 | 1 | 1 | ✅ |
| `webServer` | `@deepseek-ai/dsh-host-webserver` | `WebServer` | 1 | 11 | 15 | ✅ |
| `webTerminals` | `@deepseek-ai/dsh-api-terminal-controller` | `ClientTerminals` | 1 | 1 | 16 | ✅ |
| `webhookRuntime` | `@deepseek-ai/dsh-webhook` | `WebhookRuntime` | 1 | 1 | 4 | — |
| `workflowEngine` | `@deepseek-ai/dsh-workflow` | `WorkflowEngine` | 1 | 2 | 2 | ✅ |
| `workingDirectory` | `@deepseek-ai/dsh-working-directory` | `WorkingDirectoryService` | 2 | 32 | 7 | ✅ |
| `workspaceChanges` | `@deepseek-ai/dsh-workspace-changes` | `WorkspaceChanges` | 1 | 1 | 2 | ✅ |
| `workspaceController` | `@deepseek-ai/dsh-api-workspace-controller` | `WorkspaceController` | 1 | 0 | 10 | ✅ |
| `workspaceFiles` | `@deepseek-ai/dsh-api-workspace-files` | `WorkspaceFiles` | 1 | 2 | 14 | ✅ |
| `workspaceRegistry` | `@deepseek-ai/dsh-workspace` | `WorkspaceRegistry` | 1 | 10 | 30 | ✅ |
| `workspaces` | `@deepseek-ai/dsh-api-workspace-controller` | `import('./service.ts').IWorkspaces` | 2 | 3 | 0 | ✅ |
| `worktrees` | `@deepseek-ai/dsh-experimental-worktree` | `WorktreeService` | 1 | 3 | 13 | ✅ |

## C.4 方法索引（按服务；签名截断到 180 字符）

### `accountUi` — `@deepseek-ai/dsh-client-ui-settings-account`

- 提供类型：`AccountUi`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-settings-account` (`packages/client/ui-settings-account/src/client/account-ui.ts:11`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-settings-account` (`packages/client/ui-settings-account/src/client/index.ts:65`)
- 消费方：@deepseek-ai/dsh-client-ui-account-notifications(`packages/client/ui-account-notifications/src/client/index.ts` via inject)

- getSnapshot `getSnapshot(): AccountUiState` — Read the current state from the existing account snapshot.
- clientMetadata `clientMetadata(locale: string): AccountClientMetadata` — Build metadata for one account request.

### `actionCards` — `@deepseek-ai/dsh-action-cards`

- 提供类型：`ActionCards`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-action-cards` (`packages/experimental/action-cards/src/index.ts:161`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-action-cards` (`packages/experimental/client-ui-action-cards/src/client/mount.ts:39`)、`@deepseek-ai/dsh-action-cards` (`packages/experimental/action-cards/src/index.ts:186`)
- 消费方：@deepseek-ai/dsh-client-ui-creation-recommendations(`packages/experimental/client-ui-creation-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-recommendations(`packages/experimental/client-ui-plugin-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-recommendations(`packages/experimental/plugin-recommendations/src/index.ts` via inject)

- isLiveRoot `private isLiveRoot(agent: Agent): boolean`
- register `register<Details>(kind: ActionCardKind<Details>): () => void` — Register one action kind for the caller's lifetime.
- record `record(agent: Agent, decision: ActionCardDecision): void` — Record a card decision in the Session log; the next model request reports it.
- view `view(session: Session): ActionCardView` — Read the cards of one Session.
- act `act(agent: Agent, callId: ToolCallId, verb: string, payload?: Record<string, JsonValue>): Promise<ActionCardResult>` — Apply a user action to a logged card. Shared checks run first, then the kind reconciles the card; `dismiss` is recorded here and every other verb goes to the card's kind. `dismiss` also works on an unstarted card whose kind is no longer registered. Concurrent actions on one card share one operation.  *(decorators: @@Remote)*
- coalesce `private coalesce(agent: Agent, callId: ToolCallId, run: () => Promise<ActionCardResult>): Promise<ActionCardResult>` — Share one operation per card, run under the Agent's initiator, until it settles. */
- reconciled `private async reconciled( agent: Agent, kind: RegisteredKind, proposal: ActionCardProposal, verb: string, ): Promise<ActionCardResult \| undefined>` — Await the kind's reconciliation. A kind that unloads meanwhile still handles the action and refuses it itself.
- dismiss `private async dismiss( agent: Agent, kind: RegisteredKind \| undefined, proposal: ActionCardProposal, payload: ActionCardFields \| undefined, ): Promise<ActionCardResult>`
- perform `private async perform( agent: Agent, kind: RegisteredKind, proposal: ActionCardProposal, verb: string, policy: ActionCardVerb, payload: ActionCardFields \| undefined, ): Promise<Act…`
- append `private append(agent: Agent, decision: ActionCardDecision): void`
- appendPluginRecord `appendPluginRecord(agent.session, 'plugin:action-cards/decision', decision)`
- declares `private declares(agent: Agent): boolean` — Whether `propose_action` is declared for this agent's next step. */
- propose `private propose( args: { readonly action: string; readonly title: string; readonly brief: string; readonly details: ActionCardFields }, exec: ToolRunContext, ):`
- isStopping `private isStopping(): boolean`

### `agentDefaultModel` — `@deepseek-ai/dsh-agent-default-model`

> Default model selection for Agents created without an explicit model. */

- 提供类型：`AgentDefaultModelConfig`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-agent-default-model` (`packages/core/agent-default-model/src/index.ts:48`，class)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via inject)、@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)

- currentSelection `currentSelection(): ModelSelection` — Read the current default model selection.
- saveSelection `async saveSelection(next: ModelSelection): Promise<void>` — Save the complete default model selection. A deployment without a configuration editor keeps its composition entry. Saves commit in submission order; a failed save rejects its caller without blocking later saves.

### `agentLoop` — `@deepseek-ai/dsh-agent-loop`

- 提供类型：`AgentLoop`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-agent-loop` (`packages/core/agent-loop/src/index.ts:290`，class)
- 提供方：`@deepseek-ai/dsh-agent-loop` (`packages/core/agent-loop/src/index.ts:317`)

- validateConfiguredAgents `validateConfiguredAgents(this.config.agents)`
- applyConfiguredRoute `private applyConfiguredRoute(agent: Agent, options: AgentOptions): void`
- reportConfiguredStartupFailure `private reportConfiguredStartupFailure( configId: string, action: 'restore' \| 'resume', sessionId: SessionId, error: unknown, ): void` — Report a contained declarative-start failure to identity-bound consumers. */
- restoreOrCreateConfigured `private async restoreOrCreateConfigured( ownerCtx: Context, persistence: SessionPersistence, sessionId: SessionId, agentOptions: AgentOptions, meta: Pick<SessionHeader, 'cwd'>, ): …` — Restore a materialized exact config identity on remount, or create it on first use. */
- waitForDrainingConfiguredIdentity `private async waitForDrainingConfiguredIdentity(ownerCtx: Context, sessionId: SessionId): Promise<void>` — Wait for a draining same-id lifecycle to finish registry teardown. */
- checkReleased `checkReleased()`
- disposeAgentListener `disposeAgentListener()`
- disposeSessionListener `disposeSessionListener()`
- initializeAgent `private async initializeAgent( ownerCtx: Context, options: AgentInitializationOptions, ): Promise<AgentHandle>` — Own initialization and teardown from an acquired Session to a published Agent. Registers factory teardown and caller cancellation before constructing the scope. Failed initialization drains cleanup while retaining stored events and inbox input.
- untrack `untrack()`
- throwCollectedFailures `throwCollectedFailures(failures, `agent "${id}" disposal failed`)`
- assertAgentOptions `assertAgentOptions(agentOptions)`
- yield `yield () => teardown()`
- assertLive `assertLive()`
- create `async create(id: SessionId, options: AgentOptions = {}, meta: Pick<SessionHeader, 'cwd'> = {}): Promise<Agent>` — Create an agent and session under one caller-supplied identity, owned by the accessing fiber. Constructor-driven config calls mint a fresh combined id before entering this boundary. When a persistence backend is mounted, the session's durable identity and any seed are stored before publication.
- createStoredSession `private async createStoredSession(session: Session, signal?: AbortSignal): Promise<StoredSession \| undefined>` — Take a fresh session's write ownership when persistence is mounted. The constructor seed is stored before Session store entry. Setup then appends through the live event feed; creation failure retains any events already written to the handle.
- appendUnstoredSuffix `private async appendUnstoredSuffix(stored: StoredSession \| undefined, session: Session): Promise<void>` — Durably store the session events appended since the last stored cursor.
- createAgent `async createAgent(ownerCtx: Context, options: CreateAgentOptions): Promise<AgentHandle>` — Create an owned agent on a caller-supplied session id.
- resume `async resume(ownerCtx: Context, options: ResumeAgentOptions): Promise<AgentHandle>` — Resume an owned agent from the configured persistence service.
- resumeWith `private resumeWith( ownerCtx: Context, persistence: SessionPersistence, options: ResumeAgentOptions, ): Promise<AgentHandle>` — Resume through an explicit persistence handle used by the deferred config path. */

### `agentPresets` — `@deepseek-ai/dsh-agent-preset-registry`

- 提供类型：`AgentPresetRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-agent-preset-registry` (`packages/preset/agent-preset-registry/src/index.ts:54`，class)
- 提供方：`@deepseek-ai/dsh-agent-preset-registry` (`packages/preset/agent-preset-registry/src/index.ts:68`)
- 消费方：@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-agent-preset(`packages/preset/agent-preset/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/agent.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/agent.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/agent.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/agent.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via ctx.get)、@deepseek-ai/dsh-host-plugin-inventory(`packages/host/plugin-inventory/src/index.ts` via ctx.get)、@deepseek-ai/dsh-plugin-package-inventory-deepseek(`packages/llm/plugin-package-inventory-deepseek/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-schedule(`packages/schedule/tool-schedule/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-schedule(`packages/schedule/tool-schedule/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via ctx.get)

- presetForSession `presetForSession(session: Session): string \| null` — Read the preset recorded for a Session, including selections no longer in the roster.
- register `async register(definition: PresetDefinition): Promise<() => Promise<void>>` — Register and eagerly load a definition; activation failure remains visible in the roster.
- activate `private async activate(record: Definition): Promise<void>`
- diagnostic `private async diagnostic(record: Definition): Promise<string \| undefined>` — Current activation diagnostic of a definition. A mount failure is final. A mounted tree is re-audited on every read: a row waiting for a Host service activates by itself once that provider finishes, so the audit waits for the Host Loader tree to settle before reporting the row as unusable. Callers therefore must not run inside a Host row's own activation, which the settlement would wait on.
- collect `private async collect(generation: Generation): Promise<void>`
- generationFor `private generationFor(ctx: Context): Generation \| undefined`
- inspectCompositions `inspectCompositions(ctx?: Context): AgentPresetInspection[]` — Inspect retained revisions, or the exact revision an Agent joined.
- list `async list(): Promise<AgentPreset[]>` — Read every declared preset, including activation failures.
- remoteExportList `async remoteExportList(): Promise<AgentPresetRoster>` — Read the selection roster.  *(decorators: @@Remote('list'))*
- resolve `async resolve(id?: string): Promise<AgentPreset>` — Resolve an identity without starting an Agent.
- readDocument `readDocument(agentPreset: string): Promise<AgentPresetDocument>` — Read one declaration's child plugin list as YAML, for viewing only.  *(decorators: @@Remote('read'))*
- retain `private async retain(id?: string): Promise<Generation>`
- bind `private async bind(ctx: Context, generation: Generation): Promise<void>`
- join `private join(ctx: Context, key: ScopeKey, generation: Generation): void`
- mount `async mount(ctx: Context, id?: string): Promise<AgentPreset>` — Bind an unpublished Agent to the current preset revision.
- composeFrom `composeFrom(ctx: Context, parent: Context): string \| undefined` — Join a child to the exact revision retained by its parent.
- composedPreset `composedPreset(ctx: Context): string \| undefined` — Read the preset a live Agent uses.
- serviceFor `serviceFor<K extends string & keyof Context>(agent: { ctx: Context }, name: K): Context[K] \| undefined` — Read a service supplied inside an Agent's isolated preset group.
- recompose `async recompose(ctx: Context, id: string): Promise<AgentPreset>` — Rebind a blank Agent; the caller owns the blank-session check.
- select `async select(agent: Agent, agentPreset: string): Promise<string>` — Select a preset before a session starts its first turn. A Session whose log records the preset and whose Agent runs its current revision keeps its composition; nothing is logged or announced.  *(decorators: @@Remote('select'))*
- acquireScope `async acquireScope(id?: string): Promise<` — Read current registrations for cold transcript presentation.
- compositionInventory `compositionInventory(): Promise<AgentPresetComposition[]>` — Read plugin rows without creating an Agent.

### `agentTeams` — `@deepseek-ai/dsh-agent-team`

- 提供类型：`TeamService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-agent-team` (`packages/team/agent-team/src/index.ts:46`，class)
- 提供方：`@deepseek-ai/dsh-agent-team` (`packages/team/agent-team/src/index.ts:61`)
- 消费方：@deepseek-ai/dsh-tool-agent-team(`packages/team/tool-agent-team/src/index.ts` via inject)

- isEnabled `isEnabled(caller: Agent): boolean` — Read the Team selection shared by the caller's subagent tree.
- setEnabled `async setEnabled(agent: Agent, enabled: boolean, signal?: AbortSignal): Promise<void>` — Save a root Session's Team selection without stopping children or deleting tasks. The selection takes effect before awaiting persistence. Tools resolve availability at step preparation; prompt providers read the selection when evaluated. Task mutations check the current mode when their queued operation starts; admitted operations finish. retrying the same selection flushes without a duplicate event.  *(decorators: @@Remote)*
- createTask `async createTask(caller: Agent, request: CreateTeamTaskRequest, signal?: AbortSignal): Promise<TeamTaskView>` — Create one unowned pending task in the Team Lead log.
- getTask `getTask(caller: Agent, id: TeamTaskId): TeamTaskView` — Return one task, including a deleted tombstone.
- listTasks `listTasks(caller: Agent): TeamTaskView[]` — List current non-deleted tasks in numeric creation order.
- updateTask `async updateTask(caller: Agent, request: UpdateTeamTaskRequest, signal?: AbortSignal): Promise<TeamTaskView>` — Compare-and-set one authorized task transition.

### `agents` — `@deepseek-ai/dsh-agent`

- 提供类型：`AgentRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-agent` (`packages/core/agent/src/index.ts:246`，class)
- 提供方：`@deepseek-ai/dsh-agent` (`packages/core/agent/src/index.ts:260`)
- 消费方：@deepseek-ai/dsh-acp(`packages/acp/acp/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via inject)、@deepseek-ai/dsh-client-file-upload(`packages/client/file-upload/src/index.ts` via inject)、@deepseek-ai/dsh-compaction-image-offload(`packages/compaction/compaction-image-offload/src/index.ts` via inject)、@deepseek-ai/dsh-agent-instructions(`packages/context/agent-instructions/src/index.ts` via inject)、@deepseek-ai/dsh-file-reference-local(`packages/context/file-reference-local/src/index.ts` via inject)、@deepseek-ai/dsh-time-context(`packages/context/time-context/src/index.ts` via inject)、@deepseek-ai/dsh-tmux-context(`packages/context/tmux-context/src/index.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-tool-present(`packages/deliverables/tool-present/src/index.ts` via inject)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via inject)、@deepseek-ai/dsh-action-cards(`packages/experimental/action-cards/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-chrome-devtools-mcp(`packages/experimental/browser-use-chrome-devtools-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-playwright-mcp(`packages/experimental/browser-use-playwright-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-stagehand-native(`packages/experimental/browser-use-stagehand-native/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-cua-macos(`packages/experimental/cua-macos/src/index.ts` via inject)、@deepseek-ai/dsh-hooks-claude-code(`packages/experimental/hooks-claude-code/src/index.ts` via inject)、@deepseek-ai/dsh-hooks-codex(`packages/experimental/hooks-codex/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-recommendations(`packages/experimental/plugin-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-tool-session-query(`packages/experimental/tool-session-query/src/index.ts` via inject)、@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-goal-round-driver(`packages/goal/goal-round-driver/src/index.ts` via inject)、@deepseek-ai/dsh-goal(`packages/goal/goal/src/index.ts` via inject)、@deepseek-ai/dsh-tool-goal(`packages/goal/tool-goal/src/index.ts` via inject)、@deepseek-ai/dsh-permission-presets(`packages/interaction/permission-presets/src/index.ts` via inject)、@deepseek-ai/dsh-llm-retry(`packages/llm/llm-retry/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-package-inventory-deepseek(`packages/llm/plugin-package-inventory-deepseek/src/index.ts` via inject)、@deepseek-ai/dsh-plan-mode(`packages/plan/plan-mode/src/index.ts` via inject)、@deepseek-ai/dsh-agent-preset-registry(`packages/preset/agent-preset-registry/src/index.ts` via inject)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via inject)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/index.ts` via inject)、@deepseek-ai/dsh-session-title(`packages/session/session-title/src/index.ts` via inject)、@deepseek-ai/dsh-tool-skill(`packages/skill/tool-skill/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent-control(`packages/subagent/tool-subagent-control/src/index.ts` via inject)、@deepseek-ai/dsh-agent-team(`packages/team/agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-deepseek-account(`packages/credentials/deepseek-account/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-browser-use-runtime(`packages/experimental/browser-use-runtime/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-browser-use-runtime(`packages/experimental/browser-use-runtime/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via ctx.get)、@deepseek-ai/dsh-hooks-claude-code(`packages/experimental/hooks-claude-code/src/index.ts` via ctx.get)、@deepseek-ai/dsh-hooks-claude-code(`packages/experimental/hooks-claude-code/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)、@deepseek-ai/dsh-user-questions(`packages/interaction/user-questions/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-jobs(`packages/jobs/tool-jobs/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-jobs(`packages/jobs/tool-jobs/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/index.ts` via ctx.get)、@deepseek-ai/dsh-terminal(`packages/terminal/terminal/src/index.ts` via ctx.get)、@deepseek-ai/dsh-loader-smoke(`packages/test-support/loader-smoke/src/agent-turn.ts` via ctx.get)、@deepseek-ai/dsh-web-deepseek-api(`packages/web/web-deepseek-api/src/index.ts` via ctx.get)、@deepseek-ai/dsh-web-deepseek-api(`packages/web/web-deepseek-api/src/index.ts` via ctx.get)、@deepseek-ai/dsh-web-search-deepseek(`packages/web/web-search-deepseek/src/index.ts` via ctx.get)、@deepseek-ai/dsh-web-search-deepseek(`packages/web/web-search-deepseek/src/index.ts` via ctx.get)

- yield `yield () => this.disposeInitiators()`
- yield `yield () =>`
- installTurnArchiveAdmission `installTurnArchiveAdmission(ctx, sessionId => this.get(sessionId))` — Archive admission: the Workspace registry asks what still runs for a Session before hiding it; a running turn answers here, for every Agent.
- turnBoundaryOf `turnBoundaryOf(session: Session): TurnBoundaryProjection` — Read the turn and step positions recorded in a Session.
- currentInitiator `currentInitiator(): Agent \| undefined` — Read the Agent that initiated the inherited asynchronous driver chain. Use this optional form for logging, tracing, metrics, or host attribution that also supports agentless calls. When a parent creates a child, setup reports the causal parent while the setup callback's Agent parameter identifies the child. and inside an explicit clearing boundary.
- requireInitiator `requireInitiator(): Agent` — Read the initiating Agent and fail when no initiator boundary is active. Use this for private helpers contractually below a driver, or for a deployment-owned outbound request whose contract forbids agentless calls. Generic or direct-call paths use optional lookup or explicit request fields.
- withInitiator `withInitiator<T>(agent: Agent, operation: () => T): T` — Run an operation with one exact Agent as its process-local initiator. The exact synchronous value or Promise returned by the operation is preserved. Custom drivers and test harnesses wrap their complete returned foreground lifetime. A queue or wire receiver may establish this boundary only after validating explicit identity and resolving the exact live Agent; this method does neither. Detached work remains owned by the subsystem that starts it.
- withoutInitiator `withoutInitiator<T>(operation: () => T): T` — Run an operation inside a boundary that hides any inherited initiating Agent. The exact synchronous value or Promise is preserved. Use this while creating lazy shared timers, queue pumps, pool maintenance, watchers, or exporters so they do not inherit the first Agent that happens to initialize them. It clears only initiator attribution, not explicit fields, and does not own or drain detached resources.
- setFactory `setFactory(factory: AgentFactory): () => void` — Register the agent-creation factory (the loop calls this on construction, effect-scoped). A traced Cordis service is canonicalized to its concrete target; each create/resume call is then traced through that caller's context so ownership follows the caller without stacking proxy layers. Throws if a factory is already registered. Returns the disposer; on dispose the factory slot is cleared. Cordis effect disposer (single-shot): composite (generator) effects may yield it directly — exact identity nests the teardown in order.
- requireFactory `private requireFactory(): FactorySlot` — Return the active creation factory. */
- create `async create(options: CreateAgentOptions): Promise<AgentHandle>` — Create and publish a new agent through the registered factory. Distinct from {@link register} (which records an already-constructed agent): this constructs the agent and its session. Rejects if no factory is registered or creation/setup fails. The resolved {@link AgentHandle} lets the owner tear down exactly this agent.
- resume `async resume(options: ResumeAgentOptions): Promise<AgentHandle>` — Load a persisted session and resume an agent on it through the registered factory. Rejects if no factory is registered; the factory rejects if session persistence is not configured or persistence/setup fails.
- register `register(agent: Agent): ReturnType<Context['effect']>` — Register a live agent with source `startup`. Rejects if the id is already registered or a serial `agent/created` listener fails. Emits `agent/disposed` when the calling fiber is disposed — both with the agent's scope carrier (`scopeTarget(agent, agent)`): the subject is the agent in hand, so the emits are scope-filtered regardless of which context invoked `register` (calling through `agent.ctx` scopes EFFECTS; dispatch scoping always requires passing the carrier). Await registration before using the agent. returns undefined without awaiting an in-flight teardown). Exact identity is load-bearing: a composite (generator) effect that owns a teardown ORDER — the agent factory's lifecycle chain — must yield THIS function so Cordis nests the unregistration at that yield position; yielding a wrapper would leave it disposing as a concurrent sibling on owner unload, unregistering the agent (and emitting `agent/disposed`) while its final turn is still draining.
- enter `enter(agent: Agent): () => void` — Insert an already-constructed agent without announcing it. This is the advanced ordered-lifecycle primitive used by the async agent factory: it first completes setup while the agent is unpublished, then assigns the returned detach closure into its pre-installed composite teardown before calling {@link announce}. Ordinary callers use {@link register}. `agent/disposed` with listener failures contained. When called from a `agent/created` listener, removal and disposal wait until the serial creation dispatch settles.
- detachEntered `private detachEntered(entry: AgentEntry): void` — Remove one exact entered agent and emit its paired disposal when announced. */
- emitDisposed `private emitDisposed(entry: AgentEntry): void` — Emit the paired disposal edge through the entry's stable carrier. */
- announce `async announce(agent: Agent, source: SessionStartSource, signal?: AbortSignal): Promise<void>` — Announce an agent previously inserted with {@link enter}. creation announcement already began (including a reentrant call from a creation listener).
- get `get(id: SessionId): Agent \| undefined` — Look up a live agent.
- list `list(): Agent[]` — All live agents, in registration order.
- closeInitiators `private closeInitiators(): void` — Reject new initiator boundaries while inherited continuations drain. */
- disposeInitiators `private disposeInitiators(): Promise<void>` — Wait for returned-Promise boundaries, then invalidate retained references. */
- runWithInitiator `private runWithInitiator<T>(agent: Agent \| undefined, operation: () => T): T` — Establish one tracked initiator or clearing boundary. */
- hasLifecycleAncestor `private hasLifecycleAncestor(candidate: Fiber): boolean` — Whether one unloading fiber owns this service's lifecycle. */
- assertInitiatorsReadable `private assertInitiatorsReadable(): void`
- releaseReentrantInitiatorRuns `private releaseReentrantInitiatorRuns(): void` — Exclude the boundary chain that initiated this teardown from its own drain. */
- releaseInitiatorRun `private releaseInitiatorRun(run: InitiatorRun): void`

### `appExit` — `@deepseek-ai/dsh-cmdline`

> Bounded process-exit request; provided by a launcher before the tree mounts. */

- 提供类型：`AppExit`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:36`，interface)
- 提供方：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:87`)
- 消费方：@deepseek-ai/dsh-cmdline(`packages/boot/cmdline/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cmdline(`packages/boot/cmdline/src/index.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `appReady` — `@deepseek-ai/dsh-cmdline`

> Successful startup signal; provided by a launcher before the tree mounts. */

- 提供类型：`AppReady`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:45`，interface)
- 提供方：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:88`)
- 消费方：@deepseek-ai/dsh-cmdline(`packages/boot/cmdline/src/index.ts` via ctx.get)

- onReady `onReady(listener: () => void): () => void` — Run a listener once successful startup is committed. A failed or externally terminated startup never calls it.

### `approval` — `@deepseek-ai/dsh-user-approval`

- 提供类型：`ApprovalService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-user-approval` (`packages/interaction/user-approval/src/index.ts:167`，class)
- 提供方：`@deepseek-ai/dsh-user-approval` (`packages/interaction/user-approval/src/index.ts:177`)
- 消费方：@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-permission-presets(`packages/interaction/permission-presets/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/tools.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/ptc.ts` via ctx.get)、@deepseek-ai/dsh-tools(`packages/core/tools/src/pipeline.ts` via ctx.get)、@deepseek-ai/dsh-tools(`packages/core/tools/src/pipeline.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/sandbox.ts` via ctx.get)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)

- setPolicy `setPolicy(agent: Agent, policy: ApprovalPolicy): void` — Switch one live agent's policy and queue the transition for its next model step. Session initialization uses {@link setApprovalPolicy} directly because there is no previously visible policy to change.
- setApprovalPolicy `setApprovalPolicy(agent.session, policy)`
- request `async request(req: ApprovalRequest): Promise<ApprovalOutcome>` — Ask the composed answerers to decide one readonly same-process request. The service borrows the request, agent, session, and live signal directly. The request requires an open turn because the audit pair must be enclosed by the durable log's commit/replay boundary; an idle ask rejects before appending anything. The answerer phase always produces an outcome: an aborted signal yields `'cancelled'`, a missing or throwing answerer yields `'unavailable'` (fail closed), and a rogue non-vocabulary return value is normalized to `'unavailable'`. A failure that prevents either audit append from committing still rejects because returning an unlogged decision would violate the pair. Session contains post-commit observer failures, so an authoritative append cannot reject the request or suppress its matching audit event. append commit point.
- effectivePolicy `private effectivePolicy(session: Session): ApprovalPolicy` — The session's effective policy: its projected override, else the configured default (the schema already defaulted an omitted policy to `'ask'`; the `??` only narrows the optional-input TYPE).
- overrideOf `overrideOf(session: Session): ApprovalPolicy \| undefined` — Read the session override without applying the configured default.
- approvalStateOf `private approvalStateOf(session: Session): ApprovalState`
- decide `private async decide(req: ApprovalRequest, session: Session): Promise<ApprovalOutcome>` — Dispatch the waterfall, contained and raced against the request signal.
- scopeTarget `scopeTarget(req.agent, req.agent), 'approval/request', req,`
- resolve `resolve('cancelled')`
- resolve `resolve(outcome)` — After an abort won the race this resolve is a settled-promise no-op: the late answer is discarded by construction.

### `attachments` — `@deepseek-ai/dsh-attachment`

- 提供类型：`AttachmentStore`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-attachment` (`packages/attachment/attachment/src/index.ts:77`，class)
- 提供方：`@deepseek-ai/dsh-attachment` (`packages/attachment/attachment/src/index.ts:79`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-client-file-upload(`packages/client/file-upload/src/index.ts` via inject)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/content.ts` via ctx.get)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/content.ts` via ctx.get)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/content.ts` via ctx.get)、@deepseek-ai/dsh-client-connection(`packages/client/connection/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/index.ts` via ctx.get)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/read-image.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/read-image.ts` via ctx.get)、@deepseek-ai/dsh-commands(`packages/interaction/commands/src/index.ts` via ctx.get)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/host.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/index.ts` via ctx.get)、@deepseek-ai/dsh-llm(`packages/llm/llm/src/index.ts` via ctx.get)、@deepseek-ai/dsh-mcp-client(`packages/mcp/mcp-client/src/tools.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-spill-policy(`packages/spill/spill-policy/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/index.ts` via ctx.get)

- validateImage `abstract validateImage(input: SaveImageAttachment): Promise<void>` — Validate one image without persisting it. Batch callers validate every member before saving any member.
- validateImageBatch `protected validateImageBatch(inputs: readonly SaveImageAttachment[]): void` — Validate one ordered image batch before committing any member. Validation failures start no writes; storage failures return no partial references, although already published content-addressed objects may stay unreachable until a future retention policy collects them.
- assertMessageImages `assertMessageImages(limits, inputs.length, inputs.reduce((sum, input) => sum + input.data.byteLength, 0))`
- saveImages `async saveImages(inputs: readonly SaveImageAttachment[]): Promise<readonly ImageAttachmentRef[]>` — Validate and durably commit one ordered image batch.
- admitPromptContent `async admitPromptContent( content: readonly AttachmentAdmissionPart[], ): Promise<AdmittedPromptContentPart[]>` — Admit one Host prompt and replace each encoded image with its durable reference. Text, durable file references, and already stored images pass through unchanged. Every image part counts toward `maxImagesPerMessage` and `maxMessageImageBytes`; a stored image counts the bytes of the upload that stored it. Refused content starts no writes. A prompt without encoded images performs no storage operation.
- assertMessageImages `assertMessageImages( this.imageLimits, encoded.length + stored.length, encoded.reduce((sum, part) => sum + Buffer.byteLength(part.data, 'base64'), 0) + stored.reduce((sum, part) =>…`
- admitEncodedFile `admitEncodedFile(input: EncodedFileAttachment): Promise<FileAttachmentRef>` — Decode and durably commit one canonical base64 file upload.
- isAttachmentError `isAttachmentError(error: unknown): error is AttachmentError` — Identify a failure emitted by this attachment capability by its stable code.
- saveImage `abstract saveImage(input: SaveImageAttachment): Promise<ImageAttachmentRef>` — Validate and durably commit one image before its owning session event is appended. The returned reference describes the persisted normalized image. When normalization reduces the raster, its `originalDimensions` records the orientation-applied input dimensions.
- readImage `abstract readImage(ref: ImageAttachmentRef, signal?: AbortSignal): Promise<StoredImageAttachment>` — Read one image and verify its ID, format, byte length, and dimensions against the supplied reference.
- imageHostPath `imageHostPath(ref: ImageAttachmentRef): string \| undefined` — Locate the provider-owned normalized object in the harness host filesystem.
- saveFile `saveFile(input: SaveFileAttachment): Promise<FileAttachmentRef>` — Durably commit one file byte-for-byte before its owning session event is appended. Files carry no admission limits: any byte content and length is accepted, and the stored object is the exact submitted bytes. Backends without verbatim file storage keep this default rejection.
- saveFileStream `saveFileStream(input: SaveFileStreamAttachment): Promise<FileAttachmentRef>` — Durably commit one file byte-for-byte from bounded chunks. Providers must apply backpressure and must not collect the complete file in memory. Backends without streamed verbatim storage keep this default rejection.
- fileHostPath `fileHostPath(ref: FileAttachmentRef): string \| undefined` — Locate the verbatim stored file object in the harness host filesystem.
- readImageRequest `readImageRequest( ref: ImageAttachmentRef, target: ImageRequestTarget, signal?: AbortSignal, ): Promise<RequestImageAttachment>` — Generate or read one deterministic model-request version from the stored normalized image.

### `authorization` — `@deepseek-ai/dsh-authorization`

- 提供类型：`AuthorizationService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-authorization` (`packages/credentials/authorization/src/index.ts:189`，class)
- 提供方：`@deepseek-ai/dsh-authorization` (`packages/credentials/authorization/src/index.ts:197`)
- 消费方：@deepseek-ai/dsh-deepseek-account(`packages/credentials/deepseek-account/src/index.ts` via inject)

- registerFlow `registerFlow(flow: AuthorizationFlow): () => void` — Offer a way to obtain one credential. One flow per key: two plugins claiming the same key would each write a record in their own format, and whichever ran last would leave the other reading a payload it cannot parse.
- yield `yield () =>`
- list `list(): readonly AuthorizationEntry[]` — Every registered flow, for a surface listing what can be authorized.
- describe `describe(key: CredentialKey): AuthorizationEntry \| undefined` — One registered flow.
- entry `private entry(flow: AuthorizationFlow): AuthorizationEntry` — The public view of one registered flow. */
- cancel `cancel(key: CredentialKey): void` — Withdraw the attempt running for a key, if any. Separate from the request's own signal because a request/response transport answers a Cancel button on a second call, with no handle on the first one's signal.
- begin `async begin(request: AuthorizationRequest): Promise<AuthorizationOutcome>` — Run one attempt to authorize a key, and report how it ended. One attempt per key at a time. A second caller is refused rather than joined: the two would be prompting different humans through the same flow, and the second would answer questions the first was asked. attempt and observed, or `cancelled` when the human declined or the caller withdrew. `UNKNOWN_METHOD` when the named method is not one the flow offers, `ALREADY_IN_FLIGHT` when an attempt is already running for the key, or `NOT_COMMITTED` when the flow resolved without committing a record during the attempt.
- settle `private settle(key: CredentialKey, settlement: AuthorizationSettlement): void` — Fan `authorization/settled` out with contained listener failures: every listener runs, and a sync throw or async rejection is logged without changing the finished attempt's own outcome. The attempt is already over and its key released when this fires, so a broken watcher (that second browser tab) can never turn the caller's settled result into a failure of its own.
- warnSettledListenerFailure `private warnSettledListenerFailure(key: CredentialKey, error: unknown): void` — Contained-listener diagnostic shared by the sync and async failure paths. */
- attempt `private async attempt( flow: AuthorizationFlow, method: string, signal: AbortSignal, interaction: AuthorizationInteraction, ): Promise<AuthorizationOutcome>` — Run the flow, then hold it to its half of the commit contract. */
- unwatch `unwatch()`

### `browserUse` — `@deepseek-ai/dsh-browser-use`

- 提供类型：`BrowserUseRegistry`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-browser-use` (`packages/browser-use/browser-use/src/index.ts:16`，class)
- 提供方：`@deepseek-ai/dsh-browser-use` (`packages/browser-use/browser-use/src/index.ts:20`)
- 消费方：@deepseek-ai/dsh-experimental-browser-use-chrome-devtools-mcp(`packages/experimental/browser-use-chrome-devtools-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-playwright-mcp(`packages/experimental/browser-use-playwright-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-stagehand-native(`packages/experimental/browser-use-stagehand-native/src/index.ts` via inject)

- register `register(name: BrowserUseProviderName): () => Promise<void>` — Reserve the sole provider slot until the contribution is disposed. A second registration fails even when it repeats the current name. Providers must stop their tools and await owned work before releasing this registration.

### `chatFileMentions` — `@deepseek-ai/dsh-client-ui-chat`

> Optional prose file-mention provider. */

- 提供类型：`ChatFileMentions`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-chat` (`packages/client/ui-chat/src/client/contract/slots.ts:142`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-deliverables` (`packages/client/ui-deliverables/src/client/index.ts:117`)
- 消费方：@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/chat/register-node-renderers.ts` via ctx.get)

- forClosing `forClosing( owner: TurnTailOwnerProps, sessionId: SessionId, getFileTriggerProps?: (path: string) => ContextMenuTriggerProps, ): MarkdownFileMentions \| undefined` — Resolve prose links for one closing Turn.

### `claudeCodeMods` — `@deepseek-ai/dsh-experimental-claude-code-mods`

- 提供类型：`ClaudeCodeMods`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-experimental-claude-code-mods` (`packages/experimental/claude-code-mods/src/index.ts:201`，class)
- 提供方：`@deepseek-ai/dsh-experimental-claude-code-mods` (`packages/experimental/claude-code-mods/src/index.ts:219`)

- assertPositive `assertPositive('hookTimeoutMs', hookTimeoutMs)`
- assertPositive `assertPositive('catchTimeoutMs', catchTimeoutMs)`
- assertPositive `assertPositive('processTimeoutMs', processTimeoutMs)`
- assertPositive `assertPositive('bandColumns', bandColumns)`
- assertPositive `assertPositive('bandRows', bandRows)`
- report `report(`a button's onPress failed: ${messageOf(error)}`)`
- setTimeout `setTimeout(() => { if (agentOf(sessionId) !== undefined) void surfaces.refresh(sessionId) }, 0).unref()`
- redraw `redraw(agent.session.id)`
- redraw `redraw(session.id)`
- watchBand `watchBand(agent: Agent, signal: AbortSignal): AsyncIterable<SurfaceSnapshot>` — Watch the band above the prompt of one session: the current drawing, then every redraw, until the Client stops watching.  *(decorators: @@Remote({ mode: 'stream' }))*
- pressBand `pressBand(agent: Agent, generation: number, actionId: string): Promise<SurfaceSnapshot>` — Press a button of the band's current drawing: runs the mod's `onPress` and redraws.  *(decorators: @@Remote)*
- add `async add(definition: ModDefinition): Promise<() => Promise<void>>` — Load one mod beneath every mod loaded before it: run its `register`, keep its hooks, and report which of its events this host never raises.

### `clientModules` — `@deepseek-ai/dsh-client-modules`

> The web plugin table (provided by the client-modules node half). */

- 提供类型：`ClientModuleRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-modules` (`packages/client/modules/src/index.ts:646`，class)
- 提供方：`@deepseek-ai/dsh-client-modules` (`packages/client/modules/src/index.ts:672`)
- 消费方：@deepseek-ai/dsh-client-hmr(`packages/client/hmr/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/viewer-assets.ts` via ctx.get)

- queueMicrotask `queueMicrotask(() => { this.flushQueued = false this.flush((err) => { ctx.logger.warn(err) }) })`
- graph `graph(): WebBootGraph` — Current composed entry graph (stable object between changes).
- clientPath `clientPath(id: string): string \| undefined` — Absolute path of an entry's client bundle.
- fetchBundle `async fetchBundle(request: Request): Promise<Response>` — Serve an advertised revisioned bundle, source map, chunk, or package asset without a Web server. Unknown URLs return 404, unsupported methods return 405, and `HEAD` returns the same immutable headers without materializing a body. Each bundle body is built once on its first `GET`; script construction never reads maps. A package asset is read on every request and answers 304 without a body when `If-None-Match` equals its entity tag; its body holds the file open until the caller consumes or cancels it. A bundle, map, or chunk body is the held buffer itself, not a copy, so a caller must not modify its bytes.
- artifactBaseline `artifactBaseline(id: string): ClientArtifactBaseline \| undefined` — Filesystem baseline captured before an entry's current bytes were read. HMR compares it with the live files when installing a watch, so a write between startup composition and watch installation cannot disappear into the watcher's initial state.
- rebuilt `rebuilt(id: string): string \| undefined` — Publish one completed bundle generation (the HMR watch's registration hook; an entry restart publishes through reconciliation instead). Unchanged mtime, ctime and size preserve the graph without reading the bundle.
- notify `notify(id, rev)`
- onRebuilt `onRebuilt(listener: (id: string, rev: string) => void): () => void` — Subscribe to bundle rebuilds; fires when {@link rebuilt} changes a rev. A rev an entry restart publishes reaches only {@link onGraphChanged} listeners.
- onGraphChanged `onGraphChanged(listener: () => void): () => void` — Fires after any flush that recomposed the graph (row added/removed, or a rebuilt rev change). Pull model: listeners re-read {@link graph}.
- compose `private compose(): WebBootGraph`
- notifyGraphChanged `private notifyGraphChanged(): void`
- listener `listener()`
- resolveMeta `private resolveMeta(loaderName: string, baseUrl: string): ResolvedPkgMeta \| null`
- locatePkgJson `private locatePkgJson(loaderName: string, baseUrl: string):` — Locate the manifest of the package the Loader mounts for a row. The row's module location is authoritative: the specifier resolves through the same Loader resolution that imported the row's host half — including any active ESM hooks — and the nearest ancestor manifest declaring the name owns the module. Tree-anchored `require` resolution remains only for runtimes without Node internals.
- nearestPackage `private nearestPackage( moduleUrl: string, expectedPackageName?: string, ):`
- sourceKey `private sourceKey(loaderName: string, baseUrl: string): string`
- captureArtifactBaseline `private captureArtifactBaseline(clientPath: string): ClientArtifactBaseline` — Capture the bundle stats before reading its bytes. */
- readClientBundle `private readClientBundle<T>(pkgName: string, clientPath: string, read: () => T): T` — Run one filesystem read of a declared client bundle.
- processOne `private processOne(entryName: string, entries: readonly Entry[], onError: (err: Error) => void): boolean` — Reconcile one entry name against its sources at flush start.
- onError `onError(error instanceof Error ? error : new Error(String(error)))`
- resolveSource `private resolveSource(entry: Entry): ClientPackageSource \| undefined`
- reconcilePackage `private reconcilePackage(packageName: string): boolean`
- flush `private flush(onError: (err: Error) => void): void`
- onError `onError(error as Error)` — An unorderable module graph is a property of the whole table, not of the arriving package, so it surfaces here: aggregated into the activation throw, or warned in steady state while the last orderable graph stays served.
- chunkRequest `private chunkRequest(requestUrl: URL):` — Match an exact current-revision package-local chunk URL without reading its file. */
- chunkResponse `private chunkResponse(requestUrl: URL): LazyResponse \| undefined` — Build a package-local chunk response only when its URL is requested. */
- assetResponse `private assetResponse( method: 'GET' \| 'HEAD', record: WebPluginRecord \| undefined, assetPath: string, ifNoneMatch: string \| undefined, ):` — Answer one package-asset request. Node's `require.resolve` applies the package's `./assets/*` export as a self-reference, so unexported, `.`/`..`, missing, and directory paths answer 404. The build writes each asset's content revision into its file name, so a served path names one content: the body streams from disk on every request, and the path is the entity tag.
- bundleResource `private async bundleResource(method: string \| undefined, url: string, ifNoneMatch: string \| undefined): Promise<` — Answer one `/plugins` request. A `/plugins/<package>/assets/` path is answered by the package-asset route alone; any other path is an advertised combo or its map, a prior startup generation, or a current-revision package-local chunk, in that order, and otherwise 404.

### `cmdlineArgs` — `@deepseek-ai/dsh-cmdline`

> The invocation's inner arguments; provided by a launcher before the tree mounts. */

- 提供类型：`CmdlineArgs`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:27`，interface)
- 提供方：`@deepseek-ai/dsh-cmdline` (`packages/boot/cmdline/src/index.ts:86`)
- 消费方：@deepseek-ai/dsh-acp-app(`packages/bundle/acp-app/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/startup.ts` via inject)、@deepseek-ai/dsh-sdk-app(`packages/bundle/sdk-app/src/index.ts` via inject)、@deepseek-ai/dsh-web-app(`packages/bundle/web-app/src/startup.ts` via inject)、@deepseek-ai/dsh-cmdline(`packages/boot/cmdline/src/index.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/startup.ts` via ctx.get)、@deepseek-ai/dsh-experimental-inspector(`packages/experimental/inspector/src/host/plugin.ts` via ctx.get)

- get `get(): readonly string[]` — Read the inner arguments.

### `commandUi` — `@deepseek-ai/dsh-client-ui-commands`

- 提供类型：`CommandUiRuntime`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-commands` (`packages/client/ui-commands/src/client/service.ts:76`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-commands` (`packages/client/ui-commands/src/client/service.ts:93`)
- 消费方：@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via ctx.get)

- register `register(contribution: CommandContribution): () => void` — Register one client command contribution; effect disposer (rides the caller's fiber). Duplicate names throw.
- decorate `decorate(decoration: CommandDecoration): () => void` — Hang a bare-invocation decoration on one host command; effect disposer (rides the caller's fiber). Duplicate names throw.
- dismiss `dismiss(name: string): void` — Close every open popup for a command whose options have become stale. Pending loads and confirmations lose their binding; drafts stay intact.
- popupFor `popupFor(actx: ClientContext): PopupSelectController<ClientSessionContext>` — Resolve the per-session popup controller (lazy; dies with the session scope). The controller's consume callback dispatches the scoped consume-token event back to this session; focusComposer reaches the session's composer through the conversation input face.
- candidates `private async candidates(session: ClientSessionContext, req: CandidateRequest): Promise<readonly InputTriggerCandidate[]>` — Menu candidates: host catalog + contribution availability, built-in rows localized, then position filtering; sections for an empty query, the shared name-and-label ranking for a typed one.
- dispatch `private dispatch(pick: InputTriggerPick): PickOutcome` — Decision table, menu column: contribution/decorated-host → popup or action; host input → claim; host bare → detached execute. */
- matchSpace `private matchSpace(session: ClientSessionContext, token: string): PickOutcome` — Decision table, space column: hot-key sync check; only host leadingInput claims. */
- matchClaim `private async matchClaim(session: ClientSessionContext, token: string, signal: AbortSignal): Promise<CommandClaim \| undefined>` — Restore column: the space column's answer once the session's catalog is ready (a warmup failure rejects). It only resolves; nothing is invoked or executed.
- claimOf `private claimOf(session: ClientSessionContext, token: string): CommandClaim \| undefined` — The host leadingInput claim a token names in the hot catalog; popup and action kinds never claim. */
- matchEnter `private async matchEnter( session: ClientSessionContext, line: string, signal: AbortSignal, envelope: SubmitEnvelope, ): Promise<PickOutcome>` — Decision table, enter column. Strong-waits the session's catalog (a warmup failure rejects — never a silent downgrade). Contributions and bare host commands act on the bare token only; leadingInput claims args-tolerant. Envelope policy: an enter submission carrying attachments resolves only through a command declaring attachment acceptance. Every other submitting route — popup, non-accepting claim, bare detached execute — throws the refusal so the machine surfaces one composer notice and the draft and attachments stay in place; nothing executes and nothing is dropped. An action submits nothing and runs regardless. A typed token is resolved through the localized claim tokens, so a line written as `/计划` reaches the `plan` descriptor and executes as `/plan`.
- invoke `private invoke( name: string, ui: CommandContribution['ui'], session: ClientSessionContext, segment: TokenSegment, ): void` — Invoke one contribution or decoration (menu pick / bare enter): open the session's popup, or consume the token and run the action.
- leadingClaim `private leadingClaim(desc: CommandDescriptor, session: ClientSessionContext, shown: string): CommandClaim` — Build the leadingInput claim. The composer keeps the claimed token in the draft and reads the arguments after it, so the token is the spelling the draft will carry: the locale's token for a menu pick, the typed spelling for Space and Enter. The command.execute submit transaction always sends the catalog name.
- execute `private async execute( session: ClientSessionContext, line: string, attachments: readonly SubmitAttachment[] = [], ): Promise<SubmitOutcome>` — The command.execute transaction, addressed to the session's agent — pure admission semantics. An unmatched line reports an error outcome (the composer's immediate admission feedback); an admitted command reports plain success regardless of its handler outcome, because the host executor durably logged the lifecycle (`command/run`/`command/done`) and the outcome renders as a persistent flow node — the composer never echoes it. A handler error result reports an error outcome so the composer keeps the draft and attachments for correction. A refused call throws.
- notifyExecuted `private notifyExecuted(sessionId: SessionId, name: string, result: CommandResult): void` — Publish the local acknowledgment without letting an observer change command admission. */
- warnExecutedListenerFailure `private warnExecutedListenerFailure(name: string, error: unknown): void` — Log one contained `command/executed` observer failure. */
- runDetached `private runDetached(desc: CommandDescriptor, session: ClientSessionContext, line: string): void` — Fire-and-forget execute for the internal ('handled') paths. Outcomes are NOT surfaced here: the host executor durably logs the command lifecycle (`command/run`/`command/done`), and the mux-broadcast events render as a persistent flow node on every tab. Only an admission failure — which never entered a handler and therefore never logged — falls back to the composer notice as immediate feedback.
- consumeVia `private consumeVia(id: SessionId, segment: TokenSegment): void` — Dispatch a consume-token event to one session (menu-pick / bare-enter execute paths). */
- noticeFor `private noticeFor(id: SessionId, level: 'info' \| 'error', text: string): void` — Route an admission failure to the session's composer notice channel (scope gone = attempt died with it). */
- scopeFor `private scopeFor(id: SessionId): ClientContext \| undefined` — id → actx interchange (registered exchange point: this service coordinates for projection-only sources). */
- sessions `private sessions(): ISessions`

### `commands` — `@deepseek-ai/dsh-commands`

- 提供类型：`CommandRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-commands` (`packages/interaction/commands/src/index.ts:263`，class)
- 提供方：`@deepseek-ai/dsh-commands` (`packages/interaction/commands/src/index.ts:277`)
- 消费方：@deepseek-ai/dsh-client-file-upload(`packages/client/file-upload/src/index.ts` via inject)、@deepseek-ai/dsh-command-compact(`packages/compaction/command-compact/src/index.ts` via inject)、@deepseek-ai/dsh-command-feedback(`packages/feedback/command-feedback/src/index.ts` via inject)、@deepseek-ai/dsh-command-goal(`packages/goal/command-goal/src/index.ts` via inject)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)

- register `register(definition: CommandDefinition): () => void` — Register a global or calling-agent-scoped command.
- registerFileReceiptResolver `registerFileReceiptResolver(resolver: CommandFileReceiptResolver): () => void` — Register the sole authority that resolves staged file receipts for command submissions.
- list `list(agent: Agent): readonly CommandDescriptor[]` — List the effective immutable command descriptors for one agent.  *(decorators: @@Remote)*
- find `find(agent: Agent, name: string): CommandDefinition \| undefined` — Resolve one effective command definition.
- execute `async execute( agent: Agent, line: string, submittedAttachments: readonly CommandSubmitAttachment[], signal: AbortSignal, ): Promise<CommandExecution \| undefined>` — Parse and execute a known command without sending it to the model. A resolved command's lifecycle is logged: `command/run` is appended before the handler is invoked and `command/done` after settlement (a thrown or aborted handler settles as `kind: 'error'`). Both are direct log-only appends — no turn wraps them, and persistence drains them at ordinary checkpoints. Admission misses (syntax or unknown name) log nothing — they never entered a handler. A `command/run` append failure fails the execution loud; a `command/done` append failure on the handler-failure path is contained so the handler's own error stays the reported failure. Attachment admission is enforced here, not in the composer: attachments sent to a command that does not declare `input.attachments`, an absent attachment store, and an exceeded image limit each settle as an error result before the handler runs. Validation rejection starts no attachment writes; a storage failure can leave only unreachable content-addressed objects for deferred collection. in submission order; empty for a plain invocation. `undefined` when syntax or name does not resolve.  *(decorators: @@Remote)*
- settleThrown `private settleThrown(session: Session, command: string, commandId: CommandId, error: unknown): void` — Contained `command/done` error append for a thrown handler or admission failure. */
- mintCommandId `private mintCommandId(): CommandId` — Mint the next pairing id (monotonic; instance-token-prefixed so a resumed log never repeats one). */
- appendLifecycle `private appendLifecycle<T extends 'command/run' \| 'command/done'>( session: Session, type: T, data: SessionEventMap[T], ): SessionEvent<T>` — Append one log-only lifecycle event directly: no turn is opened for it and no flush is forced — persistence observes the eager `session/event` path and drains at ordinary checkpoints and teardown, like every other standalone plugin event.
- view `private view(agent: Agent): Map<string, RegisteredCommand>` — Resolve global definitions followed by exact scoped shadows. */
- notifyChange `private notifyChange(): void` — Notify every registry observer without making UI refresh load-bearing. */

### `compaction` — `@deepseek-ai/dsh-compaction`

- 提供类型：`CompactionEngine`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-compaction` (`packages/compaction/compaction/src/index.ts:119`，class)
- 提供方：`@deepseek-ai/dsh-compaction` (`packages/compaction/compaction/src/index.ts:121`)
- 消费方：@deepseek-ai/dsh-command-compact(`packages/compaction/command-compact/src/index.ts` via inject)

- compactIfNeeded `abstract compactIfNeeded( agent: CompactionAgentContext, trigger: CompactionTrigger, signal: AbortSignal, ): Promise<CompactionResult \| null>` — Consider automatic compaction for one explicit trigger. Pressure policy uses the latest durable routed request, while context-overflow policy may force a useful balanced reduction even below the normal threshold. Return `null` when no safe range can be compacted. A single oversized retained unit or request envelope cannot be repaired through surface compaction.
- compactNow `abstract compactNow( agent: ManualCompactAgentContext, signal: AbortSignal, sourceCommandId?: CommandId, ): Promise<CompactionResult \| null>` — Explicitly compact useful history even below automatic pressure thresholds. Implementations synchronously start an idle task before any asynchronous work, select a useful range without writing on a no-op, then append a standalone `compaction/start` before summarization. That durable marker is the compaction lock until one `compaction/end` attempt. Later waking prompts remain accepted in FIFO order and start only after the optional durability checkpoint and idle-task settlement. Context injected while the summary runs may sit between the marker pair; only the selected span must remain stable. changed-span, summarization/shrink, commit-stage, or persistence failures; an aborted request preserves its exact abort reason. Failed attempts remain visible in the log.
- compactRegion `abstract compactRegion( start: SessionSeq, end: SessionSeq, agent: CompactionAgentContext, signal?: AbortSignal, ): Promise<CompactionResult>` — Forcibly compact a range of surface nodes into a single summary node. `start` and `end` name an inclusive span by surface position, not numeric seq order; replacements can make visible seqs non-monotonic. Both edges must be balanced so assistant tool calls remain paired with their results. A model- backed implementation forwards cancellation and rejects active, missing, reversed, or unbalanced ranges. The target session is `agent.session`. Its replacement user message must use {@link compactCheckpointSource} with the transaction's `CompactionId`. Use {@link toolPairingBalancedBefore} and {@link toolPairingBalancedAfter} for the edge checks.

### `computerUse` — `@deepseek-ai/dsh-computer-use`

- 提供类型：`ComputerUseRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-computer-use` (`packages/computer-use/computer-use/src/index.ts:16`，class)
- 提供方：`@deepseek-ai/dsh-computer-use` (`packages/computer-use/computer-use/src/index.ts:20`)
- 消费方：@deepseek-ai/dsh-experimental-computer-use-cua-driver-mcp(`packages/experimental/computer-use-cua-driver-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-computer-use-cua-driver-native(`packages/experimental/computer-use-cua-driver-native/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-cua-macos(`packages/experimental/cua-macos/src/index.ts` via inject)

- register `register(name: ComputerUseProviderName): () => Promise<void>` — Reserve the sole provider slot until the contribution is disposed. A second registration fails even when it repeats the current name. Providers must stop their tools and await owned work before releasing this registration.

### `configEditor` — `@deepseek-ai/dsh-config-editor`

> Persistent edits to the active profile's plugin configuration. */

- 提供类型：`ConfigEditor`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-config-editor` (`packages/boot/config-editor/src/index.ts:26`，class)
- 消费方：@deepseek-ai/dsh-settings(`packages/settings/settings/src/index.ts` via inject)、@deepseek-ai/dsh-agent-default-model(`packages/core/agent-default-model/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/access.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/access.ts` via ctx.get)

- entries `entries(): Entry[]` — Addressable profile rows; nested Includes have independent configuration ownership.
- configuration `configuration(): Array<` — Read inherited and explicit profile values for the active entries.
- inherited `private inherited(entry: Entry, loaded: ReturnType<typeof loadProfileDirectory>): Record<string, unknown>`
- edit `async edit( entry: Entry, change: (current: Record<string, unknown>, inherited: Record<string, unknown>) => Record<string, unknown>, ): Promise<void>` — Validate, persist, and reconcile a plugin's next config; ordinary fields keep normal lifecycle rules.
- visit `visit(document, { Map(_key, node) { if (node.items.length !== 1 \|\| typeof node.get('__jsExpr') !== 'string') return const expression = new Scalar(node.get('__jsExpr')) expression.t…`

### `configForms` — `@deepseek-ai/dsh-client-ui-settings`

- 提供类型：`ConfigForms`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-settings` (`packages/client/ui-settings/src/client/config-form.ts:236`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-settings` (`packages/client/ui-settings/src/client/config-form.ts:258`)
- 消费方：@deepseek-ai/dsh-client-locale(`packages/client/locale/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-agent-loop(`packages/client/ui-settings-agent-loop/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-session-log(`packages/client/ui-settings-session-log/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-shell(`packages/client/ui-settings-shell/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-subagent(`packages/client/ui-settings-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-web-search(`packages/client/ui-settings-web-search/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-theme(`packages/client/ui-theme/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/client/mount.ts` via inject)

- describe `describe(): SettingsDescribeFace` — The shared mirror's read/fold face for cross-namespace surfaces (schema introspection, the served-namespace directory). Per-namespace consumers use {@link get}; both derive from the same snapshot, so they can never disagree about the document.
- get `get<T>(entryId: string): ConfigForm<T>` — Get the shared form values and write queue for one Host plugin entry.
- whileServed `whileServed(namespaces: readonly string[], register: (served: ReadonlySet<string>) => () => void): () => void` — Keep a registration alive while the Host serves any of some namespaces: `register` runs once one of them is in the describe mirror, and its disposer runs when none is or when the returned disposer runs. A plugin whose page edits a namespace another plugin owns registers the page through this, so a deployment that never composed the owner shows no trace of the page. The caller owns the returned disposer and wraps it in `ctx.effect`; unlike {@link bind}, nothing is registered on the caller's context here.
- off `off()`
- sync `sync()`
- unsubscribe `unsubscribe()`

### `configuredAgentIdentities` — `@deepseek-ai/dsh-agent-loop`

> Launcher-owned exact session identities for configured agents, keyed by the agent's config `id` and set with `ctx.provide()` before any Loader entry mounts (see {@link CONFIGURED_AGENT_IDENTITIES_KEY}). A launcher owns identity because only it knows whether the session already exists, while the `cordis.yml` row keeps the model route as ordinary patchable config. An entry with no matching key keeps its configured identity.

- 提供类型：`ConfiguredAgentIdentities`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-agent-loop` (`packages/core/agent-loop/src/index.ts:218`，interface)

- （方法未解析：提供类型不可达或未定义成员）

### `connection` — `@deepseek-ai/dsh-client-connection`

> Host Connection transport and RPC registrations. */

- 提供类型：`HostConnectionHandle`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-connection` (`packages/client/connection/src/rpc.ts:206`，interface)
- 提供方：`@deepseek-ai/dsh-client-connection` (`packages/client/connection/src/client/index.ts:336`)、`@deepseek-ai/dsh-client-connection` (`packages/client/connection/src/rpc-host.ts:92`)
- 消费方：@deepseek-ai/dsh-api-gateway(`packages/api/gateway/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-file-upload(`packages/client/file-upload/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-inspector(`packages/experimental/inspector/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via inject)、@deepseek-ai/dsh-host-directory-picker-auto(`packages/host/directory-picker-auto/src/index.ts` via inject)、@deepseek-ai/dsh-host-frontend-static(`packages/host/frontend-static/src/index.ts` via inject)、@deepseek-ai/dsh-host-open-in-app(`packages/host/open-in-app/src/index.ts` via inject)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/index.ts` via inject)、@deepseek-ai/dsh-api-gateway(`packages/api/gateway/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/catalog.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/viewer-session-plugin.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/viewer-session-plugin.ts` via ctx.get)、@deepseek-ai/dsh-experimental-webworker-runtime(`packages/experimental/webworker-runtime/src/worker-host.ts` via ctx.get)、@deepseek-ai/dsh-client-test-runtime(`packages/test-support/client-runtime/src/assembly/remote-proxies.ts` via ctx.get)、@deepseek-ai/dsh-client-test-runtime(`packages/test-support/client-runtime/src/assembly/test-client.ts` via ctx.get)

- createSharedFetchHandler `createSharedFetchHandler(channel: '/api'): ConnectionFetchHandler` — Compose exact Fetch routes and the shared-channel RPC interceptor.
- requestRejection `requestRejection(request: ConnectionTrustRequest): ConnectionRequestRejection` — Apply Connection's Host/Origin checks and browser authentication to another Web route.
- admit `admit(request: ConnectionTrustRequest): PeerAdmission` — Admit an HTTP request against its signed browser or API credential and live Peer.
- createPeer `createPeer(options: { readonly principal: Principal; readonly interactions?: 'answer' \| 'none' }): PeerScope` — Create an independent in-process Peer, disposed with the Context that read `ctx.connection`.
- admitConnection `admitConnection(request: ConnectionTrustRequest): ConnectionAdmission` — Claim a physical socket for an API Peer; browser sockets share their owner Peer. The carrier releases on socket termination or failed upgrade; release removes API admission synchronously without cancelling independent HTTP calls.
- authorizeIndex `authorizeIndex(request: ConnectionIndexRequest, response: ConnectionIndexResponse): boolean` — Authenticate one frontend index request, owning a token redirect or 401. The cookie this mints is `Secure` when the mounted Web carrier serves TLS, which only that listener's protocol decides.
- authenticatedUrl `authenticatedUrl(baseUrl: string): string` — Add the fresh process token to an ordinary Web application URL.

### `conversation` — `@deepseek-ai/dsh-client-ui-conversation`

> Scope-addressed Conversation actions and per-Session input registry. */

- 提供类型：`import('./service.ts').IConversation`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-conversation` (`packages/client/ui-conversation/src/client/service.ts:185`)
- 消费方：@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/navigation.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `cordisInspect` — `@deepseek-ai/dsh-cordis-client-runner`

> Browser registry for pre-definition Cordis capability discovery. */

- 提供类型：`ClientCordisInspectRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cordis-client-runner` (`packages/extensions/cordis-client-runner/src/client/inspect-registry.ts:39`，class)
- 提供方：`@deepseek-ai/dsh-cordis-client-runner` (`packages/extensions/cordis-client-runner/src/client/inspect-registry.ts:149`)、`@deepseek-ai/dsh-cordis-host-runner` (`packages/extensions/cordis-host-runner/src/inspect-registry.ts:59`)
- 消费方：@deepseek-ai/dsh-tool-cordis(`packages/extensions/tool-cordis/src/host.ts` via inject)、@deepseek-ai/dsh-tool-cordis(`packages/extensions/tool-cordis/src/index.ts` via inject)

- register `register(registration: ClientCordisInspectProviderRegistration): () => void` — Register one Client provider and publish a new complete manifest.
- publish `publish(): void` — Publish the current complete manifest, including after reconnect. */
- queueMicrotask `queueMicrotask(() => { this.publishQueued = false const manifests = [...this.providers.values()].map(provider => provider.manifest) this.syncChain = this.syncChain.then(async () =>…`
- query `async query(request: CordisInspectQueryRequest): Promise<void>` — Execute and answer one Host-broadcast query.
- close `close(requestId: CordisInspectRequestId): void` — Cancel local work after another page answered or the Tool call ended.

### `cotTranslation` — `@deepseek-ai/dsh-experimental-client-ui-cot-translation`

> Remote consumer of the experimental translation service. */

- 提供类型：`CotTranslationController`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-experimental-client-ui-cot-translation` (`packages/experimental/client-ui-cot-translation/src/index.ts:37`)

- （方法未解析：提供类型不可达或未定义成员）

### `credentials` — `@deepseek-ai/dsh-credentials`

- 提供类型：`CredentialProvider`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-credentials` (`packages/credentials/credentials/src/index.ts:171`，class)
- 提供方：`@deepseek-ai/dsh-credentials` (`packages/credentials/credentials/src/index.ts:173`)
- 消费方：@deepseek-ai/dsh-client-connection(`packages/client/connection/src/index.ts` via inject)、@deepseek-ai/dsh-authorization(`packages/credentials/authorization/src/index.ts` via inject)、@deepseek-ai/dsh-deepseek-account(`packages/credentials/deepseek-account/src/index.ts` via inject)、@deepseek-ai/dsh-webhook-github(`packages/experimental/webhook-github/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/catalog.ts` via ctx.get)、@deepseek-ai/dsh-api-settings-controller(`packages/api/settings-controller/src/credentials.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/deepseek.ts` via ctx.get)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/credential.ts` via ctx.get)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/credential.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/auth.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/auth.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/auth.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/auth.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/index.ts` via ctx.get)、@deepseek-ai/dsh-mcp-client(`packages/mcp/mcp-client/src/credentials.ts` via ctx.get)、@deepseek-ai/dsh-mcp-client(`packages/mcp/mcp-client/src/credentials.ts` via ctx.get)

- resolve `abstract resolve(ref: CredentialRef): Promise<ResolvedCredential \| undefined>` — Resolve one reference to its current value. Resolution is per call: consumers re-resolve at each operation and must not cache across operations — that per-operation read is what makes a changed credential reach the next operation without a restart.
- describe `abstract describe(ref: CredentialRef): Promise<CredentialInfo>` — Describe one reference for configuration surfaces without exposing the full value.
- set `abstract set(ref: CredentialRef, value: string): Promise<void>` — Durably store one value in the provider-managed writable source. The stored value takes precedence over ambient fallbacks, and empty values are rejected (use {@link unset}).
- unset `abstract unset(ref: CredentialRef): Promise<void>` — Remove one reference from the provider-managed writable source; removing an absent reference is a no-op. Ambient fallback layers may become effective again after removal.
- readRecord `abstract readRecord(key: CredentialKey): Promise<CredentialRecord \| undefined>` — Read one stored record. The value is returned as its owner wrote it; a {@link GrantRecord} payload is not interpreted on the way out.
- describeRecord `abstract describeRecord(key: CredentialKey): Promise<CredentialRecordInfo>` — Describe one record for configuration surfaces without exposing its value.
- listRecords `abstract listRecords(): Promise<readonly CredentialRecordEntry[]>` — Enumerate every stored record's address and tag. Unlike the reference half, which has no enumeration because configuration surfaces learn which references exist from settings schemas, records have no such discovery path: a surface that cannot list them cannot show what a user is authorized for, nor find an orphan left by an uninstalled plugin.
- modifyRecord `abstract modifyRecord( key: CredentialKey, mutate: (current: CredentialRecord \| undefined) => Promise<CredentialRecord \| undefined>, ): Promise<CredentialRecord \| undefined>` — Serialized read-modify-write over one record — the only write path. `mutate` sees the record as it stands at the moment the write is exclusive, and returning `undefined` leaves the entry untouched. Exclusion holds across processes where the backing store supports it, which is what makes a token refresh safe: two processes rotating one refresh token concurrently would otherwise lose whichever wrote first.
- deleteRecord `abstract deleteRecord(key: CredentialKey): Promise<void>` — Remove one record; removing an absent record is a no-op.
- notifyUpdated `protected notifyUpdated(ref: CredentialRef): void` — Fan `credentials/reference-updated` out with contained listener failures: every listener runs, and a sync throw or async rejection is logged without changing the committed operation's outcome. Providers call this only after the write or reload actually committed, so a broken observer can never make a durable change look failed.
- notifyRecordUpdated `protected notifyRecordUpdated(key: CredentialKey): void` — Fan `credentials/record-updated` out on exactly the terms {@link notifyUpdated} documents, for the record half of the seam.
- fanOut `private fanOut(event: 'credentials/reference-updated' \| 'credentials/record-updated', subject: string): void` — The contained dispatch both notifications run through; see {@link notifyUpdated}. */
- warnListenerFailure `private warnListenerFailure(event: string, subject: string, error: unknown): void` — Contained-listener diagnostic shared by the sync and async failure paths. */

### `credentialsController` — `@deepseek-ai/dsh-api-settings-controller`

> Host owner of the `credentials` Remote namespace. */

- 提供类型：`CredentialsController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-settings-controller` (`packages/api/settings-controller/src/credentials.ts:68`，class)
- 提供方：`@deepseek-ai/dsh-api-settings-controller` (`packages/api/settings-controller/src/credentials.ts:71`)

- describe `async describe(refs: string[]): Promise<Record<string, CredentialInfo>>` — Describe several references for one configuration surface. Batched because a settings page describes every reference its rows name at once, and one round trip keeps those rows from settling separately. rejects the whole call as `gateway/bad-request`.  *(decorators: @@Remote)*
- set `async set(ref: string, value: string): Promise<void>` — Store one value from a configuration surface. The value crosses the wire in this direction only: no read path returns it.  *(decorators: @@Remote)*
- unset `async unset(ref: string): Promise<void>` — Remove one reference from a configuration surface.  *(decorators: @@Remote)*
- provider `private provider(): CredentialProvider` — Resolve the optional provider or report how to supply it. */
- write `private async write(ref: string, write: () => Promise<void>): Promise<void>` — Run one remote write and report every refusal as `credential/rejected` carrying the seam's own message: a provider refusal, such as a stored document that no longer parses, is what a settings page must show verbatim. Callers brand the reference before entering, so a name outside the grammar never reaches this path and fails the same way it does on the read side. The details name only the reference, so no failure path can carry the value back out.

### `cuaAccess` — `@deepseek-ai/dsh-cua`

> Native permission controls and executor-owned application consent. */

- 提供类型：`CuaAccess`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cua` (`packages/experimental/cua/src/access.ts:39`，class)
- 提供方：`@deepseek-ai/dsh-cua` (`packages/experimental/cua/src/access.ts:48`)

- ptcConfiguration `ptcConfiguration():` — Read PTC execution state separately from native permission checks.  *(decorators: @@Remote)*
- enablePersistentPtc `async enablePersistentPtc(): Promise<void>` — Persist in-memory PTC execution through the existing profile editor and Loader lifecycle.  *(decorators: @@Remote)*
- applications `applications(): Promise<CuaApplicationState>` — Read fresh stored application decisions without issuing a native request.  *(decorators: @@Remote)*
- systemStatus `async systemStatus(): Promise<CuaSystemPermissionState>` — Inspect system privileges independently of application decisions and icons.  *(decorators: @@Remote)*
- applicationIcons `async applicationIcons(): Promise<Record<string, string>>` — Load presentation icons separately from application decisions.  *(decorators: @@Remote)*
- requestPermission `async requestPermission(permission: CuaSystemPermission, locale: string): Promise<CuaSystemPermissionState>` — Request the selected system privilege through the native provider.  *(decorators: @@Remote)*
- openSettings `async openSettings(permission: CuaSystemPermission, locale: string): Promise<void>` — Open the macOS privacy pane selected by the user.  *(decorators: @@Remote)*
- revoke `revoke(id: CuaApplicationId): Promise<void>` — Remove saved and session access and join affected operations.  *(decorators: @@Remote)*
- retryApproval `async retryApproval(id: CuaApplicationId): Promise<void>` — Clear this application's refusals across sessions so each session may ask for access again.  *(decorators: @@Remote)*

### `deepseekAccount` — `@deepseek-ai/dsh-deepseek-account`

- 提供类型：`DeepSeekAccount`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-deepseek-account` (`packages/credentials/deepseek-account/src/index.ts:106`，class)
- 提供方：`@deepseek-ai/dsh-deepseek-account` (`packages/credentials/deepseek-account/src/index.ts:136`)
- 消费方：@deepseek-ai/dsh-client-product-analytics(`packages/client/product-analytics/src/index.ts` via inject)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/credential.ts` via ctx.get)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/credential.ts` via ctx.get)、@deepseek-ai/dsh-web-search-deepseek(`packages/web/web-search-deepseek/src/index.ts` via ctx.get)

- installAccountTaskCancellation `installAccountTaskCancellation(ctx)`
- getState `async getState(): Promise<AccountView>` — Read stored-account presence and the latest login attempt.  *(decorators: @@Remote)*
- getProfile `async getProfile(client: AccountClientMetadata): Promise<AccountDetails['profile'] \| null>` — Query Platform profile independently of wallet balances. A ready result whose stable profile ID first becomes available or changes notifies identity-enabled watch consumers, so they re-read getPlatformSession; repeated IDs stay silent.  *(decorators: @@Remote)*
- getBalance `getBalance(client: AccountClientMetadata): Promise<AccountDetails['balance'] \| null>` — Query Platform recharge and bonus wallet balances independently of profile data.  *(decorators: @@Remote)*
- getNotifications `async getNotifications(client: AccountClientMetadata): Promise<AccountNotificationBatch \| null>` — Query unconsumed account notifications in server order without reading profile data.  *(decorators: @@Remote)*
- getNotificationContent `async getNotificationContent(id: AccountNotificationId, client: AccountClientMetadata): Promise<AccountNotification \| null>` — Query localized content of a notification, including one already consumed.  *(decorators: @@Remote)*
- reportNotificationEvent `async reportNotificationEvent(id: AccountNotificationId, event: AccountNotificationEvent, client: AccountClientMetadata): Promise<boolean>` — Report a notification interaction; the backend decides consumption.  *(decorators: @@Remote)*
- cacheProfile `private cacheProfile(token: string, profile: AccountDetails['profile']): void` — Cache one ready profile against the grant token it was read with, so identity reuse cannot cross a credential change. A stable ID that first appears or changes notifies identity-enabled watch consumers, so identity consumers re-read getPlatformSession; repeated IDs stay silent.
- getDetail `private async getDetail<K extends keyof AccountDetails>(field: K, headers: Record<string, string>, captured?: { lifetime: AbortController; stored: z.infer<typeof grant> }): Promise…`
- detailHeaders `private detailHeaders(client: AccountClientMetadata): Record<string, string>` — Deployment account headers plus the client identity headers derived from one call's metadata. */
- rejectToken `async rejectToken(token: string): Promise<void>` — Remove an inference-rejected token only while it still matches the stored login.
- expireCredential `private async expireCredential(token: string, lifetime: AbortController): Promise<void>`
- getDeviceIdentity `async getDeviceIdentity(): Promise<` — Read existing login identity without creating a device or returning credentials.
- getPlatformSession `async getPlatformSession(): Promise<PlatformSession \| null>` — Read credentials for the configured embedded-page origin, bound to their account environment, and pair them with the account ID from the last successful profile read; no profile request is made.
- readCurrentGrant `private async readCurrentGrant(lifetime: AbortController): Promise<z.infer<typeof grant> \| null>`
- resolveToken `async resolveToken(url: string): Promise<string \| undefined>` — Resolve a credential only for the inference origin allowed by the provider.
- startSignIn `async startSignIn(client: AccountClientMetadata, callbackOrigin: string, loginSource: 'web' \| 'desktop'): Promise<AccountView>` — Join an active attempt or start browser authorization.  *(decorators: @@Remote)*
- cancelSignIn `async cancelSignIn(attemptId: SignInAttemptId): Promise<AccountView>` — Cancel only the named attempt; committing attempts settle before returning.  *(decorators: @@Remote)*
- signOut `signOut(client: AccountClientMetadata): Promise<AccountView>` — Remove the local grant while retaining API keys; the provider revokes it in the background.  *(decorators: @@Remote)*
- hasRunningAccountTasks `hasRunningAccountTasks(): boolean` — Inspect running work before sign-out.  *(decorators: @@Remote)*
- stop `stop()`
- watch `watch(signal: AbortSignal, includeIdentityChanges: boolean = false): AsyncIterable<AccountUpdate>` — Subscribe to ordered updates including a complete initial snapshot.
- watchState `watchState(signal: AbortSignal): AsyncIterable<AccountUpdate>` — Stream account state without the Host-only identity subscription option.  *(decorators: @@Remote({ name: 'watch', mode: 'stream' }))*
- revoke `private revoke(token: string, headers: Record<string, string>): void`
- invalidateDetails `private invalidateDetails(): void`
- changed `private changed(kind: 'snapshot' \| 'credentials-changed' \| 'identity'): void`
- update `private update(attempt: Attempt, value: Partial<SignInAttemptView>): void`
- run `private async run(session: AuthorizationSession, attempt: Attempt): Promise<void>`
- clearTimeout `clearTimeout(timer)`
- rejectPayload `private rejectPayload(stage: string, error: z.ZodError): never`
- cancelRequest `private cancelRequest(authorizeId: string, verifier: string, headers: Record<string, string>): void`
- request `private request(method: string, body: unknown, signal: AbortSignal, headers: Record<string, string>): Promise<unknown>`
- finishFailedCallback `private finishFailedCallback(attempt: Attempt): void`

### `deepseekChatImport` — `@deepseek-ai/dsh-deepseek-chat-import`

> Upload route and Remote limits of the DeepSeek chat export importer. */

- 提供类型：`DeepseekChatImportService`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-deepseek-chat-import` (`packages/experimental/deepseek-chat-import/src/index.ts:72`)

- （方法未解析：提供类型不可达或未定义成员）

### `deepseekLlmApiExtensions` — `@deepseek-ai/dsh-deepseek-llm-api-extensions`

- 提供类型：`DeepSeekLlmApiExtensionRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-deepseek-llm-api-extensions` (`packages/llm/deepseek-llm-api-extensions/src/index.ts:66`，class)
- 提供方：`@deepseek-ai/dsh-deepseek-llm-api-extensions` (`packages/llm/deepseek-llm-api-extensions/src/index.ts:72`)
- 消费方：@deepseek-ai/dsh-plugin-package-inventory-deepseek(`packages/llm/plugin-package-inventory-deepseek/src/index.ts` via inject)、@deepseek-ai/dsh-session-log-deepseek(`packages/session/session-log-deepseek/src/index.ts` via inject)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/host.ts` via ctx.get)、@deepseek-ai/dsh-llm-replay(`packages/test-support/llm-replay/src/index.ts` via ctx.get)

- register `register<K extends keyof DeepSeekLlmApiExtensionMap>( field: K, provider: DeepSeekLlmApiExtensionProvider<DeepSeekLlmApiExtensionMap[K]>, ): () => Promise<void>` — Register the sole provider of one top-level request field. Registration is effect-scoped.
- prepare `async prepare(request: DeepSeekLlmApiExtensionRequest): Promise<PreparedDeepSeekLlmApiExtensions>` — Prepare every currently registered field from one immutable base request. A provider whose preparation throws, or whose value cannot be cloned, is omitted from this request; the first such failure per field is logged. Only cancellation rejects. Field values are cloned and frozen; providers retain no mutable alias to the outgoing request.

### `directoryPicker` — `@deepseek-ai/dsh-host-directory-picker`

- 提供类型：`DirectoryPicker`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-host-directory-picker` (`packages/host/directory-picker/src/index.ts:103`，class)
- 提供方：`@deepseek-ai/dsh-host-directory-picker` (`packages/host/directory-picker/src/index.ts:105`)
- 消费方：@deepseek-ai/dsh-api-workspace-controller(`packages/api/workspace-controller/src/directory-picker.ts` via inject)

- capability `abstract capability(): DirectoryPickerCapability` — The backend's interaction capability.

### `directoryPickerController` — `@deepseek-ai/dsh-api-workspace-controller`

> Host directory-picking Remote namespace owner. */

- 提供类型：`DirectoryPickerController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-workspace-controller` (`packages/api/workspace-controller/src/directory-picker.ts:41`，class)
- 提供方：`@deepseek-ai/dsh-api-workspace-controller` (`packages/api/workspace-controller/src/directory-picker.ts:46`)

- pick `async pick(signal: AbortSignal): Promise<string \| null>` — Open the host's OS chooser for a Remote caller.  *(decorators: @@Remote('pick'))*
- list `async list(path: string \| undefined, signal: AbortSignal): Promise<DirectoryListing>` — List one directory level for a Remote caller's in-app browser. letting it outlive a disconnected caller.  *(decorators: @@Remote('list'))*
- createDirectory `async createDirectory(path: string, name: string): Promise<string>` — Create one child directory for a Remote caller's in-app browser.  *(decorators: @@Remote('createDirectory'))*
- requireCapability `private requireCapability<Kind extends keyof DirectoryPickerCapabilities>( kind: Kind, method: string, ): DirectoryPickerCapabilities[Kind]` — Resolve the capability one wire verb needs, or refuse with the kind this backend serves. */

### `documentPreviews` — `@deepseek-ai/dsh-client-ui-sidebar-documentpreview`

> File-extension renderer registrations, independent from their keyed document bodies. */

- 提供类型：`DocumentPreviewRegistry`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-sidebar-documentpreview` (`packages/client/ui-sidebar-documentpreview/src/client/document/registry.ts:71`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-sidebar-documentpreview` (`packages/client/ui-sidebar-documentpreview/src/client/index.ts:92`)

- register `register(definition: DocumentPreviewDefinition): () => void` — Register metadata separately from the matching keyed slot component. `binaryExtensions` entry must appear in `extensions`. binary suffixes outside `extensions` throw.
- candidates `candidates(path: string): readonly DocumentPreviewDefinition[]` — List every matching implementation in automatic-selection order.
- publish `private publish(): void`
- notifySubscribers `notifySubscribers(this.listeners, '[document-previews] registry')`

### `dshHomePath` — `@deepseek-ai/dsh-app-boot`

> Harness-home path resolver available to Loader `!!js` config expressions. */

- 提供类型：`typeof dshHomePath`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-app-boot` (`packages/boot/app-boot/src/index.ts:1243`)

- （方法未解析：提供类型不可达或未定义成员）

### `dynamicCordisRunner` — `@deepseek-ai/dsh-cordis-client-runner`

> Run orchestration and page-local load state: what run surfaces read and call. */

- 提供类型：`CordisRunnerFace`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-cordis-client-runner` (`packages/extensions/cordis-client-runner/src/client/index.ts:65`，interface)
- 提供方：`@deepseek-ai/dsh-cordis-client-runner` (`packages/extensions/cordis-client-runner/src/client/index.ts:290`)、`@deepseek-ai/dsh-cordis-host-runner` (`packages/extensions/cordis-host-runner/src/index.ts:158`)
- 消费方：@deepseek-ai/dsh-client-ui-cordis(`packages/extensions/ui-cordis/src/client/index.ts` via inject)

- reconcileApprovals `reconcileApprovals(rows: readonly DynamicCordisInventoryRow[]): void` — Restore pending approvals after a page reconnect or missed event.
- approve `approve(requestId: ApprovalRequestId, approveFutureVersions: boolean): Promise<void>` — Answer one run request with "run it" and drive both halves.
- decline `decline(requestId: ApprovalRequestId): Promise<void>` — Answer one run request with "do not run it".
- startUserRun `startUserRun(request: CordisUserRunRequest): Promise<void>` — Run a definition here at the user's own request (the gesture authorizes it). A definition with a browser half also loads onto this page; a host-only one only comes up in the host process.
- subscribe `subscribe(fn: () => void): () => void` — Observe what this page has loaded.
- getSnapshot `getSnapshot(): readonly DynamicCordisLivePackage[]` — Read what this page currently has loaded.
- isLoaded `isLoaded(pluginId: CordisDynamicPluginId): boolean` — Whether this page loaded a definition's browser half — page-local truth, never the host's "it is running".

### `feedbackUi` — `@deepseek-ai/dsh-client-ui-message-feedback`

- 提供类型：`FeedbackUi`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-message-feedback` (`packages/client/ui-message-feedback/src/client/index.ts:42`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-message-feedback` (`packages/client/ui-message-feedback/src/client/index.ts:88`)
- 消费方：@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/client/index.ts` via ctx.get)

- openSession `openSession(sessionId: SessionId): void` — Open the Session feedback draft without recording feedback.

### `fileDrag` — `@deepseek-ai/dsh-client-ui-file-drag`

> File transfer ownership scoped to this plugin's lifetime. */

- 提供类型：`FileDragService`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-file-drag` (`packages/client/ui-file-drag/src/client/index.ts:14`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-file-drag` (`packages/client/ui-file-drag/src/client/index.ts:41`)
- 消费方：@deepseek-ai/dsh-client-ui-attachment(`packages/client/ui-attachment/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `fileReferences` — `@deepseek-ai/dsh-file-reference`

- 提供类型：`FileReferenceService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-file-reference` (`packages/context/file-reference/src/index.ts:26`，class)
- 提供方：`@deepseek-ai/dsh-file-reference` (`packages/context/file-reference/src/index.ts:28`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/file-references.ts` via inject)

- list `abstract list( agent: Agent, query: string, signal: AbortSignal, ): Promise<FileReferenceCandidate[]>` — List file and directory candidates for one agent's working directory.

### `fileUpload` — `@deepseek-ai/dsh-client-file-upload`

> Session-addressed browser service for staged file uploads. */

- 提供类型：`FileUploadService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-file-upload` (`packages/client/file-upload/src/client/contract.ts:16`，interface)
- 提供方：`@deepseek-ai/dsh-client-test-runtime` (`packages/test-support/client-runtime/src/index.ts:269`)、`@deepseek-ai/dsh-client-file-upload` (`packages/client/file-upload/src/client/runtime.ts:169`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)

- upload `upload( sessionId: SessionId, data: Blob \| Uint8Array \| ReadableStream<Uint8Array>, name?: string, signal?: AbortSignal, onProgress?: (progress: FileUploadProgress) => void, ): Pro…` — Store one file for a Session. Blob and stream bodies use the background carrier; exact bytes use Remote.
- uploadImage `uploadImage( sessionId: SessionId, data: Blob, mediaType: ImageMediaType, name?: string, signal?: AbortSignal, onProgress?: (progress: FileUploadProgress) => void, ): Promise<Remot…` — Store one prompt image for a Session through the background carrier. The Host validates, normalizes, and stores it as prompt admission would, and a later prompt cites the receipt in a file part.

### `fileUploads` — `@deepseek-ai/dsh-client-file-upload`

> Host storage and staged-receipt service for browser file and image uploads. */

- 提供类型：`FileUploads`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-file-upload` (`packages/client/file-upload/src/index.ts:58`，class)
- 提供方：`@deepseek-ai/dsh-client-file-upload` (`packages/client/file-upload/src/index.ts:69`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)

- registerAgentResolver `registerAgentResolver(resolve: AgentResolver): () => void` — Register the ordinary-Session resolver used when a raw upload addresses a cold Session.
- upload `async upload(agent: Agent, request: EncodedFileUploadRequest, signal: AbortSignal): Promise<FileUploadValue>` — Persist one encoded upload and stage it under the Agent receiver selected by Typert.  *(decorators: @@Remote('upload'))*
- uploadStream `async uploadStream(request: { readonly sessionId: SessionId readonly data: AsyncIterable<Uint8Array> readonly signal?: AbortSignal readonly name?: string }): Promise<FileUploadValu…` — Persist raw chunks for one Session without aggregating the upload.
- uploadImageStream `async uploadImageStream(request: { readonly sessionId: SessionId readonly data: AsyncIterable<Uint8Array> readonly mediaType: string readonly signal?: AbortSignal readonly name?: s…` — Persist one prompt image for a Session: read at most the smaller of the deployment's per-image and per-message byte limits, then validate, normalize, and store the image the way prompt admission does, so a later prompt cites it by receipt. Cancellation before storage begins stores nothing; a cancelled upload never receives a receipt, although an image whose storage already began stays in the content-addressed store. must accept, cancellation, and optional display name.
- resolve `resolve(agent: Agent, receiptId: FileUploadReceiptId): StagedAttachment \| undefined` — Resolve one staged receipt for the receiving Agent's exact Session.
- bindPrompt `bindPrompt( agent: Agent, receiptIds: readonly FileUploadReceiptId[], requestId: string, ): PromptFileBinding` — Bind receipts while one prompt enters an Agent inbox. Disposal restores every prior binding unless the caller commits successful delivery.
- retirePrompt `retirePrompt(agent: Agent, requestId: string): void` — Retire every receipt accepted by one removed queue occurrence.
- store `private async store<T>(agent: Agent, save: () => Promise<T>): Promise<T>` — Store one upload for an ordinary Agent; storage failures become Remote failures. */
- stage `private stage(agent: Agent, attachment: StagedAttachment): FileUploadReceiptId` — Stage one stored upload under a new receipt for the Agent's exact Session. */
- resolveAgent `private async resolveAgent(sessionId: SessionId): Promise<Agent>`
- assertOrdinaryAgent `private assertOrdinaryAgent(agent: Agent): void`
- observeSessionEvent `private observeSessionEvent(session: Session, event: SessionEvent): void`
- retire `private retire(session: Session, requestId: string): void`

### `forge` — `@deepseek-ai/dsh-experimental-forge`

- 提供类型：`ForgeService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-forge` (`packages/experimental/forge/src/index.ts:58`，class)
- 提供方：`@deepseek-ai/dsh-experimental-forge` (`packages/experimental/forge/src/index.ts:85`)
- 消费方：@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-forge-github(`packages/experimental/forge-github/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-forge-session(`packages/experimental/forge-session/src/index.ts` via inject)

- clearTimeout `clearTimeout(this.timer)`
- register `register(provider: ForgeProvider): () => Promise<void>` — Register the provider of one forge family as an effect on the calling fiber. Watches of that forge receive an `unavailable` failure when the registration ends. Unregistering cancels and awaits its in-flight calls; results from the withdrawn registration are discarded.
- repositoryFromRemote `repositoryFromRemote(url: string): ForgeRepository \| undefined` — Map a Git remote URL to a repository through the first provider that serves it.
- changeRequestFromUrl `changeRequestFromUrl(url: string): ChangeRequestRef \| undefined` — Map a change request web URL through the first provider that serves it.
- changeRequestUrl `changeRequestUrl(ref: ChangeRequestRef): string` — Build the canonical web URL of a change request.
- findByHead `async findByHead(repository: ForgeRepository, branch: string, signal: AbortSignal): Promise<readonly ChangeRequestRef[]>` — Find open change requests whose head is `branch`, excluding the default branch and forks.
- readiness `async readiness(repository: ForgeRepository, signal: AbortSignal): Promise<ForgeReadiness>` — Report whether the provider can reach the repository's host with current credentials.
- markReady `async markReady(ref: ChangeRequestRef, signal: AbortSignal): Promise<ForgeActionFailure \| undefined>` — Mark a draft change request ready for review, then poll it at once when it is watched.
- merge `async merge(ref: ChangeRequestRef, request: MergeRequest, signal: AbortSignal): Promise<ForgeActionFailure \| undefined>` — Merge a change request while its head is still `request.headSha`, then poll it at once when it is watched.
- rerunChecks `async rerunChecks(ref: ChangeRequestRef, request: ForgeRerunRequest, signal: AbortSignal): Promise<ForgeActionFailure \| undefined>` — Rerun the failed checks of a change request's head commit while the head is still `request.headSha`, then poll it at once when it is watched.
- requestReviews `async requestReviews( ref: ChangeRequestRef, request: ForgeReviewersRequest, signal: AbortSignal, ): Promise<ForgeActionFailure \| undefined>` — Request reviews of a change request from more reviewers, then poll it at once when it is watched.
- reviewerCandidates `async reviewerCandidates( ref: ChangeRequestRef, query: string, signal: AbortSignal, ): Promise<readonly ForgeReviewerCandidate[] \| ForgeFailure>` — List accounts a review of a change request can be requested from. reviews returns `unsupported`.
- updateBranch `async updateBranch(ref: ChangeRequestRef, request: BranchUpdateRequest, signal: AbortSignal): Promise<ForgeActionFailure \| undefined>` — Bring the base branch's new commits into a change request's head branch while its head is still `request.headSha`, then poll it at once when it is watched.
- fetchChecks `async fetchChecks(ref: ChangeRequestRef, signal: AbortSignal): Promise<ChangeRequestSnapshot \| ForgeFailure>` — Read complete check details independently of periodic polling.
- diff `async diff(ref: ChangeRequestRef, headSha: string, signal: AbortSignal): Promise<string \| ForgeFailure>` — Read the changes of a change request at one head commit as its host computes them. The first `stale` failure at a head commit polls a watched change request again at once, so its next status names the current head; later stale reads at the same commit wait for the regular poll, which bounds the reads while the host's answers disagree. When the latest status of a watched change request names `headSha`, its `baseSha` goes to the provider, which may then read the patch while it confirms the head.
- readReview `async readReview(ref: ChangeRequestRef, headSha: string, signal: AbortSignal): Promise<ForgeReviewData \| ForgeFailure>` — Read the review threads of a change request at one head commit. A `stale` failure polls a watched change request again as {@link ForgeService.diff} does.
- writeReview `async writeReview(ref: ChangeRequestRef, write: ForgeReviewWrite, signal: AbortSignal): Promise<ForgeReviewWriteResult>` — Write to the review threads or the pending review of a change request while its head is still `write.headSha`, then poll the change request at once when it is watched, unless the provider cannot write reviews. A `stale` result polls it as a stale read does. outcome must be checked on the host before the write is tried again.
- viewedFiles `async viewedFiles(ref: ChangeRequestRef, headSha: string, signal: AbortSignal): Promise<ForgeViewedFiles \| ForgeFailure \| undefined>` — Read the signed-in user's viewed marks on the files of a change request at one head commit. A `stale` failure polls a watched change request again as {@link ForgeService.diff} does. viewed marks.
- setViewed `async setViewed(ref: ChangeRequestRef, request: ForgeViewedRequest, signal: AbortSignal): Promise<ForgeActionFailure \| undefined>` — Set or clear the signed-in user's viewed mark on one file of a change request while its head is still `request.headSha`. A `stale` failure polls a watched change request again as {@link ForgeService.diff} does.
- commits `async commits(ref: ChangeRequestRef, signal: AbortSignal): Promise<ForgeCommitList \| ForgeFailure \| undefined>` — List the commits of a change request at its current head.
- compare `async compare(ref: ChangeRequestRef, base: string, head: string, signal: AbortSignal): Promise<string \| ForgeFailure>` — Read the changes between two commits of a change request's repository. does not read commits returns `unavailable`.
- submitReview `async submitReview(ref: ChangeRequestRef, request: ForgeReviewRequest, signal: AbortSignal): Promise<ForgeReviewResult>` — Publish one comment or a completed review, then refresh the watched status.
- fileText `async fileText(ref: ChangeRequestRef, commit: string, path: string, signal: AbortSignal): Promise<string \| ForgeFailure>` — Read the text of one file at a commit of a change request's repository.
- fileUrl `fileUrl(ref: ChangeRequestRef, commit: string, path: string): string` — Build the web page of one file at a commit of a change request's repository.
- watch `watch(ref: ChangeRequestRef, listener: ChangeRequestListener): () => void` — Watch one change request as an effect on the calling fiber. The first watcher starts polling at once; listeners receive every later result, and `latest` returns the current one. Polling stops when the last watcher leaves. Listeners must not throw; a thrown error is logged and skipped.
- refresh `refresh(ref: ChangeRequestRef): void` — Poll a watched change request at once, including after a terminal state. A fetch already in flight is followed immediately by another fetch; an unwatched change request is unchanged.
- latest `latest(ref: ChangeRequestRef): ChangeRequestUpdate \| undefined` — Read the latest polling result of a watched change request.
- staleRead `private staleRead(ref: ChangeRequestRef, headSha: string, code: ForgeFailure['code']): void` — Poll a watched change request at once after the first `stale` read or write at `headSha`; later ones wait for the regular poll. */
- act `private async act<A>( ref: ChangeRequestRef, signal: AbortSignal, pick: (provider: ForgeProvider) => A \| undefined, missing: string, run: (action: A, signal: AbortSignal) => Promis…` — Run one optional provider action, then poll the change request at once when it is watched and the provider has the action.
- provider `private provider(forge: string): ForgeProvider`
- providersChanged `private providersChanged(forge: string): void`
- registration `private registration(forge: string): Registration`
- invoke `private async invoke<T>( registration: Registration, signal: AbortSignal, action: (provider: ForgeProvider, signal: AbortSignal) => Promise<T>, ): Promise<T>`
- missing `private missing(forge: string): ForgeFailure`
- schedule `private schedule(): void`
- poll `private poll(): void`
- fetch `private async fetch(forge: string, batch: readonly Watch[]): Promise<void>` — Fetch one forge's batch; never rejects. */
- settle `private settle(watch: Watch, result: ChangeRequestSnapshot \| ForgeFailure, refreshAt: number \| undefined): void`
- listener `listener(update)`

### `forgePanel` — `@deepseek-ai/dsh-experimental-client-ui-forge`

> Remote that serves the forge panel of the GUI. */

- 提供类型：`ForgePanelController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-client-ui-forge` (`packages/experimental/client-ui-forge/src/index.ts:71`，class)
- 提供方：`@deepseek-ai/dsh-experimental-client-ui-forge` (`packages/experimental/client-ui-forge/src/index.ts:107`)

- worktreeCleanup `async worktreeCleanup(session: Session, revision: number \| null): Promise<WorktreeCleanup \| null>` — Read or await the worktree service's archive cleanup of the Session's checkout.  *(decorators: @@Remote)*
- branches `async branches(session: Session, signal: AbortSignal): Promise<ForgeBranches>` — List the local branches that can start a worktree of the Session's current checkout.  *(decorators: @@Remote)*
- diffBases `async diffBases(session: Session, query: string, signal: AbortSignal): Promise<ForgeBaseBranches>` — List the branches the `branch` scope of the Session's current checkout can compare with. most recently committed first, without the checked-out branch.  *(decorators: @@Remote)*
- track `async track(session: Session, url: string, signal: AbortSignal): Promise<void>` — oxlint-disable typescript/require-await -- async keeps a refused or cancelled request a rejection, as Remote callers expect */ Bind a change request to a Session by URL, or restore a dismissed binding.  *(decorators: @@Remote)*
- dismiss `async dismiss(session: Session, url: string, signal: AbortSignal): Promise<void>` — Hide a visible binding of a Session; other URLs leave the Session unchanged.  *(decorators: @@Remote)*
- refresh `async refresh(session: Session, signal: AbortSignal): Promise<void>` — Reinspect a followed Session's checkout, probe sign-in again, and poll its change requests at once; an unfollowed Session is unchanged.  *(decorators: @@Remote)*
- localDiff `async localDiff(session: Session, scope: ForgeLocalScope, signal: AbortSignal): Promise<ForgeLocalDiff>` — Read the changes one scope covers in the checkout of the Session's current directory, with Git using the Session's sandbox policy. chosen for the `branch` scope does not exist; `forgePanel/no-fork-point` for the `branch` scope without a fork point; `forgePanel/commits-missing` when chosen commits are not between the fork point and HEAD in order; `forgePanel/commits-not-linear` when a chosen commit's first parent is not the commit listed before it; `forgePanel/filter-config-failed` when filter configuration cannot be read completely, before any comparison; `forgePanel/diff-too-large` over `maxDiffBytes`; the Git error when Git fails.  *(decorators: @@Remote)*
- localCommits `async localCommits(session: Session, base: string \| null, signal: AbortSignal): Promise<ForgeLocalCommits>` — List the commits of the `branch` scope of the Session's current checkout, which the changes view can show one or several of instead of the whole scope. exist; `forgePanel/no-fork-point` without a fork point; the Git error when Git fails or the listing exceeds `maxDiffBytes`.  *(decorators: @@Remote)*
- localText `async localText(session: Session, scope: ForgeLocalScope, path: string, signal: AbortSignal): Promise<string>` — Read the new side of one changed file in a scope, which supplies the unchanged lines between its hunks: the index for `staged`, the last chosen commit for chosen commits of the `branch` scope, else the working tree. `forgePanel/commits-missing` for a chosen commit that is not a full object name; an error for a path outside the checkout, binary content, or a failed read.  *(decorators: @@Remote)*
- changeRequestChecks `async changeRequestChecks(session: Session, url: string, headSha: string, signal: AbortSignal): Promise<ChangeRequestSnapshot>` — Load complete checks for the change request whose list the user opened. or `forgePanel/checks-failed` when the provider cannot complete the read.  *(decorators: @@Remote)*
- changeRequestCommits `async changeRequestCommits(session: Session, url: string, signal: AbortSignal): Promise<ForgeCommitList \| null>` — List the commits of a change request of a Session at its current head, which the changes view can show one or several of instead of the whole change request. `forgePanel/diff-failed` when the host does not list them.  *(decorators: @@Remote)*
- changeRequestDiff `async changeRequestDiff( session: Session, url: string, commits: ForgeCommitRange \| null, signal: AbortSignal, ): Promise<ForgeChangeRequestDiff>` — Read the changes of a change request of a Session as its code host computes them, with each file's layer following the root `.gitattributes` of the commit the diff ends at. Without `commits` the diff covers the change request at the head commit of its latest status; a patch already read at the same head commit and base branch is reused from memory with its attributes, for any Session, until `maxCachedDiffBytes` evicts it. With `commits`, it covers those commits, from the first one's first parent to the last, and is read every time. `forgePanel/commits-missing` when chosen commits are not among the change request's commits in order; `forgePanel/commits-not-linear` when a chosen commit's first parent is not the commit listed before it; `forgePanel/stale-head` without `commits` when the head moved past the latest status, which is then polled again; `forgePanel/diff-too-large` when the host or its provider refuses the diff over a size limit; `forgePanel/diff-failed` before its status was read, for a first chosen commit without a parent, and when the host does not provide the commits, the diff, or an existing `.gitattributes` otherwise.  *(decorators: @@Remote)*
- gitIn `gitIn(this.home, this.config, session, this.home.workingDirectory.get(session), signal), headBranch, headSha,`
- changeRequestText `async changeRequestText(session: Session, url: string, commit: string, path: string, signal: AbortSignal): Promise<string>` — Read one file of a change request's repository at a commit, which supplies the unchanged lines between the hunks of its diff. `forgePanel/diff-too-large` when the host or its provider refuses the file over a size limit; `forgePanel/diff-failed` when the host does not provide the file otherwise.  *(decorators: @@Remote)*
- changeRequestViewed `async changeRequestViewed(session: Session, url: string, headSha: string, signal: AbortSignal): Promise<ForgeViewedFiles \| null>` — Read the signed-in user's viewed marks on the files of a change request of a Session, which the host keeps for the whole change request. `forgePanel/stale-head` when the head moved past `headSha`, which is then polled again; `forgePanel/viewed-failed` when the host does not provide the marks otherwise.  *(decorators: @@Remote)*
- setFileViewed `async setFileViewed(session: Session, url: string, request: ForgeViewedRequest, signal: AbortSignal): Promise<void>` — Set or clear the signed-in user's viewed mark on one file of a change request of a Session. `forgePanel/stale-head` when the head moved past `request.headSha`; `forgePanel/action-failed` with the host's reason when the host refuses, cannot be reached, or keeps no viewed marks; `forgePanel/action-unknown` when the host did not confirm whether it saved the mark.  *(decorators: @@Remote)*
- changeRequestReview `async changeRequestReview(session: Session, url: string, headSha: string, fresh: boolean, signal: AbortSignal): Promise<ForgeReviewData>` — Read the review threads of a change request of a Session at the head commit of its displayed diff. Threads read at the same head commit and update time are reused from memory, for any Session, until they are `reviewRefreshMs` old, `maxCachedReviewBytes` evicts them, or a review write through this panel drops them; a read again after that age, or a `fresh` read, shows threads resolved elsewhere since, which do not change a GitHub pull request's update time. reader refreshes the view; the result replaces the kept threads. `forgePanel/stale-head` when the latest status or the host names another head, which a host answer polls again; `forgePanel/review-unsupported` when the provider cannot read reviews; `forgePanel/review-failed` before the status was read and when the host does not provide the threads otherwise.  *(decorators: @@Remote)*
- submitReview `async submitReview(session: Session, url: string, request: ForgeReviewRequest, signal: AbortSignal): Promise<ForgeReviewResult>` — Publish a line comment or completed review for a visible Session binding. The threads kept for the change request are dropped once the host answers, so the next read shows the comments.  *(decorators: @@Remote)*
- changeRequestReviewWrite `async changeRequestReviewWrite( session: Session, url: string, write: ForgeReviewWrite, signal: AbortSignal, ): Promise<ForgeReviewWriteResult>` — Write to the review threads or the pending review of a change request of a Session while its head is still the head the user saw. The threads kept for the change request are dropped once the host answers, so the next read shows the write, which a resolve does not show through a GitHub pull request's update time. `unknown` when the outcome must be checked on the host before the write is tried again. for a write without text, a head that is not a commit object name, or an invalid line range.  *(decorators: @@Remote)*
- markReady `async markReady(session: Session, url: string, signal: AbortSignal): Promise<void>` — Mark a draft change request of a Session ready for review; the change request is polled again once the host answers. `forgePanel/action-failed` with the host's reason when the host refuses or cannot be reached.  *(decorators: @@Remote)*
- merge `async merge(session: Session, url: string, method: MergeMethod, headSha: string, signal: AbortSignal): Promise<void>` — Merge a change request of a Session while its head is still `headSha`; the change request is polled again once the host answers. `forgePanel/stale-head` when the head moved past `headSha`; `forgePanel/action-failed` with the host's reason when the host refuses otherwise or cannot be reached.  *(decorators: @@Remote)*
- rerunChecks `async rerunChecks(session: Session, url: string, request: ForgeRerunRequest, signal: AbortSignal): Promise<void>` — Rerun the failed checks of a change request of a Session while its head is still the commit whose checks the user saw; the change request is polled again once the host answers. `forgePanel/stale-head` when the head moved past `request.headSha`; `forgePanel/action-failed` with the host's reason when the host refuses, cannot be reached, or reruns no checks; `forgePanel/action-unknown` when the host did not confirm whether it started the rerun.  *(decorators: @@Remote)*
- requestReviews `async requestReviews( session: Session, url: string, reviewers: readonly Pick<ChangeRequestReviewer, 'kind' \| 'login'>[], signal: AbortSignal, ): Promise<void>` — Request reviews of a change request of a Session from more reviewers; the change request is polled again once the host answers. `forgePanel/action-failed` with the host's reason when the host refuses, cannot be reached, or requests no reviews; `forgePanel/action-unknown` when the host did not confirm whether it requested the reviews.  *(decorators: @@Remote)*
- reviewerCandidates `async reviewerCandidates(session: Session, url: string, query: string, signal: AbortSignal): Promise<readonly ForgeReviewerCandidate[]>` — List accounts a review of a change request of a Session can be requested from. `forgePanel/reviewers-failed` when the host does not list them.  *(decorators: @@Remote)*
- updateBranch `async updateBranch(session: Session, url: string, method: BranchUpdateMethod, headSha: string, signal: AbortSignal): Promise<void>` — Bring the base branch's new commits into the head branch of a change request of a Session while its head is still `headSha`; the change request is polled again once the host answers. `forgePanel/stale-head` when the head moved past `headSha`; `forgePanel/action-failed` with the host's reason when the host refuses, cannot be reached, or updates no branches; `forgePanel/action-unknown` when the host did not confirm whether it started the update.  *(decorators: @@Remote)*
- requestWorktree `async requestWorktree(session: Session, from: string \| null, signal: AbortSignal): Promise<void>` — Ask for a new worktree before the Session's first turn, replacing an open request and forgetting a failed attempt. While the next message waits in the inbox, or else at the first step proposal, the panel creates a branch from `from`, or from HEAD of the current checkout when it is null, and enters its checkout. A message that already waits after a failed or stopped attempt keeps waiting for {@link ForgePanelController.retryWorktree}. without a worktree service; `forgePanel/session-started` after a turn started or the worktree was created; `forgePanel/session-busy` while the worktree is being created.  *(decorators: @@Remote)*
- appendPluginRecord `appendPluginRecord(session, WORKTREE_RECORD, { action: 'request', from })`
- cancelWorktree `async cancelWorktree(session: Session, signal: AbortSignal): Promise<void>` — Withdraw the open worktree request of a Session with its failed attempt, which lets a waiting message go on in the current checkout; without a request the Session is unchanged. Withdrawing needs no worktree service. `forgePanel/session-busy` while the worktree is being created.  *(decorators: @@Remote)*
- appendPluginRecord `appendPluginRecord(session, WORKTREE_RECORD, { action: 'cancel' })`
- stopCreation `async stopCreation(session: Session, signal: AbortSignal): Promise<void>` — Stop the creation a message of the Session waits for; the message keeps waiting with the request still open. Without such a creation the Session is unchanged.  *(decorators: @@Remote)*
- retryWorktree `async retryWorktree(session: Session, signal: AbortSignal): Promise<void>` — Make another attempt, with a new branch name, at the worktree a message of the Session waits for after a failed or stopped attempt.  *(decorators: @@Remote)*
- restoreWorktree `async restoreWorktree(session: Session, signal: AbortSignal): Promise<void>` — Check out the created worktree of a Session again at its recorded directory when that directory is gone: its branch when the branch still exists, otherwise a new branch of the same name at the base commit. Changes that were never committed are not recovered. Runs as Agent maintenance, inside the wait of a message that waits for the restoration, which then goes on; without a missing directory the Session is unchanged. without a worktree service; `forgePanel/session-busy` while the Session's Agent is not loaded or has other work; `forgePanel/restore-failed` when Git fails.  *(decorators: @@Remote)*
- continueInProject `async continueInProject(session: Session, signal: AbortSignal): Promise<void>` — Move a Session from its created worktree to the source checkout the worktree came from; the Session no longer works in the worktree. Runs as Agent maintenance, inside the wait of a message that waits for the removed worktree, which then goes on. Session's Agent is not loaded or has other work; the working-directory service's error when the source checkout no longer exists.  *(decorators: @@Remote)*
- holdTurn `private holdTurn(agent: Agent): void` — Hold the turn of a message entering a Session's inbox while the Session's requested worktree does not exist yet, or while the worktree the Session works in is checked and, when gone, until it is restored or left. The message is entering, so the delivery has not woken the Agent yet and its wake waits for the hold.
- missingFor `private async missingFor(session: Session, signal: AbortSignal): Promise<ForgeMissingWorktree \| null>` — Check whether the worktree the Session works in is gone.
- commitsDiff `private async commitsDiff(ref: ChangeRequestRef, commits: ForgeCommitRange, signal: AbortSignal): Promise<ForgeChangeRequestDiff>` — The changes of consecutive commits of a change request, from the first one's first parent to the last. */
- patchAt `private async patchAt( ref: ChangeRequestRef, commit: string, readPatch: (signal: AbortSignal) => Promise<string \| ForgeFailure>, signal: AbortSignal, ): Promise<` — Read a patch that ends at `commit` together with the root `.gitattributes` at that commit. A failed patch read cancels the attributes read. Both reads end before the result: the patch's failure passes on first, and the attributes failure only after the patch was read, so the outcome does not depend on which read ends first.
- attributesAt `private async attributesAt(ref: ChangeRequestRef, commit: string, signal: AbortSignal): Promise<string>` — The root `.gitattributes` of a change request's repository at a commit, empty when the commit has none. */
- checkoutOf `private async checkoutOf(session: Session, signal: AbortSignal): Promise<Inspection>` — Inspect the checkout of the Session's current directory, which local diffs read. */
- bound `private bound(session: Session, url: string): SessionChangeRequest &` — A visible binding of the Session that a provider serves, which actions and reads are limited to. */
- worktreeState `private worktreeState(session: Session): ForgeWorktreeState`
- editableWorktree `private editableWorktree(session: Session): ForgeWorktreeState`
- changeableWorktree `private changeableWorktree(session: Session): ForgeWorktreeState` — The worktree state of a Session whose request may still change: no turn started, nothing created, and no attempt running. */
- createdWorktree `private createdWorktree(session: Session): ForgeSessionWorktree`
- maintain `private async maintain(session: Session, work: HeldWork): Promise<void>` — Run work as maintenance of the Session's Agent: inside the wait of a message that waits for the removed worktree, else as a task of its own, which the Agent refuses while it has other work.
- changeRequestStatesHub `private changeRequestStatesHub(): ChangeRequestStates` — The shared change request states, created for the first stream from the Host's Session and storage services. */
- panelOf `private panelOf(session: Session): SessionPanel`

### `forgeSession` — `@deepseek-ai/dsh-experimental-forge-session`

- 提供类型：`ForgeSessionService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-forge-session` (`packages/experimental/forge-session/src/index.ts:42`，class)
- 提供方：`@deepseek-ai/dsh-experimental-forge-session` (`packages/experimental/forge-session/src/index.ts:58`)
- 消费方：@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)

- changeRequests `changeRequests(session: Session): SessionChangeRequest[]` — List the change requests bound to a Session and not dismissed.
- track `track(session: Session, url: string): void` — Bind a change request to a Session by URL, or restore a dismissed binding. Appends a `track` record with the provider's canonical URL unless the change request is already visible.
- discoverBranch `discoverBranch(session: Session, remote: string, branch: string): Promise<void>` — Look up open change requests whose head is a branch the Session works on, and record the unbound ones as discovered, as after a push of that branch. A remote that no provider recognizes changes nothing; a failed lookup is logged and changes nothing.
- dismiss `dismiss(session: Session, url: string): void` — Hide a visible binding. Appends a `dismiss` record; a URL that is not visibly bound leaves the log unchanged. Discovery never restores a dismissed binding; `track` does.
- watch `watch(session: Session, listener: SessionChangeRequestsListener): () => void` — Watch a Session's visible change requests as an effect on the calling fiber. Every visible change request that a provider recognizes is polled through `ctx.forge` while the Session has a watcher. Listeners receive the complete list after each later binding or provider change, or polling result; read the current list with {@link changeRequests}. Listeners must not throw; a thrown error is logged and skipped.
- observeReferences `observeReferences(this.home, this.discoveryTimeoutMs, (session, url) => { if (!this.state(session).bindings.some(binding => sameChangeRequestUrl(binding.url, url))) { appendPluginR…`
- state `private state(session: Session): ForgeChangeRequestsState`
- entries `private entries(bindings: readonly BindingState[]): SessionChangeRequest[]`
- react `private react(session: Session, event: SessionEvent): void` — Discover change requests for this result's pushes and refresh watchers after binding changes. */
- sync `private sync(watch: SessionWatch): void` — Poll exactly the visible change requests that a provider recognizes. */
- unwatch `unwatch()`
- notify `private notify(watch: SessionWatch): void`
- listener `listener(changeRequests)`
- discover `private discover(session: Session, remote: string, branch: string): Promise<void>`
- lookup `private async lookup(session: Session, repository: ForgeRepository, branch: string, signal: AbortSignal): Promise<void>`
- appendPluginRecord `appendPluginRecord(session, BINDING_RECORD, { action: 'discover', url })`

### `fs` — `@deepseek-ai/dsh-fs`

- 提供类型：`FileSystem`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-fs` (`packages/fs/fs/src/index.ts:104`，class)
- 提供方：`@deepseek-ai/dsh-fs` (`packages/fs/fs/src/index.ts:106`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-tool-present(`packages/deliverables/tool-present/src/index.ts` via inject)、@deepseek-ai/dsh-workspace-changes(`packages/deliverables/workspace-changes/src/index.ts` via inject)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-str-replace-editor(`packages/fs/tool-str-replace-editor/src/index.ts` via inject)、@deepseek-ai/dsh-lsp-stdio(`packages/lsp/lsp-stdio/src/index.ts` via inject)、@deepseek-ai/dsh-ptc-runtime-node(`packages/ptc-runtime/ptc-runtime-node/src/index.ts` via inject)、@deepseek-ai/dsh-working-directory(`packages/session/working-directory/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-agent-instructions(`packages/context/agent-instructions/src/index.ts` via ctx.get)、@deepseek-ai/dsh-office-kit(`packages/document/office-kit/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)、@deepseek-ai/dsh-llm-deepseek(`packages/llm/llm-deepseek/src/host.ts` via ctx.get)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/index.ts` via ctx.get)、@deepseek-ai/dsh-llm(`packages/llm/llm/src/index.ts` via ctx.get)、@deepseek-ai/dsh-skill-filesystem(`packages/skill/skill-filesystem/src/index.ts` via ctx.get)、@deepseek-ai/dsh-spill-policy(`packages/spill/spill-policy/src/index.ts` via ctx.get)、@deepseek-ai/dsh-agent-loop-testkit(`packages/test-support/agent-loop-testkit/src/index.ts` via ctx.get)

- watch `watch(target: FsTarget, changed: (error?: Error) => void, signal: AbortSignal): Promise<() => Promise<void>>` — Observe one file or a directory's direct entries in this provider's execution world.
- resolve `abstract resolve(path: string, opts?: { cwd?: string; signal?: AbortSignal }): Promise<FsTarget>` — Resolve a model/plugin-supplied path into a stable {@link FsTarget}. May perform I/O (a remote/sandboxed backend may need a round-trip to map a path to a stable identity), hence async even though the local backend only normalizes + realpaths.
- processPath `abstract processPath(target: FsTarget): string` — Return the canonical absolute path a subprocess in this filesystem's execution world can open. The path is deliberately separate from {@link FsTarget.targetKey}: consumers may pass this value to another OS capability, but must continue treating the target key as opaque.
- processPathFromHostPath `processPathFromHostPath(hostPath: string): string \| undefined` — Map an absolute path from the harness host into this filesystem's execution world when both paths identify the same file. The base provider exposes no mapping; host-backed or explicitly shared backends override it. execution world cannot read that host file.
- fileUrl `abstract fileUrl(target: FsTarget): string` — Return the canonical `file:` URI for a target in this filesystem's execution world. Backends own URI encoding because the host platform may differ from the execution platform.
- contains `abstract contains(parent: FsTarget, child: FsTarget): boolean` — Test canonical containment without exposing or parsing backend target keys. Both targets must come from this provider.
- stat `abstract stat(target: FsTarget, signal?: AbortSignal): Promise<FsInfo \| undefined>` — Return target metadata, or `undefined` when the target does not exist.
- lstat `abstract lstat(path: string, opts?: { cwd?: string }, signal?: AbortSignal): Promise<FsPathInfo \| undefined>` — Return path metadata without following the final path component when it is a symbolic link. This is intentionally path-shaped, not target-shaped: {@link resolve} follows symlinks to produce the stable identity used by normal reads/writes, while `lstat` lets a consumer reject the path itself before that follow happens. `opts.cwd` follows {@link resolve}'s cwd rules. `undefined` means the path is absent.
- readText `abstract readText(target: FsTarget, signal?: AbortSignal): Promise<string>` — Read the whole regular text file as a single decoded string.
- streamText `abstract streamText(target: FsTarget, signal?: AbortSignal): Promise<AsyncIterable<string>>` — Stream the whole regular text file as decoded text chunks (same text semantics as {@link readText}, for large files). The backend owns cross-chunk UTF-8 decoding and binary rejection so the policy layer never touches raw bytes.
- readBytes `abstract readBytes(target: FsTarget, signal: AbortSignal \| undefined, maxBytes: number): Promise<Uint8Array>` — Read the whole regular file as raw bytes with no decoding or binary rejection. The bound lives at this seam so a backend can never buffer an unbounded file: a target known or discovered to exceed `maxBytes` fails with `FS_TOO_LARGE` instead of returning a truncated result.
- readByteRange `abstract readByteRange(target: FsTarget, range: { offset: number; length: number }, signal?: AbortSignal): Promise<Uint8Array>` — Read one byte window of the regular file as raw bytes with no decoding or binary rejection: the bytes at `[offset, offset + length)`, shorter when the file ends inside the window and empty when `offset` lies at or past its end. The window is the bound here, not the file: a backend transfers at most `length` bytes of content beyond the prefix it skips to reach `offset` and never buffers the whole file, so the caller's cap on `length` is the guard against unbounded buffering.
- listDir `abstract listDir(target: FsTarget, signal?: AbortSignal): Promise<FsDirEntry[]>` — List direct children of a directory in stable name order. Returns resolved child targets plus cheap metadata only; never reads file contents.
- writeText `abstract writeText( target: FsTarget, content: string, expected?: FsWriteIntent, signal?: AbortSignal, sandboxPolicy?: SandboxExecutionPolicy, ): Promise<FsWriteOutcome>` — Atomically create or replace UTF-8 text. `expected` guards intent and staleness; omission allows unconditional overwrite. runs under; a sandboxing backend fences the write by it, the bare backend ignores it. Omit to leave the backend its own default.
- editText `abstract editText( target: FsTarget, edit: FsEditRequest, expected?: { version: FsVersion }, signal?: AbortSignal, sandboxPolicy?: SandboxExecutionPolicy, ): Promise<FsEditOutcome>` — Atomically edit literal text. When supplied, the version guard is checked before matching so stale content reports `FS_STALE_VERSION`; omission edits the current content without a freshness precondition. under; a sandboxing backend fences the edit by it, the bare backend ignores it. Omit to leave the backend its own default.
- patchText `abstract patchText( target: FsTarget, hunks: readonly PatchHunk[], expected?: { version: FsVersion }, signal?: AbortSignal, sandboxPolicy?: SandboxExecutionPolicy, ): Promise<FsEdi…` — Atomically apply parsed hunks to the LF-normalized text and restore the stored line-ending style. A missing or stale target reports `FS_STALE_VERSION`; an unmatched hunk reports `FS_PATCH_MISMATCH`. under; a sandboxing backend fences the patch by it, the bare backend ignores it. Omit to leave the backend its own default.
- deleteFile `abstract deleteFile( target: FsTarget, expected?: { version: FsVersion }, signal?: AbortSignal, sandboxPolicy?: SandboxExecutionPolicy, ): Promise<FsDeleteOutcome>` — Remove a regular file. A missing or stale target reports `FS_STALE_VERSION`; a directory or other non-file reports `FS_NOT_REGULAR_FILE`. Resolution has already followed symlinks, so the target is the real file. runs under; a sandboxing backend fences it, the bare backend ignores it. Omit to leave the backend its own default.
- moveFile `abstract moveFile( source: FsTarget, destination: FsTarget, options: { hunks?: readonly PatchHunk[] expectedSource?: { version: FsVersion } expectedDestination?: FsWriteIntent }, s…` — Publish the source text, optionally patched, at the destination, then remove the source. Both targets stay locked in canonical order. Identical targets report `FS_SAME_TARGET`; the source guard follows `patchText` and the destination guard follows `writeText`. The two effects are separate: a published destination with a retained source is a final outcome reported through `sourceDeleted: false`. under; a sandboxing backend fences them, the bare backend ignores it. Omit to leave the backend its own default.

### `goals` — `@deepseek-ai/dsh-goal`

- 提供类型：`GoalService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-goal` (`packages/goal/goal/src/index.ts:236`，class)
- 提供方：`@deepseek-ai/dsh-goal` (`packages/goal/goal/src/index.ts:249`)
- 消费方：@deepseek-ai/dsh-command-goal(`packages/goal/command-goal/src/index.ts` via inject)、@deepseek-ai/dsh-goal-round-driver(`packages/goal/goal-round-driver/src/index.ts` via inject)、@deepseek-ai/dsh-tool-goal(`packages/goal/tool-goal/src/index.ts` via inject)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/query-activity.ts` via ctx.get)

- get `get(agent: Agent): GoalView \| undefined` — Read the current goal for one exact live agent.  *(decorators: @@Remote('get'))*
- disarm `disarm(agent: Agent): GoalView \| undefined` — Remove process-local continuation authority without changing durable goal phase or revision. Lifecycle owners use this before unloading a driver; a later human-authorized {@link resume} records the new activation edge.
- create `create(agent: Agent, request: CreateGoalRequest): GoalView` — Create and arm a goal. A completed goal may be replaced; every other current phase must be cleared or resumed instead.
- edit `edit(agent: Agent, ref: GoalRef, request: EditGoalRequest): GoalView` — Edit objective and/or round cap without changing phase.  *(decorators: @@Remote('edit'))*
- pause `pause(agent: Agent, ref: GoalRef): GoalView` — Pause an active goal and disarm automatic continuation.  *(decorators: @@Remote('pause'))*
- resume `resume(agent: Agent, ref: GoalRef): GoalView` — Resume and arm a stopped goal, or rearm an active goal after a session-start edge, while its round budget still has capacity.  *(decorators: @@Remote('resume'))*
- complete `complete(agent: Agent, ref: GoalRef): GoalView` — Mark a current non-complete goal complete and disarm it.  *(decorators: @@Remote('complete'))*
- block `block(agent: Agent, ref: GoalRef, reason: GoalBlockReason): GoalView` — Mark an active goal blocked and disarm it.
- clear `clear(agent: Agent, ref: GoalRef): GoalRef` — Clear the current goal while retaining a durable tombstone and history.  *(decorators: @@Remote('clear'))*
- prepareMutation `private prepareMutation(agent: Agent): readonly [GoalProjection \| null, GoalRuntimeState]` — Resolve the durable and process-local state used by a mutation. */
- expectCurrent `private expectCurrent(state: GoalProjection \| null, ref: GoalRef): GoalProjection` — Reject stale or missing current-state refs. */
- assertLive `private assertLive(agent: Agent): void` — Enforce exact live-agent identity rather than trusting a matching id. */
- state `private state(session: Session): GoalProjection \| null` — Read the current durable projection maintained by the registry. */
- runtimeState `private runtimeState(session: Session): GoalRuntimeState` — Return the process-local activation state, initially disarmed. */
- setActivation `private setActivation(session: Session, activation: GoalActivation): void` — Publish one process-local activation edge when it actually changes. */
- withPhase `private withPhase(current: GoalSnapshot, phase: GoalPhase): GoalSnapshot` — Build a new revision with one replacement phase. */
- transition `private transition( agent: Agent, ref: GoalRef, operation: Exclude<GoalOperation, 'create' \| 'edit' \| 'clear'>, allowed: readonly GoalPhase[], phase: GoalPhase, activation: GoalAct…` — Shared validated phase transition. */
- transitionError `private transitionError(current: GoalSnapshot, operation: GoalOperation, allowed: readonly GoalPhase[]): GoalError` — Render a stable invalid-transition error. */
- commitCurrent `private commitCurrent( agent: Agent, state: GoalProjection, runtime: GoalRuntimeState, operation: Exclude<GoalOperation, 'create' \| 'clear'>, goal: GoalSnapshot, activation: GoalAc…` — Commit a mutation that retains the current goal's derived counters/times. */
- nextMutationTime `private nextMutationTime(state: GoalProjection): number` — Clamp a current goal's next timestamp across backward wall-clock movement. */
- commitSnapshot `private commitSnapshot( agent: Agent, runtime: GoalRuntimeState, operation: Exclude<GoalOperation, 'clear'>, goal: GoalSnapshot, roundsStarted: number, createdAt: number, updatedAt…` — Build and commit one full-snapshot mutation. */
- commit `private commit(agent: Agent, runtime: GoalRuntimeState, change: GoalChangeMeta, activation: GoalActivation): void` — Commit one mutation into the goal log and live event stream. */
- agentEvents `agentEvents(this.ctx, agent).emit('goal/changed',`
- view `private view(state: GoalProjection \| null, runtime: GoalRuntimeState): GoalView \| undefined` — Build a detached current view. */
- remoteExportCreate `remoteExportCreate(agent: Agent, request: CreateGoalRequest): CreateGoalResult` — Create one Goal through the remote boundary.  *(decorators: @@Remote('create'))*

### `headlessStartup` — `@deepseek-ai/dsh-headless`

> Parsed arguments of this headless invocation. */

- 提供类型：`HeadlessStartupValues`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-headless` (`packages/bundle/headless/src/startup.ts:27`，interface)
- 消费方：@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `hmr` — `@deepseek-ai/dsh-hmr`

> Serialized plugin-code and configuration reloads. */

- 提供类型：`Hmr`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-hmr` (`packages/boot/hmr/src/index.ts:213`，class)
- 提供方：`@deepseek-ai/dsh-hmr` (`packages/boot/hmr/src/index.ts:308`)

- runExclusive `runExclusive<T>(operation: () => Promise<T>): Promise<T>` — Serialize a caller-owned mutation with all automatic reload paths.
- runReload `private runReload(operation: () => Promise<void>): Promise<void>`
- watchConfig `async watchConfig(filename: string, refresh: () => Promise<void>): Promise<() => Promise<void>>` — Watch a configuration path through the same queue as module replacement.
- esmJob `private esmJob(url: string): ModuleJob \| undefined` — The cached ES module job for a URL. The packed worker loader exposes no Node module cache; native Node retains this cache even when asynchronous module hooks run in a separate thread.
- hasEsmCache `private hasEsmCache(): boolean` — Whether this thread keeps a Node ES module cache; the packed worker loader keeps none. */
- esmHas `private esmHas(url: string, type?: string): boolean` — Whether the ES module cache holds a job for a URL; `false` when this thread keeps no ES module cache. */
- esmUrls `private esmUrls(): string[]` — ES module cache keys, empty when this thread keeps no ES module cache. */
- mainJob `private mainJob(): ModuleJob \| undefined` — The module job of the process entry point, when the loader cached it under the entry's real path. */
- yield `yield () =>`
- getLinked `async getLinked(url: string): Promise<string[]>` — Read direct module dependency URLs from the active Node loader.
- analyzeChanges `private async analyzeChanges()` — Classify changed files into accepted (should reload) and declined (should not). A file is accepted if it's directly changed (stashed) or if any of its dependents are accepted. A file is declined if all its dependents are declined or if it's an external.
- partialReload `private async partialReload()`
- handleError `handleError(this.ctx, e)`
- rollback `rollback()`
- evict `private evict(urls: Iterable<string>): () => void` — Remove modules from the ES module and CommonJS caches so the next import evaluates their files again. CommonJS modules loaded through `import()` appear in both caches. Node's `LoadCache` maps each URL to per-type jobs, and its own `delete()` only clears one type slot, so whole entries are removed through `Map.prototype`.
- profileModules `private profileModules(roots: readonly string[]): string[]` — Loaded `file:` modules below the given profile roots. */
- moduleGraph `private async moduleGraph(): Promise<Map<string, Set<string>>>` — Static import edges between loaded modules, across ES module links and CommonJS `require` children. */
- planReplacement `private async planReplacement(stale: ReadonlySet<string>, roots: readonly string[]): Promise<ReplacementPlan>` — Plan the replacement of changed modules without changing anything. A changed module whose importers reach the process entry point's static graph, or a plugin that no affected Loader entry starts, stays loaded with its importers and is pending. The other changed modules and every module importing them are evicted by {@link stopPlanned}, which also expires the manifests from each changed file up to its root and stops the Loader entries running affected plugins.
- pluginsOf `private pluginsOf(url: string): Plugin[]` — The plugins a loaded module exports, read from the ES module namespace and the CommonJS exports Node cached for it without evaluating anything.
- stopPlanned `private async stopPlanned(plan: ReplacementPlan): Promise<void>` — Carry out a planned replacement: expire its manifests, evict its modules without a backup, and stop its Loader entries, so applying the generation imports the current files when it starts them.
- evictDropped `private async evictDropped(dropped: readonly string[], kept: ReadonlySet<string>): Promise<void>` — Evict the loaded modules below the directories of mappings a recomposition dropped and expire their package configuration, so a disabled or removed package that is installed or enabled again is imported afresh. Modules of DSH's own static graph, and those below a directory that is still mapped, stay loaded.
- contained `private async contained<T>(step: string, operation: () => T \| Promise<T>, fallback: T): Promise<T>` — Report a failed replacement step and retain the caller’s fallback outcome. */
- reconcileProfile `async reconcileProfile(requiredIds: readonly string[] = []): Promise<ProfileReconciliation>` — Recompose the profile from its manifest and patch files, replacing running plugins whose loaded files below the profile directory or its linked package targets changed on disk, and publishing its runtime resolution. Changed modules are evicted and the Loader entries running them stop; app-boot's {@link recomposeProfile} then publishes the resolution, applies the generation, starts the stopped entries with the current files and configuration, imports entries whose import failed again, and judges activation. Afterwards the modules below the mappings the recomposition dropped are evicted, so a removed or deselected package is imported afresh when it returns. Callers run inside {@link runExclusive}. replacement plugin that fails to load or start, whose previous code no longer runs.

### `inputTriggers` — `@deepseek-ai/dsh-client-ui-input-trigger`

> The outward face only; the concrete service stays inside this plugin. */

- 提供类型：`import('./contract.ts').InputTriggerServiceContract`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-input-trigger` (`packages/client/ui-input-trigger/src/client/service.ts:42`)
- 消费方：@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `inspector` — `@deepseek-ai/dsh-experimental-inspector`

> Publish Client-realm observations and query the shared Inspector state. */

- 提供类型：`InspectorService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-inspector` (`packages/experimental/inspector/src/client/plugin.ts:26`，interface)
- 提供方：`@deepseek-ai/dsh-experimental-inspector` (`packages/experimental/inspector/src/client/plugin.ts:136`)、`@deepseek-ai/dsh-experimental-inspector` (`packages/experimental/inspector/src/host/plugin.ts:85`)

- （方法未解析：提供类型不可达或未定义成员）

### `invocation` — `@deepseek-ai/dsh-typert-protocol`

> The Remote call this Context was derived for, or `undefined` on a Context no Remote call derived. A Service method reads it as `this.ctx.invocation`.

- 提供类型：`RemoteInvocation \| undefined`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-typert-protocol` (`packages/typert/protocol/src/types.ts:498`，interface)

- uplink `uplink<In = unknown>(): AsyncIterable<In>` — The Client's uplink items for this call. Available once; a second call throws. With an uplink codec on the descriptor every item is decoded to `In`; without one items arrive as `unknown` after a JSON-safety check. Iteration ends when the Client ends its uplink; when the method finishes its downlink the Gateway calls the iterator's `return()` and unread items are dropped. `In` is the caller's assertion: the runtime decodes by the descriptor and does not cross-check it.

### `jobController` — `@deepseek-ai/dsh-api-job-controller`

> Host job Remote namespace owner. */

- 提供类型：`JobController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-job-controller` (`packages/api/job-controller/src/index.ts:43`，class)
- 提供方：`@deepseek-ai/dsh-api-job-controller` (`packages/api/job-controller/src/index.ts:59`)

- list `list(request: JobListRequest, signal: AbortSignal): AsyncIterable<JobListFrame>` — Stream the jobs one session can see — its own plus every unowned job — as whole-set frames: one on open, then one after each coalesced burst of lifecycle commits. The stream has no natural end; the carrier closes it.  *(decorators: @@Remote({ mode: 'stream' }))*
- follow `follow(request: JobFollowRequest, signal: AbortSignal): AsyncIterable<JobFollowFrame>` — Stream one job's retained output from an absolute byte offset, then its terminal projection once settled and drained. Non-consuming: the model-facing cursor and notice state never observe these reads. The request's session is the fenced read's caller; the registry rejects a job the session cannot see and an unknown job.  *(decorators: @@Remote({ mode: 'stream' }))*
- kill `kill(request: JobKillRequest): JobKillValue` — Kill one background job on a human's behalf. The request's session is the fenced read's caller, so the job must be one that session can see: the registry's owner fence is the only access rule, and a child session's own jobs are killable from its list like any other. The kill records `cancelled by the user` as its reason; it is not one the model requested, so the owning agent still receives the completion notice, and a shell tool waiting on that job reads the reason in its own result.  *(decorators: @@Remote('kill'))*

### `jobs` — `@deepseek-ai/dsh-api-job-controller`

> React-free client job rosters and observation control. */

- 提供类型：`IJobs`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-job-controller` (`packages/api/job-controller/src/client/service.ts:49`，interface)
- 提供方：`@deepseek-ai/dsh-api-job-controller` (`packages/api/job-controller/src/client/service.ts:108`)、`@deepseek-ai/dsh-jobs` (`packages/jobs/jobs/src/index.ts:97`)
- 消费方：@deepseek-ai/dsh-api-job-controller(`packages/api/job-controller/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-jobs(`packages/client/ui-jobs/src/client/index.ts` via inject)、@deepseek-ai/dsh-tool-jobs(`packages/jobs/tool-jobs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-terminal(`packages/experimental/tool-terminal/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-workflow(`packages/workflow/tool-workflow/src/index.ts` via ctx.get)

- watchRows `watchRows(sessionId: SessionId): () => void` — Keep one session's roster current; reference-counted, so two watchers of the same session share one stream and the rows leave with the last.
- observe `observe(sessionId: SessionId \| undefined, id: JobId): () => void` — Start observing one job's live output; reference-counted, so two viewers of the same job share one stream.
- kill `kill(sessionId: SessionId, id: JobId): Promise<RemoteResult<JobKillValue>>` — Kill one background job from a session's job list. Pure RPC passthrough: row state converges through the roster stream, and the caller (the job-list control) owns error presentation.

### `launchEnvironment` — `@deepseek-ai/dsh-launch-environment`

> Launcher-owned snapshot of this run's environment; absent in compositions the product CLI did not boot. */

- 提供类型：`LaunchEnvironmentSnapshot`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-launch-environment` (`packages/util/launch-environment/src/index.ts:37`，interface)

- get `get(name: string): LaunchEnvironmentEntry \| undefined` — Resolve one name across every layer, most trusted first.
- getFrom `getFrom(name: string, sources: readonly LaunchEnvironmentSource[]): LaunchEnvironmentEntry \| undefined` — Resolve one name only from `sources`, retaining canonical trust order; omitted layers are unreachable.

### `launcherSessionQueryPath` — `@deepseek-ai/dsh-session-query-sqlite`

> Launcher-owned absolute path to this process's disposable derived query index. */

- 提供类型：`string`；方法覆盖：unresolved；asar 核对：—

- （方法未解析：提供类型不可达或未定义成员）

### `layout` — `@deepseek-ai/dsh-client-ui-layout`

> The outward face only; the concrete service stays inside this plugin. */

- 提供类型：`import('./service.ts').ILayout`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-layout` (`packages/client/ui-layout/src/client/index.ts:191`)
- 消费方：@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `liveshareShares` — `@deepseek-ai/dsh-experimental-liveshare`

> Owner share management served to the owner page over Typert Remote. */

- 提供类型：`LiveshareShares`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-liveshare` (`packages/experimental/liveshare/src/host/share-remote.ts:44`，class)
- 提供方：`@deepseek-ai/dsh-experimental-liveshare` (`packages/experimental/liveshare/src/host/share-remote.ts:50`)

- create `create(request: CreateShareRequest): Promise<CreatedShare>` — Publish one Session and store the share.  *(decorators: @@Remote('create'))*
- addSessions `addSessions(request: AddShareSessionsRequest): Promise<ShareSessions>` — Add source Sessions to one share this host already publishes.  *(decorators: @@Remote('addSessions'))*
- list `list(): Promise<OwnerShareList>` — Refresh titles and Liveshare server authority, then list this host's shares.  *(decorators: @@Remote('list'))*
- stop `stop(request: StopShareRequest): Promise<StopShareResult>` — Stop one share locally, revoke its forks, and delete its row on the Liveshare server when reachable.  *(decorators: @@Remote('stop'))*
- updatePermissions `updatePermissions(request: UpdateSharePermissionsRequest): Promise<SharePermissions>` — Change one share's tier, fork switch, or both.  *(decorators: @@Remote('updatePermissions'))*
- setCapabilities `setCapabilities(request: SetShareCapabilitiesRequest): Promise<ShareCapabilities>` — Replace one share's exposed plugin endpoints.  *(decorators: @@Remote('setCapabilities'))*
- capabilities `capabilities(): ShareCapabilityOffers` — Read the endpoints plugins currently offer.  *(decorators: @@Remote('capabilities'))*
- relay `relay(): OwnerRelayState` — Read the Liveshare server address the owner saved.  *(decorators: @@Remote('relay'))*
- setRelay `setRelay(request: SetRelayRequest): Promise<OwnerRelayState>` — Choose the Liveshare server address later shares publish to.  *(decorators: @@Remote('setRelay'))*
- identity `identity(request: OwnerIdentityRequest): Promise<OwnerIdentityStatus>` — Report this host's owner identity for one Liveshare server address.  *(decorators: @@Remote('identity'))*
- audit `audit(request: ShareAuditRequest): Promise<ShareAudit>` — Read the Liveshare server's durable audit trail for one share.  *(decorators: @@Remote('audit'))*
- testRelay `testRelay(): Promise<RelayConnectivityView>` — Check that the effective Liveshare server answers at all.  *(decorators: @@Remote('testRelay'))*
- testPublish `testPublish(request: TestPublishRequest): Promise<RelayPublishView>` — Register one throwaway share to check whether this host may publish.  *(decorators: @@Remote('testPublish'))*

### `llm` — `@deepseek-ai/dsh-llm`

- 提供类型：`LlmRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-llm` (`packages/llm/llm/src/index.ts:369`，class)
- 提供方：`@deepseek-ai/dsh-llm` (`packages/llm/llm/src/index.ts:378`)
- 消费方：@deepseek-ai/dsh-acp(`packages/acp/acp/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-compaction-basic(`packages/compaction/compaction-basic/src/index.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-session-title-all-prompts-llm(`packages/experimental/session-title-all-prompts-llm/src/index.ts` via inject)、@deepseek-ai/dsh-llm-deepseek-account(`packages/llm/llm-deepseek-account/src/index.ts` via inject)、@deepseek-ai/dsh-llm-deepseek-api-key(`packages/llm/llm-deepseek-api-key/src/index.ts` via inject)、@deepseek-ai/dsh-llm-pi-ai(`packages/llm/llm-pi-ai/src/index.ts` via inject)、@deepseek-ai/dsh-session-checkpoint-policy(`packages/session/session-checkpoint-policy/src/index.ts` via inject)、@deepseek-ai/dsh-session-title-first-prompt-llm(`packages/session/session-title-first-prompt-llm/src/index.ts` via inject)、@deepseek-ai/dsh-llm-replay(`packages/test-support/llm-replay/src/index.ts` via inject)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/content.ts` via ctx.get)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/content.ts` via ctx.get)、@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/deepseek.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/read-image.ts` via ctx.get)、@deepseek-ai/dsh-token-meter(`packages/llm/token-meter/src/index.ts` via ctx.get)、@deepseek-ai/dsh-token-meter(`packages/llm/token-meter/src/index.ts` via ctx.get)、@deepseek-ai/dsh-mcp-client(`packages/mcp/mcp-client/src/tools.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-spill-policy(`packages/spill/spill-policy/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/manager.ts` via ctx.get)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/list-models.ts` via ctx.get)、@deepseek-ai/dsh-web-deepseek-api(`packages/web/web-deepseek-api/src/index.ts` via ctx.get)

- emitAdaptersUpdated `private emitAdaptersUpdated(): void` — Notify topology observers without letting one broken listener veto the commit. */
- warnAdaptersListenerFailure `private warnAdaptersListenerFailure(error: unknown): void` — Contained-listener diagnostic shared by the sync and async failure paths. */
- registerAdapter `registerAdapter(providers: string[], adapter: LlmAdapter): AdapterRegistrationHandle` — Register an adapter for the given provider routes. Throws `LlmError` with code `DUPLICATE_ADAPTER` if any provider already has an adapter (all-or-nothing). Disposed with the fiber.
- yield `yield () =>`
- prepareRoutes `private prepareRoutes(providers: string[], adapter: LlmAdapter, owned: ReadonlySet<string>): AdapterRegistration[]` — Validate one candidate route set for `adapter`, treating routes this registration already holds as available. Nothing is mutated: a rejected candidate leaves the registry exactly as it was.
- commitRoutes `private commitRoutes(owned: Set<string>, registrations: readonly AdapterRegistration[]): void` — Swap this registration's routes for the prepared ones in one synchronous section, so no observer can see the registry between the release and the re-registration. The route set's one mutation point is also where `llm/adapters-updated` is published, so a `replace` announces itself exactly like a first registration.
- listProviders `listProviders(): LlmProviderInfo[]` — Describe provider routes with a registered adapter.  *(decorators: @@Remote)*
- registerConfigurableProviders `registerConfigurableProviders(entries: readonly LlmConfigurableProvider[]): DirectoryRegistrationHandle` — Declare provider routes an adapter plugin can activate through configuration. Registration is all-or-nothing: an empty list, invalid entry, or a provider already declared by any registration throws `LlmError` without registering the rest. Disposed with the fiber.
- commit `commit(entries)`
- commit `commit(next)`
- listConfigurableProviders `listConfigurableProviders(): LlmConfigurableProvider[]` — List every declared configurable provider, registered or dormant.  *(decorators: @@Remote)*
- registerModelDiscovery `registerModelDiscovery( settingsNs: string, discover: ( request: LlmModelDiscoveryRequest, signal?: AbortSignal, ) => Promise<readonly LlmDiscoveredModel[]>, ): () => void` — Offer to interrogate provider endpoints on behalf of the settings namespace this plugin owns. The namespace is the key because that is what a configuration surface already holds from the configurable-provider directory, and because a provider being *added* has no route to name yet. Disposed with the fiber.
- discoverModels `async discoverModels( settingsNs: string, request: LlmModelDiscoveryRequest, signal?: AbortSignal, ): Promise<LlmDiscoveredModel[]>` — Interrogate one provider endpoint for the models it advertises. The request describes a draft, not a stored route, so nothing here reads or writes settings or credentials — the caller owns both, and the reply is candidate metadata a surface may offer for adoption.
- remoteDiscoverModels `async remoteDiscoverModels( settingsNs: string, request: LlmModelDiscoveryRequest, signal: AbortSignal, ): Promise<LlmDiscoveredModel[]>` — Remote adapter for one draft provider interrogation.  *(decorators: @@Remote('discoverModels'))*
- providerRetryPolicy `providerRetryPolicy(provider: string): ResolvedRetryPolicy` — Resolve the retry policy captured when one provider route was registered.
- imageRequestPricing `imageRequestPricing(provider: string, model: string): LlmImageRequestPricing \| undefined` — Resolve provider-side request-image pricing for one exact route, or `undefined` when the provider is unregistered or declares none. Unknown providers degrade to `undefined` rather than throwing because callers price durable history whose route may no longer be mounted.
- imageRequestTarget `imageRequestTarget(provider: string, model: string, image: ImageAttachmentRef): ImageRequestTarget` — Resolve the image projection for an exact registered model route.
- fileRequestText `fileRequestText(ref: FileAttachmentRef): string` — Resolve the exact text one durable file occurrence contributes to every provider request in the current execution environment.
- detachedModalities `private detachedModalities(modalities: readonly ModelModality[] \| undefined): ModelModality[] \| undefined` — Detach typed adapter-owned modality metadata. */
- listModels `async listModels(provider: string): Promise<LlmModelInfo[]>` — Discover models advertised by one registered provider. Catalog membership does not constrain core routing. Catalog-driven entry points may restrict selection and submission to the advertised models.
- resolveModelInfo `async resolveModelInfo( provider: string, model: string, signal?: AbortSignal, ): Promise<LlmResolvedModelInfo>` — Resolve and validate all metadata from the adapter that owns one exact route. The result is detached from adapter-owned objects; catalog membership remains advisory and does not control request routing.
- resolveModelInfoFor `private async resolveModelInfoFor( registration: AdapterRegistration, model: string, signal?: AbortSignal, ): Promise<LlmResolvedModelInfo>`
- normalizeModelInfo `private normalizeModelInfo( registration: AdapterRegistration, model: string, resolved: LlmResolvedModelInfo, ): LlmResolvedModelInfo` — Validate and detach one adapter-returned exact model result. */
- resolveCallConfig `async resolveCallConfig(config: LlmCallConfig, signal?: AbortSignal): Promise<LlmCallConfig>` — Validate a conversation call config against its exact model capability and materialize adapter-configured defaults. Unsupported explicit efforts reject before provider I/O; no clamping or aliasing is performed. This standalone query does not bind a later dispatch; use {@link prepareCall} when logging and streaming must share one adapter registration.
- resolveCallFor `private async resolveCallFor( registration: AdapterRegistration, config: LlmCallConfig, signal?: AbortSignal, ): Promise<`
- resolveCallWithInfo `private resolveCallWithInfo( config: LlmCallConfig, info: LlmResolvedModelInfo, ):` — Validate request controls against one already-bound exact model result. */
- prepareCall `async prepareCall( config: LlmCallConfig, signal?: AbortSignal, configure?: ConfigureCall, ): Promise<PreparedLlmCall>` — Resolve one call under its current adapter registration. The returned one-shot handle keeps that registration across header logging and dispatch, so HMR cannot combine one adapter's capability result with another adapter. An optional synchronous callback selects concrete controls using captured model metadata. Defaults and validation apply to its result. Callback failures and cancellation reject preparation before dispatch.
- registration `private registration(provider: string): AdapterRegistration`
- forAdapter `private forAdapter(options: GenerateOptions, adapter: LlmAdapter): GenerateOptions` — Remove replay state whose historical route is owned by another adapter. */
- fileReadPath `private fileReadPath(ref: FileAttachmentRef): string \| undefined` — Resolve the current execution-world read path of one durable file reference through the mounted attachment and filesystem providers.
- stream `stream(options: GenerateOptions): AsyncIterable<StreamChunk>` — Stream one model call as raw chunks (token-level deltas). Replay state is retained only when the same adapter instance owns its historical provider and the target provider. Final adapter selection remains fixed through asynchronous exact-model resolution and dispatch. Adapter selection, dispatch, and iteration failures become terminal `error` or `aborted` finish chunks; middleware, nested-call, cleanup, and consumer failures remain thrown.
- streamWithRegistration `private streamWithRegistration( options: GenerateOptions, prepared?: PreparedDispatch, ): AsyncIterable<StreamChunk>`

### `locale` — `@deepseek-ai/dsh-client-locale`

- 提供类型：`LocaleRuntime`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-locale` (`packages/client/locale/src/client/index.ts:166`，class)
- 提供方：`@deepseek-ai/dsh-client-locale` (`packages/client/locale/src/client/index.ts:588`)
- 消费方：@deepseek-ai/dsh-client-shortcuts(`packages/client/shortcuts/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-account-notifications(`packages/client/ui-account-notifications/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-team(`packages/client/ui-agent-team/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-approval(`packages/client/ui-approval/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-context-menu(`packages/client/ui-context-menu/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-browse(`packages/client/ui-directory-picker-browse/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-file-drag(`packages/client/ui-file-drag/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-goal(`packages/client/ui-goal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-input-trigger(`packages/client/ui-input-trigger/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-jobs(`packages/client/ui-jobs/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-layout(`packages/client/ui-layout/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-message-feedback(`packages/client/ui-message-feedback/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-market(`packages/client/ui-plugin-market/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-secret-mask(`packages/client/ui-secret-mask/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-agent-loop(`packages/client/ui-settings-agent-loop/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugin-inventory(`packages/client/ui-settings-plugin-inventory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugins(`packages/client/ui-settings-plugins/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-session-log(`packages/client/ui-settings-session-log/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-shell(`packages/client/ui-settings-shell/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-subagent(`packages/client/ui-settings-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-web-search(`packages/client/ui-settings-web-search/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-shortcuts(`packages/client/ui-shortcuts/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-browser(`packages/client/ui-sidebar-browser/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-files(`packages/client/ui-sidebar-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-subagent(`packages/client/ui-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-theme(`packages/client/ui-theme/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workflow-run(`packages/client/ui-workflow-run/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-action-cards(`packages/experimental/client-ui-action-cards/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-claude-code-mods(`packages/experimental/client-ui-claude-code-mods/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-creation-recommendations(`packages/experimental/client-ui-creation-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-recommendations(`packages/experimental/client-ui-plugin-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-stats(`packages/experimental/client-ui-stats/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-voice-input(`packages/experimental/client-ui-voice-input/src/client/mount.ts` via inject)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/client/mount.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-cordis(`packages/extensions/ui-cordis/src/client/index.ts` via inject)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/client/index.ts` via inject)、@deepseek-ai/dsh-message-quotes(`packages/session/message-quotes/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via ctx.get)

- getLocale `getLocale(): LocaleSnapshot` — Read the current immutable locale snapshot.
- resolveText `resolveText(text: LocalizedText): string` — Resolve package text through the active language's declared fallback chain. Plain strings stay verbatim; maps do not consult registered dictionaries.
- getSnapshot `getSnapshot(): LocaleSnapshot` — LocaleFace getSnapshot: the current snapshot (carries `revision`; stable reference between changes, uSES-safe).
- subscribe `subscribe(fn: () => void): () => void` — LocaleFace subscribe: notified on every snapshot change (locale switch or dictionary registration — registrations bump the revision so already rendered outlets pick up late-arriving dictionaries and locale definitions).
- setLocale `setLocale(id: string): void` — Switch the active locale — the only user preference write entry. The durable write happens even when the id already matches the active locale, because the active value may be a provisional browser-derived or fallback resolution that nothing has stored yet. Picking the language already on screen is still an explicit choice, and it must survive a different browser sharing the same DSH home. Only the render notification is conditional: republishing an unchanged locale would churn every subscriber for nothing.
- addLanguage `addLanguage(input: LanguageRegistration): () => void` — Add one selectable language to the shared catalog. Its fallback must already be registered, and following fallback definitions must terminate at English. Dictionaries may register before or after this definition. Registration rechecks an unresolved Host preference and the browser's ordered language list. The caller owns the returned disposer; removing an active language falls back without clearing the stored id. target is unknown or creates a cycle.
- adopt `private adopt(host: ConfigForm<LocaleSettings>): void` — Adopt the scope's accepted durable selection without writing it back; an absent selection returns to the browser-derived locale.
- publishCatalog `private publishCatalog(): void` — Recompute browser fallback and publish the current catalog. */
- resolveActive `private resolveActive(): LocaleId` — Resolve an explicit preference only while its definition is available. */
- localeList `private localeList(): readonly LocaleDefinition[]` — Snapshot the catalog in registration order. */
- assertFallbackChain `private assertFallbackChain(start: LocaleId): void` — Fail a new definition whose complete fallback path does not reach English. */
- fallbackChain `private fallbackChain(start: LocaleId): readonly LocaleId[]` — Resolve a lookup chain, falling directly to English across an unload gap. */
- register `register(ns: string, locale: string, dict: LocaleDict): () => void` — Single-locale untyped form for language-pack contributions and namespaces outside the merge table.
- register `register(ns: string, localeOrDicts: string \| Record<string, LocaleDict>, dict?: LocaleDict): () => void`
- bind `bind(ns: string): Translate` — Untyped form for namespaces outside the merge table (dynamic composition, tests).
- translate `private translate(ns: string, key: string, params?: Record<string, unknown>): string`
- lookup `private lookup(ns: string, key: string, chain: readonly LocaleId[]): string \| undefined`
- publish `private publish( active: LocaleId, localeChanged: boolean, locales: readonly LocaleDefinition[] = this.snapshot.locales, ): void` — Advance the snapshot revision and notify LocaleFace subscribers (render refresh). Only an active-locale switch additionally emits `locale/change` — dictionary registrations stay off the event so registration-heavy boot cannot storm event listeners (which may re-register slots in response).
- fn `fn()`

### `lsp` — `@deepseek-ai/dsh-lsp`

- 提供类型：`LspService`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-lsp` (`packages/lsp/lsp/src/types.ts:113`，interface)
- 提供方：`@deepseek-ai/dsh-lsp` (`packages/lsp/lsp/src/index.ts:98`)
- 消费方：@deepseek-ai/dsh-lsp-stdio(`packages/lsp/lsp-stdio/src/index.ts` via inject)、@deepseek-ai/dsh-tool-lsp(`packages/lsp/tool-lsp/src/index.ts` via inject)

- registerProvider `registerProvider(provider: LspProvider): () => void` — Register a provider, atomically reserving its id and every normalized extension. Any conflict or invalid input publishes nothing and throws `LspError`; the returned disposer releases all reservations. Disposed with the calling fiber.
- query `query(request: LspQueryRequest, signal?: AbortSignal): Promise<LspQueryResult>` — Select a provider by the file's extension and run one query. Selection is per-query and order-independent; no match throws `LspError` `LSP_UNAVAILABLE`.

### `mcpManager` — `@deepseek-ai/dsh-mcp-manager`

> The MCP server manager. */

- 提供类型：`McpServerManager`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-mcp-manager` (`packages/mcp/mcp-manager/src/index.ts:221`)

- （方法未解析：提供类型不可达或未定义成员）

### `mcpResources` — `@deepseek-ai/dsh-mcp-resources`

- 提供类型：`McpResourceRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-mcp-resources` (`packages/mcp/mcp-resources/src/index.ts:49`，class)
- 提供方：`@deepseek-ai/dsh-mcp-resources` (`packages/mcp/mcp-resources/src/index.ts:58`)

- register `register(server: string, provider: McpResourceProvider): () => void` — Register one server and expose resource tools while that scope has providers.
- yield `yield () => disposal` — Tools disappear synchronously; Cordis owns any pending scoped-fiber teardown.
- remove `remove()`
- registerTools `private registerTools(scope: ScopeKey \| undefined): () => void \| Promise<void>` — Own one scope's tools independently of its configured server plugins. */
- request `private request(server: string, request: McpResourceRequest, exec: ToolExecution): Promise<JsonValue>` — Resolve the caller-visible server before starting any network operation. */

### `messageFeedback` — `@deepseek-ai/dsh-message-feedback`

- 提供类型：`MessageFeedbackService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-message-feedback` (`packages/feedback/message-feedback/src/index.ts:118`，class)
- 提供方：`@deepseek-ai/dsh-message-feedback` (`packages/feedback/message-feedback/src/index.ts:135`)

- list `list(request: MessageFeedbackListRequest): Promise<MessageFeedbackListResult>` — Read current feedback from the canonical log.  *(decorators: @@Remote('list'))*
- success `success(Object.freeze({ items: Object.freeze(currentItems(request.sessionId, events).map(snapshotItem)) }))))`
- put `put(request: MessageFeedbackPutRequest): Promise<MessageFeedbackPutResult>` — Create or replace feedback after checking its current version. Matching no-ops retain the version and append no event.  *(decorators: @@Remote('put'))*
- delete `delete(request: MessageFeedbackDeleteRequest): Promise<MessageFeedbackDeleteResult>` — Delete one item after checking its version; absence succeeds without an event.  *(decorators: @@Remote('delete'))*
- withSession `private async withSession<T>( sessionId: SessionId, write: boolean, operation: (events: readonly SessionEvent[], append: Append) => T \| Promise<T>, ): Promise<T \| MissingSession>` — Hold cold write ownership across read/compare/append; use live owners directly. */
- resolveNote `private resolveNote(note: string \| undefined): ResolvedNote`
- versionConflict `private versionConflict(current: MessageFeedbackItem \| null): MessageFeedbackVersionConflict`
- enqueue `private enqueue<T>(sessionId: SessionId, operation: () => Promise<T>): Promise<T>` — Serialize complete operations and drain their handles before disposal. */

### `modelDirectories` — `@deepseek-ai/dsh-client-ui-model-selection`

- 提供类型：`ModelDirectoryResolver`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-model-selection` (`packages/client/ui-model-selection/src/client/service.ts:37`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-model-selection` (`packages/client/ui-model-selection/src/client/service.ts:47`)

- directoryFor `directoryFor(sessionId: SessionId): ModelDirectory` — Resolve the per-session shared directory (lazy; the scope disposer removes and disposes it). Unknown sessions fail loud.

### `modules` — `@deepseek-ai/dsh-client-modules`

> The client module system the web shell builds at boot (provided by the `./client` wrapper plugin). */

- 提供类型：`ClientModuleLoader`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-modules` (`packages/client/modules/src/client/manifest.ts:433`，interface)
- 提供方：`@deepseek-ai/dsh-client-modules` (`packages/client/modules/src/client/index.ts:68`)
- 消费方：@deepseek-ai/dsh-client-hmr(`packages/client/hmr/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugin-inventory(`packages/client/ui-settings-plugin-inventory/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/index.ts` via ctx.get)

- import `import(specifier: string, parentURL: string, attrs: Record<string, unknown>): Promise<unknown>` — Internal contract consumed by the vendored Loader's `tree.import`. Resolves `specifier` through the branch order documented on the module, fetching and executing a bundle when needed.
- prefetch `prefetch(id: string): Promise<void>` — Stage-one arrival: load the entry's declared dynamic requests, then its own script, to register their factories (no materialization — module side effects wait for import). No-op for materialized bootstrap ids. A registered graph row still registers any unresolved declared requests before skipping its own script; concurrent arrivals share one in-flight task. To force a fresh load (HMR), {@link invalidate} first.
- importError `importError(id: string): Error \| undefined` — The last failure of {@link import} or {@link prefetch} for one graph row: transport, registration, dependency cascade, or factory execution. Cleared by a later success and by {@link invalidate}. The boot audit reads it to report why a Loader entry has no fiber.
- invalidate `invalidate(id: string, rev?: string): void` — Full reset of one non-bootstrap package: drop its entry and chunk factories and materialized records so the next prefetch/import loads its one-resource combo script rather than the initial multi-resource request. The bootstrap module remains materialized. the graph revision or for page-local modules that register directly.

### `officeKit` — `@deepseek-ai/dsh-office-kit`

> Shared Office rendering, conversion, recalculation, and authorized workspace-file previews. */

- 提供类型：`OfficeKit`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-office-kit` (`packages/document/office-kit/src/index.ts:127`，class)
- 提供方：`@deepseek-ai/dsh-office-kit` (`packages/document/office-kit/src/index.ts:147`)
- 消费方：@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via ctx.get)

- convert `async convert(request: OfficeKitRequest, signal?: AbortSignal): Promise<OfficeKitResult>` — Convert Office bytes to PDF without modifying the source or writing Session events.
- renderImages `async renderImages(request: OfficeImagesRequest, signal?: AbortSignal): Promise<OfficeImagesResult>` — Render selected pages, slides, or worksheet areas of one document as PNG images. Requests share the admission queue, concurrency, source-byte reservation, and cache with previews, and run at foreground priority. selection exceeds a limit, and the other conversion codes; cancellation rejects with its reason.
- convertTo `async convertTo(request: OfficeConversionRequest, signal?: AbortSignal): Promise<OfficeFileResult>` — Convert one document to another format at foreground priority, sharing admission, concurrency, and cache with previews, and save the result in the provider's output store. outputs need `maxOutputStoreBytes`, when the Session whose id is `output.owner` is disposed, or when the provider is disposed. codes; cancellation rejects with its reason.
- recalculate `async recalculate(request: OfficeRecalculationRequest, signal?: AbortSignal): Promise<OfficeFileResult>` — Recalculate every formula of one workbook at foreground priority and save formulas with refreshed cached results, sharing admission, concurrency, and cache with previews, and save the workbook in the provider's output store. This does not validate formulas or business data.
- saveFile `private async saveFile( output: OfficeOutputTarget, result: Extract<OfficeOperationOutput, { kind: 'file' }>, signal: AbortSignal \| undefined, ): Promise<OfficeFileResult>`
- render `async render( workspaceFileScope: WorkspaceFileScope, path: string, priority: OfficeKitPriority, signal: AbortSignal, ): Promise<RenderedDocumentBytes>` — Read and convert one Office file using the Session's ordinary filesystem authorization.  *(decorators: @@Remote)*
- getGeneration `getGeneration(signal: AbortSignal): OfficeKitGeneration` — Read the current rendering generation before reusing a Client PDF.  *(decorators: @@Remote('generation'))*
- renderFile `private async renderFile( scope: WorkspaceFileScope, path: string, priority: OfficeKitPriority, signal: AbortSignal, ): Promise<RenderedDocumentBytes>`
- assertUnchanged `assertUnchanged(authorized)`
- assertUnchanged `assertUnchanged({ absolutePath: fs.processPath(target), version: info.version })`
- assertUnchanged `assertUnchanged(await files.stat(scope, path, upstream))`
- assertUnchanged `assertUnchanged(after)`
- loadKit `private loadKit(): Promise<LoadedKit>` — Locate and import Kit for a converter. A successful import is reused for the provider lifetime; a missing or unloadable Kit rejects as `unavailable` without being retained, so the next converter request locates Kit again.
- importKit `private async importKit(): Promise<LoadedKit>`
- unavailableKit `private unavailableKit(message: string, cause: unknown): OfficeKitError` — Classify a Kit failure as `unavailable`, logging each distinct message and cause once per provider lifetime. */
- runOperation `private async runOperation( bytes: Uint8Array, request: Pick<QueueRequest, 'extension' \| 'operation'>, signal: AbortSignal, ): Promise<OfficeOperationOutput>`
- createConverter `createConverter({ ...this.options, resolveEnginePackage })).catch((error: unknown) =>`
- runEngine `private async runEngine( converter: Converter, inputPath: string, directory: string, operation: OfficeOperation, signal: AbortSignal, ): Promise<OfficeOperationOutput>` — Run one engine operation in a private scratch directory and read its complete, bounded output. */
- readFile `private async readFile(path: string, format: string, signal: AbortSignal): Promise<Uint8Array>`
- renderPng `private async renderPng( converter: Converter, inputPath: string, directory: string, operation: Extract<OfficeOperation, { kind: 'images' }>, signal: AbortSignal, ): Promise<Office…`

### `otel` — `@deepseek-ai/dsh-otel`

- 提供类型：`OTel`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-otel` (`packages/telemetry/otel/src/index.ts:14`)
- 消费方：@deepseek-ai/dsh-host-product-telemetry-otel(`packages/host/product-telemetry-otel/src/index.ts` via inject)、@deepseek-ai/dsh-session-telemetry-otel(`packages/session/session-telemetry-otel/src/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `permissionPresets` — `@deepseek-ai/dsh-permission-presets`

- 提供类型：`PermissionPresetService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-permission-presets` (`packages/interaction/permission-presets/src/index.ts:174`，class)
- 提供方：`@deepseek-ai/dsh-permission-presets` (`packages/interaction/permission-presets/src/index.ts:204`)
- 消费方：@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)

- catalog `catalog(): PermissionCatalog` — Read the complete process-level catalog exposed to current-session UI.  *(decorators: @@Remote('catalog'))*
- registerAuto `registerAuto(admit: () => void): () => Promise<void>` — Publish the fixed current-session Auto preset for the calling integration's effect lifetime.
- permissionState `private permissionState(session: Session): PermissionProjectionState`
- current `current(session: Session): string` — Resolve the preset matching the effective knob values. A still-matching last selection wins shared-bundle ties, and a still-selected Auto also matches the `never` approval policy; otherwise the first configured match wins. Returns {@link CUSTOM_PRESET} when no available preset matches.
- derive `private derive(state: KnobState): string` — Resolve the preset for one folded knob state (the shared mathematics of `current` and the projection unit). */
- resolve `resolve(name: string): PresetSpec` — Resolve an available preset's knob bundle.
- optionOf `optionOf(name: string): PresetOption` — Build the client option for an available preset or {@link CUSTOM_PRESET}. A missing label falls back to the preset key.
- set `set(session: Session, name: string): void` — Record a changed preset, then update each changed knob through its own setter. Selecting the effective preset again appends nothing.
- apply `private apply(session: Session, name: string, setApproval: (policy: ApprovalPolicy) => void): void` — Apply one preset through its durable identity and canonical knob setters. */
- setSandboxMode `setSandboxMode(session, spec.sandbox)`
- setApproval `setApproval(spec.approval)`
- updateKnobs `updateKnobs()`
- pinInitialPermission `private pinInitialPermission(session: Session): void` — Fill every missing permission fact during Agent creation. A genuinely fresh session uses the current user default; seeded or partially initialized sessions preserve their effective knob values and only gain the missing durable facts. A stored Auto identity requires its live integration and passes its admission check before creation completes. Creation while the permission reader is still registering fails so the publishing caller can roll back.
- setApprovalPolicy `setApprovalPolicy(session, spec.approval)`
- setSandboxMode `setSandboxMode(session, this.ctx.shell.sandboxMode as SandboxMode)`
- setApprovalPolicy `setApprovalPolicy(session, this.ctx.approval.config.policy ?? 'ask')`
- emitCatalogChanged `private emitCatalogChanged(): void` — Publish a non-vetoing payload-free catalog invalidation. */
- specOf `private specOf(name: string): PresetSpec \| undefined` — Resolve one configured or currently live fixed preset without throwing. */

### `planMode` — `@deepseek-ai/dsh-plan-mode`

- 提供类型：`PlanModeController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-plan-mode` (`packages/plan/plan-mode/src/index.ts:176`，class)
- 提供方：`@deepseek-ai/dsh-plan-mode` (`packages/plan/plan-mode/src/index.ts:191`)

- loggedActive `private loggedActive(session: Session): boolean`
- selectedActive `private selectedActive(session: Session): boolean` — The state a proposed step presents: a pending selection, else the logged state. */
- hasOpenTurn `private hasOpenTurn(session: Session): boolean`
- loggedActiveAtLastHeader `private loggedActiveAtLastHeader(session: Session): boolean \| undefined`
- planState `private planState(session: Session): PlanUnitState`
- get `get(agent: Agent):` — Read the logged plan state and any selected state awaiting the next accepted in-turn pre-step.
- set `set(agent: Agent, active: boolean): 'committed' \| 'queued' \| 'cancelled' \| 'noop'` — Select whether plan mode should be active. Between turns the method appends the change immediately because no in-turn pre-step will run until another prompt starts a turn. The open-turn fold is the idle signal: agent status stays `running` through post-turn checkpointing, when no further in-turn pre-step runs. During an open turn the selection remains pending until the next accepted in-turn pre-step. Repeated selection of the current or already-pending state is a no-op. next accepted in-turn pre-step), `cancelled` (an opposite pending selection was cleared; the logged state already matches), or `noop` (already in that state).
- onBoundary `private onBoundary(session: Session): void` — Append one pending selection before the next request assembly. */
- narration `private narration(session: Session, target: boolean): UserMessage \| undefined` — Build a user-switch notice when the last logged header described the other mode. */

### `pluginChanges` — `@deepseek-ai/dsh-client-ui-plugin-manager`

> Read-only management activity, independent of the visible Plugins page. */

- 提供类型：`{ /** * Observe whether a bundle or one of its rows is being changed. * @param packageName Bundle package name. * @returns A snapshot source whose subscriptions belong to the caller. */ bundle(packageName: string): HostObservable<boolean> }`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-plugin-manager` (`packages/client/ui-plugin-manager/src/client/index.ts:99`)

- （方法未解析：提供类型不可达或未定义成员）

### `pluginManager` — `@deepseek-ai/dsh-plugin-manager`

> Persistent management of the current profile's composition and packages. */

- 提供类型：`PluginManager`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-plugin-manager` (`packages/boot/plugin-manager/src/index.ts:323`，class)
- 提供方：`@deepseek-ai/dsh-plugin-manager` (`packages/boot/plugin-manager/src/index.ts:369`)
- 消费方：@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/tools.ts` via inject)、@deepseek-ai/dsh-plugin-market(`packages/boot/plugin-market/src/index.ts` via inject)、@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-recommendations(`packages/experimental/plugin-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-host-plugin-inventory(`packages/host/plugin-inventory/src/index.ts` via ctx.get)

- readBundleDetail `async readBundleDetail(name: string, language: string, options?: { npmFileSources?: NpmFileSource[] }): Promise<BundleDetail>` — Read a bundle's long description: the Markdown file its locale `meta.detail` names in `language`, otherwise its README. An installed bundle is read from its directory without network access; an official bundle the installation offers before it is installed is read from the npm file CDNs at its offered version. Nothing is cached. a Client measured as fastest; configured CDNs it omits follow, and CDNs that are not configured are not asked. `plugin-manager/detail-unavailable`.  *(decorators: @@Remote)*
- listedBundle `private async listedBundle(name: string): Promise<BundleInfo>`
- serveDetailFile `private async serveDetailFile(request: Request): Promise<Response>` — Answer `GET ${DETAIL_FILE_PATH}?bundle=<name>&document=<path>&path=<destination>[&sources=<cdn>,...]` with one image beside a bundle document; `sources` names npm file CDNs to ask first for an offered bundle, as `readBundleDetail` does.
- listVersionExemptions `listVersionExemptions():` — Read exact plugin-version exemptions saved in this profile. record or file problem the reader rejected, which the caller reports instead of failing.  *(decorators: @@Remote)*
- setVersionExemption `setVersionExemption(packageVersion: string, runtimeVersion: string, enabled: boolean, acceptRisk?: boolean): Promise<ChangeResult>` — Grant or revoke one exact plugin/runtime exemption and reevaluate live plugins.  *(decorators: @@Remote)*
- listPlugins `async listPlugins(): Promise<PluginInfo[]>` — Read current plugins, including why a row cannot be changed through the profile patch.  *(decorators: @@Remote)*
- listBundles `listBundles(): Promise<BundleInfo[]>` — Read installed, installation-provided, and offline Official catalog bundles, plus selected non-bundle names. A dependency without a bundle patch is listed, as a `not-bundle` problem, only while it is selected. display metadata, activation selections, whether the installation offers the bundle, and removal availability.  *(decorators: @@Remote)*
- readBundles `private readBundles(): Omit<BundleInfo, 'update'>[]` — The bundle inventory before update eligibility, which is derived from each listed bundle. */
- registries `async registries(): Promise<PluginRegistries>` — Read the registries this manager asks: the configured first one, its fallbacks in order, and what pnpm's own configuration names.  *(decorators: @@Remote)*
- inspect `async inspect(spec: string, options?: InspectOptions, signal?: AbortSignal): Promise<PluginSpecInspection>` — Read what a spec names before installing it.  *(decorators: @@Remote)*
- listVersions `async listVersions(name: string, options?: ListVersionsOptions, signal?: AbortSignal): Promise<PluginVersionList>` — Read the published versions newer than an installed registry package's version, from the first registry that answers. Official bundles follow the DSH version and are not listed. and DSH compatibility, and the registry that answered; or why no list could be read, with every registry asked.  *(decorators: @@Remote)*
- updateBundle `async updateBundle(name: string, version: string, options?: UpdateBundleOptions): Promise<PluginUpdateResult>` — Replace an installed bundle with a newer version. A registry copy updates to `name@version`, checked on the registry first: it must exist, declare a bundle, and accept the running DSH version, or nothing changes. A Git copy updates to the Git spec `options.spec` names, which must pin a full commit of the repository directory the copy came from; with HMR, a network failure or timeout reaching its repository stops the update before anything changes. pnpm reads a Git package only while installing it, so its bundle and compatibility are checked then. Either target installation is undone, profile files and modules included, before its bundle loads unless it installs `name` at `version`. With HMR the installed version is removed, so its plugins stop, and the target is installed with the same selection; when that installation fails or is cancelled, the removed version is installed again: a registry copy from the registry it came from, a Git copy from its saved spec. Without HMR the target is installed over the running version and the result reports the restart. only by a bundle `listBundles` lists with `update: 'git'`; and the request id naming the progress and the target installation's logs and cancellation.  *(decorators: @@Remote)*
- announce `announce('checking')`
- announce `announce('installing')`
- announce `announce('removing')`
- announce `announce('restoring')`
- planGitUpdate `private planGitUpdate(name: string, origin: string, options: UpdateBundleOptions \| undefined): UpdatePlan \| ManagementError` — The target of a Git copy's update: the caller's Git spec, pinned to a full commit of the copy's repository directory.
- gitHostUnreachable `private async gitHostUnreachable(spec: string): Promise<PackageResult \| undefined>` — Check that the network reaches the repository of a Git update's target. Only a network failure or a timeout counts: a check Git cannot run, or one the repository refuses without credentials, leaves the answer to pnpm.
- checkRegistryUpdate `private async checkRegistryUpdate( name: string, version: string, options: UpdateBundleOptions \| undefined, ): Promise<UpdatePlan \| ManagementError>` — Check a registry copy's update target on the registry plan before anything changes.
- registryFor `private registryFor(name: string, requested: Registry \| undefined): Registry \| undefined` — The registry a version listing or an update asks first.
- askRegistries `private async askRegistries( spec: string, fields: readonly string[], plan: readonly Registry[], parsed: ParsedInstallSpec, signal?: AbortSignal, ): Promise<RegistryAnswer>` — Ask registries in turn through `pnpm view`, moving to the next one while a failure is the registry's: unreachable, timed out, or without the package or version, which a mirror not yet synced reports.
- setPluginEnabled `setPluginEnabled(id: PluginEntryId, enabled: boolean): Promise<ChangeResult>` — Persist a plugin entry's desired enablement and apply it on live profiles.  *(decorators: @@Remote)*
- setBundleEnabled `setBundleEnabled(name: string, enabled: boolean): Promise<ChangeResult>` — Select or remove a bundle layer while retaining installed dependencies.  *(decorators: @@Remote)*
- installBundle `installBundle(spec: string, options?: InstallBundleOptions): Promise<ChangeResult>` — Install a package using the same pnpm implementation as dsh plugin. GitHub repositories get a connection check bounded by githubConnectionTimeoutMs before pnpm starts; only network failures or timeouts stop installation, and a stop streams the check's diagnostic as the installation's install-log run under its request id, while pnpm owns authentication and transport fallback. An HTTP(S) Git URL on another host is installed over SSH instead when access probes bounded by gitTransportTimeoutMs find that only SSH can read it. A run that fails, is cancelled, or adds a package without a bundle patch restores `package.json` and `pnpm-lock.yaml` as they were; downloaded files can stay. the pending build scripts to allow, whether to save an exact dependency, and the registry asked first.  *(decorators: @@Remote)*
- announce `announce('installing', { registry, index: index + 1, total: plan.length })`
- announce `announce('applying')`
- waitForInstall `async waitForInstall(requestId: PluginInstallRequestId): Promise<ChangeResult \| null>` — Recover the result of an active installation without cancelling it. Completed results are not retained; null establishes neither success nor cancellation.  *(decorators: @@Remote)*
- cancelInstall `async cancelInstall(requestId: PluginInstallRequestId): Promise<PluginInstallCancellation>` — Stop an installation this manager owns and wait until its files are back. applied, `not-running` for any other id.  *(decorators: @@Remote)*
- removeBundle `removeBundle(name: string): Promise<ChangeResult>` — Unload and remove a profile-owned bundle dependency through dsh plugin's pnpm path; a selected name no dependency holds is only deselected.  *(decorators: @@Remote)*
- declaredRows `private declaredRows(name: string, info: ProfileManifest): Pick<BundleInfo, 'rows' \| 'overrides'>` — The rows a bundle's patch inserts and the existing rows it changes; an unreadable patch throws. */
- runPnpm `private async runPnpm( args: readonly string[], signal?: AbortSignal, requestId?: PluginInstallRequestId, expected?: InstallBundleOptions['expected'], ): Promise<PackageResult>` — Run one pnpm command in the profile, streaming its output as install-log chunks; `expected` is the package an `add` must install. */
- readRestoredFiles `private async readRestoredFiles(): Promise<Map<string, string \| undefined>>` — The profile files an installation may rewrite, as they are now; absent files read as undefined. */
- restoreFiles `private async restoreFiles(files: Map<string, string \| undefined>): Promise<void>` — Put the profile files back; pnpm has exited by the time this runs. */
- selectBundle `private async selectBundle(name: string, enabled: boolean): Promise<void>`
- assertBundlePlatform `assertBundlePlatform(metadata.dsh?.bundle?.platforms, process.platform)`
- bundleRows `private bundleRows(name: string): EntryOptions[]`
- protectsManager `private protectsManager(name: string): boolean`
- configure `private configure<T>(operation: () => Promise<T>): Promise<T>`
- refreshPackages `private async refreshPackages(): Promise<void>` — Publish the profile's runtime resolution without HMR, unless a deselected startup bundle still runs and needs the current table. A publication that needs a restart waits for the restart the result already reports.
- publishAndReload `private async publishAndReload(requiredIds: readonly string[] = []): Promise<Reload>` — Apply a package change: without HMR, publish the runtime resolution when that is safe, then {@link reload}.
- reload `private async reload(requiredIds: readonly string[] = []): Promise<Reload>` — Apply the saved profile; with HMR it recomposes live, including the runtime resolution.
- composeEntries `composeEntries([readProfilePatches('dsh', this.profile)])` — Startup-only profiles recompose at restart; the saved patches still have to compose.
- change `private async change( operation: (result: ChangeResult) => Promise<ChangeResult['application'] \| void>, request: Pick<ChangeResult, 'stage' \| 'target' \| 'enabled'>, reason: PluginC…`
- reportOperation `private reportOperation(operation: PluginOperation): void`
- operationTarget `private operationTarget(reason: PluginChange['reason'], target: string): string \| null`
- operationVersion `private operationVersion(reason: PluginChange['reason'], target: string \| null): string \| undefined` — Read the request-time package version without preventing recovery from damaged metadata. */
- diskState `private diskState(): string`

### `pluginMarket` — `@deepseek-ai/dsh-plugin-market`

> Configured plugin market index sources and their validated listings. */

- 提供类型：`PluginMarket`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-plugin-market` (`packages/boot/plugin-market/src/index.ts:135`)

- （方法未解析：提供类型不可达或未定义成员）

### `pluginNavigation` — `@deepseek-ai/dsh-client-ui-plugin-manager`

> Cross-plugin navigation to the Plugins panel. */

- 提供类型：`{ /** * Open a bundle's details without changing the current Session. * An absent bundle displays the plugin list after loading. * @param packageName - npm package name of the bundle. */ openBundle(packageName: string): void /** Open the Plugins main list without opening a dialog or changing the current Session. */ openList(): void }`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-plugin-manager` (`packages/client/ui-plugin-manager/src/client/index.ts:153`)
- 消费方：@deepseek-ai/dsh-client-ui-plugin-recommendations(`packages/experimental/client-ui-plugin-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-voice-input(`packages/experimental/client-ui-voice-input/src/client/mount.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `pluginPackages` — `@deepseek-ai/dsh-app-boot`

> Deterministic package lookup for configured plugin specifiers. */

- 提供类型：`PluginPackages`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-app-boot` (`packages/boot/app-boot/src/profile-resolution/service.ts:60`，class)
- 提供方：`@deepseek-ai/dsh-app-boot` (`packages/boot/app-boot/src/profile-resolution/service.ts:67`)
- 消费方：@deepseek-ai/dsh-app-boot(`packages/boot/app-boot/src/compatibility-preflight.ts` via ctx.get)、@deepseek-ai/dsh-app-boot(`packages/boot/app-boot/src/index.ts` via ctx.get)、@deepseek-ai/dsh-app-boot(`packages/boot/app-boot/src/startup-diagnostics.ts` via ctx.get)、@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-cordis(`packages/extensions/tool-cordis/src/config.ts` via ctx.get)、@deepseek-ai/dsh-host-plugin-inventory(`packages/host/plugin-inventory/src/index.ts` via ctx.get)、@deepseek-ai/dsh-plugin-package-inventory-deepseek(`packages/llm/plugin-package-inventory-deepseek/src/index.ts` via ctx.get)、@deepseek-ai/dsh-typert-loader(`packages/typert/loader/src/index.ts` via ctx.get)

- replace `replace(successor: RuntimeResolution): void` — Publish a complete successor generation for this process and subsequently created Workers. Profile mappings and local package names may be removed after their plugins stop; linked roots may also be removed. Retained profile mappings may change their declarer and version, but not their normalized directory or scope; installation mappings must remain unchanged. Publication does not unload modules or clear Node caches.
- refresh `async refresh(): Promise<void>` — Publish the latest generation computed by the installed resolution through {@link replace}. Package contents and loaded modules are not reloaded. reading the latest files fails, or the successor is rejected. A computed resolution without a profile can refresh.
- packageOf `packageOf(specifier: string, parentURL: string): PluginPackage \| undefined` — Locate the package named by a specifier without requiring a package export.
- metaOf `metaOf(specifier: string, parentURL: string): PluginLocalizedMeta \| undefined` — Read display metadata without loading or activating the target plugin.

### `pluginRecommendations` — `@deepseek-ai/dsh-plugin-recommendations`

- 提供类型：`PluginRecommendations`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-plugin-recommendations` (`packages/experimental/plugin-recommendations/src/index.ts:46`，class)
- 提供方：`@deepseek-ai/dsh-plugin-recommendations` (`packages/experimental/plugin-recommendations/src/index.ts:55`)

- registerOfficialPluginsSkill `registerOfficialPluginsSkill(this.ctx)`
- describe `async describe(agent: Agent, callId: ToolCallId): Promise<RecommendationDetails>` — Read the current catalog text for a logged card.  *(decorators: @@Remote)*
- isStopping `private isStopping(): boolean`
- tracked `private tracked<T>(operation: Promise<T>): Promise<T>` — Track an operation until it settles, so unloading waits for it. */
- confirm `private async confirm(agent: Agent, proposal: PluginProposal): Promise<void>` — Record `enabled` on an unconfirmed card whose interrupted enable has since turned its plugin on. */
- enable `private async enable(agent: Agent, proposal: PluginProposal): Promise<ActionCardResult>` — Enable the card's plugin once; an enabled card settles unchanged, and a failed or unconfirmed one can be retried. */
- record `record('unconfirmed')`

### `pluginRegistryProbe` — `@deepseek-ai/dsh-client-ui-plugin-manager`

- 提供类型：`PluginRegistryProbe`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-client-ui-plugin-manager` (`packages/client/ui-plugin-manager/src/index.ts:37`)

- （方法未解析：提供类型不可达或未定义成员）

### `productAnalytics` — `@deepseek-ai/dsh-client-product-analytics`

- 提供类型：`DesktopAnalytics`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-product-analytics` (`packages/client/product-analytics/src/client/index.ts:16`，class)
- 提供方：`@deepseek-ai/dsh-client-product-analytics` (`packages/client/product-analytics/src/client/index.ts:23`)、`@deepseek-ai/dsh-client-product-analytics` (`packages/client/product-analytics/src/index.ts:46`)
- 消费方：@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/input/submission-analytics.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/manager-store.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via ctx.get)

- void `void (async () => { for await (const frame of stream) { this.collecting = frame.value; frame.accept() } })().catch(() =>`
- track `track<K extends keyof ProductEventMap>(name: K, attributes: ProductEventMap[K], timestamp = Date.now()): void` — Send an event without retaining it for reconnect or later enablement.

### `productTelemetry` — `@deepseek-ai/dsh-host-product-telemetry-otel`

- 提供类型：`ProductTelemetry`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-host-product-telemetry-otel` (`packages/host/product-telemetry-otel/src/index.ts:84`)
- 消费方：@deepseek-ai/dsh-client-product-analytics(`packages/client/product-analytics/src/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `profileContext` — `@deepseek-ai/dsh-app-boot`

> Present only in a profile launched by dsh. */

- 提供类型：`ProfileContext`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-app-boot` (`packages/boot/app-boot/src/profile-context.ts:15`，interface)
- 消费方：@deepseek-ai/dsh-config-editor(`packages/boot/config-editor/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/index.ts` via inject)、@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-settings(`packages/settings/settings/src/index.ts` via inject)、@deepseek-ai/dsh-app-boot(`packages/boot/app-boot/src/compatibility-preflight.ts` via ctx.get)、@deepseek-ai/dsh-app-boot(`packages/boot/app-boot/src/compatibility-preflight.ts` via ctx.get)、@deepseek-ai/dsh-plugin-market(`packages/boot/plugin-market/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/permission-store.ts` via ctx.get)、@deepseek-ai/dsh-shell-env(`packages/shell/shell-env/src/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `ptcRuntime` — `@deepseek-ai/dsh-ptc-runtime`

- 提供类型：`PtcRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-ptc-runtime` (`packages/ptc-runtime/ptc-runtime/src/index.ts:105`，class)
- 提供方：`@deepseek-ai/dsh-ptc-runtime` (`packages/ptc-runtime/ptc-runtime/src/index.ts:150`)
- 消费方：@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-workflow-ptc(`packages/workflow/workflow-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/ptc.ts` via ctx.get)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/ptc.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/access.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/access.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/index.ts` via ctx.get)

- release `release(owner: object): Promise<void>` — Release an owner's retained environment and await its execution resources. Stateless providers have no retained resources to release.
- resolve `abstract resolve(request: PtcRunRequest): PtcRunSpec` — Resolve supported options and provider defaults before execution.
- run `abstract run(spec: PtcRunSpec): Promise<PtcRunResult>` — Execute resolved inputs; program outcomes resolve as result fields.

### `remote` — `@deepseek-ai/dsh-api-gateway`

> Generated Remote namespaces selected by the Client assembly. */

- 提供类型：`ClientRemote`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-gateway` (`packages/api/gateway/src/client/index.ts:103`，interface)
- 提供方：`@deepseek-ai/dsh-client-test-runtime` (`packages/test-support/client-runtime/src/remote.ts:43`)、`@deepseek-ai/dsh-api-gateway` (`packages/api/gateway/src/client/index.ts:155`)
- 消费方：@deepseek-ai/dsh-api-job-controller(`packages/api/job-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-remote-access(`packages/api/remote-access/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-remotes(`packages/api/remotes/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-controller(`packages/api/workspace-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-file-upload(`packages/client/file-upload/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-locale(`packages/client/locale/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-product-analytics(`packages/client/product-analytics/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-account-notifications(`packages/client/ui-account-notifications/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-approval(`packages/client/ui-approval/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-goal(`packages/client/ui-goal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-message-feedback(`packages/client/ui-message-feedback/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-market(`packages/client/ui-plugin-market/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-session(`packages/client/ui-session/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugin-inventory(`packages/client/ui-settings-plugin-inventory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-subagent(`packages/client/ui-settings-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-web-search(`packages/client/ui-settings-web-search/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings(`packages/client/ui-settings/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-files(`packages/client/ui-sidebar-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-theme(`packages/client/ui-theme/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-tool(`packages/client/ui-tool/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-action-cards(`packages/experimental/client-ui-action-cards/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-claude-code-mods(`packages/experimental/client-ui-claude-code-mods/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-recommendations(`packages/experimental/client-ui-plugin-recommendations/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-voice-input(`packages/experimental/client-ui-voice-input/src/client/mount.ts` via inject)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/client/mount.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-cordis(`packages/extensions/ui-cordis/src/client/index.ts` via inject)

- $stream `$stream<Item>(options: RemoteStreamOptions<Item>): RemoteStream<Item>` — Create an independently cancellable, reconnecting logical stream. Requires interactions=answer; passive Clients use generated stream methods.

### `remoteAccess` — `@deepseek-ai/dsh-api-remote-access`

> Client access answers for the calling Peer. */

- 提供类型：`ClientRemoteAccess`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-remote-access` (`packages/api/remote-access/src/client/mount.ts:30`，interface)
- 提供方：`@deepseek-ai/dsh-api-remote-access` (`packages/api/remote-access/src/client/mount.ts:92`)、`@deepseek-ai/dsh-api-remote-access` (`packages/api/remote-access/src/index.ts:135`)、`@deepseek-ai/dsh-client-test-runtime` (`packages/test-support/client-runtime/src/access.ts:49`)
- 消费方：@deepseek-ai/dsh-api-gateway(`packages/api/gateway/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-controller(`packages/api/workspace-controller/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-native(`packages/client/ui-directory-picker-native/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-session(`packages/client/ui-session/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-action-cards(`packages/experimental/action-cards/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-session(`packages/client/ui-session/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/navigation.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)

- source `source(kind: TypertResourceKind, id: string, action: string): HostObservable<boolean>` — Whether the current Peer may call `action` on one resource. True for the owner; false without a baseline and after a non-owner stream fails; otherwise whether the resource's grant lists the action. Only the package that owns a resource kind calls it, to build that kind's access Hook; other plugins read access through the access Hooks or `whenAccess`.
- whenAccess `whenAccess(action: RemoteEndpoint, callback: () => AccessEffect): () => void` — Keep `callback`'s effects installed while the current Peer may call `action` on the global resource: run it when the answer becomes true, dispose its effects in reverse order when it becomes false, and run it again on the next true. The callback runs synchronously when the answer is already true, as it always is for the owner. Effect forms and fiber ownership match `ctx.slots.inject`.
- whenResourceAccess `whenResourceAccess(kind: TypertResourceKind, id: string, action: RemoteEndpoint, callback: () => AccessEffect): () => void` — {@link whenAccess} for one resource of a declared kind. Only the package that owns a resource kind calls it, to build that kind's `whenAccess`, as it builds the kind's access Hook over {@link source}.

### `resources` — `@deepseek-ai/dsh-client-resources`

> Resource model: protocol providers, pins, and per-address live sources. */

- 提供类型：`Resources`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-resources` (`packages/client/resources/src/client/contract.ts:93`，interface)
- 提供方：`@deepseek-ai/dsh-client-resources` (`packages/client/resources/src/client/index.ts:34`)
- 消费方：@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)

- register `register<P extends ResourceProtocol>(provider: ResourceProvider<P>): () => void` — Register the provider for one protocol for the caller's lifetime.
- pin `pin(address: string, signal: AbortSignal): void` — Hold one resource open without subscribing to it.
- source `source(address: string): ObservableSnapshot<ResourceSnapshot<unknown>>` — The live source of one resource. Reference-stable for one address while the resource is held; the first subscriber or pin opens the provider's stream, and a subscriber arriving later reads the latest value at once.

### `sandbox` — `@deepseek-ai/dsh-sandbox`

- 提供类型：`SandboxProvider`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-sandbox` (`packages/sandbox/sandbox/src/index.ts:207`，class)
- 提供方：`@deepseek-ai/dsh-sandbox` (`packages/sandbox/sandbox/src/index.ts:210`)
- 消费方：@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-ptc-runtime-python(`packages/experimental/ptc-runtime-python/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-ptc-runtime-node(`packages/ptc-runtime/ptc-runtime-node/src/index.ts` via inject)、@deepseek-ai/dsh-bash-sandbox(`packages/shell/bash-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-pwsh-sandbox(`packages/shell/pwsh-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-terminal-bash(`packages/terminal/terminal-bash/src/index.ts` via ctx.get)

- confine `abstract confine(argv: readonly string[], policy: SandboxPolicy, signal?: AbortSignal): Promise<ConfinedArgv>` — Wrap `argv` so it executes confined under `policy` on this host; the caller spawns the returned argv in place of its own. arguments), NOT a shell string — a shell-shaped consumer passes `['bash', '-c', command]`. carried per call (see {@link SandboxPolicy}). the selected backend achieves for it.

### `sandboxPolicy` — `@deepseek-ai/dsh-sandbox-policy`

- 提供类型：`SandboxPolicyService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-sandbox-policy` (`packages/sandbox/sandbox-policy/src/index.ts:135`，class)
- 提供方：`@deepseek-ai/dsh-sandbox-policy` (`packages/sandbox/sandbox-policy/src/index.ts:158`)
- 消费方：@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/tools.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-ptc-runtime-python(`packages/experimental/ptc-runtime-python/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-panel(`packages/experimental/terminal-panel/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-fs-sandbox(`packages/fs/fs-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-ptc-runtime-node(`packages/ptc-runtime/ptc-runtime-node/src/index.ts` via inject)、@deepseek-ai/dsh-bash-sandbox(`packages/shell/bash-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-pwsh-sandbox(`packages/shell/pwsh-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-fs-ssh(`packages/ssh/fs-ssh/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-bash(`packages/terminal/terminal-bash/src/index.ts` via inject)、@deepseek-ai/dsh-workflow-ptc(`packages/workflow/workflow-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/ptc.ts` via ctx.get)、@deepseek-ai/dsh-action-cards(`packages/experimental/action-cards/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/sandbox.ts` via ctx.get)、@deepseek-ai/dsh-tool-str-replace-editor(`packages/fs/tool-str-replace-editor/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/child-agent.ts` via ctx.get)

- resolve `resolve(request: SandboxPolicyRequest = {}): SandboxExecutionPolicy` — Resolve the complete policy for one capability call. An approved explicit mode outranks the session's last `sandbox/mode` event, which outranks the deployment default. A session cwd is its workspace-write boundary; the configured root is the fallback for agentless calls and sessions without a cwd. Configured extra roots and this Session's active registrations are snapshotted together; existing operations and processes keep their policy. relative or contains a NUL byte.
- sessionWorkspaceRoot `private sessionWorkspaceRoot(session: Session \| undefined): string` — The session's recorded cwd, or the configured root, as the workspace-write boundary. */
- registerWritableRoot `registerWritableRoot(session: Session, directory: string): () => void` — Permit writes under one directory in this Session's future workspace-write operations. The calling context owns the effect; disposal removes only this registration. Other grants to the directory remain effective. Existing operations and persistent processes retain their resolved permissions. Grants are runtime-only and must be registered again after resume or fork. On Windows, only harness file tools honor extra grants; process permissions stay unchanged.
- resolveAdditionalWritableRoots `resolveAdditionalWritableRoots([directory])`
- overrideOf `overrideOf(session: Session): SandboxMode \| undefined` — Read the session override without applying the deployment default.

### `schedule` — `@deepseek-ai/dsh-schedule`

> Durable Host-wide reminder management. */

- 提供类型：`ScheduleService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-schedule` (`packages/schedule/schedule/src/index.ts:223`，class)
- 提供方：`@deepseek-ai/dsh-schedule` (`packages/schedule/schedule/src/index.ts:248`)

- async `async (task) =>`
- stop `stop()`
- activity `activity()`
- deliveryLimits `deliveryLimits():` — Read effective delivery limits without loading or activating a task.  *(decorators: @@Remote('deliveryLimits'))*
- remoteCreate `async remoteCreate(request: ScheduleCreateRequest, signal?: AbortSignal): Promise<ScheduleCatalogEntry>` — Create one task with a Host-generated identity for a human Remote caller.  *(decorators: @@Remote('create'))*
- throwRemoteScheduleInput `throwRemoteScheduleInput(error)`
- create `async create( request: ScheduleCreateRequest, actorSessionId?: SessionId, signal?: AbortSignal, ): Promise<ScheduleCatalogEntry>` — Create one task and record the acting Agent's Session as involved; the Remote form omits that Session. The record is built from the clock reading taken before the request joins the serialized queue. A `session` target must exist and must not belong to a delegated child; a `new_once` target reserves its Session identity.
- list `async list(request: ScheduleListRequest = {}): Promise<ScheduleListResult>` — Read one page of Host tasks without activating target Sessions.
- remoteList `async remoteList(request: ScheduleListRequest): Promise<ScheduleListResult>` — Remote form of the shared Host-wide list.  *(decorators: @@Remote('list'))*
- catalog `async catalog(): Promise<ScheduleCatalogEntry[]>` — Read every Host task without a page bound or Session activation.  *(decorators: @@Remote('catalog'))*
- view `async view(request: ScheduleViewRequest): Promise<ScheduleViewResult>` — Read one task without activating its target Sessions.  *(decorators: @@Remote('view'))*
- history `async history(request: ScheduleDeliveryHistoryRequest): Promise<ScheduleDeliveryHistoryResult>` — Read one page of saved deliveries without activating or reading a target Session.
- remoteHistory `async remoteHistory(request: ScheduleDeliveryHistoryRequest): Promise<ScheduleDeliveryHistoryResult>` — Remote form of the target-based {@link ScheduleService.history}; an invalid limit rejects with `schedule/input-invalid`.  *(decorators: @@Remote('history'))*
- run `async run(request: ScheduleRunRequest, signal?: AbortSignal): Promise<ScheduleRunResult>` — Deliver one task now without consuming or moving its scheduled occurrence; an archived destination Session rejects with `schedule/target-archived`. another execution of the task is queued, running, or inside its delivery floor, or a non-mutating miss.  *(decorators: @@Remote('run'))*
- deleteInactive `async deleteInactive(): Promise<ScheduleDeleteInactiveResult>` — Delete every ended Host task, leaving active tasks armed. Ended tasks never schedule another delivery, so the removal changes no pending target and no timer is recomputed. Rows are enumerated and removed in one FIFO slot, so a delivery ordered behind this call ends its task after the enumeration rather than during it. The batch is one domain write: a normal failure rejects with every listed row still stored, while a backend `unknown-state` failure may have removed rows and quarantines the Host domain, so later schedule operations reject until the domain is reopened. A successful nonempty batch emits `schedule/changed` without Agent notices. A rejected batch announces `schedule/changed` because it does not establish which rows landed, and clients then re-read the catalog.  *(decorators: @@Remote('deleteInactive'))*
- remoteEdit `async remoteEdit(request: ScheduleEditRequest, signal?: AbortSignal): Promise<ScheduleEditResult>` — Update or delete one task for a human Remote caller; an invalid patch rejects with `schedule/input-invalid`.  *(decorators: @@Remote('edit'))*
- edit `async edit( request: ScheduleEditRequest, actorSessionId?: SessionId, signal?: AbortSignal, ): Promise<ScheduleEditResult>` — Update or delete one task and record the acting Agent's Session as involved; the Remote form omits that Session. An update applies every patch field in one write and recomputes the next occurrence when the rule changes or the task resumes. A supplied `expectedUpdatedAt` that differs from the stored value returns `schedule_conflict`.
- emitChanged `private emitChanged(): void` — Dispatch one post-commit `schedule/changed` notification, containing synchronous listener failures: every call site emits only after its durable task write landed, so a throwing listener must not reject the caller or skip the following `requestDrive()`.
- getDomain `private async getDomain(): Promise<Domain<typeof scheduleDomain>>`
- resolveTarget `private async resolveTarget(request: ScheduleTargetRequest, signal?: AbortSignal): Promise<ScheduleTarget>` — Resolve a requested destination without activating a Session. A `session` target must exist and must not belong to a delegated child: a live Agent answers through {@link delegationDepthOf}, and a stored Session answers through the delegation depth in its saved header.
- validateTarget `private async validateTarget(target: ScheduleTarget, signal?: AbortSignal): Promise<void>` — Check arming prerequisites without activating a Session; repeated inside the mutation FIFO. */
- requireSessionCreation `private requireSessionCreation(): void` — New destinations require a provider before a task can be armed. */
- entries `private async entries(): Promise<ScheduleCatalogEntry[]>` — Every stored task as a catalog entry, in {@link compareEntries} order. */
- entry `private entry(task: ScheduleTask): ScheduleCatalogEntry`
- notify `private async notify(task: ScheduleTask, actorSessionId: SessionId \| undefined, change: ScheduleChangeKind): Promise<void>` — Tell each involved Session's live Agent about one committed change, except the acting Session. A stored Session stays inactive; it reads the current task state when it next lists its tasks.
- queueNotification `private queueNotification(task: ScheduleTask, actorSessionId: SessionId \| undefined, change: ScheduleChangeKind): void` — Queue one change notice behind earlier notices without adding Session I/O to the management operation. Callers queue inside the serialized operation, so teardown, which drains that queue first, cannot overtake it.
- stopSessionTasks `private async stopSessionTasks(sessionId: SessionId): Promise<void>` — Remove every active task that delivers to one Session, inside the queue the tools use. Enumerating and deleting in one queue slot is what makes an archive stop ordered behind a create whose write is still in flight: a stop that read the table outside the queue could miss a row the create was about to commit and leave an armed reminder behind. Re-entering the public `edit()` from here would deadlock on this queue, so the rows are removed directly.
- removeRows `private async removeRows(ids: readonly ScheduleRecord['id'][], label: string, rearm: boolean): Promise<number>` — Remove rows as one durable batch inside the current queue slot. The batch is one domain write: on success every present row is removed and announced. Any rejection announces `schedule/changed` because it does not establish which rows landed; a normal failure leaves every row stored, and an `unknown-state` failure may have removed some. A rejection reason that carries no Error is wrapped with the operation label.
- serialize `private serialize<T>(work: () => Promise<T>): Promise<T>`

### `sessionController` — `@deepseek-ai/dsh-api-session-controller`

> Host Session business API and Remote namespace owner. */

- 提供类型：`SessionController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/index.ts:135`，class)
- 提供方：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/index.ts:179`)
- 消费方：@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/index.ts` via inject)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via ctx.get)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/runtime.ts` via ctx.get)

- promote `private promote(observation: SessionObservation): void` — Request background activation through the existing Session Agent controller.
- resolveAgent `resolveAgent(sessionId: SessionId): Promise<ApiSessionAgentResult>` — Resolve or resume one ordinary Session for another Host API domain.
- list `async list(_request: SessionListRequest, signal: AbortSignal): Promise<SessionListValue>` — Read all visible Session rows without resuming an Agent.  *(decorators: @@Remote('list'))*
- search `async search(request: SessionSearchRequest, signal: AbortSignal): Promise<SessionSearchValue>` — Search visible Session content without resuming an Agent. A non-owner receives only the hits whose Session `allows()` admits; `hasMore` describes the bounded result before that filtering.  *(decorators: @@Remote('search'))*
- create `create(request: SessionCreateRequest): Promise<SessionCreateValue>` — Create one ordinary Session for a new conversation, reusing the named blank Session while it is reusable.  *(decorators: @@Remote('create'))*
- selectModel `selectModel(request: SessionSelectModelRequest): Promise<SessionSelectModelValue>` — Select one Session-local model after explicitly resuming the Session; save the default in the background.  *(decorators: @@Remote('selectModel'))*
- initializeDefaultModel `async initializeDefaultModel(): Promise<void>` — Select the first available account model after login when no provider API key is configured.  *(decorators: @@Remote)*
- modelCatalog `modelCatalog(): Promise<ModelCatalog>` — Describe every currently routable model for Host-generation selectors.  *(decorators: @@Remote('modelCatalog'))*
- canOpenWorkspacePath `canOpenWorkspacePath(): boolean` — Report whether this deployment can hand a Session workspace path to a native desktop.  *(decorators: @@Remote)*
- workspaceDesktop `workspaceDesktop():` — Describe the serving desktop for authenticated file-action routes.
- openWorkspacePath `async openWorkspacePath( request: SessionOpenWorkspacePathRequest, signal: AbortSignal, ): Promise<SessionOpenWorkspacePathValue>` — Verify one path through the composed filesystem and open it on the Host desktop.  *(decorators: @@Remote('openWorkspacePath'))*
- workspacePathApplications `async workspacePathApplications( request: { readonly path: string }, signal: AbortSignal, ): Promise<readonly SessionWorkspacePathApplication[]>` — Query current file handlers on the serving desktop without activating an Agent.  *(decorators: @@Remote('workspacePathApplications'))*
- verifyDesktopPath `private async verifyDesktopPath(path: string, signal: AbortSignal): Promise<string>`
- rename `rename(request: SessionRenameRequest): Promise<SessionRenameValue>` — Rename one Session after explicitly resuming it.  *(decorators: @@Remote('rename'))*
- fork `async fork(request: SessionForkRequest): Promise<SessionForkValue>` — Fork one cold-readable exact event prefix into a new Session. An omitted boundary selects the latest completed-turn prefix; an open cut receives synthetic fork closers.  *(decorators: @@Remote('fork'))*
- prompt `async prompt(request: SessionPromptRequest, signal: AbortSignal): Promise<SessionPromptValue>` — Admit one prompt after explicitly resuming its Session.  *(decorators: @@Remote('prompt'))*
- attachment `attachment(request: SessionAttachmentRequest): Promise<SessionAttachmentValue>` — Read one image from the attachment store after gateway authorization.  *(decorators: @@Remote('attachment'))*
- updateQueue `updateQueue(request: SessionUpdateQueueRequest): Promise<SessionUpdateQueueValue>` — Mutate one still-pending queue occurrence, resuming a cold Agent first.  *(decorators: @@Remote('updateQueue'))*
- cancel `cancel(request: SessionCancelRequest): SessionCancelValue` — Cancel one active Agent turn without dropping its pending inbox.  *(decorators: @@Remote('cancel'))*
- page `page(request: SessionPageRequest, signal: AbortSignal): Promise<SessionEventsPage>` — Read one cold-safe, message-aligned Session history page.  *(decorators: @@Remote('page'))*
- events `events(request: SessionPageRequest, signal: AbortSignal): Promise<SessionEventsPage>` — Read one cold-safe, message-aligned Session history page.  *(decorators: @@Remote)*
- observeEvent `observeEvent(request: SessionObserveEventRequest, signal: AbortSignal): AsyncIterable<SessionEventFrame>` — Subscribe to Session events without reading a snapshot.  *(decorators: @@Remote({ mode: 'stream' }))*
- observeProjections `observeProjections(request: SessionProjectionsRequest, signal: AbortSignal): AsyncIterable<SessionProjectionFrame>` — Subscribe to Session projection changes.  *(decorators: @@Remote({ mode: 'stream' }))*
- state `state(request: SessionStateRequest, signal: AbortSignal): Promise<SessionState>` — Read passive Session state.  *(decorators: @@Remote)*
- observeState `observeState(request: SessionStateRequest, signal: AbortSignal): AsyncIterable<SessionState>` — Subscribe to complete Session state replacements.  *(decorators: @@Remote({ mode: 'stream' }))*
- wait `wait(request: SessionWaitRequest, signal: AbortSignal): Promise<SessionWaitValue>` — Wait for Session quiescence or pending input with bounded assistant output.  *(decorators: @@Remote)*
- follow `follow(request: SessionFollowRequest, signal: AbortSignal): AsyncIterable<SessionFollowFrame>` — Follow one Session log from its opening or resume cursor. frames and optional cursorless assistant-stream frames.  *(decorators: @@Remote({ mode: 'stream' }))*
- projections `projections(request: SessionProjectionsRequest, signal: AbortSignal): Promise<SessionProjectionsValue>` — Read exact projections, returning cached hints only when migration is required.  *(decorators: @@Remote('projections'))*
- assertNever `assertNever(frame)`

### `sessionFeedback` — `@deepseek-ai/dsh-command-feedback`

- 提供类型：`SessionFeedbackService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-command-feedback` (`packages/feedback/command-feedback/src/index.ts:85`，class)
- 提供方：`@deepseek-ai/dsh-command-feedback` (`packages/feedback/command-feedback/src/index.ts:92`)

- record `record(request: SessionFeedbackRecordRequest): Promise<SessionFeedbackRecordResult>` — Record one remark on a live Session. Session carries the id.  *(decorators: @@Remote('record'))*
- recordFeedback `recordFeedback(session, request)`

### `sessionFileReferences` — `@deepseek-ai/dsh-api-session-controller`

> Host owner of the `fileReferences` Remote namespace. */

- 提供类型：`SessionFileReferences`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/file-references.ts:17`，class)
- 提供方：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/file-references.ts:22`)

- list `list( agent: Agent, query: string, signal: AbortSignal, ): Promise<FileReferenceCandidate[]>` — List file and directory candidates for one Agent's working directory.  *(decorators: @@Remote)*

### `sessionLogDeepSeek` — `@deepseek-ai/dsh-session-log-deepseek`

- 提供类型：`SessionLogDeepSeekService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-log-deepseek` (`packages/session/session-log-deepseek/src/index.ts:188`，class)
- 提供方：`@deepseek-ai/dsh-session-log-deepseek` (`packages/session/session-log-deepseek/src/index.ts:194`)

- registerExclusion `registerExclusion(exclude: SessionLogUploadExclusion): () => Promise<void>` — Exclude matching requests before reading or preparing their log contribution. Any matching rule suppresses both the field and its acceptance callback. With no matching rules, normal upload eligibility applies. A throwing rule fails this contribution; the request-extension registry omits it and reports the error.

### `sessionLogDownload` — `@deepseek-ai/dsh-session-log-export`

- 提供类型：`SessionLogDownloadController`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-session-log-export` (`packages/session-query/session-log-export/src/client/controller.ts:57`，class)
- 提供方：`@deepseek-ai/dsh-session-log-export` (`packages/session-query/session-log-export/src/client/index.ts:43`)

- download `download(sessionId: SessionId): Promise<void>` — Download one Session tree; concurrent gestures for the same Session share one operation. Different Sessions run concurrently; each new operation joins the modal FIFO.
- dismiss `dismiss(sessionId: SessionId): void` — Close one Session's dialog without cancelling an in-flight browser download.
- dispose `async dispose(): Promise<void>` — Abort active fetches and reach quiescence.
- run `private async run(sessionId: SessionId, signal: AbortSignal, order: number): Promise<void>`
- publish `private publish(sessionId: SessionId, entry: SessionLogDownloadEntry): void`

### `sessionPersistence` — `@deepseek-ai/dsh-session-persistence`

- 提供类型：`SessionPersistence`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-persistence` (`packages/session/session-persistence/src/index.ts:144`，class)
- 提供方：`@deepseek-ai/dsh-session-persistence` (`packages/session/session-persistence/src/index.ts:149`)
- 消费方：@deepseek-ai/dsh-acp(`packages/acp/acp/src/index.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via inject)、@deepseek-ai/dsh-message-feedback(`packages/feedback/message-feedback/src/index.ts` via inject)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via inject)、@deepseek-ai/dsh-session-checkpoint-policy(`packages/session/session-checkpoint-policy/src/index.ts` via inject)、@deepseek-ai/dsh-agent-team(`packages/team/agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/history/controller.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via ctx.get)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via ctx.get)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/storage.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/storage.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/index.ts` via ctx.get)、@deepseek-ai/dsh-session-query(`packages/session-query/session-query/src/observation.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/manager.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/manager.ts` via ctx.get)

- create `abstract create(header: SessionHeader, options?: SessionPersistenceCreateOptions): Promise<SessionHandle>` — Create a new stored session and take its write ownership.
- open `abstract open(id: SessionId, access: SessionAccess, options?: SessionPersistenceOpenOptions): Promise<SessionHandle>` — Open an existing stored session. `read` never takes ownership and works while another handle (or process) holds write ownership. `write` atomically claims single-writer ownership; an existing active owner rejects.
- flush `abstract flush(): Promise<void>` — Flush every active write handle owned by this service instance in one durability barrier: each handle's routed live events drain durably and its session materializes, exactly as that handle's own `SessionHandle.flush` would. Read handles buffer nothing and are untouched. A handle closed concurrently counts as flushed — close itself drains durably. remaining handles still flush.
- stat `abstract stat(id: SessionId, options?: SessionPersistenceStatOptions): Promise<SessionPersistenceSnapshot \| undefined>` — Observe one stored session without reading its event log or taking ownership. The snapshot's `revision` is an opaque change token comparable only against revisions from the same service instance and session id: equal revisions may be treated as an unchanged log; unequal revisions promise nothing. Write-ownership churn does not change a revision. It exists for derived read-model caches keyed off `stat`/`list`; it plays no part in open, read, or resume.
- list `abstract list(options?: SessionPersistenceListOptions): Promise<readonly SessionPersistenceSnapshot[]>` — List every stored session visible to this process, in no promised order.

### `sessionProjectionCache` — `@deepseek-ai/dsh-session-projection-cache`

- 提供类型：`SessionProjectionCache`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-projection-cache` (`packages/session/session-projection-cache/src/index.ts:105`，class)
- 提供方：`@deepseek-ai/dsh-session-projection-cache` (`packages/session/session-projection-cache/src/index.ts:114`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/history/controller.ts` via ctx.get)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/list.ts` via ctx.get)、@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via ctx.get)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-session-query(`packages/session-query/session-query/src/observation.ts` via ctx.get)

- recordFor `private recordFor(id: SessionId, expected: CurrentCheckpointIdentity): CheckpointRecord \| undefined` — The stored record for one session, accepted only when its bound log identity matches `expected`. A session id names a slot, not a lifecycle: a recreated id or a persistence store swapped under a surviving cache must not let an old record seed state folded from an unrelated log. Synchronous from the domain's in-memory state — the same state every write mutated, so a read can never go around the write chain to the medium.
- cachedSnapshot `cachedSnapshot( meta: SessionHeader, keys?: ProjectionKeySelection, ): ProjectionSnapshot \| undefined` — The zero-I/O listing read: whole values viewed straight from the stored rows (version-matching keys only) of the record bound to the caller's lifecycle. The header is the only identity witness a listing holds, so this face matches the lifecycle identity (`formatVersion`, `createdAt`, `cwd`, `isSeeded`) and not the inherited cut: within one format generation the cut is fixed at fork time, so it distinguishes no lifecycle the other fields do not, and a viewed value never seeds a fold. The view is as stale as the last durable checkpoint but never wrong and never from an unrelated log. Its `asOfSeq` is the lowest watermark among the served rows: the stored record's own position, which the header cannot relate to the log the caller later opens. The Session list therefore labels the block as cached, and the client lets every value the connected Session produces supersede it whatever this number says. this lifecycle at the current Session format.
- cachedPredecessorTitle `cachedPredecessorTitle(meta: SessionHeader): ProjectionSnapshot \| undefined` — Read only a predecessor checkpoint's title as a zero-I/O listing hint. The authoritative Session header supplies the lifecycle identity. A cache checkpoint can lag that log but cannot lead it because writes flush the log first, so a matching predecessor title is a genuine (possibly stale) fact from this Session. The registry still requires the current title projection's row version and schema. No other predecessor projection is exposed: format normalization can change their current meaning, and the {@link cachedSnapshot} / hydration paths continue to reject them. `undefined` when the record is current, newer, unrelated, missing, or incompatible with the title unit.
- viewRecord `private viewRecord( record: CheckpointRecord, keys?: ProjectionKeySelection, ): ProjectionSnapshot \| undefined` — View selected wire rows as one block bound to the lowest served watermark: the seq every served value has folded through at least. The number is the record's own; whether a consumer may compare it with a live Session's seqs is decided by the face that serves the block, not here.
- hydratePrepared `hydratePrepared( session: Session, events: readonly SessionEvent[], ): ProjectionSnapshot` — Hydrate projection cells for an already-prepared Session without another persistence read. The cache seeds matching rows; the supplied exact log advances every unit to the observation cut. No checkpoint is written because the logical observation may contain recovery events not yet durable.
- identityOf `identityOf(session.header, session.inheritedEventCount),`
- SessionLogOffset `SessionLogOffset(0),`
- write `async write(session: Session): Promise<void>` — Durably checkpoint one live session NOW (all mandatory points call this; tests and carriers may too). The registry cut is snapshotted at this boundary (states are live references), then the session's record is replaced on the domain's write chain. NOT fail-soft — callers on the fail-soft paths contain it.
- coldSnapshot `coldSnapshot( meta: SessionHeader, inheritedEventCount: SessionLogOffset, events: readonly SessionEvent[], ): ProjectionSnapshot` — Cold-read one session's projections from its complete log. Each unit is seeded from the identity-checked cached rows — the registry skips `apply` for the already-folded prefix (events at or below the row's `seq`) — and the refreshed checkpoint is written back (fail-soft, fire-and-forget), so the first cold read creates the cache row and later ones seed from it. The caller supplies the complete log in seq order: this service never consults the persistence layer.
- installWritePath `private installWritePath(): void`
- flushSoft `private async flushSoft(session: Session, trigger: string): Promise<void>` — One fail-soft durable checkpoint. Every caller has work by construction: the throttle triggers only fire dirty (markClean clears the timer with the counter) and the mandatory points write unconditionally.
- markClean `private markClean(session: Session): void` — Reset one session's dirty bookkeeping (its checkpoint is being written). */
- clearTimeout `clearTimeout(state.timer)`
- put `private async put(id: SessionId, identity: CheckpointIdentity, rows: ProjectionCheckpoint): Promise<void>` — Replace one session's stored record with its log identity and a detached snapshot of `rows`. */
- requireTable `private requireTable(): KvTable<SessionId, CheckpointRecord>`

### `sessionProjections` — `@deepseek-ai/dsh-session-projection`

- 提供类型：`SessionProjectionRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-projection` (`packages/session/session-projection/src/index.ts:282`，class)
- 提供方：`@deepseek-ai/dsh-session-projection` (`packages/session/session-projection/src/index.ts:296`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-harness-dev-context(`packages/context/harness-dev-context/src/index.ts` via inject)、@deepseek-ai/dsh-time-context(`packages/context/time-context/src/index.ts` via inject)、@deepseek-ai/dsh-tmux-context(`packages/context/tmux-context/src/index.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-agent(`packages/core/agent/src/index.ts` via inject)、@deepseek-ai/dsh-action-cards(`packages/experimental/action-cards/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-forge-session(`packages/experimental/forge-session/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-goal(`packages/goal/goal/src/index.ts` via inject)、@deepseek-ai/dsh-permission-presets(`packages/interaction/permission-presets/src/index.ts` via inject)、@deepseek-ai/dsh-user-approval(`packages/interaction/user-approval/src/index.ts` via inject)、@deepseek-ai/dsh-llm-retry(`packages/llm/llm-retry/src/index.ts` via inject)、@deepseek-ai/dsh-token-meter(`packages/llm/token-meter/src/index.ts` via inject)、@deepseek-ai/dsh-plan-mode(`packages/plan/plan-mode/src/index.ts` via inject)、@deepseek-ai/dsh-agent-preset-registry(`packages/preset/agent-preset-registry/src/index.ts` via inject)、@deepseek-ai/dsh-sandbox-policy(`packages/sandbox/sandbox-policy/src/index.ts` via inject)、@deepseek-ai/dsh-session-projection-cache(`packages/session/session-projection-cache/src/index.ts` via inject)、@deepseek-ai/dsh-session-stats(`packages/session/session-stats/src/index.ts` via inject)、@deepseek-ai/dsh-session-title(`packages/session/session-title/src/index.ts` via inject)、@deepseek-ai/dsh-session-turn-outline(`packages/session/session-turn-outline/src/index.ts` via inject)、@deepseek-ai/dsh-working-directory(`packages/session/working-directory/src/index.ts` via inject)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/model-selection-settings.ts` via inject)、@deepseek-ai/dsh-agent-team(`packages/team/agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-tool-todo(`packages/todo/tool-todo/src/index.ts` via inject)、@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via ctx.get)、@deepseek-ai/dsh-user-questions(`packages/interaction/user-questions/src/index.ts` via ctx.get)、@deepseek-ai/dsh-session-query(`packages/session-query/session-query/src/observation.ts` via ctx.get)、@deepseek-ai/dsh-session-query(`packages/session-query/session-query/src/observation.ts` via ctx.get)

- register `register<K extends keyof SessionProjectionMap, S>( definition: Omit<ProjectionDefinition<K, S>, 'wire'> & { wire: NonNullable<ProjectionDefinition<K, S>['wire']> }, ): Promise<Proj…` — Register one domain's unit on the calling context's fiber. Fiber or handle disposal releases one reference; the final release removes live participation. Retained handles remain readable after release. Callers must await registration before publishing consumers; registration may perform asynchronous work.
- register `register<K extends string, S>( definition: ProjectionDefinition<K, S> & { key: Exclude<K, keyof SessionProjectionMap> }, ): Promise<ProjectionHandle<S>>` — Register one host-only unit. Its state is omitted from client snapshots and always checkpointed like every other unit. Callers must await registration before publishing consumers; registration may perform asynchronous work.
- register `register<K extends string, S>( definition: ProjectionDefinition<K, S>, ): Promise<ProjectionHandle<S>>` — Legacy runtime behavior: [plugin compatibility](../README.md#deprecated-plugin-compatibility). */
- setImmediate `setImmediate(() => { if (observed) return if (owner.fiber.state !== FiberState.LOADING && owner.fiber.state !== FiberState.ACTIVE) return owner.logger.error(error) })`
- then `then(onFulfilled, onRejected)`
- finally `finally(onFinally)`
- acquire `private async acquire<K extends string, S>( definition: ProjectionDefinition<K, S>, onEffect: (release: () => Promise<void>) => void, ): Promise<ProjectionHandle<S>>` — Install one unit; `onEffect` receives its release before the asynchronous handoff. */
- view `view(state: S): unknown`
- onEffect `onEffect(dispose)`
- dispose `async dispose()`
- stateOf `stateOf(session: Session, key: string): unknown` — Read a currently registered unit after materializing every registered unit at the Session cursor. Unrelated wire views are not produced. The returned state is live; do not mutate it. A released key has no value. The first read of each key logs one deprecation warning per registry.
- onChanged `onChanged(listener: ProjectionChangeListener): () => void` — Subscribe to the change feed. The registration is an effect on the calling context's fiber.
- onEventChanged `onEventChanged(listener: ProjectionEventChangeListener): () => void` — Subscribe to the event-level change feed. The registration is an effect on the calling context's fiber. The listener runs synchronously inside the committed event's `session/event` handling, once after every unit has been driven and after every {@link onChanged} call for that event. If a unit or an {@link onChanged} listener throws during that drive, the listener still receives the changes made before the throw.
- snapshot `snapshot( session: Session, keys?: ProjectionKeySelection, ): ProjectionSnapshot` — One consistent cut over every registered client-visible unit for one session, read from the watermark cache (missing cells fold lazily over the in-memory log). Only the returned units are computed: other units, including Host-only units without `wire`, are neither folded nor advanced by this read. Fully synchronous — every value and `asOfSeq` reflect the same log position. Each value passes its unit's `viewSchema` before leaving.
- cachedSnapshot `cachedSnapshot( session: Session, keys?: ProjectionKeySelection, ): ProjectionSnapshot \| undefined` — Read only already-materialized client-visible cells without folding history. Values may trail the live Session and are therefore hints, not a complete baseline. Missing cells are omitted. Use snapshot(session, keys) for complete values, or a retained handle for host state.
- summaryKeys `summaryKeys(): ReadonlySet<Extract<keyof SessionProjectionMap, string>>` — The keys a Session summary carries: every registered client-visible key whose unit does not declare `summary: false`. The returned set is stable — the same instance on every call — until a registration or its disposal changes the key table, so a consumer may hold it across rows. Callers pass it to a key-taking read face such as `snapshot(session, summaryKeys())` or `viewCheckpoint(rows, summaryKeys())`; those faces use the set as-is.
- deriveSummaryKeys `private deriveSummaryKeys(): ReadonlySet<Extract<keyof SessionProjectionMap, string>>` — Rebuild the summary key set from the current registrations. */
- checkpoint `checkpoint(session: Session): ProjectionCheckpoint` — State-level checkpoint of every persisted unit for one session, read from the watermark cache (missing cells fold lazily over the in-memory log). This is the write side of the persisted projection cache: the returned rows are the `(key → {ver, seq, val})` part of the durable `(sessionId, key, ver, seq, val)` rows. Every `val` is a DETACHED structured clone — never the live cell reference: the watermark cache is this registry's authoritative mutable state, and a caller reaching the live reference could corrupt every subsequent snapshot and frame through it (plain JSON by the unit contract, so the clone is total). A released unit contributes the Session's last cell. The registry no longer advances that cell, while a retained handle read still advances it forward, so a writer running after a plugin unloads keeps that unit's latest state; a Session that has no cell of it gets no row. {@link restore} folds only live units, so its refreshed rows omit released units.
- restoreFloor `restoreFloor(checkpoint: ProjectionCheckpoint): SessionLogOffset \| undefined` — The stored seq a {@link restore} tail read over `checkpoint` must start at: one event BELOW the lowest usable watermark (a row is usable when its `ver` matches the live unit's `stateVersion`; an absent or mismatched row pulls the floor to `0` — that key must refold the full log). The one-below anchor is load-bearing: the tail then proves how far the stored log still extends, so {@link restore} can detect a log that shrank below a row's watermark (crash-repair truncation) instead of serving the stale row as current — an empty tail read from the anchor yields an end below every watermark and the restore rejects for a full re-read. or `undefined` when no live unit is registered (released predecessors do not count; no read needed — {@link restore} would serve empty values regardless).
- viewCheckpoint `viewCheckpoint( checkpoint: ProjectionCheckpoint, keys?: ProjectionKeySelection, ): Partial<SessionProjectionMap>` — View a checkpoint's rows without any log read: for every registered client-visible unit whose row's `ver` matches, serve the schema-validated `view` of the schema-validated stored state; mismatched, malformed, or absent rows leave their key absent (a cold or listing consumer treats it as not-yet-available and a fuller read path refolds it). The zero-I/O rung of the read ladder — values are as stale as their rows, never wrong.
- restore `restore( checkpoint: ProjectionCheckpoint, events: readonly SessionEvent[], baseSeq: SessionLogOffset, header: SessionHeader, inheritedEventCount: SessionLogOffset, ):` — Cold read: fold every persisted unit over a stored log suffix, seeding each from its checkpoint row when usable — the one read recipe (cached state + forward tail replay + `view`) applied without a live `Session`. Call with the stored events at or past `restoreFloor(checkpoint)` (a `SessionHandle.read` slice) and that same floor as `baseSeq`; the floor's one-below anchor makes the supplied end honest, so a shrunk log is detected here. A row is usable iff its `ver` matches the live unit's `stateVersion`, it does not predate `baseSeq` (`seq >= baseSeq - 1`), and it does not claim events past the supplied end (`seq <= endSeq`); an unusable row is discarded and its key refolds from `init` — which is only sound over the full log, so a discarded row with `baseSeq > 0` throws (the caller re-reads from seq 0, e.g. after a crash-repair truncation shrank the log below a row's watermark). supplied event's seq, `baseSeq - 1` for an empty tail) plus the refreshed checkpoint rows at that cut, ready for a durable write-back. The rows cover live units only: a released unit has no cell for a log folded without a live `Session`, so a write-back of them omits it.
- hydrate `hydrate( session: Session, checkpoint: ProjectionCheckpoint, events: readonly SessionEvent[], baseSeq: SessionLogOffset, ): ProjectionSnapshot` — Restore an exact cut and install its states on the supplied prepared Session. A later publication reuses these cells; ordinary live reads and event drive advance any constructor-owned suffix exactly once.
- materializeCells `private materializeCells(session: Session): void` — Materialize every registered unit cell at the Session's current cursor. */
- buildCell `private buildCell( def: ErasedDefinition, header: SessionHeader, inheritedEventCount: SessionLogOffset, events: readonly SessionEvent[], ): UnitCell` — Fold one unit from init over `events`, producing a cell watermarked at the last folded event. */
- cellFor `private cellFor(registration: Registration, session: Session): UnitCell` — Read (or lazily build, folding the full in-memory log) one unit's cell. */
- advanceCell `private advanceCell( def: ErasedDefinition, cell: UnitCell, session: Session, throughSeq: SessionSeqCursor, ): void` — Advance one existing cell through a contiguous Session prefix. */
- drive `private drive(session: Session, event: SessionEvent): void` — Eager drive: pass one committed event through every unit; notify per-key listeners on each changed raw view reference, then event listeners once. When a unit or a per-key listener throws, event listeners still receive the changes collected before the throw, and the error then propagates.
- listener `listener(session, key, value, event.seq)`
- listener `listener(session, changes, event.seq)`
- viewCell `private viewCell(registration: Registration, cell: UnitCell): unknown` — Return one schema-validated wire value. */

### `sessionQuery` — `@deepseek-ai/dsh-session-query`

- 提供类型：`SessionQueryEngine`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-query` (`packages/session-query/session-query/src/index.ts:98`，class)
- 提供方：`@deepseek-ai/dsh-session-query` (`packages/session-query/session-query/src/index.ts:106`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via inject)、@deepseek-ai/dsh-tool-session-query(`packages/experimental/tool-session-query/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/list.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/fork-enforcement.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/index.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/list-children.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/manager.ts` via ctx.get)

- observeSession `observeSession( sessionId: SessionId, options: SessionObservationOptions = {}, ): Promise<SessionObservation>` — Observe one exact live or prepared Session without a persistence listing preflight.
- inspectSession `inspectSession<T>(sessionId: SessionId, read: (session: Session) => T, signal?: AbortSignal): Promise<T>` — Inspect domain-owned state without attaching or resuming a cold Session. The getter runs synchronously after preparation and must not mutate or retain the Session.
- searchSessions `abstract searchSessions( request: SessionSearchRequest, exec?: SessionSearchExecContext, ): Promise<SessionSearchPage<SessionSearchHit>>` — Search the live-preferred logical corpus and group by session.
- searchEvents `abstract searchEvents( request: SessionEventSearchRequest, exec?: SessionSearchExecContext, ): Promise<SessionEventSearchPage>` — Search events within one live-preferred logical session.
- listSessions `listSessions(signal?: AbortSignal): Promise<SessionRecord[]>` — List the complete logical corpus using live-preferred records.
- readSession `async readSession(sessionId: SessionId): Promise<SessionLogSnapshot>` — Read and replay-validate one complete logical session log without making it live.
- filterSessions `async filterSessions( filters: readonly SessionResultFilter[], signal?: AbortSignal, ): Promise<SessionRecord[]>` — Filter the complete logical corpus with provider-independent predicates.
- readTitle `async readTitle( sessionId: SessionId, signal?: AbortSignal, ): Promise<SessionTitleSnapshot \| undefined>` — Fold the latest log-backed title from one live-preferred logical session.
- readTitleSnapshot `async readTitleSnapshot( sessionId: SessionId, signal?: AbortSignal, ): Promise<SessionTitleObservation>` — Fold the latest title and return its source header from one corpus observation.
- readTitleSnapshots `async readTitleSnapshots( sessionIds: readonly SessionId[], signal?: AbortSignal, ): Promise<SessionTitleObservationResult[]>` — Fold titles for unique sessions from one cancellable corpus observation. Results preserve first-occurrence input order. Operational failures stay isolated per session, while cancellation rejects the complete operation.
- listEvents `async listEvents(sessionId: SessionId): Promise<SessionEventRecord[]>` — List lightweight raw-log event records for one logical session.
- filterEvents `async filterEvents( sessionId: SessionId, filters: readonly SessionEventResultFilter[], ): Promise<SessionEventSearchDocument[]>` — Scan first-party semantic event documents with provider-independent filters.
- _filterSessions `private async _filterSessions( filters: readonly SessionResultFilter[], signal?: AbortSignal, ): Promise<SessionRecord[]>`
- _filterEvents `private async _filterEvents( sessionId: SessionId, filters: readonly SessionEventResultFilter[], ): Promise<SessionEventSearchDocument[]>`
- readSurface `async readSurface(sessionId: SessionId): Promise<SessionSurfaceSnapshot>` — Read one session's complete current model surface from one corpus observation.
- traceSession `async traceSession(sessionId: SessionId, signal?: AbortSignal): Promise<SessionLineageTrace>` — Trace known ancestry and descendants from one corpus observation.
- traceEvent `async traceEvent(request: SessionEventTraceRequest, signal?: AbortSignal): Promise<SessionEventTraceObservation>` — Trace one event's direct positional replacements and cited source events.
- readEvent `async readEvent(request: SessionEventReadRequest, signal?: AbortSignal): Promise<SessionEventWindow>` — Read one full event plus a bounded raw-log context window.
- _readEvent `private async _readEvent( sessionId: SessionId, seq: SessionSeqType, before: number, after: number, signal?: AbortSignal, ): Promise<SessionEventWindow>`
- _readWindow `private _readWindow(name: 'before' \| 'after', value: number \| undefined): number`

### `sessionReferenceResolver` — `@deepseek-ai/dsh-session-reference`

- 提供类型：`SessionReferenceResolver`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-reference` (`packages/context/session-reference/src/index.ts:88`，class)
- 提供方：`@deepseek-ai/dsh-session-reference` (`packages/context/session-reference/src/index.ts:100`)

- prepareDirectMessages `private async prepareDirectMessages( agent: Agent, messages: readonly UserMessage[], route: Readonly<Pick<LlmCallConfig, 'provider' \| 'model'>>, signal: AbortSignal, ): Promise<Use…` — Replace canonical mentions in direct user messages and place each prepared snapshot immediately after the message that cited it.
- listCandidates `async listCandidates( agent: Agent, query: string = '', limit: number = this.config.candidateLimit, signal?: AbortSignal, ): Promise<SessionReferenceCandidate[]>` — List reference candidates, ranked by working-directory affinity. Discovery runs at keystroke rate, so titles and subagent labels only ever come from projection reads; sessions without either fall back to their id.
- assertNotCancelled `assertNotCancelled(signal)`
- projectedLabels `private projectedLabels<T extends { readonly record: SessionRecord }>( items: readonly T[], ): Array<T &` — The mention label and display title each listed Session's projections can answer without reading its log. Attachment is decided by the store at read time, not by the listing: a session that attached in between would otherwise be answered from a checkpoint its live log has already moved past. An attached session answers from its live registry cut, which advances with every committed event, so a rename or a just-generated title is visible immediately; its events are already in memory, so the lazy fold costs no I/O. A cold session answers from the durable checkpoint the projection cache wrote when it went cold. Nothing else is attempted. Folding a title from a log costs the whole log, and this call sits under every keystroke of `@` completion. A session that no projection can answer for — one persisted before the cache was composed — is labeled by its id and cannot be found by its title until it is opened once, which checkpoints it. Services are resolved once per call and the cache's snapshot method is bound once: a service lookup per listed session would dominate the call.
- remoteExportCandidates `async remoteExportCandidates( agent: Agent, query: string, signal: AbortSignal, ): Promise<SessionReferenceMentionCandidate[]>` — Remote face of {@link listCandidates}: the configured candidate limit applies, and every candidate carries the canonical mention a host inserts into the prompt draft.  *(decorators: @@Remote('candidates'))*
- prepare `async prepare( agent: Agent, content: ContentBlock[], references: SessionReferenceInput[], route: Readonly<Pick<LlmCallConfig, 'provider' \| 'model'>>, signal?: AbortSignal, ): Prom…` — Snapshot all references for one accepted direct message and return one aggregated durable context. Automatic budgets use the context capacity of `route`. Missing model capacity or adapter uses 64 KiB; other metadata lookup failures and cancellation reject preparation. Truncated previews include omission facts and a full-snapshot spill locator, or an explicit unavailable notice. Cancellation prevents context publication, including when storage completes after cancellation.
- prepareReferenceOmission `prepareReferenceOmission(this.ctx.get('spillStore'), agent.session.id, source, index),`
- referenceBudget `private async referenceBudget(route: Readonly<Pick<LlmCallConfig, 'provider' \| 'model'>>, signal: AbortSignal \| undefined): Promise<number>`
- renderSources `private renderSources(sources: readonly PreparedSource[], maxReferenceBytes: number): RenderedSource[]`

### `sessionSkillCatalog` — `@deepseek-ai/dsh-api-session-controller`

> Host owner of the Session-addressed `skills` Remote namespace. */

- 提供类型：`SessionSkillCatalog`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/skill-catalog.ts:20`，class)
- 提供方：`@deepseek-ai/dsh-api-session-controller` (`packages/api/session-controller/src/skill-catalog.ts:25`)

- list `async list(request: SkillListRequest, signal: AbortSignal): Promise<SkillListValue>` — List the user-invocable skills visible to one Session composition.  *(decorators: @@Remote)*
- scopeFor `private async scopeFor( agentPreset: string \| undefined, ): Promise<(` — Resolve a live or standing preset scope without creating an Agent. */

### `sessionTelemetry` — `@deepseek-ai/dsh-session-telemetry`

- 提供类型：`SessionTelemetryBackend`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-telemetry` (`packages/session/session-telemetry/src/index.ts:148`，class)
- 提供方：`@deepseek-ai/dsh-session-telemetry` (`packages/session/session-telemetry/src/index.ts:150`)

- emit `abstract emit(record: SessionTelemetryRecord): void` — See {@link SessionTelemetrySink.emit} — that declaration is the contract's one home.
- shutdown `abstract shutdown(): Promise<void>` — See {@link SessionTelemetrySink.shutdown}.

### `sessionTitle` — `@deepseek-ai/dsh-session-title`

- 提供类型：`SessionTitleService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-session-title` (`packages/session/session-title/src/index.ts:301`，class)
- 提供方：`@deepseek-ai/dsh-session-title` (`packages/session/session-title/src/index.ts:318`)
- 消费方：@deepseek-ai/dsh-session-title-all-prompts-llm(`packages/experimental/session-title-all-prompts-llm/src/index.ts` via inject)、@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-session-title-first-prompt-llm(`packages/session/session-title-first-prompt-llm/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/commands.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/tunnel-supervision.ts` via ctx.get)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/runtime.ts` via ctx.get)

- assertPositiveInteger `assertPositiveInteger('fallbackMaxWords', value.fallbackMaxWords)`
- assertPositiveInteger `assertPositiveInteger('fallbackMaxBytes', value.fallbackMaxBytes)`
- assertPositiveInteger `assertPositiveInteger('maxTitleBytes', value.maxTitleBytes)`
- get `get(session: Session): SessionTitleSnapshot \| undefined` — Read the latest folded title from one live or replayed session.
- rename `rename(session: Session, title: string): SessionTitleSnapshot` — Accept an explicit user title. Appends a `session/title` event with the `user` source, which pins the title: in-flight automatic generation is superseded and later user messages schedule none (an explicit {@link SessionTitleService.refresh} remains the deliberate unpin).
- refresh `async refresh(session: Session, signal?: AbortSignal): Promise<SessionTitleSnapshot \| undefined>` — Explicitly retry the registered provider, or materialize the built-in fallback when no provider is registered.
- register `register(provider: SessionTitleProvider): () => Promise<void>` — Register the sole optional title provider. Disposal aborts its pending and active work; a replacement may register once disposal has started, and the closing provider's late results never commit.
- onUserMessage `private async onUserMessage(session: Session, event: Extract<SessionEvent, { type: 'user/message' }>): Promise<void>` — Schedule current-provider work; activation-time messages only request the fallback. */
- onRequestHeader `private onRequestHeader(session: Session, event: Extract<SessionEvent, { type: 'request/header' }>): void` — Start pending automatic work only after its exact main-request route is logged. */
- onMainRequest `private onMainRequest(options: GenerateOptions): void` — Start unchanged-route work from the marked loop request after its header fold is current. */
- startPending `private startPending( session: Session, state: SessionTitleWorkState, pending: PendingAutomaticWork, route: SessionTitleModelIdentity, ): void` — Consume one pending revision and schedule its non-blocking provider call. */
- startProvider `private startProvider( session: Session, work: ActiveProviderWork, route?: SessionTitleModelIdentity, ): Promise<SessionTitleSnapshot \| undefined>` — Start one tracked provider call after publishing its active revision. */
- runProvider `private async runProvider( session: Session, work: ActiveProviderWork, route?: SessionTitleModelIdentity, ): Promise<SessionTitleSnapshot \| undefined>` — Execute and accept one current provider revision. */
- validateResult `private validateResult( result: unknown, messages: readonly SessionTitleUserMessage[], ): SessionTitleProviderResult` — Validate and normalize provider output against the supplied message snapshot. */
- assertCurrent `private assertCurrent(session: Session, work: ActiveProviderWork): void` — Fail a completion whose provider, revision, session, or signal is stale. */
- activate `private activate( pending: PendingAutomaticWork, state: SessionTitleWorkState, upstream?: AbortSignal, ): ActiveProviderWork` — Create and publish an active provider call from one fixed revision. */
- supersede `private supersede(state: SessionTitleWorkState, reason: string): number` — Abort older active work and reserve the next session-local revision. */
- stateFor `private stateFor(session: Session): SessionTitleWorkState` — Return mutable work state for one session. */
- titleInputOf `private titleInputOf(session: Session): TitleInputState`
- defer `private defer(task: () => Promise<void>): void` — Queue detached service work and retain it through service disposal. */
- track `private track<T>(run: Promise<T>, registration?: ProviderRegistration): Promise<T>` — Retain one promise until settlement for service and optional provider teardown. */
- drain `private async drain(active: Set<Promise<unknown>>): Promise<void>` — Await every current and settling promise in one lifecycle registry. */
- serviceActive `private serviceActive(): boolean` — Whether the owning plugin fiber can still start or commit title work. */
- assertServiceActive `private assertServiceActive(): void` — Reject work once the owning plugin fiber has begun unloading. */
- validateProvider `private validateProvider(provider: unknown): asserts provider is SessionTitleProvider` — Reject malformed provider registrations before publishing an effect. */
- appendFallback `private appendFallback(session: Session, first: SessionTitleUserMessage): void` — Derive and append the deterministic fallback title over whatever stands (the refresh unpin path: overwriting a pinned user title is the point). Synchronous on purpose — no await may separate derivation from append, so it needs neither ensureFallback's in-flight dedup nor its liveness re-check. An underivable fallback (empty after the caps) appends nothing.
- ensureFallback `private async ensureFallback(session: Session): Promise<SessionTitleSnapshot \| undefined>` — Create the first deterministic fallback if the session still lacks a title. */

### `sessions` — `@deepseek-ai/dsh-api-session-controller`

> Client Session object layer and Agent scope owner. */

- 提供类型：`import('./contract/sessions.ts').ISessions`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-client-test-runtime` (`packages/test-support/client-runtime/src/index.ts:267`)、`@deepseek-ai/dsh-session` (`packages/core/session/src/index.ts:1172`)
- 消费方：@deepseek-ai/dsh-acp(`packages/acp/acp/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-approval(`packages/client/ui-approval/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-goal(`packages/client/ui-goal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-input-trigger(`packages/client/ui-input-trigger/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-input-trigger(`packages/client/ui-input-trigger/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/service.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-session(`packages/client/ui-session/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-subagent(`packages/client/ui-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-tool(`packages/client/ui-tool/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workflow-run(`packages/client/ui-workflow-run/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-compaction-basic(`packages/compaction/compaction-basic/src/index.ts` via inject)、@deepseek-ai/dsh-compaction-image-offload(`packages/compaction/compaction-image-offload/src/index.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-stats(`packages/experimental/client-ui-stats/src/client/index.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-forge-session(`packages/experimental/forge-session/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)、@deepseek-ai/dsh-session-title-all-prompts-llm(`packages/experimental/session-title-all-prompts-llm/src/index.ts` via inject)、@deepseek-ai/dsh-command-feedback(`packages/feedback/command-feedback/src/index.ts` via inject)、@deepseek-ai/dsh-message-feedback(`packages/feedback/message-feedback/src/index.ts` via inject)、@deepseek-ai/dsh-goal-round-driver(`packages/goal/goal-round-driver/src/index.ts` via inject)、@deepseek-ai/dsh-permission-presets(`packages/interaction/permission-presets/src/index.ts` via inject)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via inject)、@deepseek-ai/dsh-session-query-sqlite(`packages/session-query/session-query-sqlite/src/index.ts` via inject)、@deepseek-ai/dsh-session-query(`packages/session-query/session-query/src/index.ts` via inject)、@deepseek-ai/dsh-message-quotes(`packages/session/message-quotes/src/client/index.ts` via inject)、@deepseek-ai/dsh-session-checkpoint-policy(`packages/session/session-checkpoint-policy/src/index.ts` via inject)、@deepseek-ai/dsh-session-log-deepseek(`packages/session/session-log-deepseek/src/index.ts` via inject)、@deepseek-ai/dsh-session-projection-cache(`packages/session/session-projection-cache/src/index.ts` via inject)、@deepseek-ai/dsh-session-telemetry-otel(`packages/session/session-telemetry-otel/src/index.ts` via inject)、@deepseek-ai/dsh-session-title-first-prompt-llm(`packages/session/session-title-first-prompt-llm/src/index.ts` via inject)、@deepseek-ai/dsh-session-title(`packages/session/session-title/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/model-selection-settings.ts` via inject)、@deepseek-ai/dsh-agent-team(`packages/team/agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-commands(`packages/client/ui-commands/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-input-trigger(`packages/client/ui-input-trigger/src/client/service.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/viewer-session-plugin.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/viewer-session.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/tunnel-supervision.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/storage.ts` via ctx.get)、@deepseek-ai/dsh-experimental-translator(`packages/experimental/translator/src/storage.ts` via ctx.get)、@deepseek-ai/dsh-ptc-runtime-node(`packages/ptc-runtime/ptc-runtime-node/src/policy-processes.ts` via ctx.get)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/archive.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/list-children.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/manager.ts` via ctx.get)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via ctx.get)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via ctx.get)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via ctx.get)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `settings` — `@deepseek-ai/dsh-settings`

> Schema-derived plugin configuration forms. */

- 提供类型：`SettingsForms`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-settings` (`packages/settings/settings/src/index.ts:223`，class)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/catalog.ts` via ctx.get)、@deepseek-ai/dsh-api-settings-controller(`packages/api/settings-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-plugin-market(`packages/boot/plugin-market/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-speech-to-text(`packages/experimental/speech-to-text/src/index.ts` via ctx.get)

- importLegacyDocument `private async importLegacyDocument(): Promise<void>` — Move the sections of the removed `settings.yaml` into the active profile once the Loader has settled every entry. The document is renamed before the first write, so a partial import never repeats; a section the running composition rejects is logged and remains only in the renamed file. */
- configure `configure(presentation: { auto?: boolean }, owner: Fiber = this.ctx.fiber): () => void` — Register the calling plugin instance's page policy without changing its Config.
- invalidate `private invalidate(): void`
- queueMicrotask `queueMicrotask(() => { this.scheduled = false if (this.closed \|\| this.ownerContext.fiber.state !== FiberState.ACTIVE) return try { this.describe() } catch (error) { this.ownerConte…`
- prepareDocument `prepareDocument(): Promise<string>` — Locate the profile patch for native editing.
- describe `describe(options?: SettingsDescribeOptions): SettingsDescriptor[]` — Read active plugin schemas and their live values.
- update `async update(ns: string, patch: object, expectedRevision?: number): Promise<void>` — Merge editable fields into an entry's config.
- replace `async replace(ns: string, section: object, expectedRevision?: number): Promise<void>` — Reset all live fields, then set the supplied fields; ordinary config is preserved.
- mutate `async mutate(ns: string, ops: readonly SettingsPathOp[], expectedRevision?: number): Promise<void>` — Apply field edits without restating redacted secrets; unsetting an array index removes its element.
- write `private async write( ns: string, change: (current: Record<string, unknown>, base: Record<string, unknown>, schema: z) => Record<string, unknown>, expected?: number, paths: readonly…`
- validatePaths `validatePaths(next, form)`
- schema `private schema(entry: Entry): z \| undefined`

### `settingsController` — `@deepseek-ai/dsh-api-settings-controller`

> Host owner of the `settings` Remote namespace. */

- 提供类型：`SettingsController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-settings-controller` (`packages/api/settings-controller/src/index.ts:76`，class)
- 提供方：`@deepseek-ai/dsh-api-settings-controller` (`packages/api/settings-controller/src/index.ts:86`)

- describe `describe(): SettingsDescribeValue` — Describe every registered namespace for a configuration page: redacted layered values plus the serialized schema the page renders its form from.  *(decorators: @@Remote)*
- update `update( ns: string, patch: Record<string, JsonValue>, expectedRevision: number \| undefined, ): Promise<SettingsNamespaceView>` — Merge a patch into one namespace's stored user section.  *(decorators: @@Remote)*
- replace `replace( ns: string, section: Record<string, JsonValue>, expectedRevision: number \| undefined, ): Promise<SettingsNamespaceView>` — Replace one namespace's stored user section wholesale.  *(decorators: @@Remote)*
- mutate `async mutate( ns: string, ops: SettingsPathOpView[], expectedRevision: number \| undefined, ): Promise<SettingsNamespaceView>` — Apply path-addressed edits to one namespace's user section, resolved against the section as stored rather than against whatever the caller last read, then answer with that namespace's new redacted view.  *(decorators: @@Remote)*
- openSettingsDocument `async openSettingsDocument(signal: AbortSignal): Promise<SettingsDocumentOpenValue>` — Materialize the provider-owned settings document and open it in a native text editor.  *(decorators: @@Remote)*
- write `private async write( ns: string, mode: 'update' \| 'replace' \| 'mutate', input: Record<string, JsonValue> \| SettingsPathOpView[], expectedRevision: number \| undefined, ): Promise<Se…`
- provider `private provider(): SettingsForms` — Resolve the optional provider or report how to supply it. */

### `settingsSchema` — `@deepseek-ai/dsh-client-ui-settings`

> Settings-owned synchronous schema and immutable path operations. */

- 提供类型：`SettingsSchemaService`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-settings` (`packages/client/ui-settings/src/client/schema.ts:39`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-settings` (`packages/client/ui-settings/src/client/schema.ts:42`)
- 消费方：@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via inject)

- rehydrate `rehydrate(serialized: unknown): SchemaNode` — Rehydrate one serialized `schema.toJSON()` envelope.
- validate `validate(schema: SchemaNode, draft: unknown): string \| undefined` — Validate a settings draft.
- nodeAtPath `nodeAtPath(root: SchemaNode, path: readonly string[]): SchemaNode \| undefined` — Resolve an object, dict, or array schema node at a settings path.
- getPath `getPath(value: unknown, path: readonly string[]): unknown` — Read a nested value by a string-key or array-index path.
- hasPath `hasPath(value: unknown, path: readonly string[]): boolean` — Report whether the final path key exists independently of its value.
- setPath `setPath(root: Record<string, unknown>, path: readonly string[], value: unknown): Record<string, unknown>` — Immutably set a nested value, materializing missing containers.
- deletePath `deletePath(root: Record<string, unknown>, path: readonly string[]): Record<string, unknown>` — Immutably remove a nested key, preserving an unchanged missing root.

### `shell` — `@deepseek-ai/dsh-shell`

- 提供类型：`ShellExecutor`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-shell` (`packages/shell/shell/src/index.ts:64`，class)
- 提供方：`@deepseek-ai/dsh-shell` (`packages/shell/shell/src/index.ts:66`)
- 消费方：@deepseek-ai/dsh-hooks-claude-code(`packages/experimental/hooks-claude-code/src/index.ts` via inject)、@deepseek-ai/dsh-hooks-codex(`packages/experimental/hooks-codex/src/index.ts` via inject)、@deepseek-ai/dsh-permission-presets(`packages/interaction/permission-presets/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via inject)、@deepseek-ai/dsh-tmux-context(`packages/context/tmux-context/src/index.ts` via ctx.get)

- resolve `abstract resolve(request: ShellExecRequest): ShellExecSpec` — Apply implementation-owned defaults and caps to a request before execution. implementation's defaults, capped fields are clamped.
- execute `abstract execute(spec: ShellExecSpec): Promise<ShellExecution>` — Prepare and spawn the command under its resolved deadline. preparation timeout yields an already-settled handle with no output.

### `shellEnv` — `@deepseek-ai/dsh-shell-env`

- 提供类型：`ShellEnvRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-shell-env` (`packages/shell/shell-env/src/index.ts:101`，class)
- 提供方：`@deepseek-ai/dsh-shell-env` (`packages/shell/shell-env/src/index.ts:112`)
- 消费方：@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via inject)

- register `register(contributor: BashEnvContributor): () => void` — Register one environment contributor. Names and keys are unique; built-in keys are reserved. Registration is disposed with the calling plugin fiber.
- yield `yield () =>`
- collect `collect(execution: ToolExecution): DshEnvironment` — Build the trusted `DSH_*` snapshot for one shell tool execution.
- list `list(): BashEnvVariableInfo[]` — TODO(bash-env-list-builtins): Include registry-owned built-ins before diagnostics, prompt, or UI code treats list() as an exhaustive environment catalog. Enumerate plugin-contributed variables without executing their resolvers.

### `shortcuts` — `@deepseek-ai/dsh-client-shortcuts`

> Window-local application commands and effective keycap catalog. */

- 提供类型：`Shortcuts`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-shortcuts` (`packages/client/shortcuts/src/client/types.ts:83`，interface)
- 提供方：`@deepseek-ai/dsh-client-shortcuts` (`packages/client/shortcuts/src/client/index.ts:47`)
- 消费方：@deepseek-ai/dsh-client-ui-context-menu(`packages/client/ui-context-menu/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-layout(`packages/client/ui-layout/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-shortcuts(`packages/client/ui-shortcuts/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)

- registerFixed `registerFixed(command: ShortcutFixedCommand): () => void` — Contribute one fixed action and reserve its keys against editable bindings.
- observeFixedInput `observeFixedInput(listener: (input: ShortcutFixedInput) => void): () => void` — Observe locally arbitrated input and interaction resets for fixed sequences.
- describeBinding `describeBinding(binding: ShortcutBinding \| null):` — Describe a candidate using the device's physical-key and reservation rules; invalid codes throw.
- edit `edit(edit: ShortcutEdit, revision: ShortcutRevision): Promise<ShortcutSaveResult>` — Save a reviewed edit; failures preserve both accepted preferences and the caller's draft.
- recording `recording(active: boolean): Promise<void>` — Suppress native menu accelerators while the recording layer owns keyboard input; reject if Desktop cannot acknowledge it.
- closeWindow `closeWindow(): Promise<void>` — Request closure of the Desktop window using the currently accepted shortcut revision.
- register `register(command: ShortcutCommand): () => void` — Register a command; duplicate ids and overlapping default bindings throw.

### `sidebarRight` — `@deepseek-ai/dsh-client-ui-sidebar-right`

> Right-Sidebar navigation and presentation face. */

- 提供类型：`SidebarRightController`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-sidebar-right` (`packages/client/ui-sidebar-right/src/client/service.ts:301`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-sidebar-right` (`packages/client/ui-sidebar-right/src/client/index.ts:183`)
- 消费方：@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-browser(`packages/client/ui-sidebar-browser/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-files(`packages/client/ui-sidebar-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-subagent(`packages/client/ui-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)

- registerCloseHandler `registerCloseHandler(kind: string, handler: SidebarRightCloseHandler): () => void` — Register resource cleanup before explicit removal. Failure preserves the tab.
- menuTabs `menuTabs(sessionId: SessionId, paneId: PaneId, tabId: TabId):` — Read closeable tabs from the clicked pane.
- tabsIn `tabsIn(sessionId: SessionId): readonly TabRecord[]` — Read the committed tabs of a Session so providers can restore their content.
- openResource `openResource(address: string, options: SidebarRightOpenResourceOptions = {}): void` — Open a resource: claim it, place it, reveal the column, record the navigation.
- openTab `openTab<K extends string>(kind: K, options: SidebarRightOpenTabOptions<K> = {}): void` — Open a page type by kind at the address this package records pages under.
- openResourceIn `openResourceIn(sessionId: SessionId, address: string, options: SidebarRightOpenResourceOptions = {}): void` — Open a resource in one session, for a tab's own action; nothing happens for a session whose store was never adopted or whose adoption was released. Not part of `ISidebarRight`: the Tab domain's path.
- openTabIn `openTabIn<K extends string>(sessionId: SessionId, kind: K, options: SidebarRightOpenTabOptions<K> = {}): void` — Open a page type in one session, for a tab's own action; nothing happens for a session whose store was never adopted or whose adoption was released. Not part of `ISidebarRight`: the Tab domain's path.
- closeIn `closeIn(sessionId: SessionId, tabId: TabId): void` — Close a tab of one session, preserving the sole docked guide; nothing happens for a session whose store was never adopted or whose adoption was released. Not part of `ISidebarRight`: the Tab domain's path.
- removeAfterCleanup `private removeAfterCleanup(sessionId: SessionId, tab: TabRecord, commit: () => void): void`
- commit `commit()`
- placeResource `private placeResource( sessionId: SessionId, actions: SurfaceActions, address: string, options: SidebarRightOpenResourceOptions, ): void` — Claim a resource and place it in one session; an address outside the scheme or one no type claims throws. */
- placeIn `private placeIn( sessionId: SessionId, actions: SurfaceActions, claim: SidebarRightTabClaim, address: string, destination: SidebarRightDestination, params: SidebarRightNavigationPa…` — Settle a claimed resource in an explicit host: one store intent, no close handler, and a flash only for a reveal. */
- placeTab `private placeTab<K extends string>( sessionId: SessionId, actions: SurfaceActions, kind: K, options: SidebarRightOpenTabOptions<K>, ): void` — Place a page type in one session at the address pages are recorded under; an unregistered kind throws. */
- place `private place( sessionId: SessionId, actions: SurfaceActions, claim: SidebarRightTabClaim, address: string, placement: SidebarRightPlacement, params: SidebarRightNavigationParams, …` — The steps both opens share: one store intent, and the navigation record for the tab it settles on. */
- flashOf `flashOf(sessionId: SessionId): ObservableSnapshot<SidebarRightFlash \| undefined>` — The flash requests of one Session's seat: each open that reveals an existing tab names the pane holding it, with a serial that changes on every request.
- flashSource `private flashSource(sessionId: SessionId): SnapshotStore<SidebarRightFlash \| undefined>`
- flashShowing `private flashShowing(sessionId: SessionId, layout: LayoutState, tabId: TabId): void` — Flash the pane holding a revealed tab only when that tab was already on screen; a reveal that switches tabs or expands the column is its own visible change.
- flash `private flash(sessionId: SessionId, paneId: PaneId): void` — Ask a Session's seat to highlight the pane holding a revealed tab. */
- close `close(tabId: TabId): void` — Close one tab of the on-screen Session; the sole docked guide remains open.
- hide `hide(tabId: TabId): void` — Hide a tab: close its floating occurrence, or collapse its docked column.
- active `active(): TabRecord \| undefined` — The active tab of the active pane.
- isExpanded `isExpanded(): boolean` — Whether the column is currently showing its panel.
- toggleExpanded `toggleExpanded(): void` — Collapse the column, or expand it and focus its active dock pane after rendering. */
- focus `focus(tabId: TabId): void` — Focus a tab and the pane holding it; a missing tab is left alone.
- focusedTarget `focusedTarget(element: Element \| null = document.activeElement): SidebarRightTarget \| undefined` — Capture the page owning current DOM focus; outside focus never uses layout history.
- commandTarget `commandTarget(element: Element \| null = document.activeElement): SidebarRightTarget \| undefined` — Choose a focused sidebar pane, or the on-screen Session's active dock pane for an outside open.
- openTabFromTarget `openTabFromTarget(kind: string, target: SidebarRightTarget): void` — Open from a captured pane using the guide's replacement and floating placement rules.
- canCloseTarget `canCloseTarget(target: SidebarRightTarget): boolean` — Test explicit close eligibility without using the last selected page.
- closeTarget `closeTarget(target: SidebarRightTarget): 'closed' \| 'unavailable' \| 'stale'` — Remove a captured page through its resource cleanup handler, or collapse the sole docked guide. Cleanup errors propagate and preserve the page.
- isTargetCurrent `isTargetCurrent(target: SidebarRightTarget): boolean` — Check a captured target before acting, including reopened records and intervening navigation.
- splitBlock `splitBlock(target: SidebarRightTarget): 'stale' \| 'collapsed' \| 'float' \| 'empty' \| 'budget' \| 'width' \| undefined` — Explain the same geometry and pane-budget rule used by the split control.
- toggleFullscreen `toggleFullscreen(target: SidebarRightTarget): void` — Toggle the right panel's display mode through the same action as its chrome button.
- split `split(paneId?: PaneId): PaneId \| undefined` — Split a docked pane to its right when the budget and the room rule allow.
- float `float(tabId: TabId, rect?: FloatRect): void` — Take a docked tab out into a floating panel; a missing or floating tab is left alone.
- dock `dock(paneId: PaneId): void` — Return a floating panel's tab to the active docked pane and expand the column; a missing or docked pane is left alone.
- _undo `_undo(): void` — Step the on-screen Session's surface back one intent. with no user-facing control yet. Kept reachable for tests.
- _redo `_redo(): void` — Step the on-screen Session's surface forward one intent.
- screen `private screen():` — The on-screen Session and its committed surface; `undefined` with no Session on screen, before the runtime mints its store, or before its first open.
- mountedSurface `private mountedSurface(): SurfaceState \| undefined` — The on-screen Session's surface; see {@link SidebarRightController.screen}. */
- canSplitPane `private canSplitPane(sessionId: SessionId, paneId: PaneId): boolean` — Whether a Session's docked pane has room for two working halves, as its seat last measured; unmeasured panes do. */
- actionsFor `private actionsFor(sessionId: SessionId): SurfaceActions \| undefined` — The store actions a tab's own action on `sessionId` runs through: that session's adopted store. `undefined` — nothing to act on — for a session whose store was never minted or whose adoption was released.
- require `private require():`

### `sidebarRightTabs` — `@deepseek-ai/dsh-client-ui-sidebar-right`

> Right-Sidebar tab-type registry (stage one of a tab type's registration). */

- 提供类型：`SidebarRightTabRegistry`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-sidebar-right` (`packages/client/ui-sidebar-right/src/client/tab-registry.ts:229`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-sidebar-right` (`packages/client/ui-sidebar-right/src/client/index.ts:182`)
- 消费方：@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-browser(`packages/client/ui-sidebar-browser/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-files(`packages/client/ui-sidebar-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via ctx.get)

- register `register(definition: SidebarRightTabDefinition): () => void` — Register one tab type for the caller's lifetime. The caller holds the returned disposer inside its own `ctx.effect`, so a type's registration lives exactly as long as the plugin that contributed it. An `extension` may register a kind a `builtin` already holds and takes it over until it unregisters; a second registration in the same band, or any registration meeting a `fallback` of the same kind, is a wiring mistake, and so is an `id` already in use.
- enter `private enter(kind: string, entry: Registered): KindSlot` — Add a registration to its kind's slot, the higher band in force; `coexists` has already admitted it. */
- leave `private leave(kind: string, slot: KindSlot, entry: Registered): void` — Remove a registration from its kind's slot: a shadowed builtin resumes, and an emptied kind is freed. */
- active `private active(): Registered[]` — Every kind's registration in force, in registration order. */
- entries `entries(): readonly SidebarRightTabDefinition[]` — Registered types in registration order.
- guide `guide(): readonly SidebarRightGuideBox[]` — Every type in force's guide entries, in `order`, each naming the kind it opens.
- get `get(kind: string): SidebarRightTabDefinition \| undefined` — The type in force for a kind.
- candidates `candidates(address: string): readonly SidebarRightTabDefinition[]` — Every type that would open an address, best first. Ranked by priority band, then by the length of the pattern that matched, then by registration order. Types whose `canOpen` vetoes are absent.
- claim `claim(address: string, kind?: string): SidebarRightTabClaim` — Decide which type opens an address, and as what. Without `kind`, the best candidate wins. With `kind`, that type opens the address if its `canOpen` agrees — its globs are not consulted, because naming the type IS the decision. An address no type will open is a wiring mistake, not a user error, so this throws rather than reporting absence.
- subscribe `subscribe(listener: () => void): () => void` — Observe low-frequency registry changes.
- refresh `private refresh(): void`
- notifySubscribers `notifySubscribers(this.listeners, '[ui-sidebar-right] tab registry')`

### `skills` — `@deepseek-ai/dsh-skill`

- 提供类型：`SkillRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-skill` (`packages/skill/skill/src/index.ts:356`，class)
- 提供方：`@deepseek-ai/dsh-skill` (`packages/skill/skill/src/index.ts:374`)
- 消费方：@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-plugin-recommendations(`packages/experimental/plugin-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-skill-badge(`packages/experimental/skill-badge/src/index.ts` via inject)、@deepseek-ai/dsh-skill-filesystem(`packages/skill/skill-filesystem/src/index.ts` via inject)、@deepseek-ai/dsh-skill-office(`packages/skill/skill-office/src/index.ts` via inject)、@deepseek-ai/dsh-tool-skill(`packages/skill/tool-skill/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via ctx.get)

- assertPositiveInteger `assertPositiveInteger('collectCacheMaxEntries', this.collectCacheMaxEntries)`
- registerProvider `registerProvider(create: (control: SkillProviderControl) => SkillProvider): () => void` — Register a borrowed same-process provider synchronously during plugin apply, into the calling context's layer: a scoped context (an agent preset's standing mount) registers for that scope alone, an unscoped context registers globally. Duplicate names within one layer and reserved names throw; remote initialization belongs in `list()`. Fiber disposal unregisters the provider and invalidates catalog caches. composite effects may yield it directly to preserve teardown ordering.
- undo `undo()`
- register `register(skill: SkillRegistration): () => void` — Register a borrowed readonly runtime skill into the calling context's layer. Project entries outrank runtime entries, which outrank user entries, within one layer. Same-name runtime entries in one layer are first-wins; a duplicate logs a warning and receives a no-op disposer so it cannot remove the winner.
- validateRuntimeSkill `validateRuntimeSkill(skill)`
- list `async list(options: SkillViewOptions = {}): Promise<SkillSummary[]>` — List invocation-neutral skill summaries for a workspace. Consumers apply model or user invocation policy at their operational boundary. Lookup options and provider candidates are readonly same-process values borrowed throughout discovery.
- snapshot `async snapshot(options: SkillViewOptions = {}): Promise<SkillCatalogSnapshot>` — Observe the current invocation-neutral catalog and whether discovery completed within a stable revision. Incomplete observations are never cached, allowing consumers to retain last-good state and retry on their next request boundary.
- get `async get(name: string, options: SkillViewOptions = {}): Promise<SkillDefinition \| undefined>` — Load and validate the winning candidate, passing its opaque discovery locator back to the provider. Cancellation is rechecked after selection, including cache hits, and raced against loading so an uncooperative provider cannot hang the caller. `cwd` selects workspace-sensitive skills, and `signal` cancels work.
- throwIfAborted `throwIfAborted(options.signal)`
- validateDefinition `validateDefinition(definition)`
- collect `private async collect(options: SkillViewOptions): Promise<CollectResult>`
- collectFresh `private async collectFresh(options: SkillViewOptions): Promise<CollectResult>`
- collectLayer `private async collectLayer(layer: SkillLayer, options: SkillLookupOptions): Promise<LayerCollectResult>`
- listLayerCandidates `private async listLayerCandidates(layer: SkillLayer, options: SkillLookupOptions): Promise<LayerCollectResult>`
- validateCandidate `validateCandidate(candidate, provider.name)`
- invalidateCache `private invalidateCache(): void`
- invalidateEntry `private invalidateEntry(entry: IndexedCandidate): void` — Invalidate after a stale definition load, only while the exact registration that produced the entry is still live. */
- scopeId `private scopeId(key: ScopeKey): number`
- collectCacheKey `private collectCacheKey(cwd: string \| undefined, chain: ScopeKey[], revision: number): string`
- notifyChange `private notifyChange(): void` — Notify catalog observers without making their refresh work load-bearing. */

### `slots` — `@deepseek-ai/dsh-client-ui-renderer`

> Renderer-owned UI composition registry. */

- 提供类型：`SlotRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-client-ui-renderer` (`packages/client/ui-renderer/src/client/registry.ts:120`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-renderer` (`packages/client/ui-renderer/src/client/registry.ts:160`)
- 消费方：@deepseek-ai/dsh-api-remote-access(`packages/api/remote-access/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-locale(`packages/client/locale/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-resources(`packages/client/resources/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-account-notifications(`packages/client/ui-account-notifications/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-preset(`packages/client/ui-agent-preset/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-agent-team(`packages/client/ui-agent-team/src/client/mount.ts` via inject)、@deepseek-ai/dsh-client-ui-approval(`packages/client/ui-approval/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-attachment(`packages/client/ui-attachment/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-brand-official(`packages/client/ui-brand-official/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-context-menu(`packages/client/ui-context-menu/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-browse(`packages/client/ui-directory-picker-browse/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-native(`packages/client/ui-directory-picker-native/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-file-drag(`packages/client/ui-file-drag/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-goal(`packages/client/ui-goal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-jobs(`packages/client/ui-jobs/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-layout(`packages/client/ui-layout/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-message-feedback(`packages/client/ui-message-feedback/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-model-selection(`packages/client/ui-model-selection/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-open-in-app(`packages/client/ui-open-in-app/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-permission-presets(`packages/client/ui-permission-presets/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-manager(`packages/client/ui-plugin-manager/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plugin-market(`packages/client/ui-plugin-market/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-secret-mask(`packages/client/ui-secret-mask/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-session(`packages/client/ui-session/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-agent-loop(`packages/client/ui-settings-agent-loop/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-general(`packages/client/ui-settings-general/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-models(`packages/client/ui-settings-models/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugin-inventory(`packages/client/ui-settings-plugin-inventory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-plugins(`packages/client/ui-settings-plugins/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-session-log(`packages/client/ui-settings-session-log/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-shell(`packages/client/ui-settings-shell/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-subagent(`packages/client/ui-settings-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-web-search(`packages/client/ui-settings-web-search/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-shortcuts(`packages/client/ui-shortcuts/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-browser(`packages/client/ui-sidebar-browser/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-documentpreview(`packages/client/ui-sidebar-documentpreview/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-files(`packages/client/ui-sidebar-files/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-subagent(`packages/client/ui-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-theme(`packages/client/ui-theme/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-tool(`packages/client/ui-tool/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workflow-run(`packages/client/ui-workflow-run/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-action-cards(`packages/experimental/client-ui-action-cards/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-claude-code-mods(`packages/experimental/client-ui-claude-code-mods/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-stats(`packages/experimental/client-ui-stats/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-voice-input(`packages/experimental/client-ui-voice-input/src/client/mount.ts` via inject)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/client/mount.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/client/mount.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-cordis(`packages/extensions/ui-cordis/src/client/index.ts` via inject)、@deepseek-ai/dsh-session-log-export(`packages/session-query/session-log-export/src/client/index.ts` via inject)、@deepseek-ai/dsh-message-quotes(`packages/session/message-quotes/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/providers.ts` via ctx.get)、@deepseek-ai/dsh-client-test-runtime(`packages/test-support/client-runtime/src/index.ts` via ctx.get)

- inject `inject(key: keyof SlotMap & string, callback: () => SlotInjectionEffect): () => void` — Install an effect for each declaration lifetime of a slot. The callback runs synchronously when the declaration already exists; otherwise it runs inside the declaring `register()` call after the declaration is committed. Collapse disposes the effect and a later declaration runs it again. Callback effects are synchronous disposers; iterable effects install transactionally and dispose in reverse order. The controller belongs to the caller's fiber, so plugin unload cancels a pending wait and removes any active contribution.
- unsubscribe `unsubscribe()`
- reconcile `reconcile()`
- stop `stop()`
- queueMicrotask `queueMicrotask(() => { throw failure })`
- install `install(renderer: SlotRenderer): void` — Install the shell's renderer (ui-renderer's createSlotRenderer product). Boot-once: a second install throws. Runs through the caller's ctx.effect, so shell fiber unload uninstalls the renderer.
- installLocale `installLocale(face: LocaleFace): void` — Install the locale face backing the `t` standard seat (the locale plugin's product; same boot-once discipline as the renderer install). Runs through the caller's ctx.effect, so the installing fiber's unload uninstalls the face.
- provideRoot `provideRoot(contribution: RootStandardSourceContribution): () => void` — Contribute domain-owned root data. Hook names must be globally unique; registration and disposal republish one atomic root binding.
- installScope `installScope( scope: Exclude<SlotScope, 'root' \| 'session-maybe'>, adapter: SlotScopeAdapter, ): void` — Install the owner adapter for one strict scope. Its optional counterpart resolves through the same adapter.
- bindStoreScope `bindStoreScope(binding: Pick<ScopedStandardSourceBinding, 'key' \| 'ctx'>): void` — Bind scoped Store instances to one Context generation. Rebinding the key drops the previous generation's memory instances before the new owner can resolve them. Cleanup never clears persisted state, which belongs to the durable scope key, or drops a replacement generation's instances.
- renderSlot `renderSlot<K extends keyof SlotMap & string>(key: K, owner: OwnerOf<K>): ReturnType<SlotRenderer['renderRoot']>` — The single ctx-level render entry: the shell renders 'root'; every other key renders inside components through the props renderSlot face. All three guards are fail-loud boot-order checks, no fallback.
- entries `entries(key: keyof SlotMap & string): readonly StoredEntry[]` — Snapshot entries for a key (render-erased view; stable reference between mutations).
- entriesOfSlot `entriesOfSlot(key: keyof SlotMap & string): readonly StoredEntry[]` — Shadowing winners per cell for a key: the first live (non-abdicated) entry of each cell in priority order — what outlets render; chain keys pass through unchanged (election consumes every entry). The raw {@link SlotRegistry.entries} view stays the inspection surface. Fresh array per call, not a uSES getSnapshot source.
- snapshot `snapshot(root?: string): LiveCompositionNode[]` — Export the current JSON-safe Slot and Factory declaration trees for read-only inspection.
- onEntryError `onEntryError(fn: ( key: string, registration: StoredEntry \| StoredFactory, error: unknown, info: { abdicated: boolean }, ) => void): () => void` — Observe ordinary entry and Factory occurrence crashes through one supervision channel. Fires synchronously after any ordinary-entry abdication mutation. Callers own the disposer (wire it through ctx.effect for fiber-lifetime cleanup, as with {@link SlotRegistry.subscribe}). registration, cause, and whether an ordinary entry was retired.
- spec `spec<K extends keyof SlotMap & string>(key: K): SlotSpec<SlotMap[K]> \| undefined` — Look up a declared spec (register-declared or the built-in 'root').
- subscribe `subscribe(key: keyof SlotMap & string, fn: () => void): () => void` — Subscribe to a key's registration changes (microtask-batched).
- getVersion `getVersion(key: keyof SlotMap & string): number` — Version counter for uSES pairing.
- _register `private _register(options: ErasedRegisterOptions, component: unknown): () => void` — Delegating registration path: factory minting + registrant stamp + core write + instance-axis bookkeeping. */
- dispose `dispose()`
- _registerFactory `private _registerFactory(options: ErasedFactoryOptions, component: unknown): () => void`
- hostFace `private hostFace(): SlotRendererHost` — Build the domain-neutral host face once; installed adapters remain live through getters. */
- rebuildRootBinding `private rebuildRootBinding(): void` — Validate and atomically publish the current root contribution roster. */
- copyUnique `copyUnique('hook', hooks, contribution.hooks, finalProps, standardHookPropName)`
- copyUnique `copyUnique('keyed hook', keyedHooks, contribution.keyedHooks, finalProps, standardHookPropName)`
- copyUnique `copyUnique('prop', props, contribution.props, finalProps, name => name)`
- listener `listener()`
- publishScopeRevision `private publishScopeRevision(): void` — Publish one installed-scope roster transition after the map is authoritative. */
- resolveStore `private resolveStore( handle: EngineStoreHandle, scopeBinding: ScopedStandardSourceBinding \| undefined, ): StoreInstanceLike` — Resolve (create or reuse) the store instance for a registered handle under a scope key. */
- resolveFactoryStore `private resolveFactoryStore( definition: StoredFactory, scopeBinding: ScopedStandardSourceBinding \| undefined, occurrence: object, ): StoreInstanceLike \| undefined`
- retainFactoryOccurrence `private retainFactoryOccurrence(definition: StoredFactory, occurrence: object): () => void`
- releaseStoreScope `private releaseStoreScope(key: string): void` — Drop every materialized non-root Store instance for one ended Context generation. */
- _acquire `private _acquire(handle: EngineStoreHandle, scope: SlotScope): void` — Bind (or re-reference) a handle on the axis; cross-scope conflicts already threw in the core. */
- _release `private _release(handle: EngineStoreHandle): void` — Drop one reference; the last holder's unload drops the record (instances go with it — engine stores need no explicit dispose). */

### `speechController` — `@deepseek-ai/dsh-experimental-api-speech-to-text`

> Experimental speech Remote controller. */

- 提供类型：`SpeechController`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-experimental-api-speech-to-text` (`packages/experimental/api-speech-to-text/src/index.ts:36`)

- （方法未解析：提供类型不可达或未定义成员）

### `speechToText` — `@deepseek-ai/dsh-experimental-speech-to-text`

> Experimental speech recognition provider registry. */

- 提供类型：`SpeechToText`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-experimental-speech-to-text` (`packages/experimental/speech-to-text/src/index.ts:48`)
- 消费方：@deepseek-ai/dsh-experimental-api-speech-to-text(`packages/experimental/api-speech-to-text/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-speech-to-text-sensevoice(`packages/experimental/speech-to-text-sensevoice/src/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `spillStore` — `@deepseek-ai/dsh-spill`

- 提供类型：`SpillStore`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-spill` (`packages/spill/spill/src/index.ts:45`，class)
- 提供方：`@deepseek-ai/dsh-spill` (`packages/spill/spill/src/index.ts:47`)
- 消费方：@deepseek-ai/dsh-session-reference(`packages/context/session-reference/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-fs-search(`packages/fs/tool-fs-search/src/search-core.ts` via ctx.get)、@deepseek-ai/dsh-spill-policy(`packages/spill/spill-policy/src/index.ts` via ctx.get)

- saveText `abstract saveText(input: SaveTextSpill): Promise<SpillRef>` — Persist `input.content` to a session-scoped spill artifact.

### `ssh` — `@deepseek-ai/dsh-ssh`

- 提供类型：`SshConnection`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-ssh` (`packages/ssh/ssh/src/index.ts:59`，class)
- 提供方：`@deepseek-ai/dsh-ssh` (`packages/ssh/ssh/src/index.ts:89`)
- 消费方：@deepseek-ai/dsh-fs-ssh(`packages/ssh/fs-ssh/src/index.ts` via inject)、@deepseek-ai/dsh-sandbox-ssh(`packages/ssh/sandbox-ssh/src/index.ts` via inject)、@deepseek-ai/dsh-subprocess-ssh(`packages/ssh/subprocess-ssh/src/index.ts` via inject)

- request `async request<T>(method: string, params: unknown, result: z.ZodType<T>, signal?: AbortSignal, wait: boolean = false): Promise<T>` — Send a helper operation; cancellation never replays an ambiguous mutation.
- connectStream `async connectStream(endpoint: SshStreamEndpoint, signal?: AbortSignal): Promise<Socket>` — Forward one authenticated stream through an independent SSH channel.
- establishStream `private async establishStream(endpoint: SshStreamEndpoint, signal?: AbortSignal): Promise<Socket>`
- dispose `dispose(): Promise<void>` — Tear down the helper's remote managed ranges before releasing the SSH master when reachable. */
- disposeOnce `private async disposeOnce(): Promise<void>`
- controlPath `private controlPath(): string`
- assertOpen `private assertOpen(): void`
- track `private track<T>(operation: Promise<T>): Promise<T>`
- controlCommand `private async controlCommand(args: string[], signal?: AbortSignal): Promise<void>`
- fail `private fail(error: Error): void`
- start `private async start(): Promise<Hello>`

### `storage` — `@deepseek-ai/dsh-storage`

- 提供类型：`Storage`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-storage` (`packages/storage/storage/src/index.ts:47`，class)
- 提供方：`@deepseek-ai/dsh-storage` (`packages/storage/storage/src/index.ts:54`)
- 消费方：@deepseek-ai/dsh-storage-domain(`packages/storage/storage-domain/src/index.ts` via inject)、@deepseek-ai/dsh-storage-json(`packages/storage/storage-json/src/index.ts` via inject)、@deepseek-ai/dsh-storage-sqlite(`packages/storage/storage-sqlite/src/index.ts` via inject)

- mount `mount<K extends keyof StorageForms>(form: K, facility: StorageForms[K]): () => void` — Mount a data-form facility on the hub. Mounting is an effect: the returned disposer unmounts the form.
- form `form<K extends keyof StorageForms>(form: K): StorageForms[K]` — Resolve a mounted data form.

### `storageDomain` — `@deepseek-ai/dsh-storage-domain`

- 提供类型：`DomainFacility`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-storage-domain` (`packages/storage/storage-domain/src/index.ts:69`，class)
- 消费方：@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via inject)、@deepseek-ai/dsh-session-projection-cache(`packages/session/session-projection-cache/src/index.ts` via inject)、@deepseek-ai/dsh-workspace(`packages/workspace/workspace/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/permission-store.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/permission-store.ts` via ctx.get)

- open `async open<S extends DomainSpec>(spec: S): Promise<Domain<S>>` — Open one declared domain. Steps, each failing the whole call: reject a name that is already open (`already-open`); resolve the backend route (`backend-not-found` passes through from the hub); require its `kv` facet (`facet-unsupported`); open the unit projected from the spec (backend `version-mismatch`/`malformed-medium` pass through); load and validate every stored record against the spec's zod schemas (`invalid-record` with the offending table and key — unless the spec declares `invalidRecords: 'backup-and-skip'` and the unit can move documents aside, in which case the failing record is backed up, logged, and skipped); construct the domain. Lifecycle: the CALLER owns the returned handle and closes it via `Domain.close()` (typically as its own `ctx.effect` disposer) — the facility does not tie the domain to any consumer fiber. Domains still open when the facility unmounts are closed by the plugin disposer.
- get `get(name: string): DomainImpl \| undefined` — Look up an open domain by name, untyped. Diagnostic surface; typed consumers hold the handle returned by {@link open}.
- closeAll `async closeAll(): Promise<void>` — Close every domain still open on this facility. The unmount path for consumers that never called `Domain.close()` themselves; closing is idempotent, so double-closing an already-closed domain is harmless.

### `subagentModelSelection` — `@deepseek-ai/dsh-tool-subagent`

> User preference sampled during Agent creation. */

- 提供类型：`SubagentModelSelectionConfig`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-tool-subagent` (`packages/subagent/tool-subagent/src/model-selection-settings.ts:42`，class)
- 提供方：`@deepseek-ai/dsh-tool-subagent` (`packages/subagent/tool-subagent/src/model-selection-settings.ts:51`)

- current `private current(): SubagentModelSelectionSettings` — Read a detached selection preference for the next fresh top-level Session.
- assertAllowedModelRoutes `assertAllowedModelRoutes(allowedModels)`

### `subagents` — `@deepseek-ai/dsh-subagent`

- 提供类型：`SubagentRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-subagent` (`packages/subagent/subagent/src/index.ts:194`，class)
- 提供方：`@deepseek-ai/dsh-subagent` (`packages/subagent/subagent/src/index.ts:210`)
- 消费方：@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-subagent-oar(`packages/experimental/subagent-oar/src/index.ts` via inject)、@deepseek-ai/dsh-tool-ralph(`packages/experimental/tool-ralph/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-tool-subagent-oar(`packages/experimental/tool-subagent-oar/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-acp(`packages/subagent/subagent-acp/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-claude-code(`packages/subagent/subagent-claude-code/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-codex(`packages/subagent/subagent-codex/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-dsh-sdk(`packages/subagent/subagent-dsh-sdk/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-fork-in-process(`packages/subagent/subagent-fork-in-process/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-spawn-in-process(`packages/subagent/subagent-spawn-in-process/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent-control(`packages/subagent/tool-subagent-control/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via inject)、@deepseek-ai/dsh-agent-team(`packages/team/agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-tool-agent-team(`packages/team/tool-agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-workflow-ptc(`packages/workflow/workflow-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/session.ts` via ctx.get)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/session.ts` via ctx.get)、@deepseek-ai/dsh-headless(`packages/bundle/headless/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via ctx.get)、@deepseek-ai/dsh-goal-round-driver(`packages/goal/goal-round-driver/src/index.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/server.ts` via ctx.get)

- resolveMaxDepth `resolveMaxDepth(configured?: number \| 'provider-managed'): number \| undefined` — Resolve a delegation tool's depth policy against the current user setting.
- assertSubagentMaxDepth `assertSubagentMaxDepth(depth)`
- startActivation `startActivation(spec: SubagentActivationSpec & { readonly childId: SessionId }):` — Start a local child under its reserved identity.
- startActivation `startActivation(spec: SubagentActivationSpec): Promise<SubagentActivation>` — Start a local or external child.
- startActivation `async startActivation(spec: SubagentActivationSpec): Promise<SubagentActivation>` — Establish a managed child with backend-specific execution capabilities. childId requires a local backend and guarantees an accepted messageId.
- assertSubagentMaxDepth `assertSubagentMaxDepth(spec.maxDepth)`
- rootOf `rootOf(caller: Agent): Agent` — Resolve the root shared by an Agent and its other agents in its subagent tree.
- namesOf `namesOf(agent: Agent): SubagentMemberNames` — Report the model-facing names of a live tree member and its direct creator. The root is `lead`; a descendant is the slash-separated path of names from the root, or its Session id when it or a creator below the root has no name.
- resolveName `async resolveName(caller: Agent, name: string, signal: AbortSignal): Promise<SessionId>` — Resolve a model-supplied agent reference within the caller's tree. `lead` selects the root and a slash-separated path is looked up through the catalogs along it. Any other text that is not a name in the tree is returned as a Session id, because a single token can be one; a slash-separated address never is, so an unmatched path fails instead of reaching a member lookup as an unknown id. Resolution grants no authority: messaging, interruption, and assignment authorize the result. when the caller's root is unavailable; or when a catalog along the path cannot be read.
- waitForTreeWork `async waitForTreeWork(root: Agent): Promise<boolean>` — Join progressing subagent tree work for its root. Idle members with parked input stay resident without delaying host completion. Ordinary members return false.
- sendMessage `async sendMessage( sender: Agent, targetId: SessionId, content: ContentBlock[], options: SubagentSendMessageOptions, ): Promise<MessageId>` — Steer one model-authored message to another member of the same subagent tree. A running target receives it at its next step; an idle target starts a turn. A cold target resumes under its runtime subagent tree root without restoring its creation ancestors. Sender identity is rechecked before inbox acceptance; cancellation stops only pre-acceptance work and never retracts an accepted message.
- interrupt `interrupt(targetSessionId: SessionId, authority: SubagentInterruptAuthority): void` — Interrupt one live child's current execution under a trusted user operation or an exact live ancestor Agent. Fire-and-return: the cancel signal is issued before this returns, but the target may keep running until it observes the signal. Unclaimed pending inbox work, the Activation, and published descendants are preserved; claimed work is not requeued. Once the interrupted Agent is idle, a waking send resumes the parked FIFO queue. External backends stop their single execution. An absent target is an accepted no-op, as is a manager-less composition, which cannot own a live Activation. live target.
- drainDescendants `async drainDescendants(parents: readonly Agent[]): Promise<void>` — Close admission and stop all instances in the selected subagent trees, then await pending startup and cleanup. Ordinary members are ignored. The cutoff lasts until each exact root leaves the registry; unrelated subagent trees remain live.
- listDescendants `listDescendants(rootSessionId: SessionId, signal?: AbortSignal): Promise<SubagentDescendantListEntry[]>` — Recursively list reachable parent catalogs in stable pre-order, preserving each catalog's event order. Each row carries its catalog parent and depth; external children are leaves; one-shot and unknown-mode children remain traversal nodes. Unknown modes produce unsupported diagnostics. Unreadable child catalogs produce corrupt or unavailable diagnostics and stop only that branch. Root read failures, missing services or projections, and cancellation reject the whole listing. Each catalog is observed once and released before the next read. No Agent is loaded or resumed; Sessions absent from reachable catalogs are omitted.
- prompt `async prompt(request: SubagentPromptRequest, signal: AbortSignal): Promise<SubagentPromptReceipt>` — Deliver one browser-authored message to a continuable child through its live subagent tree root, retaining the caller-minted request identity and validated browser zone on the accepted message. Success identifies the message the child's inbox accepted; later execution is independent of this call. Queue delivery targets a later turn; steer delivery targets the nearest step and retains the Agent loop's best-effort fallback semantics. Image parts are admitted and persisted through the attachment store before delivery, and the child's model must accept image input. Cold resume at capacity rejects with `subagent/delivery-unavailable`. Access is checked on the target Session before attachment admission or restoration. `subagent/invalid-time-zone`, `subagent/not-resumable`, `subagent/unauthorized`, `subagent/delivery-unavailable`, `gateway/cancelled`, or `gateway/internal`.  *(decorators: @@Remote({ name: 'prompt', resources: { session: request => request.childSessionId } }))*
- validateControlRequest `validateControlRequest('subagent.prompt', request)`
- interruptByUser `interruptByUser(childSessionId: SessionId): SubagentInterruptReceipt` — Remote face of {@link interrupt}, authorized on the target Session by the Gateway. No catalog, history, persistence, or parent Agent lookup runs. Absent, idle, and already-completed targets are accepted no-ops there. otherwise `gateway/internal`.  *(decorators: @@Remote({ name: 'interruptByUser', resources: { session: childSessionId => childSessionId } }))*
- validateControlRequest `validateControlRequest('subagent.interrupt', { childSessionId })`
- registerProvider `registerProvider(provider: SubagentProvider): () => void` — Register a provider under its name. Registration is effect-scoped and HMR safe; removing a provider blocks new starts but does not revoke runs that were already returned to their holders. Providers without either execution method are rejected with UNSUPPORTED_CAPABILITY before registration.
- yield `yield () =>`
- getProvider `getProvider(name: string): SubagentProvider \| undefined` — Look up a provider by name.
- assertProviderCurrent `private assertProviderCurrent(provider: SubagentProvider): void` — A pending start must use the exact provider whose capabilities were checked. */
- expectProvider `private expectProvider(name: string): SubagentProvider` — Look up a provider for dispatch or fail loud. */
- requireManager `private requireManager(): SubagentManager` — Resolve the subagent manager or fail loud. */
- assertCapabilities `private assertCapabilities(provider: SubagentProvider, request: SubagentStartRequest): void` — Reject the first requested capability that the provider lacks. */

### `subprocess` — `@deepseek-ai/dsh-subprocess`

- 提供类型：`SubprocessRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-subprocess` (`packages/subprocess/subprocess/src/index.ts:124`，class)
- 提供方：`@deepseek-ai/dsh-subprocess` (`packages/subprocess/subprocess/src/index.ts:126`)
- 消费方：@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via inject)、@deepseek-ai/dsh-workspace-changes(`packages/deliverables/workspace-changes/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-cua-macos(`packages/experimental/cua-macos/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-speech-to-text-sensevoice(`packages/experimental/speech-to-text-sensevoice/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs-search(`packages/fs/tool-fs-search/src/index.ts` via inject)、@deepseek-ai/dsh-host-open-in-app(`packages/host/open-in-app/src/index.ts` via inject)、@deepseek-ai/dsh-lsp-stdio(`packages/lsp/lsp-stdio/src/index.ts` via inject)、@deepseek-ai/dsh-ptc-runtime-node(`packages/ptc-runtime/ptc-runtime-node/src/index.ts` via inject)、@deepseek-ai/dsh-bash-local(`packages/shell/bash-local/src/index.ts` via inject)、@deepseek-ai/dsh-bash-sandbox(`packages/shell/bash-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-pwsh-local(`packages/shell/pwsh-local/src/index.ts` via inject)、@deepseek-ai/dsh-pwsh-sandbox(`packages/shell/pwsh-sandbox/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-acp(`packages/subagent/subagent-acp/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-claude-code(`packages/subagent/subagent-claude-code/src/index.ts` via inject)、@deepseek-ai/dsh-subagent-codex(`packages/subagent/subagent-codex/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-bash(`packages/terminal/terminal-bash/src/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)

- resolveExecutable `abstract resolveExecutable( command: string, env?: Readonly<Record<string, string>>, signal?: AbortSignal, ): Promise<string>` — Resolve one configured executable in this provider's execution world. Absolute paths are verified; bare names use the provider's scrubbed PATH plus explicit environment overrides. Relative paths containing separators are rejected: the resolution base is undefined, so providers fail loud instead of guessing.
- terminalEnvironment `abstract terminalEnvironment(signal?: AbortSignal): Promise<SubprocessTerminalEnvironment>` — Inspect shell-selection facts in the provider's execution environment.
- spawn `abstract spawn(spec: SubprocessSpawnSpec): SubprocessHandle` — Start one managed child process from a fully-specified spec; this seam applies no defaults.
- spawnTerminal `abstract spawnTerminal(spec: SubprocessTerminalSpawnSpec): Promise<SubprocessTerminalHandle>` — Allocate a real terminal and start one owned process session. This is the only non-pipe process primitive: implementations own terminal byte I/O, foreground groups, signals, and whole-session quiescence.

### `systemPrompt` — `@deepseek-ai/dsh-system-prompt`

- 提供类型：`SystemPrompt`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-system-prompt` (`packages/core/system-prompt/src/index.ts:436`，class)
- 提供方：`@deepseek-ai/dsh-system-prompt` (`packages/core/system-prompt/src/index.ts:453`)
- 消费方：@deepseek-ai/dsh-harness-dev-context(`packages/context/harness-dev-context/src/index.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-tools(`packages/core/tools/src/index.ts` via inject)、@deepseek-ai/dsh-deliverable-file-references(`packages/deliverables/deliverable-file-references/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-chrome-devtools-mcp(`packages/experimental/browser-use-chrome-devtools-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-playwright-mcp(`packages/experimental/browser-use-playwright-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-stagehand-native(`packages/experimental/browser-use-stagehand-native/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-computer-use-cua-driver-native(`packages/experimental/computer-use-cua-driver-native/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-cua-macos(`packages/experimental/cua-macos/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-panel(`packages/experimental/terminal-panel/src/index.ts` via inject)、@deepseek-ai/dsh-tool-ralph(`packages/experimental/tool-ralph/src/index.ts` via inject)、@deepseek-ai/dsh-tool-session-query(`packages/experimental/tool-session-query/src/index.ts` via inject)、@deepseek-ai/dsh-tool-terminal(`packages/experimental/tool-terminal/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs-search(`packages/fs/tool-fs-search/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-goal(`packages/goal/tool-goal/src/index.ts` via inject)、@deepseek-ai/dsh-tool-jobs(`packages/jobs/tool-jobs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-lsp(`packages/lsp/tool-lsp/src/index.ts` via inject)、@deepseek-ai/dsh-plan-mode(`packages/plan/plan-mode/src/index.ts` via inject)、@deepseek-ai/dsh-persona(`packages/preset/persona/src/index.ts` via inject)、@deepseek-ai/dsh-tool-schedule(`packages/schedule/tool-schedule/src/index.ts` via inject)、@deepseek-ai/dsh-working-directory(`packages/session/working-directory/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent-control(`packages/subagent/tool-subagent-control/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-agent-team(`packages/team/tool-agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-tool-web(`packages/web/tool-web/src/index.ts` via inject)、@deepseek-ai/dsh-tool-workflow(`packages/workflow/tool-workflow/src/index.ts` via inject)

- section `section(section: PromptSection): () => void` — Register an ordered prompt section in the calling context's scope. A scoped section shadows a global section with the same name; duplicates within one layer and non-finite orders throw. Registration and disposal emit `system-prompt/change`.
- getSectionOrder `getSectionOrder(name: PromptSectionOrderName): number` — Resolve the centrally owned placement of a repository prompt section.
- getContextOrder `getContextOrder(name: PromptContextOrderName): number` — Resolve the centrally owned placement of a repository runtime context.
- context `context(context: PromptContext): () => void` — Register ordered dynamic context in the calling context's scope. Scoped entries shadow global entries with the same name.
- suppressRuntimeContext `suppressRuntimeContext(): () => void` — Suppress optional dynamic runtime-context contributions in the calling context's scope without changing the services that own or enforce those facts. Multiple suppressors remain independently disposable.
- tools `tools(provider: (context: AssembleContext) => ToolProviderResult): () => void` — Register a tool-schema provider in the calling context's scope. Global and matching scoped providers both contribute; returning the reserved {@link TOOL_ORDER_REST} name makes assembly fail.
- variable `variable(name: string, provider: (context: AssembleContext) => string \| undefined): () => void` — Register a prompt variable in the calling context's scope. Scoped values shadow globals; invalid or duplicate names throw. A provider may return `undefined`, but rendering a section that references that value then fails.
- refreshContext `refreshContext(assembly: PromptAssembly, context: AssembleContext = {}): PromptAssembly` — Refresh accepted registered runtime facts for request admission. Contexts added only by the assembly waterfall retain their accepted values. Current suppression removes optional contexts, and missing required registrations are restored in registry order. Sections, tools, and interpolation variables retain the accepted assembly; their providers and waterfall do not rerun.
- assemble `async assemble(context: AssembleContext = {}): Promise<PromptAssembly>` — Assemble global and scoped providers, detach tool parameters, apply canonical ordering, then run the presentation waterfall. Scoped sections and variables shadow globals. The waterfall's text is authoritative except that an effective complete section is restored afterwards as the sole prompt section; tool declarations stay provider-owned. Keep configuration failures on the declared asynchronous error path.
- scopeTarget `scopeTarget(this, scope), 'system-prompt/assemble', assembly, context,`

### `terminalController` — `@deepseek-ai/dsh-api-terminal-controller`

> Interactive user terminals, separate from the Agent terminal tool registry. */

- 提供类型：`TerminalController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-terminal-controller` (`packages/api/terminal-controller/src/index.ts:108`，class)
- 提供方：`@deepseek-ai/dsh-api-terminal-controller` (`packages/api/terminal-controller/src/index.ts:137`)
- 消费方：@deepseek-ai/dsh-terminal-panel(`packages/experimental/terminal-panel/src/index.ts` via inject)

- environment `environment(agent: Agent, signal: AbortSignal): TerminalEnvironment` — Read the Session's current directory and terminal limits without filesystem validation or shell lookup.  *(decorators: @@Remote)*
- shells `shells(agent: Agent, signal: AbortSignal): Promise<TerminalShell[]>` — Discover installed shells in the Session's execution environment.  *(decorators: @@Remote)*
- list `list(sessionId: SessionId): WebTerminalInfo[]` — List retained terminals without resolving or activating an Agent.  *(decorators: @@Remote)*
- create `async create(agent: Agent, request: TerminalCreateRequest, signal: AbortSignal): Promise<WebTerminalInfo>` — Allocate a user shell once for a caller-generated identity, without Agent sandbox or approval restrictions.  *(decorators: @@Remote)*
- openForAgent `async openForAgent(agent: Agent, request: AgentTerminalRequest, signal: AbortSignal): Promise<AgentTerminal>` — Open a terminal for the Session's Agent under a caller-resolved sandbox policy; it appears in every window that watches the Session and passes to the person on the person's first typed input.
- readScreen `readScreen(agent: Agent, id: WebTerminalId, request: TerminalScreenRequest): Promise<TerminalScreenPage>` — Render a page of any terminal in the Agent's Session, including terminals the person opened.
- inspectActivity `inspectActivity(agent: Agent, id: WebTerminalId): Promise<'idle' \| 'busy' \| 'unknown'>` — Observe whether a Session terminal's shell is running a command.
- retain `retain(sessionId: SessionId, id: WebTerminalId, signal: AbortSignal): AsyncIterable<TerminalRetentionFrame>` — Retain an existing terminal for a window without activating its Agent or taking input control.  *(decorators: @@Remote({ mode: 'stream' }))*
- attach `attach(agent: Agent, id: WebTerminalId, signal: AbortSignal): RemoteStream<TerminalFrame, TerminalInput>` — Attach terminal input and output to one physical Remote stream.  *(decorators: @@Remote({ mode: 'stream' }))*
- rename `rename(agent: Agent, id: WebTerminalId, title: string): void` — Rename a terminal without changing its shell.  *(decorators: @@Remote)*
- close `async close(agent: Agent, id: WebTerminalId): Promise<void>` — Close an identity to future creation and kill its process range; repeated closes succeed.  *(decorators: @@Remote)*
- owner `private owner(agent: Agent): OwnedSession`
- disposeOwner `private disposeOwner(id: SessionId, owner: OwnedSession): Promise<void>`
- changed `private changed(sessionId: SessionId): void`
- requireCapacity `private requireCapacity(owner: OwnedSession): void`
- allocate `private async allocate( agent: Agent, owner: OwnedSession, id: WebTerminalId, prepare: (signal: AbortSignal) => Promise<TerminalLaunch>, signal: AbortSignal, ): Promise<BrowserTerm…`
- userLaunch `private async userLaunch(agent: Agent, request: TerminalCreateRequest, signal: AbortSignal): Promise<TerminalLaunch>`
- agentLaunch `private async agentLaunch(agent: Agent, id: WebTerminalId, request: AgentTerminalRequest, signal: AbortSignal): Promise<TerminalLaunch>`
- removeHistory `private async removeHistory(subprocess: Context['subprocess'], path: string): Promise<void>` — Delete a confined Agent shell's history file in its execution environment after the shell ends.
- agentShell `private async agentShell(agent: Agent, preferred: readonly string[], signal: AbortSignal): Promise<TerminalShell>`
- confine `private async confine( agent: Agent, argv: readonly string[], policy: SandboxExecutionPolicy, signal: AbortSignal, ): Promise<readonly string[]>`
- terminal `private terminal(agent: Agent, id: WebTerminalId): BrowserTerminal`
- requireOpen `private requireOpen(owner: OwnedSession, id: WebTerminalId): void`
- dimensions `private dimensions(cols: number, rows: number): void`
- execution `private execution(agent: Agent):`
- spawn `private async spawn( agent: Agent, owner: OwnedSession, id: WebTerminalId, prepare: (signal: AbortSignal) => Promise<TerminalLaunch>, signal: AbortSignal, ): Promise<BrowserTermina…`

### `terminals` — `@deepseek-ai/dsh-terminal`

- 提供类型：`TerminalSessionService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-terminal` (`packages/terminal/terminal/src/index.ts:86`，class)
- 提供方：`@deepseek-ai/dsh-terminal` (`packages/terminal/terminal/src/index.ts:97`)
- 消费方：@deepseek-ai/dsh-terminal-panel(`packages/experimental/terminal-panel/src/index.ts` via inject)、@deepseek-ai/dsh-tool-terminal(`packages/experimental/tool-terminal/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash-persistent(`packages/shell/tool-bash-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh-persistent(`packages/shell/tool-pwsh-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-bash(`packages/terminal/terminal-bash/src/index.ts` via inject)

- registerBackend `registerBackend(backend: TerminalBackend): () => void` — Register one backend type for this effect scope.
- listBackends `listBackends(): string[]` — List registered backend types in registration order.
- spawn `async spawn(owner: Agent, request: TerminalSpawnRequest, signal?: AbortSignal): Promise<TerminalSpawnResult>` — Create and publish one owner-scoped session after backend setup succeeds.
- releaseName `releaseName()`
- hasOwnerActivity `hasOwnerActivity(owner: Agent): boolean` — Test whether an exact owner has a published session or unpublished spawn.
- startSend `startSend(owner: Agent, id: TerminalSessionId, request: TerminalSendRequest): TerminalSendOperation` — Start one exclusive interactive send.
- read `read(owner: Agent, id: TerminalSessionId, request: TerminalReadRequest = {}): TerminalReadResult` — Read one bounded scrollback page from an owned session.
- signal `signal(owner: Agent, id: TerminalSessionId, signal: TerminalSignal): Promise<TerminalSignalResult>` — Deliver an allowed signal through an owned backend session.
- kill `async kill(owner: Agent, id: TerminalSessionId, reason: string = 'model request'): Promise<boolean>` — Close one owned session and remove it only after quiescent backend cleanup.
- list `list(owner: Agent): TerminalSessionSnapshot[]` — List fresh snapshots for exactly one owner.
- assertActive `private assertActive(): void`
- isLiveOwner `private isLiveOwner(owner: Agent): boolean`
- ensureOwnerCleanup `private ensureOwnerCleanup(owner: Agent): void`
- reserveName `private reserveName(owner: Agent, name: string \| undefined): () => void`
- reserveSpawn `private reserveSpawn(owner: Agent): SpawnReservation`
- removePendingSpawn `private removePendingSpawn(pending: PendingSpawn): void`
- abortPendingSpawns `private async abortPendingSpawns(owner: Agent \| undefined, reason: TerminalError): Promise<void>`
- expectOwned `private expectOwned(owner: Agent, id: TerminalSessionId): SessionRecord`
- snapshot `private snapshot(record: SessionRecord): TerminalSessionSnapshot`
- snapshot `private snapshot(record: SessionRecord, motd: string): TerminalSpawnResult`
- snapshot `private snapshot(record: SessionRecord, motd?: string): TerminalSpawnResult \| TerminalSessionSnapshot`
- abortAndClose `private async abortAndClose(owner: Agent \| undefined, abortReason: TerminalError, closeReason: string): Promise<void>`
- disposeOwned `private async disposeOwned(owner: Agent): Promise<void>`
- disposeAll `private async disposeAll(): Promise<void>`
- closeRecords `private async closeRecords(records: SessionRecord[], reason: string): Promise<void>`

### `theme` — `@deepseek-ai/dsh-client-ui-theme`

- 提供类型：`ThemeRuntime`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-theme` (`packages/client/ui-theme/src/client/index.ts:181`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-theme` (`packages/client/ui-theme/src/client/index.ts:609`)
- 消费方：@deepseek-ai/dsh-client-ui-layout(`packages/client/ui-layout/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-settings-account(`packages/client/ui-settings-account/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)、@deepseek-ai/dsh-cordis-client-runner(`packages/extensions/cordis-client-runner/src/client/providers.ts` via ctx.get)

- installFontSizeShortcuts `installFontSizeShortcuts(ctx, (delta) => { this.adjustFontSizes(delta) })`
- getTheme `getTheme(): ThemeSnapshot` — Read the current immutable theme snapshot.
- exportInspectTokens `exportInspectTokens(): ThemeTokenInspection[]` — Export the current token directory without reading DOM or computed styles.
- setTheme `setTheme(id: string): void` — Switch the theme preference — the only user preference write entry. Built-in preferences are written through the settings scope and every accepted value emits `theme/change`.
- setFontSize `setFontSize(role: FontRole, px: number): void` — Change one role's font size. Accepted values are written through the settings scope and emit `theme/change`.
- adjustFontSizes `private adjustFontSizes(delta: 1 \| -1): void` — Step all font sizes within their own ranges and save changed fields in one mutation. Emits one `theme/change`; no write or event occurs when every role is at its limit.
- setFontFamily `setFontFamily(role: FontRole, value: string): void` — Change one role's font list — the only font-family write entry. The value is normalized, written through the settings scope, and emits `theme/change` when the normalized list differs.
- write `private write(operation: () => Promise<boolean>): void` — Queue one settings write, then adopt the durable section once no own write remains. */
- adopt `private adopt(): void` — Adopt the scope's accepted durable preference without writing it back. */
- register `register(definition: ThemeDefinition): () => void` — Register a theme. Duplicate id throws (single occupant per id; the built-in pair counts; `system` is a preference, not a registrable id). optional icon replacements; the runtime keeps a frozen copy of `icons`. Invalid icon replacements throw a `TypeError` naming the theme and icon. resets the preference to the default so the UI never keeps tokens of an unregistered theme.
- overrideTokens `overrideTokens(source: string, tokens: ThemeTokenOverrides): () => void` — Stack a token override layer on top of the active theme — the token-level analogue of slot shading: the base theme stays untouched, layers compose in seq order with later layers winning per-token, and removing a layer restores whatever it covered. Calling again with the same source replaces that source's whole layer and restacks it on top (effect re-registration semantics). Emits `theme/change` with the recomposed snapshot. pass their package id — the façade pins it, so it also names the layer's origin for inspection). runtime (model-authored callers reach this boundary with untyped JS); a bare string value throws a teaching error. once the source has re-overridden (the newer layer is not torn down).
- buildSnapshot `private buildSnapshot(): ThemeSnapshot`
- composeActive `private composeActive(active: ThemeDefinition): ThemeDefinition` — Fold the override layers into the active definition: seq order, later layers win per-token, each value picked for the active color scheme (the presenter consumes the composed snapshot and needs no override awareness). Without layers the registered definition passes through by identity.
- publish `private publish(): void`

### `tokenMeter` — `@deepseek-ai/dsh-token-meter`

- 提供类型：`TokenMeter`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-token-meter` (`packages/llm/token-meter/src/index.ts:87`，class)
- 提供方：`@deepseek-ai/dsh-token-meter` (`packages/llm/token-meter/src/index.ts:99`)
- 消费方：@deepseek-ai/dsh-compaction-basic(`packages/compaction/compaction-basic/src/index.ts` via inject)、@deepseek-ai/dsh-compaction-tool-result-pruner(`packages/compaction/compaction-tool-result-pruner/src/index.ts` via inject)、@deepseek-ai/dsh-acp(`packages/acp/acp/src/updates.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)

- validateConfigKeys `validateConfigKeys(config)`
- contextPressure `contextPressure(session: Session): Pick<ContextPressureProjection, 'pressureTokens' \| 'contextWindow'>` — Read the latest logged provider prompt size and route capacity.
- measure `measure(session: Session, requestHeader?: EpochHeader): TokenMeasurement` — Measure current request pressure and surface through the durable tail. The effective envelope's routed provider/model selects the request-image pricing every node is priced under: a route whose adapter declares image pricing charges each retained image its visual tokens plus its model-visible text, while other routes keep the fixed heuristic. Provider usage is reused only when the latest successful call's canonical request envelope matches `requestHeader` and its total is no lower than that call's full route-priced anchor; otherwise the complete envelope and surface are repriced. The anchor includes all surface nodes immediately before the assistant message, including inputs admitted after step/start. `requestHeader` replaces the latest logged envelope for pressure and node pricing; the node set always describes the current session surface. Every call clones those positional nodes, so measurement is O(surface).
- _routeImagePricing `private _routeImagePricing(header: EpochHeader \| undefined): LlmImageRequestPricing \| undefined` — Resolve the routed model's image pricing, when the llm service and route declare one. */
- _fileRequestText `private _fileRequestText(): ( (ref: Parameters<LlmRuntime['fileRequestText']>[0]) => string ) \| undefined` — Resolve request-time file projection when an LLM service is mounted. */
- estimateMessage `estimateMessage(message: Message): number` — Heuristically price one model-visible message (instance face of the pure `estimateMessage` export from `estimate.ts`).
- _cachedHeader `private _cachedHeader(state: ReplayState, seq: SessionSeqType \| null): EpochHeader \| undefined` — Resolve one of the two header payloads retained by the rebuildable price cache. */
- _sync `private _sync(session: Session, useProjection = true):` — Catch rebuildable prices up to the current durable tail. */
- advanceMeasurement `advanceMeasurement(measurement, event)`
- _foldEvent `private _foldEvent(state: ReplayState, event: SessionEvent): void` — Update only discardable positional prices and the pre-assistant view. */

### `toolResultPruner` — `@deepseek-ai/dsh-compaction-tool-result-pruner`

- 提供类型：`ToolResultPruner`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-compaction-tool-result-pruner` (`packages/compaction/compaction-tool-result-pruner/src/index.ts:44`，class)
- 提供方：`@deepseek-ai/dsh-compaction-tool-result-pruner` (`packages/compaction/compaction-tool-result-pruner/src/index.ts:59`)
- 消费方：@deepseek-ai/dsh-compaction-basic(`packages/compaction/compaction-basic/src/index.ts` via ctx.get)、@deepseek-ai/dsh-compaction-basic(`packages/compaction/compaction-basic/src/index.ts` via ctx.get)

- measureContent `measureContent(blocks: readonly ContentBlock[]): number` — Measure text content in Unicode code points; non-text blocks cost zero.
- pruneContent `pruneContent(blocks: readonly ContentBlock[]): ContentBlock[] \| null` — Replace an over-budget text middle while retaining rich-block order. Text slicing is by Unicode code point, not UTF-16 code unit, so a retained boundary cannot split a surrogate pair. Grapheme clusters may still split.
- pruneSession `pruneSession(session: Session): PruneResult` — Prune every over-budget tool result from one stable current-surface snapshot. Each replacement preserves the complete event data except for `content`, cites the shadowed node so replay can recover the replacement input, and is immediately preceded by a `compaction/prune` shadow-price event pricing the shadowed node through the injected token meter, so pure consumers can subtract it without per-node state. earlier in the pass remain durable.

### `tools` — `@deepseek-ai/dsh-tools`

- 提供类型：`ToolsService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-tools` (`packages/core/tools/src/index.ts:99`，class)
- 提供方：`@deepseek-ai/dsh-tools` (`packages/core/tools/src/index.ts:112`)
- 消费方：@deepseek-ai/dsh-plugin-manager(`packages/boot/plugin-manager/src/tools.ts` via inject)、@deepseek-ai/dsh-plugin-market(`packages/boot/plugin-market/src/tools.ts` via inject)、@deepseek-ai/dsh-agent-loop(`packages/core/agent-loop/src/index.ts` via inject)、@deepseek-ai/dsh-agent-tool-presentation(`packages/core/agent-tool-presentation/src/index.ts` via inject)、@deepseek-ai/dsh-tool-executor-native(`packages/core/tool-executor-native/src/index.ts` via inject)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-tool-present(`packages/deliverables/tool-present/src/index.ts` via inject)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via inject)、@deepseek-ai/dsh-action-cards(`packages/experimental/action-cards/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-chrome-devtools-mcp(`packages/experimental/browser-use-chrome-devtools-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-playwright-mcp(`packages/experimental/browser-use-playwright-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-stagehand-native(`packages/experimental/browser-use-stagehand-native/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-computer-use-cua-driver-mcp(`packages/experimental/computer-use-cua-driver-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-computer-use-cua-driver-native(`packages/experimental/computer-use-cua-driver-native/src/index.ts` via inject)、@deepseek-ai/dsh-creation-recommendations(`packages/experimental/creation-recommendations/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-cua-macos(`packages/experimental/cua-macos/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-panel(`packages/experimental/terminal-panel/src/index.ts` via inject)、@deepseek-ai/dsh-tool-ralph(`packages/experimental/tool-ralph/src/index.ts` via inject)、@deepseek-ai/dsh-tool-session-query(`packages/experimental/tool-session-query/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-tool-subagent-oar(`packages/experimental/tool-subagent-oar/src/index.ts` via inject)、@deepseek-ai/dsh-tool-terminal(`packages/experimental/tool-terminal/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-tool-worktree(`packages/experimental/tool-worktree/src/index.ts` via inject)、@deepseek-ai/dsh-cordis-host-runner(`packages/extensions/cordis-host-runner/src/index.ts` via inject)、@deepseek-ai/dsh-tool-cordis(`packages/extensions/tool-cordis/src/host.ts` via inject)、@deepseek-ai/dsh-tool-cordis(`packages/extensions/tool-cordis/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs-search(`packages/fs/tool-fs-search/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-str-replace-editor(`packages/fs/tool-str-replace-editor/src/index.ts` via inject)、@deepseek-ai/dsh-tool-goal(`packages/goal/tool-goal/src/index.ts` via inject)、@deepseek-ai/dsh-tool-call-timeout-policy(`packages/guard/timeout-policy/src/index.ts` via inject)、@deepseek-ai/dsh-tool-ask-user(`packages/interaction/tool-ask-user/src/index.ts` via inject)、@deepseek-ai/dsh-tool-jobs(`packages/jobs/tool-jobs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-lsp(`packages/lsp/tool-lsp/src/index.ts` via inject)、@deepseek-ai/dsh-mcp-client(`packages/mcp/mcp-client/src/index.ts` via inject)、@deepseek-ai/dsh-mcp-manager(`packages/mcp/mcp-manager/src/index.ts` via inject)、@deepseek-ai/dsh-mcp-resources(`packages/mcp/mcp-resources/src/index.ts` via inject)、@deepseek-ai/dsh-plan-mode(`packages/plan/plan-mode/src/index.ts` via inject)、@deepseek-ai/dsh-tool-schedule(`packages/schedule/tool-schedule/src/index.ts` via inject)、@deepseek-ai/dsh-session-checkpoint-policy(`packages/session/session-checkpoint-policy/src/index.ts` via inject)、@deepseek-ai/dsh-tool-working-directory(`packages/session/tool-working-directory/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash-persistent(`packages/shell/tool-bash-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh-persistent(`packages/shell/tool-pwsh-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via inject)、@deepseek-ai/dsh-tool-skill(`packages/skill/tool-skill/src/index.ts` via inject)、@deepseek-ai/dsh-tool-workspace-dependencies(`packages/skill/tool-workspace-dependencies/src/index.ts` via inject)、@deepseek-ai/dsh-spill-policy(`packages/spill/spill-policy/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent-control(`packages/subagent/tool-subagent-control/src/index.ts` via inject)、@deepseek-ai/dsh-tool-subagent(`packages/subagent/tool-subagent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-agent-team(`packages/team/tool-agent-team/src/index.ts` via inject)、@deepseek-ai/dsh-tool-todo(`packages/todo/tool-todo/src/index.ts` via inject)、@deepseek-ai/dsh-tool-web(`packages/web/tool-web/src/index.ts` via inject)、@deepseek-ai/dsh-tool-workflow(`packages/workflow/tool-workflow/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)

- register `register(definition: ToolDefinition, options: ToolRegistrationOptions = {}): () => void` — Register globally or in the calling agent scope. Scoped tools shadow globals; duplicates within one layer and the reserved `run_code` name fail.
- assertSupportedJsonSchema `assertSupportedJsonSchema(output.schema)`
- restrict `restrict(filter: ToolRestriction): () => void` — Restrict global tools for the calling agent scope. Empty filters, unknown names, scope-local names, and reserved transport names fail. Restrictions intersect; scoped registrations remain visible.
- view `private view(scope?: ScopeKey): ToolView` — Resolve visible tools and pre-restriction names. Restrictions across the scope chain intersect over inherited global and ancestor tools; the viewing scope's own registrations remain exempt. Nearer registrations shadow farther ones. Pre-restriction names support restriction and prompt-order validation.
- get `get(name: string, scope?: ScopeKey, toolSet?: ResolvedToolSet): ToolDefinition \| undefined` — Look up a tool as one scope sees it (scoped shadows global; a restricted-away global reads as absent). Presenters pass the calling agent so the rendered card matches the definition that actually executed.
- executable `executable(name: string, scope?: ScopeKey, toolSet?: ResolvedToolSet): ToolDefinition \| undefined` — Resolve the definition a call may execute. With a step's admitted set, the set decides; without one, conditional registrations are unavailable.
- resolve `async resolve(context: ToolActivationContext): Promise<ResolvedToolSet>` — Resolve conditions once for this step without changing shared registrations. Cancellation or a rejected condition publishes no partial selection. Removed registrations cannot be restored by a late condition result.
- definitions `definitions(scope?: ScopeKey, toolSet?: ResolvedToolSet): readonly ToolDefinition[]` — Read the visible capability definitions for descriptions and program bindings.
- schemas `schemas(scope?: ScopeKey, toolSet?: ResolvedToolSet): ToolSchema[]` — Project visible definitions onto the allowlisted model-facing schema fields, excluding execution and presentation callbacks.
- setExecutor `setExecutor(executor: ToolExecutor): () => void` — Provide the executor for the calling scope; an unscoped contribution is the deployment default. Rendering any executor-owned section requires the viewing scope's selection to remain available.
- yield `yield () =>`
- selectExecutor `private selectExecutor(scope?: ScopeKey): ToolExecutor` — Resolve the nearest scoped provider, or the deployment default.
- execute `async execute(input: ToolBatchInput): Promise<ToolBatchResult>` — Delegate a raw call batch to its Agent's provider or the deployment default. Select at dispatch; accepted batches settle through that provider even if it unloads.
- guard `guard(guard: ToolGuard): () => void` — Register a monotonic denial in the calling scope.
- checkGuards `checkGuards(exec: ToolExecution): ToolGuardDenial \| undefined` — Check global and inherited guards after pre-execute policy and approval resolve.

### `translator` — `@deepseek-ai/dsh-experimental-translator`

> Experimental text translator with optional durable Session reuse. */

- 提供类型：`Translator`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-experimental-translator` (`packages/experimental/translator/src/index.ts:70`)
- 消费方：@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/index.ts` via inject)

- （方法未解析：提供类型不可达或未定义成员）

### `typert` — `@deepseek-ai/dsh-typert-protocol`

- 提供类型：`TypertRegistryContract`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-typert-protocol` (`packages/typert/protocol/src/types.ts:939`，interface)
- 提供方：`@deepseek-ai/dsh-typert-registry` (`packages/typert/registry/src/service.ts:518`)
- 消费方：@deepseek-ai/dsh-api-gateway(`packages/api/gateway/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-gateway(`packages/api/gateway/src/index.ts` via inject)、@deepseek-ai/dsh-api-job-controller(`packages/api/job-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/client/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/file-references.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-controller(`packages/api/workspace-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-files(`packages/api/workspace-files/src/index.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-api-speech-to-text(`packages/experimental/api-speech-to-text/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-cot-translation(`packages/experimental/client-ui-cot-translation/src/index.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via inject)、@deepseek-ai/dsh-typert-loader(`packages/typert/loader/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/source-access.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `typertGateway` — `@deepseek-ai/dsh-api-gateway`

> Host dispatcher for Typert Remote calls. */

- 提供类型：`TypertGateway`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-gateway` (`packages/api/gateway/src/types.ts:154`，interface)
- 提供方：`@deepseek-ai/dsh-api-gateway` (`packages/api/gateway/src/index.ts:243`)
- 消费方：@deepseek-ai/dsh-api-remotes(`packages/api/remotes/src/index.ts` via inject)、@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)、@deepseek-ai/dsh-experimental-webworker-runtime(`packages/experimental/webworker-runtime/src/worker-host.ts` via ctx.get)、@deepseek-ai/dsh-cordis-host-runner(`packages/extensions/cordis-host-runner/src/inspect-registry.ts` via ctx.get)

- hasLiveClient `hasLiveClient(): boolean` — Check for an active owner Client event stream, the only kind that can answer forwarded waterfalls.
- getPendingRemoteEvents `getPendingRemoteEvents(): readonly PendingRemoteEventInfo[]`
- registerRemoteEvents `registerRemoteEvents( source: TypertRemoteEventSource, host: RemoteEventHostInfo, ): () => Promise<void>` — Register the application-selected forwarded-event source.
- invoke `invoke(request: InvokeRemoteRequest): Promise<unknown>` — Invoke one live Remote method without assuming a carrier or response envelope.
- stream `stream(request: InvokeRemoteRequest): Promise<AsyncIterable<unknown>>` — Open one live stream Remote method without assuming a physical carrier.

### `uiConversation` — `@deepseek-ai/dsh-client-ui-conversation`

> Target-neutral Conversation registries and per-Session assembly. */

- 提供类型：`import('./conversation/assembly.ts').UiConversation`；方法覆盖：unresolved；asar 核对：—
- 提供方：`@deepseek-ai/dsh-client-ui-conversation` (`packages/client/ui-conversation/src/client/conversation/assembly.ts:222`)
- 消费方：@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-goal(`packages/client/ui-goal/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-plan(`packages/client/ui-plan/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-reference(`packages/client/ui-reference/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-secret-mask(`packages/client/ui-secret-mask/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-skill(`packages/client/ui-skill/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workflow-run(`packages/client/ui-workflow-run/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-stats(`packages/experimental/client-ui-stats/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)、@deepseek-ai/dsh-message-quotes(`packages/session/message-quotes/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/service.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `uiRenderer` — `@deepseek-ai/dsh-client-ui-renderer`

> Mount face provided after the UI renderer activates. */

- 提供类型：`UiRendererService`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-renderer` (`packages/client/ui-renderer/src/client/index.ts:24`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-renderer` (`packages/client/ui-renderer/src/client/index.ts:92`)
- 消费方：@deepseek-ai/dsh-client-test-runtime(`packages/test-support/client-runtime/src/assembly/test-client.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `uiSession` — `@deepseek-ai/dsh-client-ui-session`

> Session Controller adapter and session-scoped source registry. */

- 提供类型：`UiSession`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-session` (`packages/client/ui-session/src/client/index.ts:282`，class)
- 提供方：`@deepseek-ai/dsh-client-ui-session` (`packages/client/ui-session/src/client/index.ts:317`)
- 消费方：@deepseek-ai/dsh-client-ui-approval(`packages/client/ui-approval/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar-right(`packages/client/ui-sidebar-right/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-trajectory(`packages/client/ui-trajectory/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-user-questions(`packages/client/ui-user-questions/src/client/index.ts` via inject)、@deepseek-ai/dsh-experimental-session-inspector(`packages/experimental/session-inspector/src/client/index.ts` via inject)

- disposeList `disposeList()`
- disposeStatus `disposeStatus()`
- disposeRemoteStatus `disposeRemoteStatus()`
- bindingSource `bindingSource(reference: SessionReference \| undefined): HostObservable<StandardSourceBinding>` — Resolve a stable renderer source for an owned Session reference or explicit absence.
- whenAccess `whenAccess(sessionId: SessionId, action: RemoteEndpoint, callback: () => AccessEffect): () => void` — Keep `callback`'s effects installed while the current Peer may call `action` on one Session resource, with the semantics of `ctx.remoteAccess.whenAccess`: `useSessionAccess` answers the same question during render.
- registerPendingInteraction `registerPendingInteraction<T extends SessionPendingInteractionBase>( precedence: (interaction: T) => number, ): PendingInteractionPublisher<T>` — Register one pending-interaction domain and return its publication function. Domain teardown first removes its visible values, then delegates and awaits every still-active owner request.
- rebuildBindings `private rebuildBindings(): void`
- notifySubscribers `notifySubscribers(this.absent.listeners, '[ui-session] absent binding')`
- notifySubscribers `notifySubscribers(source.listeners, '[ui-session] Session binding')`
- sourceFor `private sourceFor(owner: SessionBinding): BindingSource`
- publishMain `private publishMain(): void`
- notifySubscribers `notifySubscribers(this.current.listeners, '[ui-session] main binding')`
- watchMainRetention `private watchMainRetention(sessionId: SessionId \| undefined): void`
- publishPendingInteractions `private publishPendingInteractions(): void`
- observeRunning `private observeRunning(sessionId: SessionId, running: boolean): void`
- reconcileStatus `private reconcileStatus(): void`
- isMain `private isMain(sessionId: SessionId): boolean`
- publishStatus `private publishStatus(): void`
- notifySubscribers `notifySubscribers(this.statusListeners, '[ui-session] Session status')`
- createMaterializedBinding `private createMaterializedBinding(owner: SessionBinding): MaterializedBinding`
- materialize `private materialize(binding: SessionBinding): ScopedStandardSourceBinding`
- validateContribution `validateContribution(descriptor, contribution)`
- copyDeclared `copyDeclared('hook', hooks, descriptor.hooks, contribution.hooks, finalProps)`
- copyDeclared `copyDeclared('keyed hook', keyedHooks, descriptor.keyedHooks, contribution.keyedHooks, finalProps)`
- copyDeclared `copyDeclared('prop', props, descriptor.props, contribution.props, finalProps)`
- materializeAbsent `private materializeAbsent(): StandardSourceBinding`
- declareAbsent `declareAbsent('hook', hooks, descriptor.hooks, finalProps)`
- declareAbsent `declareAbsent('keyed hook', keyedHooks, descriptor.keyedHooks, finalProps)`
- declareAbsent `declareAbsent('prop', props, descriptor.props, finalProps)`

### `uiWorkspace` — `@deepseek-ai/dsh-client-ui-workspace`

> Cross-Controller Workspace navigation and directory UI capability. */

- 提供类型：`UiWorkspace`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-workspace` (`packages/client/ui-workspace/src/client/navigation.ts:40`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-workspace` (`packages/client/ui-workspace/src/client/navigation.ts:195`)
- 消费方：@deepseek-ai/dsh-client-ui-chat(`packages/client/ui-chat/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-browse(`packages/client/ui-directory-picker-browse/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-directory-picker-native(`packages/client/ui-directory-picker-native/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-entry-customization(`packages/client/ui-entry-customization/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-subagent(`packages/client/ui-subagent/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workflow-run(`packages/client/ui-workflow-run/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-conversation(`packages/client/ui-conversation/src/client/apply.ts` via ctx.get)、@deepseek-ai/dsh-client-ui-sidebar(`packages/client/ui-sidebar/src/client/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/client/index.ts` via ctx.get)

- openSession `openSession(target: SessionTarget): void` — Select a Session and show its Conversation as one UI navigation action.
- openWorkspace `openWorkspace( workspaceId: WorkspaceId, beforeOpen?: (sessionId: SessionId) => void, options?: Pick<StartSessionOptions, 'agentPreset'>, ): Promise<void>` — Connect a Workspace and open its Session unless a later navigation supersedes it. skipped after supersession; a throw aborts the open and releases the retained reference. notice unless a later navigation or disposal superseded the request.
- forkSession `forkSession( sessionId: SessionId, onCreated?: (childId: SessionId) => void, options?: Pick<Parameters<ISessions['fork']>[0], 'allowMigration'>, ): Promise<SessionId>` — Fork a Session without changing the current selection.
- connectWorkspace `connectWorkspace(workspaceId: WorkspaceId, options?: Pick<StartSessionOptions, 'agentPreset'>): Promise<SessionId>` — Resolve the Session for a new conversation in a Workspace: navigation names the first reusable blank member — listed in the Workspace, not archived, and listing no preset or the requested one — and the Host reuses it under the requested preset or its default, creating another Session when it reuses none. Concurrent calls for the same Workspace and preset share one attempt.
- startSession `startSession(workspaceId?: WorkspaceId, options?: StartSessionOptions): void` — Open the Workspace blank `connectWorkspace` resolves, so New Session returns to that blank's unsent draft. A creation the Host refuses is shown through the Workspace notice and leaves the selection as it was. whether existing text or attachments are kept, replaced, or followed by the prompt.
- archiveSession `archiveSession(sessionId: SessionId, options?: { readonly stopActivity?: boolean }): Promise<void>` — Archive a Session and clear it when it is the current selection.
- unarchiveSession `unarchiveSession(sessionId: SessionId): Promise<void>` — Unarchive a Session, restoring it to its recorded Workspace position.
- pinSession `pinSession(sessionId: SessionId): Promise<void>` — Pin a Session on the Host, then lead it in its accounts' saved orders (its Workspace group or Ungrouped, and the flat list). The order write reads the memberships current at completion, so reorders that landed while the Host call was pending keep their positions.
- unpinSession `unpinSession(sessionId: SessionId): Promise<void>` — Unpin a Session on the Host; saved positions stay as they are.
- pickDirectory `pickDirectory(): Promise<string \| null>` — Open the Host-native directory picker.
- listDirectory `listDirectory(path?: string, signal?: AbortSignal): Promise<DirectoryListing>` — List one Host directory level.
- createDirectory `createDirectory(path: string, name: string): Promise<string>` — Create a child directory.
- whenAccess `whenAccess(workspaceId: WorkspaceId, action: RemoteEndpoint, callback: () => AccessEffect): () => void` — Keep `callback`'s effects installed while the current Peer may call `action` on one Workspace resource, with the semantics of `ctx.remoteAccess.whenAccess`: `useWorkspaceAccess` answers the same question during render.

### `userQuestionPanels` — `@deepseek-ai/dsh-client-ui-tool`

> Optional user-question answer-panel provider. */

- 提供类型：`UserQuestionPanels`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-client-ui-tool` (`packages/client/ui-tool/src/client/contract/slots.ts:109`，interface)
- 提供方：`@deepseek-ai/dsh-client-ui-user-questions` (`packages/client/ui-user-questions/src/client/index.ts:376`)
- 消费方：@deepseek-ai/dsh-client-ui-tool(`packages/client/ui-tool/src/client/tool/toolviews/ask-question-row.tsx` via ctx.get)、@deepseek-ai/dsh-client-ui-tool(`packages/client/ui-tool/src/client/tool/toolviews/ask-question-row.tsx` via ctx.get)

- reveal `reveal(sessionId: SessionIdOf, callId: string): boolean` — Put one call's answer panel back in the composer, ahead of any other pending question.
- review `review(sessionId: SessionIdOf, callId: string, record: UserQuestionRecord): boolean` — Show one settled call's recorded answers as a read-only panel, ahead of any other pending question. Closing that panel drops it for good; the row builds it again from the same record.

### `userQuestions` — `@deepseek-ai/dsh-user-questions`

- 提供类型：`UserQuestionService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-user-questions` (`packages/interaction/user-questions/src/index.ts:79`，class)
- 提供方：`@deepseek-ai/dsh-user-questions` (`packages/interaction/user-questions/src/index.ts:86`)
- 消费方：@deepseek-ai/dsh-tool-ask-user(`packages/interaction/tool-ask-user/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/application-access.ts` via ctx.get)、@deepseek-ai/dsh-cua(`packages/experimental/cua/src/mouse-control.ts` via ctx.get)、@deepseek-ai/dsh-plan-mode(`packages/plan/plan-mode/src/index.ts` via ctx.get)

- releaseReply `private releaseReply(session: Session, callId: ToolCallId, messageId: MessageId): void`
- assertLiveRoot `private assertLiveRoot(agent: Agent): void`
- continued `private continued(agent: Agent): readonly PendingUserQuestion[]`
- answer `answer(agent: Agent, callId: ToolCallId, answer: AskUserQuestionAnswer): boolean` — Answer a continued question. The reply is steered into the agent as a user message whose source names the call; that message is also the record that closes the question in the projection. queued until the agent admits its user message. question of the call exactly once, or `REPLY_QUEUED` when a reply is already waiting for admission.  *(decorators: @@Remote)*
- askTimed `async askTimed( request: AskUserQuestionRequest & { agent: Agent }, callId: ToolCallId, timeoutMs: number, ): Promise<TimedUserQuestionResult>` — Foreground wait whose first settlement the Client decides: the Client rejects with `ASK_TIMED_OUT` when its countdown ends, and this method maps that code to the pending result. result, also when no connected Client claimed the request by the deadline. or oversized wait.
- ask `async ask(request: AskUserQuestionRequest): Promise<AskUserQuestionAnswer>` — Ask the scoped answerer waterfall and wait for the user's answer. When a caller supplies an agent, human interaction is valid only for the exact live instance of an ordinary Session. Explicit subagent origin rejects delegated callers; historical ordinary forks may retain parent metadata and still ask normally. is already or becomes aborted, `CALLER_NOT_LIVE` when a supplied agent is not the registry's exact live instance, or `DELEGATED_CALLER` when that live agent has subagent origin.
- scopeTarget `scopeTarget(agent, agent),`

### `web` — `@deepseek-ai/dsh-web`

- 提供类型：`WebRuntime`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-web` (`packages/web/web/src/index.ts:82`，class)
- 提供方：`@deepseek-ai/dsh-web` (`packages/web/web/src/index.ts:99`)
- 消费方：@deepseek-ai/dsh-tool-web(`packages/web/tool-web/src/index.ts` via inject)、@deepseek-ai/dsh-web-deepseek-api(`packages/web/web-deepseek-api/src/index.ts` via inject)、@deepseek-ai/dsh-web-fetch-http(`packages/web/web-fetch-http/src/index.ts` via inject)、@deepseek-ai/dsh-web-search-deepseek(`packages/web/web-search-deepseek/src/index.ts` via inject)

- registerSearchProvider `registerSearchProvider(provider: WebSearchProvider): () => void` — Register a search provider. `listProviders()` lists it until the registration is disposed, which happens with the calling fiber or through the returned disposer; registration and disposal each emit `web/providers-changed`. Throws {@link WebError} `WEB_DUPLICATE_PROVIDER` if its id is already registered for search.
- registerFetchProvider `registerFetchProvider(provider: WebFetchProvider): () => void` — Register a fetch provider, with the listing, disposal, and event behavior of {@link WebRuntime.registerSearchProvider}. Throws {@link WebError} `WEB_DUPLICATE_PROVIDER` if its id is already registered for fetch.
- registerProvider `private registerProvider<P extends { readonly id: string }>(store: Map<string, P>, provider: P): () => void`
- emitChanged `emitChanged()`
- yield `yield () =>`
- listProviders `listProviders(): WebProviderList` — List every registered search and fetch provider for provider pickers. Availability does not filter the lists.  *(decorators: @@Remote)*
- emitProvidersChanged `private emitProvidersChanged(): void` — Emit `web/providers-changed`, containing each listener's failure so none vetoes the mutation. */
- warnListenerFailure `private warnListenerFailure(error: unknown): void`
- search `async search(request: WebSearchRequest, signal?: AbortSignal): Promise<WebSearchResult>` — Run one search through the selected provider. Resolves the provider at call time with the selection rules above; throws {@link WebError} when the capability cannot run. The seam enforces `request.maxResults` on the result: if the provider over-returns, `sources[]` is truncated and `truncated` set.
- searchReady `async searchReady(llmProvider?: string): Promise<boolean>` — Whether the provider `search()` would select can authenticate a search made for a model request on the `llmProvider` chat route. Asks only that provider's `ready()`; one without `ready()` counts as ready. Makes no network calls. A selection failure answers true, because `search()` reports that failure as a structured `WebError`.
- selectSearchProvider `private selectSearchProvider(): WebSearchProvider` — Select the search provider with the rules above, throwing the matching {@link WebError}. */
- fetch `async fetch(request: WebFetchRequest, signal?: AbortSignal): Promise<WebFetchResult>` — Retrieve one URL through the selected provider. Resolves the provider at call time with the selection rules above; throws {@link WebError} when the capability cannot run. A non-2xx response is a result, not a throw.
- fetchReady `async fetchReady(llmProvider?: string): Promise<boolean>` — Whether the provider `fetch()` would select can authenticate a fetch made for a model request on the `llmProvider` chat route. Asks only that provider's `ready()`; one without `ready()` counts as ready. Makes no network calls. A selection failure answers true, because `fetch()` reports that failure as a structured `WebError`.
- selectFetchProvider `private selectFetchProvider(): WebFetchProvider` — Select the fetch provider with the rules above, throwing the matching {@link WebError}. */

### `webApp` — `@deepseek-ai/dsh-web-app`

> The Web GUI this process serves; absent when no Web runtime is mounted. */

- 提供类型：`WebApp`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-web-app` (`packages/bundle/web-app/src/index.ts:31`，interface)
- 提供方：`@deepseek-ai/dsh-web-app` (`packages/bundle/web-app/src/index.ts:205`)
- 消费方：@deepseek-ai/dsh-harness-dev-context(`packages/context/harness-dev-context/src/index.ts` via inject)

- getAdvertisedUrl `getAdvertisedUrl(): string` — The URL this GUI advertises, also used for `DSH_WEB_URL` and the startup URL line.

### `webServer` — `@deepseek-ai/dsh-host-webserver`

- 提供类型：`WebServer`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-host-webserver` (`packages/host/webserver/src/index.ts:357`，class)
- 提供方：`@deepseek-ai/dsh-host-webserver` (`packages/host/webserver/src/index.ts:398`)
- 消费方：@deepseek-ai/dsh-web-app(`packages/bundle/web-app/src/index.ts` via inject)、@deepseek-ai/dsh-client-hmr(`packages/client/hmr/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-inspector(`packages/experimental/inspector/src/index.ts` via inject)、@deepseek-ai/dsh-webhook-github(`packages/experimental/webhook-github/src/index.ts` via inject)、@deepseek-ai/dsh-host-directory-picker-auto(`packages/host/directory-picker-auto/src/index.ts` via inject)、@deepseek-ai/dsh-host-frontend-static(`packages/host/frontend-static/src/index.ts` via inject)、@deepseek-ai/dsh-host-open-in-app(`packages/host/open-in-app/src/index.ts` via inject)、@deepseek-ai/dsh-client-connection(`packages/client/connection/src/rpc-host.ts` via ctx.get)、@deepseek-ai/dsh-deepseek-account(`packages/credentials/deepseek-account/src/index.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/viewer-assets.ts` via ctx.get)、@deepseek-ai/dsh-experimental-webworker-runtime(`packages/experimental/webworker-runtime/src/worker-host.ts` via ctx.get)

- getOrigin `getOrigin(): string` — The root URL local clients use to reach the bound listener: the protocol, the {@link bindUrlHost} form of the bind address, and the listening port.
- register `register(route: WebRoute \| WebResourceRoute): () => void` — Register a named route. Duplicate (kind, path) throws — route patterns are a composition-level contract, so a collision is a misconfiguration.
- registerUpgrade `registerUpgrade(route: WebUpgradeRoute): () => void` — Register an exact-path HTTP upgrade route. Duplicate paths throw because one socket can have only one protocol owner.
- registerFallback `registerFallback(fallback: WebRoute['handler'] \| Pick<WebResourceRoute, 'resource'>): () => void` — Claim the fallback seat: the handler or resource answering every request no named route matches (the SPA dist server in the shipped Web composition). One owner only — a second registration throws, because two fallbacks cannot compose. unmatched requests, or `{ resource }` answering them.
- readResource `async readResource(request: Request, peer: PeerScope): Promise<Response>` — Read the response an HTTP request for the same URL would receive, as the resource computes it for `peer`, without an HTTP exchange. The request path picks the responder by the HTTP match order — exact, longest prefix, then the fallback — and only a resource answers. This method checks no cookie, Host, or Origin: the caller admits the reader before reading. 405 with `Allow: GET, HEAD` for any other method, checked before matching, where over HTTP a handler route or an unmatched path answers such a method itself; 404 when the path matches a handler route, or reaches the fallback seat while it is unclaimed or holds a handler. A resource that throws rejects the read, where an HTTP request would receive 400.
- tapIndex `tapIndex(transform: (html: string) => string): () => void` — Register a raw-HTML index transform, the escape hatch for markup no {@link IndexInjection} row expresses: {@link renderIndex} applies taps in registration order after rendering the structured rows.
- readTlsFile `readTlsFile('certFile', certFile),`
- readTlsFile `readTlsFile('keyFile', keyFile),`
- resolve `resolve()`
- responderFor `private responderFor(pathname: string): WebRoute \| WebResourceRoute \| WebRoute['handler'] \| Pick<WebResourceRoute, 'resource'> \| undefined` — The responder for one request path, shared by HTTP requests and {@link readResource}: the matched named route, otherwise the fallback.
- match `private match(pathname: string): WebRoute \| WebResourceRoute \| undefined` — Longest-prefix-wins over the prefix table after an exact-table miss. */
- serveResource `private async serveResource(req: IncomingMessage, res: ServerResponse, target: URL, resource: WebResource): Promise<void>` — Answer one HTTP exchange from a resource. Only GET and HEAD reach it; any other method receives 405 and its request body is never read. The request becomes a Fetch `Request` without a Peer whose URL is the request target resolved against a placeholder origin, as the match reads it; the client's authority stays only in the `host` header. The connection closing before this method ends the response aborts the request signal and cancels the response body.
- applyIndexTaps `applyIndexTaps(html: string): string` — Run an index.html body through the registered taps in registration order — called by the fallback owner on every index response it renders.
- collectIndexInjections `collectIndexInjections(peer: PeerScope): IndexInjection[]` — Gather the structured injection table for one Peer: one `webserver/index-inject` emit, every subscriber pushes its current rows. Fresh per call, so subscribers read live state (module graph, theme preference, the Peer's access) at emit time.
- renderIndex `renderIndex(html: string, peer: PeerScope): string` — Render one index.html body for one Peer: the structured injection table first, then the raw `tapIndex` transforms over the result.

### `webTerminals` — `@deepseek-ai/dsh-api-terminal-controller`

> React-free browser terminal views and explicit process cleanup. */

- 提供类型：`ClientTerminals`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-terminal-controller` (`packages/api/terminal-controller/src/client/index.ts:42`，class)
- 提供方：`@deepseek-ai/dsh-api-terminal-controller` (`packages/api/terminal-controller/src/client/index.ts:64`)
- 消费方：@deepseek-ai/dsh-client-ui-sidebar-terminal(`packages/client/ui-sidebar-terminal/src/client/index.ts` via inject)

- view `view(sessionId: SessionId, key: string, contentId: string, terminalId?: WebTerminalId, shellPath?: string): TerminalView` — Return the stable model for one sidebar occurrence.
- watch `watch(sessionId: SessionId, listener: TerminalRosterListener): () => void` — Watch one Session's retained terminals; every watcher in this window shares one Host stream.
- boundTerminal `boundTerminal(sessionId: SessionId, contentId: string): WebTerminalId \| undefined` — Read the Host terminal a tab's content is bound to in this window.
- bind `bind(sessionId: SessionId, contentId: string, id: WebTerminalId): void` — Bind a just-opened tab to an existing Host terminal so reload and later mounts attach to it.
- isRepresented `isRepresented(sessionId: SessionId, id: WebTerminalId): boolean` — Report whether this window already shows, binds or is closing a terminal.
- inventory `private inventory(sessionId: SessionId): TerminalInventory`
- launchShells `async launchShells(sessionId: SessionId, signal: AbortSignal): Promise<TerminalLaunchShells>` — Discover available launch choices on demand without allocating a PTY.
- selectShell `selectShell(path: string): void` — Remember the guide selection before allocating its terminal tab.
- close `close(sessionId: SessionId, key: string, contentId: string, terminalId?: WebTerminalId): void` — Save a close intent and release the tab immediately; cleanup outlives DOM unmount and reload.
- retainTabs `retainTabs(tabs: readonly { sessionId: SessionId; tabId: string; contentId: string }[]): void` — Reconcile this window's open terminal occurrences, including dormant saved Sessions.
- hold `private hold(sessionId: SessionId, id: WebTerminalId): TerminalWindowHold`
- reconcileHolds `private reconcileHolds(): void`
- release `private release(hold: TerminalWindowHold): void`
- recover `async recover(sessionId: SessionId, refresh: boolean = false): Promise<WebTerminalInfo[]>` — Read shared Session discovery without a live view or unfinished close.
- retryClose `retryClose(id: WebTerminalId): void` — Retry a saved close request without reopening its tab.
- cleanup `private cleanup(record: TerminalCloseRequest, view?: TerminalView): void`

### `webhookRuntime` — `@deepseek-ai/dsh-webhook`

- 提供类型：`WebhookRuntime`；方法覆盖：resolved；asar 核对：—
- 方法来源：`@deepseek-ai/dsh-webhook` (`packages/experimental/webhook/src/index.ts:58`，class)
- 提供方：`@deepseek-ai/dsh-webhook` (`packages/experimental/webhook/src/index.ts:73`)
- 消费方：@deepseek-ai/dsh-webhook-github(`packages/experimental/webhook-github/src/index.ts` via inject)

- register `register<K extends string>(rule: WebhookRule<K>): () => Promise<void>` — Register one trusted programmatic rule.
- dispatch `dispatch<K extends string>(delivery: VerifiedWebhookDelivery<K>): void` — Start every currently matching rule and return before any callback settles.
- startInvocation `private startInvocation(registration: RuleRegistration, delivery: VerifiedWebhookDelivery): void` — Start one contained invocation and attach it to registration teardown. */
- disposeRegistration `private disposeRegistration(registration: RuleRegistration): Promise<void>` — Memoized registration teardown: hide, abort, then drain. */

### `workflowEngine` — `@deepseek-ai/dsh-workflow`

- 提供类型：`WorkflowEngine`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-workflow` (`packages/workflow/workflow/src/index.ts:157`，class)
- 提供方：`@deepseek-ai/dsh-workflow` (`packages/workflow/workflow/src/index.ts:159`)
- 消费方：@deepseek-ai/dsh-tool-ralph(`packages/experimental/tool-ralph/src/index.ts` via inject)、@deepseek-ai/dsh-tool-workflow(`packages/workflow/tool-workflow/src/index.ts` via inject)

- start `abstract start(request: WorkflowStartRequest): WorkflowRun` — Parse and execute a workflow script. optional cancel signal.
- emitWorkflowEvent `protected emitWorkflowEvent(name: WorkflowEventName, ...args: unknown[]): void` — Emit a lifecycle event while containing and logging each listener failure.

### `workingDirectory` — `@deepseek-ai/dsh-working-directory`

- 提供类型：`WorkingDirectoryService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-working-directory` (`packages/session/working-directory/src/index.ts:76`，class)
- 提供方：`@deepseek-ai/dsh-agent-loop-testkit` (`packages/test-support/agent-loop-testkit/src/working-directory-fixture.ts:13`)、`@deepseek-ai/dsh-working-directory` (`packages/session/working-directory/src/index.ts:92`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/skill-catalog.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via inject)、@deepseek-ai/dsh-agent-instructions(`packages/context/agent-instructions/src/index.ts` via inject)、@deepseek-ai/dsh-file-reference-local(`packages/context/file-reference-local/src/index.ts` via inject)、@deepseek-ai/dsh-tool-present(`packages/deliverables/tool-present/src/index.ts` via inject)、@deepseek-ai/dsh-tool-office(`packages/document/tool-office/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-auto-review(`packages/experimental/auto-review/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-chrome-devtools-mcp(`packages/experimental/browser-use-chrome-devtools-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-browser-use-playwright-mcp(`packages/experimental/browser-use-playwright-mcp/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/index.ts` via inject)、@deepseek-ai/dsh-hooks-claude-code(`packages/experimental/hooks-claude-code/src/index.ts` via inject)、@deepseek-ai/dsh-hooks-codex(`packages/experimental/hooks-codex/src/index.ts` via inject)、@deepseek-ai/dsh-tool-terminal(`packages/experimental/tool-terminal/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-worktree(`packages/experimental/worktree/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs-search(`packages/fs/tool-fs-search/src/index.ts` via inject)、@deepseek-ai/dsh-tool-fs(`packages/fs/tool-fs/src/index.ts` via inject)、@deepseek-ai/dsh-tool-lsp(`packages/lsp/tool-lsp/src/index.ts` via inject)、@deepseek-ai/dsh-sdk-jsonrpc-server(`packages/sdk/server/src/index.ts` via inject)、@deepseek-ai/dsh-tool-working-directory(`packages/session/tool-working-directory/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash-persistent(`packages/shell/tool-bash-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-bash(`packages/shell/tool-bash/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh-persistent(`packages/shell/tool-pwsh-persistent/src/index.ts` via inject)、@deepseek-ai/dsh-tool-pwsh(`packages/shell/tool-pwsh/src/index.ts` via inject)、@deepseek-ai/dsh-tool-skill(`packages/skill/tool-skill/src/index.ts` via inject)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/index.ts` via inject)、@deepseek-ai/dsh-terminal-bash(`packages/terminal/terminal-bash/src/index.ts` via inject)、@deepseek-ai/dsh-workflow-ptc(`packages/workflow/workflow-ptc/src/index.ts` via inject)、@deepseek-ai/dsh-api-terminal-controller(`packages/api/terminal-controller/src/index.ts` via ctx.get)、@deepseek-ai/dsh-tool-executor-ptc(`packages/core/tool-executor-ptc/src/ptc.ts` via ctx.get)、@deepseek-ai/dsh-experimental-browser-use-runtime(`packages/experimental/browser-use-runtime/src/mcp.ts` via ctx.get)、@deepseek-ai/dsh-experimental-claude-code-mods(`packages/experimental/claude-code-mods/src/host-ops.ts` via ctx.get)

- get `get(session: Session): string` — Read the committed directory without filesystem I/O.
- ensure `ensure(agent: Agent, signal?: AbortSignal): Promise<string>` — Validate the current directory and restore the original project when it disappeared. A notice failure is warned without reverting the committed state. unavailable or the service is disposed, or the rejection of a `working-directory/access` listener.
- set `set(agent: Agent, path: string, signal?: AbortSignal): Promise<string>` — Change one Session's directory without changing existing processes or permissions. A notice failure is warned; the next request still receives the committed directory. `WORKING_DIRECTORY_NOT_FOUND` when the path is not an existing directory, or the rejection of a `working-directory/access` listener.
- contextText `private contextText(session: Session): string`
- directory `private async directory( path: string, cwd: string, signal: AbortSignal, missing = (): WorkingDirectoryError => new WorkingDirectoryError( `working-directory: directory does not ex…`
- commit `private commit(agent: Agent, directory: string, recovered: boolean, signal: AbortSignal): void`
- serialize `private serialize<T>(agent: Agent, signal: AbortSignal \| undefined, action: (signal: AbortSignal) => Promise<T>): Promise<T>`

### `workspaceChanges` — `@deepseek-ai/dsh-workspace-changes`

> Per-turn changed-file summaries and comparisons of live Sessions. */

- 提供类型：`WorkspaceChanges`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-workspace-changes` (`packages/deliverables/workspace-changes/src/types.ts:79`，interface)
- 提供方：`@deepseek-ai/dsh-workspace-changes` (`packages/deliverables/workspace-changes/src/index.ts:120`)
- 消费方：@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)

- summary `summary(sessionId: SessionId, seq: number): WorkspaceChangesSummary \| undefined` — The summary announced by one `workspace/changes` event.
- diff `diff(sessionId: SessionId, seq: number, index: number, signal: AbortSignal): Promise<WorkspaceFileDiff \| undefined>` — Compare one listed file's contents at turn start and turn end.

### `workspaceController` — `@deepseek-ai/dsh-api-workspace-controller`

> Host Workspace business API and Remote namespace owner. */

- 提供类型：`WorkspaceController`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-workspace-controller` (`packages/api/workspace-controller/src/client/service.ts:118`，class)
- 提供方：`@deepseek-ai/dsh-api-workspace-controller` (`packages/api/workspace-controller/src/index.ts:72`)

- create `async create(input: { path: string }): Promise<WorkspaceView>`
- initializeDefault `async initializeDefault(signal?: AbortSignal): Promise<WorkspaceView \| undefined>`
- rename `async rename(workspaceId: WorkspaceId, title: string): Promise<WorkspaceView>`
- delete `async delete(workspaceId: WorkspaceId): Promise<void>`
- insertBefore `async insertBefore(workspaceId: WorkspaceId, beforeWorkspaceId?: WorkspaceId): Promise<void>`
- archiveSession `async archiveSession(sessionId: SessionId, options: { readonly stopActivity?: boolean } = {}): Promise<void>`
- unarchiveSession `async unarchiveSession(sessionId: SessionId): Promise<void>`
- pinSession `async pinSession(sessionId: SessionId): Promise<void>`
- unpinSession `async unpinSession(sessionId: SessionId): Promise<void>`
- insertSessionBefore `async insertSessionBefore( workspaceId: WorkspaceId, sessionId: SessionId, beforeSessionId?: SessionId, ): Promise<WorkspaceView>`

### `workspaceFiles` — `@deepseek-ai/dsh-api-workspace-files`

> Host owner of the `workspaceFiles` Remote namespace. */

- 提供类型：`WorkspaceFiles`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-api-workspace-files` (`packages/api/workspace-files/src/index.ts:189`，class)
- 提供方：`@deepseek-ai/dsh-api-workspace-files` (`packages/api/workspace-files/src/index.ts:213`)
- 消费方：@deepseek-ai/dsh-client-ui-deliverables(`packages/client/ui-deliverables/src/index.ts` via inject)、@deepseek-ai/dsh-office-kit(`packages/document/office-kit/src/index.ts` via ctx.get)

- read `async read( workspaceFileScope: WorkspaceFileScope, path: string, range: WorkspaceFileRange, signal: AbortSignal, ): Promise<WorkspaceFileText>` — Read one page of lines from a UTF-8 file readable by the filesystem backend.  *(decorators: @@Remote)*
- readBytes `async readBytes( workspaceFileScope: WorkspaceFileScope, path: string, options: WorkspaceByteReadOptions, signal: AbortSignal, ): Promise<WorkspaceFileBytes>` — Read a complete regular file or one byte range without text decoding.  *(decorators: @@Remote)*
- stat `async stat(workspaceFileScope: WorkspaceFileScope, path: string, signal: AbortSignal): Promise<WorkspaceFileStat>` — Report one regular file's identity, version, and size without its content.  *(decorators: @@Remote)*
- list `async list(workspaceFileScope: WorkspaceFileScope, path: string, signal: AbortSignal): Promise<WorkspaceDirectoryListing>` — List the direct children of one directory inside the Session's workspace.  *(decorators: @@Remote)*
- search `async search( workspaceFileScope: WorkspaceFileScope, request: WorkspaceFileSearchRequest, signal: AbortSignal, ): Promise<WorkspaceFileSearchResult>` — Search files and their inferred ancestor directories with packaged ripgrep. Native ignore rules apply unless disabled; VCS metadata, symlinks and empty directories are absent. Within the bounded set of listed files, matches sort by depth, then workspace-relative path.  *(decorators: @@Remote)*
- changes `changes(workspaceFileScope: WorkspaceFileScope, path: string, signal: AbortSignal): AsyncIterable<WorkspaceFileWatchFrame>` — Watch one file or a directory's direct entries in the Session's filesystem. Files use the backend's read authority; directories remain workspace-scoped.  *(decorators: @@Remote({ mode: 'stream' }))*
- relativePath `private async relativePath(scope: WorkspaceFileScope, baseFile: string, path: string, signal: AbortSignal): Promise<string>`
- resolvePage `private resolvePage(range: WorkspaceFileRange):` — Apply the page defaults and caps here, so the request never carries them implicitly. */
- resolveWindow `private resolveWindow(range: WorkspaceByteRange, path: string):` — Apply the byte-window defaults and cap; a window above the cap is refused, not shortened. */
- inspect `private async inspect( workspaceFileScope: WorkspaceFileScope, path: string, signal: AbortSignal, ): Promise<` — Inspect the requested path itself before resolution follows its final component. Directory containment is checked separately by `list`.
- confine `private async confine(root: FsTarget, workspaceRoot: string, path: string, signal: AbortSignal): Promise<FsTarget>` — Resolve an inspected path and refuse it unless the workspace contains it. */
- locateFile `private async locateFile( workspaceFileScope: WorkspaceFileScope, path: string, signal: AbortSignal, ): Promise<` — All gates for a regular file, ending in the one stat that names its version and size. The stat re-checks what `lstat` saw: the file may have gone or changed kind in between.
- statOf `private statOf(target: FsTarget, info: FsInfo): WorkspaceFileStat`
- cutPage `private async cutPage(target: FsTarget, offset: number, limit: number, signal: AbortSignal, path: string): Promise<Page>` — Stream the file as text and cut the page, classifying the backend's non-text refusal. */

### `workspaceRegistry` — `@deepseek-ai/dsh-workspace`

- 提供类型：`WorkspaceRegistry`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-workspace` (`packages/workspace/workspace/src/index.ts:186`，class)
- 提供方：`@deepseek-ai/dsh-workspace` (`packages/workspace/workspace/src/index.ts:211`)
- 消费方：@deepseek-ai/dsh-api-session-controller(`packages/api/session-controller/src/index.ts` via inject)、@deepseek-ai/dsh-api-workspace-controller(`packages/api/workspace-controller/src/index.ts` via inject)、@deepseek-ai/dsh-deepseek-chat-import(`packages/experimental/deepseek-chat-import/src/index.ts` via inject)、@deepseek-ai/dsh-webhook(`packages/experimental/webhook/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)、@deepseek-ai/dsh-experimental-liveshare(`packages/experimental/liveshare/src/host/share-host.ts` via ctx.get)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/index.ts` via ctx.get)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/runtime.ts` via ctx.get)、@deepseek-ai/dsh-schedule(`packages/schedule/schedule/src/runtime.ts` via ctx.get)、@deepseek-ai/dsh-subagent(`packages/subagent/subagent/src/archive-admission.ts` via ctx.get)

- create `async create(path: string, title?: string): Promise<Workspace>` — Create or reuse a workspace for an existing directory. The fully qualified path is canonicalized through `fs.realpath`; a relative, nonexistent, or non-directory path rejects. Repeated calls for the same canonical path return the existing entity without changing its title. A newly created workspace is prepended to the durable registry order. Different canonical paths may share a display title. TODO: `title` lost its last production caller when the gateway's create-by-name branch was deleted (.agents/notes/archived/simplification/2026-07-31-one-route-to-add-a-workspace.md); drop the parameter with its @param clause and the `create(path, title?)` lines in this package's README pair.
- initializeDefault `initializeDefault(resolveDirectory: () => Promise<string>): Promise<Workspace \| undefined>` — Initialize the default Workspace only while both the registry and Session history are empty. Repeated requests reuse its durable identity; deleting that registration permanently disables automatic creation. eligible creation, inside the registry mutation queue. Missing directories are created recursively before registration, and the initial title is the requested directory's own final segment — not the canonical one, so a symlink at that path does not retitle the Workspace after its target. After resolution, caller cancellation does not roll back creation or registration.
- get `get(id: WorkspaceId): Workspace \| undefined` — Look up a workspace by id.
- list `list(): Workspace[]` — Synchronous workspace projection in durable registry order. Every entity's `sessionIds` getter is already filtered by the startup/live canonical-cwd header index; this method performs no persistence reads.
- delete `delete(id: WorkspaceId): Promise<boolean>` — Delete one workspace registration while retaining its directory and every session log. The durable order is updated before the table deletion; a failed table write restores the prior order and keeps the entity published. Unknown ids are an idempotent no-op for domain callers.
- insertBefore `insertBefore(id: WorkspaceId, beforeId?: WorkspaceId): Promise<readonly WorkspaceId[]>` — Move one workspace within the durable display order, DOM-insertBefore-like. With an anchor it lands before that workspace; without one it appends.
- archiveSession `archiveSession(sessionId: SessionId, options: ArchiveSessionOptions = {}): Promise<void>` — Archive one session durably. The session must exist (live or in session persistence); its workspace accounting — or lack of one — is irrelevant. Without `stopActivity` the session must also be inactive: the `workspace/session-activity` waterfall is asked once, and any reported activity rejects with {@link WorkspaceActiveSessionError} before anything is written. With `stopActivity` the archive is written without an activity check, and the `workspace/session-stop` providers are then asked to stop the session's work: the durable archive set is what a provider's `agent/pre-step` gate reads, so every wake the stops induce is already blocked. Archiving drops the session's pin in the same durable write (pinning and archival are mutually exclusive). An already archived id resolves without writing, asking, or stopping.
- unarchiveSession `unarchiveSession(sessionId: SessionId): Promise<void>` — Unarchive one session durably by dropping it from the registry-global archive set; the accounting slot was never touched, so the session returns to its recorded position. Unarchiving runs no session-existence check because removing an id cannot introduce an unknown one, so an entry whose session is gone still resolves. An id that is not archived resolves without writing.
- pinSession `pinSession(sessionId: SessionId): Promise<void>` — Pin one session durably, prepending it to the registry-global pin set. The session must exist (live or in session persistence) and must not be archived. An already pinned id resolves without writing or reordering.
- unpinSession `unpinSession(sessionId: SessionId): Promise<void>` — Unpin one session durably by dropping it from the registry-global pin set. Unpinning runs no session-existence check because removing an id cannot introduce an unknown one, so an entry whose session is gone still resolves. An id that is not pinned resolves without writing.
- sessionKnown `private async sessionKnown(id: SessionId): Promise<boolean>` — Whether a session is live, header-indexed, or present in a fresh persistence listing. Only a definite miss returns false — a failing `sessionPersistence.list()` propagates so storage faults never masquerade as an unknown session.
- stopSessionActivity `private async stopSessionActivity(sessionId: SessionId): Promise<void>` — Request every provider's stop; a failing provider is logged, never a reason to keep the session visible. */
- resolveByPath `async resolveByPath(path: string): Promise<Workspace \| undefined>` — Resolve by canonical directory path without creating or mutating a workspace. A missing path rejects during `realpath`; an existing unowned directory returns `undefined`.
- createCanonical `private async createCanonical(canonical: string, title?: string, firstUse = false): Promise<WorkspaceEntity>`
- deleteKnown `private async deleteKnown(id: WorkspaceId): Promise<boolean>`
- recoverPendingMutation `private async recoverPendingMutation(): Promise<void>` — Complete the one mutation explicitly named by durable state. Unexplained order/table divergence still reaches {@link validateStoredState} and fails loud; this path never guesses which operation created a row from its shape alone.
- bootstrap `private async bootstrap(headers: readonly SessionHeader[]): Promise<void>`
- validateStoredState `private validateStoredState(state: WorkspaceDomainState): void`
- rebuildEntities `private rebuildEntities(): void`
- replaceHeaderIndex `private async replaceHeaderIndex(headers: readonly SessionHeader[]): Promise<void>`
- indexHeaders `private async indexHeaders(headers: readonly SessionHeader[]): Promise<void>`
- indexHeader `private async indexHeader(header: SessionHeader): Promise<void>`
- listStoredHeaders `private async listStoredHeaders(): Promise<SessionHeader[]>` — Every stored session's header, projected from the persistence snapshot listing. */
- indexLiveSessions `private async indexLiveSessions(): Promise<void>`
- reportFilteredCandidates `private reportFilteredCandidates(): void`
- readSessionHeader `private async readSessionHeader(id: SessionId): Promise<SessionHeader>`
- requireTable `private requireTable(): KvTable<WorkspaceId, WorkspaceRecord>`
- requireState `private requireState(): WorkspaceDomainState`
- setState `private async setState(state: WorkspaceDomainState): Promise<void>`
- enqueueOperation `private enqueueOperation<T>(operation: () => Promise<T>): Promise<T>`

### `workspaces` — `@deepseek-ai/dsh-api-workspace-controller`

> React-free Client Workspace state and commands. */

- 提供类型：`import('./service.ts').IWorkspaces`；方法覆盖：unresolved；asar 核对：✅
- 提供方：`@deepseek-ai/dsh-client-test-runtime` (`packages/test-support/client-runtime/src/index.ts:268`)、`@deepseek-ai/dsh-api-workspace-controller` (`packages/api/workspace-controller/src/client/service.ts:126`)
- 消费方：@deepseek-ai/dsh-client-ui-schedule(`packages/client/ui-schedule/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via inject)、@deepseek-ai/dsh-client-ui-workspace(`packages/client/ui-workspace/src/client/index.ts` via ctx.get)

- （方法未解析：提供类型不可达或未定义成员）

### `worktrees` — `@deepseek-ai/dsh-experimental-worktree`

- 提供类型：`WorktreeService`；方法覆盖：resolved；asar 核对：✅
- 方法来源：`@deepseek-ai/dsh-experimental-worktree` (`packages/experimental/worktree/src/index.ts:86`，class)
- 提供方：`@deepseek-ai/dsh-experimental-worktree` (`packages/experimental/worktree/src/index.ts:108`)
- 消费方：@deepseek-ai/dsh-experimental-tool-worktree(`packages/experimental/tool-worktree/src/index.ts` via inject)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/panel.ts` via ctx.get)、@deepseek-ai/dsh-experimental-client-ui-forge(`packages/experimental/client-ui-forge/src/worktree.ts` via ctx.get)

- create `async create( agent: Agent, request: CreateWorktreeRequest = {}, signal?: AbortSignal, onPhase?: (phase: CreateWorktreePhase) => void, ): Promise<CreatedWorktree>` — Create a fresh branch and checkout at a pinned local revision, then enter it. Existing branches or checkout paths fail. Uncommitted files stay in the source checkout. Checkout disables configured clean, smudge, and process filters without changing Git config. Repository-local replacement refs still apply; baseCommit reports the resolved object name. The new checkout becomes current only after Git setup succeeds. Failures may retain newly allocated Git/filesystem artifacts; no branch or checkout is removed automatically.
- restore `async restore( agent: Agent, request: RestoreWorktreeRequest, signal?: AbortSignal, onPhase?: (phase: CreateWorktreePhase) => void, ): Promise<RestoredWorktree>` — Check out a removed worktree again at its recorded directory: its branch when the branch still exists, otherwise a new branch of the same name at `baseCommit`. Only the missing target's unlocked registration is removed, and an existing directory fails. Changes that were never committed are not recovered. Checkout disables configured clean, smudge, and process filters, as creation does. The calling Session's working directory does not change. Failures may retain newly allocated Git/filesystem artifacts.
- cleanupOf `async cleanupOf(session: Session, revision: number \| null): Promise<WorktreeCleanup \| null>` — Read the archive cleanup of a Session's created checkout; waiting never starts one. Absent without the Workspace and query providers.
- removeCheckout `private async removeCheckout( session: Session, request: RestoreWorktreeRequest, signal: AbortSignal, admit: () => boolean, ): Promise<boolean>` — Inspect a recorded checkout under the Session's policy and, when eligible and admitted, remove it and its registration without force or branch deletion. A rejection can leave a partial directory; the branch stays.
- exclusiveCheckout `private exclusiveCheckout<T>(path: string, body: () => Promise<T>): Promise<T>`
- resolve `private resolve(agent: Agent, request: CreateWorktreeRequest): WorktreeSpec`
- createCheckout `private async createCheckout( agent: Agent, { branch, revision }: WorktreeSpec, signal: AbortSignal, onPhase: ((phase: CreateWorktreePhase) => void) \| undefined, ): Promise<Created…`
- appendPluginRecord `appendPluginRecord(agent.session, CREATED_RECORD, created)`
- restoreCheckout `private async restoreCheckout( agent: Agent, { path, branch, baseCommit, repositoryRoot }: RestoreWorktreeRequest, signal: AbortSignal, onPhase: ((phase: CreateWorktreePhase) => vo…`
- gitRunner `private gitRunner(policy: SandboxExecutionPolicy, signal: AbortSignal): GitRun` — Confine Git commands to the caller's sandbox policy, collecting bounded stdout. */
- gitScanner `private gitScanner(policy: SandboxExecutionPolicy, signal: AbortSignal): GitScan` — Confine Git commands to the caller's sandbox policy, streaming stdout instead of collecting it. */
- gitArgv `private gitArgv(args: string[]): [string, ...string[]]` — The configured Git executable with hooks and the filesystem monitor disabled, followed by `args`. */
- prepareDirectory `private async prepareDirectory( policy: SandboxExecutionPolicy, repositoryRoot: string, poolPath: string, path: string, signal: AbortSignal, ): Promise<void>` — Allocate the checkout directory exclusively inside the pool, creating a self-ignoring pool when it is new. */

---

# 覆盖度与诚实声明

- **Layer B schemas 是精确的**：不是猜的，是 `dsh-typert-generator` 从 Host FaceModel 生成后落进 `typert.remote-client.js` 的 `jsonSchema`（含 `typeSymbol` 与 `sourceLocation` 指回原始 `.ts` 路径/行/列，可反向核对）。
- **Layer A 的 payload 字段形状是转录的**：随包 `.js` 里 TS 类型已抹除、`.d.ts` 未随包发，字段形状按协议 README 正文逐条抄录，可能比真实类型宽松（README 是权威描述，但不是可机读 schema）。
- **Layer B 返回 schema 有 68 个缺失**：官方生成器对 `void` 结果和字典/union 类型报 `jsonSchemaError`（void 结果（无返回体）×31；字典/union 类型（生成器无法表达为 JSON Schema）×26；typert tool schema: unsupported undefined value×3；typert tool schema: selected union branches overlap or have no required discriminator×6；typert tool schema: unsupported selected reference Uint8Array×2），这些 endpoint 只保留 `typeSymbol`+`description`，原因已逐个写在上文条目里。入参 schema 则完整。
- **Layer C 是类型化抽取，不是反推**：服务键的提供类型直接读公开仓库 `deepseek-ai/deepseek-harness` 在 tag `dsh-v0.2.2-rc.3` 的 TypeScript 声明合并（`declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }`）。npm 不发 `.ts` 源码、同一包的 `.d.ts` 在随包产物里也缺失，所以并非从 `.js` 反推；运行期注册（`ctx.provide` / `ctx.reflect.provide` / `static inject`）再用本机安装的 DSH 桌面 app.asar 解包树编译后 `.js` 交叉核对（114/151 生产键可见）。npm 上的 `.d.ts` 仅作独立参考。
- **未覆盖**：协议版本协商（DSH 明说没有）；cancel/session-close（DSH 明说没有）。Layer C 的方法签名来自 `.ts` 源码解析，个别生成器未导出的运行期动态方法可能未列全。

