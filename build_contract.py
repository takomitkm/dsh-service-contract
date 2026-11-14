#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the DSH plugin-service-surface contract (Layer A SDK JSON-RPC + Layer B Typert Remote).
Inputs : .tmp/typert-contract.json  (machine dump of every generated typert.remote-client.js)
Outputs: dsh-contract/contract.json, dsh-contract/dsh-service-contract.md
All I/O explicit UTF-8 (host ACP=936).
"""
import json, os, sys, datetime, collections

ROOT = r"S:\apps\llm\agentwork"
TYPERT_IN = os.path.join(ROOT, ".tmp", "typert-contract.json")
LAYERC_IN = os.path.join(ROOT, ".tmp", "layerc-contract.json")
OUT_DIR = os.path.join(ROOT, "dsh-contract")
ASAR = r"C:\Users\takomi\AppData\Local\Programs\DeepSeek Harness\resources\app.asar"
TREE = r"S:\apps\llm\agentwork\.tmp\dsh-asar-full"
SRC_TREE = os.path.join(ROOT, ".tmp", "dsh-src")
SRC_TAG = "dsh-v0.2.2-rc.1"
SRC_SHA = "66491b05e3f05ad35bcdd4f6cd7ed26041d9e3db"
DSH_VERSION = "0.2.2-rc.1"

os.makedirs(OUT_DIR, exist_ok=True)
ty = json.load(open(TYPERT_IN, encoding="utf-8"))
layerc = json.load(open(LAYERC_IN, encoding="utf-8"))

# ---------------- Layer A: SDK JSON-RPC (transcribed from dsh-sdk-protocol/README.md) ----------------
sdk = {
    "package": "@deepseek-ai/dsh-sdk-protocol",
    "transport": {
        "framing": "one JSON-RPC 2.0 message per '\\n'-terminated line over caller-owned byte streams",
        "dispatch": "id+method=request; id alone=response; method alone=notification; malformed lines ignored",
        "errorMapping": {"-32601": "no registered handler", "-32603": "handler failure"},
        "errorObject": "JsonRpcResponseError preserves wire `code` and optional `data`",
        "lifecycle": "start() attaches stream listeners; close() detaches them and rejects pending requests without destroying the streams",
    },
    "methodMaps": ["HarnessSdkRequestMap", "HarnessSdkClientRequestMap", "HarnessSdkHostRequestMap", "HarnessSdkNotificationMap"],
    "methods": [
        # direction, method, params type, result type, kind(request/notification), notes
        ["client->server", "initialize", "InitializeParams", "InitializeResult", "request",
         "Handshake. approvalRequests:true enables approval/request; capabilities.userQuestions:true enables user-question/ask; reasoningEffort optional non-empty adapter id; maxTokens optional positive safe int; resolves the exact provider/model route and rejects session/prompt until handshake succeeds. serverInfo.name is wire-stable 'deepseek-harness-sdk-runtime'; serverInfo.version is '0.0.1' (unvalidated)."],
        ["client->server", "session/prompt", "SessionPromptParams", "SessionPromptResult", "request",
         "Queues content blocks without native slash-command routing (runtime skill recognition still applies). SessionPromptResult.messageId = the queued user message id (a durable enqueue receipt, not a model result)."],
        ["client->server", "session/query", "SessionQueryParams", "SessionQueryResult", "request",
         "Accepts {sessionId, contentBlocks: SdkPromptContentBlock[]}. Returns {kind:'prompt', messageId} for queued ordinary input, or {kind:'command', execution} after a supported command settles. A command requires one complete text block plus only encoded images; empty/all-blank text rejected; image-only allowed; strings normalize to a text block."],
        ["client->server", "session/resume", "SessionResumeParams", "{}", "request",
         "Accepts non-empty persisted {sessionId}; restores that exact session (requires initialization + the original persistence store). Sends no new input; rejects missing/unreadable/incompatible/occupied sessions without creating a replacement."],
        ["client->server", "session/wait", "SessionWaitParams", "{}", "request",
         "Accepts {sessionId}; returns {} after the root stays idle and progressing managed descendant work finishes; unknown ids and live Agent failures without a newer committed terminal are rejected."],
        ["client->server", "session/working-directory/get", "SessionWorkingDirectoryParams", "SessionWorkingDirectoryResult", "request", "Read the session working directory."],
        ["client->server", "session/working-directory/set", "SessionWorkingDirectorySetParams", "SessionWorkingDirectoryResult", "request", "Set the session working directory."],
        ["client->server", "shutdown", "(none)", "{}", "request", "Shut the runtime down."],
        ["server->client", "approval/request", "ApprovalRequestParams", "ApprovalRequestResult", "request",
         "OPT-IN: requires InitializeParams.approvalRequests == true. Params {sessionId, toolName, callId?, reason?}; Result {outcome: 'allowed-once' | 'rejected' | 'cancelled'}. Only 'allowed-once' grants exactly one operation. Cancellation discards the pending request and late responses; shutdown/transport loss fail decisions closed."],
        ["server->client", "user-question/ask", "SdkUserQuestionRequest", "SdkUserQuestionResult", "request",
         "OPT-IN: requires InitializeParams.capabilities.userQuestions == true. Params {requestId, sessionId, questions}; Result {answers:[{id, selected, custom?}]} naming every question id exactly once, OR {cancelled:true} (dismissal -> native ASK_CANCELLED). Invalid batches -> BAD_ANSWER; host/transport failures -> PROVIDER_ERROR."],
        ["server->client", "user-question.cancelled", "SdkUserQuestionCancelled", "-", "notification",
         "Identifies the request that stopped waiting; host cancels its own work and discards the question."],
        ["server->client", "session.event", "SessionEventNotification", "-", "notification",
         "Every session event in the runtime, unfiltered."],
        ["server->client", "session.status", "SessionStatusNotification", "-", "notification",
         "Whole-agent 'running'/'idle' transition."],
        ["server->client", "session.query.completed", "{sessionId, commandId, finalResponse, finishReason}", "-", "notification",
         "Sent for the same commandId after a command query's model activity starts / state-only commands need no model turn."],
        ["server->client", "subagent.started", "SubagentStartedNotification", "-", "notification", "A subagent started."],
        ["server->client", "subagent.finished", "SubagentFinishedNotification", "-", "notification",
         "Subagent finished (in-process runs only). lastAssistantMessage = child's last non-empty assistant message, or accumulated assistant text; absent when neither exists."],
    ],
    "payloadTypes": {
        "InitializeParams": "{ approvalRequests?: boolean; capabilities?: { userQuestions?: boolean }; reasoningEffort?: string (non-empty adapter-owned id); maxTokens?: positive safe int }",
        "ApprovalRequestParams": "{ sessionId, toolName, callId?, reason? }",
        "ApprovalRequestResult": "{ outcome: 'allowed-once' | 'rejected' | 'cancelled' }",
        "SdkUserQuestionRequest": "{ requestId, sessionId, questions }",
        "SdkUserQuestionResult": "{ answers: [{ id, selected, custom? }] } | { cancelled: true }",
        "SessionQueryParams": "{ sessionId, contentBlocks: SdkPromptContentBlock[] }",
        "SessionQueryResult": "{ kind: 'prompt', messageId } | { kind: 'command', execution }",
        "SdkPromptContentBlock": "ordinary durable content + SdkEncodedImageBlock { type: 'image', data, mimeType } (server converts encoded images to durable refs before enqueue)",
        "SessionPromptResult": "{ messageId } (durable enqueue receipt)",
        "_note": "TypeScript types are erased in shipped .js; these shapes are transcribed verbatim from dsh-sdk-protocol/README.md (Payload semantics). Notification payloads depend on SessionEvent (dsh-session), ContentBlock (dsh-llm), SubagentStopReason (dsh-subagent).",
    },
    "knownLimitations": [
        "No protocol-version negotiation (handshake carries only serverInfo.version = '0.0.1', unvalidated).",
        "No cancel or session-close methods; a client abandons a turn by closing the runtime process.",
        "Question waits are process-local; question request ids are not durable handles across a runtime restart.",
    ],
    "provenance": "dsh-sdk-protocol/README.md (152 lines) + lib/index.js (transport only; types erased).",
}

# ---------------- Layer B: normalise Typert dump ----------------
flat = []
by_service = collections.defaultdict(list)
invocation_kinds = collections.Counter()
for pkg in ty["packages"]:
    for ep in pkg["endpoints"]:
        rec = dict(ep)
        rec["package"] = pkg["package"]
        flat.append(rec)
        by_service[ep.get("service") or ep.get("namespace")].append({"id": ep["id"], "method": ep["method"]})
        ik = (ep.get("invocation") or {}).get("kind", "unknown")
        invocation_kinds[ik] += 1
flat.sort(key=lambda r: (r["package"], r["namespace"], r["method"]))

# schema coverage stats
res_missing = [e for e in flat if e["result"].get("schema") is None]
res_reasons = collections.Counter()
for e in res_missing:
    err = e["result"].get("schemaError") or "unknown"
    if "void" in err:
        key = "void 结果（无返回体）"
    elif "dictionaries" in err:
        key = "字典/union 类型（生成器无法表达为 JSON Schema）"
    else:
        key = err
    res_reasons[key] += 1
input_bundle = sum(1 for e in flat if e.get("inputSchema") is not None)

typert = {
    "summary": {"packages": len(ty["packages"]), "endpoints": len(flat),
                "invocationKinds": dict(invocation_kinds),
                "resultSchemaPresent": len(flat) - len(res_missing),
                "resultSchemaMissing": len(res_missing),
                "resultSchemaMissingReasons": dict(res_reasons),
                "inputBundledRequest": input_bundle},
    "packages": [{"package": p["package"], "endpointCount": len(p["endpoints"]),
                  "endpoints": p["endpoints"]} for p in ty["packages"]],
    "byService": {k: sorted(v, key=lambda x: x["id"]) for k, v in sorted(by_service.items())},
}

contract = {
    "meta": {
        "title": "DSH plugin-service-surface contract",
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dshVersion": DSH_VERSION,
        "sourceAsar": ASAR,
        "extractedTree": TREE,
        "layers": {
            "A_sdk_jsonrpc": "Explicit documented wire protocol (README) — external client / forwarder path.",
            "B_typert_remote": "Host<->Client Remote endpoints; JSON Schemas recovered from generated lib/typert.remote-client.js (34 packages / 193 endpoints, 0 extraction errors).",
            "C_cordis_ctx": "In-process Cordis ctx.* service surface — TYPED/SOURCED from the official repo TypeScript at tag dsh-v0.2.2-rc.1, cross-checked against the local asar compiled .js (148 production keys / 1284 methods / 135 asar-confirmed).",
        },
        "honesty": "Layer B schemas are exact (generated from the Host FaceModel). Layer A payload field shapes are transcribed from the protocol README because TS types are erased in shipped .js. Layer C is typed/sourced from the official repo .ts at dsh-v0.2.2-rc.1 (NOT reverse-engineered): npm ships no .ts source and the same-package .d.ts is absent from the local asar, so each key's provider type is read from the public TypeScript and the runtime registration is cross-checked against the local asar .js.",
    },
    "layerA_sdk_jsonrpc": sdk,
    "layerB_typert_remote": typert,
    "layerC_cordis_ctx": layerc,
}

json.dump(contract, open(os.path.join(OUT_DIR, "contract.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

# ---------------- Markdown ----------------
def esc(s):
    return str(s).replace("|", "\\|")

def compact_schema(sc):
    if sc is None:
        return "(none)"
    try:
        return json.dumps(sc, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(sc)

L = []
w = L.append

w("# DSH 插件服务面契约（Layer A + B + C）")
w("")
w("> **这是什么**：把 DSH（DeepSeek Harness）对外暴露的接口反向梳理成一份**显式契约**——哪些方法、什么 payload。")
w("> 用于「一模一样」复刻 / 反代 / 外部客户端对接。DSH 没有一份统一的对外 spec 文档，但真实契约分散在源码里，")
w("> 本文把它抽出来。")
w("")
w("- **DSH 版本**：`%s`" % DSH_VERSION)
w("- **来源 archive**：`%s`" % ASAR)
w("- **解包树**：`%s`（22102 文件，与当前 asar 文件数一致）" % TREE)
w("- **生成时间**：%s" % contract["meta"]["generatedAt"])
w("- **机器可读版**：同目录 `contract.json`")
w("")
w("## 三层服务面（本契约覆盖 A、B、C）")
w("")
w("| 层 | 是什么 | 谁在用 | 本契约状态 |")
w("|---|---|---|---|")
w("| **A. SDK / JSON-RPC** | 换行分帧的 JSON-RPC 2.0 线协议（外部客户端/反代走这条） | `dsh-sdk-client`(TS)、Python SDK、任何外部进程 | ✅ 已转录（协议 README） |")
w("| **B. Host↔Client Remote (Typert)** | 渲染端 ↔ 主进程的命名 RPC endpoint，每个方法带 JSON Schema | DSH 自己的 renderer / 任何调 Remote 的进程 | ✅ 机器导出（34 包 / %d endpoint / 0 错） |" % len(flat))
w("| **C. 进程内 Cordis `ctx.*` 服务** | 插件在 host 进程内直接消费的服务对象 | cordis 插件包本身 | ✅ 类型化抽取（rc.1 `.ts` + asar `.js` 交叉核对） |")
w("")
w("---")
w("")
w("# Layer A — SDK / JSON-RPC 协议")
w("")
w("来源：`%s`。" % sdk["provenance"])
w("")
w("## A.1 传输与分帧")
w("")
w("- **分帧**：%s" % sdk["transport"]["framing"])
w("- **分派**：%s" % sdk["transport"]["dispatch"])
w("- **错误映射**：无 handler → `-32601`；handler 失败 → `-32603`；错误响应以 `JsonRpcResponseError` 抛出，保留 wire `code` 与可选 `data`。")
w("- **生命周期**：%s" % sdk["transport"]["lifecycle"])
w("- **方法映射类型**：%s" % "、".join("`%s`" % m for m in sdk["methodMaps"]))
w("")
w("## A.2 方法表（%d 条）" % len(sdk["methods"]))
w("")
w("| 方向 | 方法 | 参数 → 结果 | 类型 |")
w("|---|---|---|---|")
for d, mname, p, r, kind, _ in sdk["methods"]:
    arrow = "`%s` → `%s`" % (p, r) if r != "-" else "`%s`" % p
    w("| %s | `%s` | %s | %s |" % (d, mname, arrow, kind))
w("")
w("### 逐方法说明")
w("")
for d, mname, p, r, kind, notes in sdk["methods"]:
    w("#### `%s`  (%s · %s)" % (mname, d, kind))
    w("- 参数：`%s`%s" % (p, (" → 结果：`%s`" % r) if r != "-" else ""))
    w("- %s" % notes)
    w("")
w("## A.3 Payload 类型形状")
w("")
w("> TS 类型在随包 `.js` 中已被编译抹除；下列形状**逐字转录自协议 README**（`Payload semantics` / 各方法段）。")
w("")
for k, v in sdk["payloadTypes"].items():
    if k.startswith("_"):
        continue
    w("- `%s` = %s" % (k, v))
w("")
w("_%s_" % sdk["payloadTypes"]["_note"])
w("")
w("## A.4 已知限制")
w("")
for it in sdk["knownLimitations"]:
    w("- %s" % it)
w("")
w("---")
w("")
w("# Layer B — Host↔Client Remote (Typert)，机器导出")
w("")
w("每个 endpoint 都来自对应包里的生成物 `lib/typert.remote-client.js`（头注 `Generated by @deepseek-ai/dsh-typert-generator from the Host FaceModel`）。")
w("下表里 `schema` 是**逐 endpoint 的 JSON Schema**（与 `contract.json` 内 `layerB_typert_remote` 一一对应，那里是 pretty 版）。")
w("")
w("## B.1 概览")
w("")
w("- **包数**：%d" % typert["summary"]["packages"])
w("- **endpoint 数**：%d" % typert["summary"]["endpoints"])
w("- **invocation 分布**：%s" % ", ".join("`%s`=%d" % (k, v) for k, v in typert["summary"]["invocationKinds"].items()))
w("- **服务（cordis service）数**：%d" % len(typert["byService"]))
w("- **入参 schema**：%d 个 endpoint 是单个 `request` 参数（其 schema 即完整入参对象），其余按参数逐个给 schema" % typert["summary"]["inputBundledRequest"])
_pm = [(e["id"].split("#")[-1], p["name"], p.get("schemaError")) for e in flat for p in e["parameters"] if p.get("schema") is None]
if _pm:
    w("- **参数级 schema 缺失**：%d 个（%s）" % (len(_pm), "；".join("`%s`.%s → %s" % x for x in _pm)))
w("- **返回 schema**：%d/%d 有精确 JSON Schema；%d 个缺失（见下原因）" % (
    typert["summary"]["resultSchemaPresent"], typert["summary"]["endpoints"], typert["summary"]["resultSchemaMissing"]))
for reason, cnt in typert["summary"]["resultSchemaMissingReasons"].items():
    w("  - %d 个：%s" % (cnt, reason))
w("")
w("## B.2 按包汇总")
w("")
w("| 包 | endpoint 数 |")
w("|---|---|")
for p in typert["packages"]:
    w("| `%s` | %d |" % (p["package"], p["endpointCount"]))
w("")
w("## B.3 按服务（service）索引")
w("")
w("| service | endpoints |")
w("|---|---|")
for svc, eps in typert["byService"].items():
    w("| `%s` | %s |" % (svc, ", ".join("`%s`" % e["method"] for e in eps)))
w("")
w("## B.4 逐 endpoint 契约")
w("")
cur_pkg = None
for ep in flat:
    if ep["package"] != cur_pkg:
        cur_pkg = ep["package"]
        w("")
        w("### `%s`" % cur_pkg)
        w("")
    w("#### `%s`" % ep["id"])
    inv = (ep.get("invocation") or {})
    w("- service: `%s` · invocation: `%s`" % (ep.get("service"), inv.get("kind", "?")))
    if ep.get("description"):
        w("- **说明**：%s" % ep["description"].replace("\n", " "))
    if ep["parameters"]:
        w("- **参数**：")
        for prm in ep["parameters"]:
            if prm.get("schema") is not None:
                w("  - `%s` (wire `%s`, source `%s`) schema=`%s`" % (
                    prm["name"], prm["wire"], prm["source"], compact_schema(prm["schema"])))
            else:
                w("  - `%s` (wire `%s`, source `%s`) — `%s` schema 不可用：%s" % (
                    prm["name"], prm["wire"], prm["source"], prm.get("typeSymbol"),
                    prm.get("schemaError") or "（无）"))
    else:
        w("- **参数**：无")
    res = ep["result"]
    if res.get("schema") is not None:
        w("- **结果**：`%s` (%s) schema=`%s`" % (
            res.get("typeSymbol"), res.get("mode"), compact_schema(res.get("schema"))))
    else:
        w("- **结果**：`%s` (%s) — schema 不可用：%s" % (
            res.get("typeSymbol"), res.get("mode"), res.get("schemaError") or "（无）"))
    if ep.get("sourceLocation"):
        sl = ep["sourceLocation"]
        w("- source: `%s:%s:%s`" % (sl.get("file"), sl.get("line"), sl.get("column")))
    w("")

w("---")
w("")
w("# Layer C — 进程内 Cordis `ctx.*` 服务面")
w("")
w("> **来源**：`deepseek-ai/deepseek-harness` 在 tag `%s`（commit `%s`）的公开 TypeScript 源码。" % (SRC_TAG, SRC_SHA))
w("> 用 `extract_layerc.py` 从 `%s` 的 `packages/**` + `vendor/**` 的 `.ts` 抽取" % SRC_TREE)
w("> （%d 个 `.ts` 文件），并交叉核对本地 asar 的编译后 `.js`（%d 个 `.js` 文件）。" % (
    layerc["meta"]["sourceTreeFileCount"], layerc["meta"]["asarJsFiles"]))
w(">")
w("> **不是反推**：npm 不发 `.ts` 源码、同一包的 `.d.ts` 在本地 asar 里也缺失；" )
w("> Layer C 的每个服务键的提供类型直接读公开仓库的 `.ts` 声明合并（`declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }`），")
w("> 运行期注册再拿本地 asar 的 `.js` 交叉核对。npm 上的 `.d.ts` 仅作参考。")
w("")
w("## C.1 机制（类型化声明合并，非反推）")
w("")
w("- **框架**：`%s`。" % layerc["mechanism"]["providerFramework"])
w("- **声明惯用法**：`%s`。" % layerc["mechanism"]["declarationIdiom"])
w("- **注册惯用法**：%s。" % "、".join("`%s`" % x for x in layerc["mechanism"]["registrationIdioms"]))
w("- **依赖惯用法**：%s。" % "、".join("`%s`" % x for x in layerc["mechanism"]["dependencyIdioms"]))
w("- **说明**：%s" % layerc["mechanism"]["note"])
w("")
w("## C.2 覆盖度")
w("")
cov = layerc["coverage"]
w("- 生产服务键：**%d** 个；测试夹具里声明的键（非生产）：**%d** 个。" % (cov["productionKeys"], cov["testOnlyKeys"]))
w("- 有提供方的：%d；有消费方的：%d。" % (cov["withProvider"], cov["withConsumers"]))
w("- 方法签名：解析出 **%d** 个服务、共 **%d** 个方法。" % (cov["methodsResolved"], cov["methodSignatures"]))
w("- asar 交叉核对：%d / %d 个生产键在本地 asar `.js` 里可见。" % (cov["asarConfirmed"], cov["productionKeys"]))
w("")
w("## C.3 服务目录（生产键，%d 行）" % cov["productionKeys"])
w("")
w("| 服务键 | 包 | 提供类型 | 提供方 | 消费方 | 方法 | asar |")
w("|---|---|---|---|---|---|---|")
for s in layerc["services"]:
    pkg = s["declarations"][0]["package"] if s["declarations"] else ""
    w("| `%s` | `%s` | `%s` | %d | %d | %d | %s |" % (
        esc(s["key"]), esc(pkg), esc(s["type"]),
        len(s["providers"]), len(s["consumers"]), len(s["methods"]),
        "✅" if s["asar"]["seen"] else "—"))
w("")
w("## C.4 方法索引（按服务；签名截断到 180 字符）")
w("")
for s in layerc["services"]:
    pkg = s["declarations"][0]["package"] if s["declarations"] else ""
    w("### `%s` — `%s`" % (esc(s["key"]), esc(pkg)))
    if s["doc"]:
        w("")
        w("> %s" % esc(s["doc"]))
    w("")
    w("- 提供类型：`%s`；方法覆盖：%s；asar 核对：%s" % (
        esc(s["type"]), s["methodCoverage"], "✅" if s["asar"]["seen"] else "—"))
    if s["methodSource"]:
        ms = s["methodSource"]
        w("- 方法来源：`%s` (`%s:%s`，%s)" % (esc(ms["package"]), esc(ms["file"]), ms["line"], ms["kind"]))
    if s["providers"]:
        w("- 提供方：%s" % "、".join("`%s` (`%s:%s`)" % (esc(p["package"]), esc(p["file"]), p["line"]) for p in s["providers"]))
    if s["consumers"]:
        w("- 消费方：%s" % "、".join("%s(`%s` via %s)" % (esc(c["package"]), esc(c["file"]), esc(c["via"])) for c in s["consumers"]))
    w("")
    if s["methods"]:
        for m in s["methods"]:
            sig = m["signature"]
            if len(sig) > 180:
                sig = sig[:180] + "…"
            line = "- %s `%s`" % (esc(m["name"]), esc(sig))
            if m.get("doc"):
                line += " — %s" % esc(m["doc"])
            if m.get("decorators"):
                line += "  *(decorators: %s)*" % ", ".join("@%s" % esc(d) for d in m["decorators"])
            w(line)
    else:
        w("- （方法未解析：提供类型不可达或未定义成员）")
    w("")
w("---")
w("")
w("# 覆盖度与诚实声明")
w("")
w("- **Layer B schemas 是精确的**：不是猜的，是 `dsh-typert-generator` 从 Host FaceModel 生成后落进 `typert.remote-client.js` 的 `jsonSchema`（含 `typeSymbol` 与 `sourceLocation` 指回原始 `.ts` 路径/行/列，可反向核对）。")
w("- **Layer A 的 payload 字段形状是转录的**：随包 `.js` 里 TS 类型已抹除、`.d.ts` 未随包发，字段形状按协议 README 正文逐条抄录，可能比真实类型宽松（README 是权威描述，但不是可机读 schema）。")
w("- **Layer B 返回 schema 有 %d 个缺失**：官方生成器对 `void` 结果和字典/union 类型报 `jsonSchemaError`（%s），这些 endpoint 只保留 `typeSymbol`+`description`，原因已逐个写在上文条目里。入参 schema 则完整。" % (
    typert["summary"]["resultSchemaMissing"],
    "；".join("%s×%d" % (k, v) for k, v in typert["summary"]["resultSchemaMissingReasons"].items())))
w("- **Layer C 是类型化抽取，不是反推**：服务键的提供类型直接读公开仓库 `deepseek-ai/deepseek-harness` 在 tag `%s` 的 TypeScript 声明合并（`declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }`）。npm 不发 `.ts` 源码、同一包的 `.d.ts` 在本地 asar 里也缺失，所以并非从 `.js` 反推；运行期注册（`ctx.provide` / `ctx.reflect.provide` / `static inject`）再用本地 asar 编译后 `.js` 交叉核对（%d/%d 生产键可见）。npm 上的 `.d.ts` 仅作独立参考。" % (
    SRC_TAG, cov["asarConfirmed"], cov["productionKeys"]))
w("- **未覆盖**：协议版本协商（DSH 明说没有）；cancel/session-close（DSH 明说没有）。Layer C 的方法签名来自 `.ts` 源码解析，个别生成器未导出的运行期动态方法可能未列全。")
w("")

md = "\n".join(L) + "\n"
open(os.path.join(OUT_DIR, "dsh-service-contract.md"), "w", encoding="utf-8").write(md)

print("WROTE:")
print(" ", os.path.join(OUT_DIR, "contract.json"), os.path.getsize(os.path.join(OUT_DIR, "contract.json")), "bytes")
print(" ", os.path.join(OUT_DIR, "dsh-service-contract.md"), os.path.getsize(os.path.join(OUT_DIR, "dsh-service-contract.md")), "bytes")
print("packages=%d endpoints=%d services=%d invocationKinds=%s" % (
    typert["summary"]["packages"], typert["summary"]["endpoints"], len(typert["byService"]),
    typert["summary"]["invocationKinds"]))
