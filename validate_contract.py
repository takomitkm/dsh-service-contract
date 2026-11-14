#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate regenerated contract.json (Layer A/B/C) + markdown Layer C section."""
import json, os

ROOT = r"S:\apps\llm\agentwork"
P = os.path.join(ROOT, "dsh-contract", "contract.json")
MD = os.path.join(ROOT, "dsh-contract", "dsh-service-contract.md")

d = json.load(open(P, encoding="utf-8"))
c = d["layerC_cordis_ctx"]
print("top-level keys:", list(d.keys()))
print("layerC keys:", list(c.keys()))
print("coverage:", c["coverage"])
print("services count:", len(c["services"]))
print("injectEdges:", len(c["injectEdges"]), "provideCalls:", len(c["provideCalls"]),
      "ctxGetCalls:", len(c["ctxGetCalls"]))
print("testFixtures count:", c["testFixtures"]["count"], "keys:", len(c["testFixtures"]["keys"]))
print("meta.honesty:", d["meta"]["honesty"][:180])
print("layers C:", d["meta"]["layers"]["C_cordis_ctx"][:140])
print("layerB endpoints:", len(d["layerB_typert_remote"]["byService"]), "services")
print("layerA methods:", len(d["layerA_sdk_jsonrpc"]["methods"]))
print()
for s in c["services"]:
    if s["key"] in ("jobController", "typertGateway", "fs", "sandbox", "approval"):
        print("SPOT", s["key"], "| type", s["type"], "| methods", len(s["methods"]),
              "| asar", s["asar"]["seen"], "| prov", len(s["providers"]),
              "| cons", len(s["consumers"]), "| cover", s["methodCoverage"])
print()
# method sample
s0 = next(s for s in c["services"] if s["methods"])
print("sample service:", s0["key"], "first 3 methods:")
for m in s0["methods"][:3]:
    print("  -", m["name"], ":", m["signature"][:120])
print()
# markdown checks
txt = open(MD, encoding="utf-8").read()
lines = txt.splitlines()
print("markdown lines:", len(lines), "bytes:", os.path.getsize(MD))
for marker in ("# DSH 插件服务面契约（Layer A + B + C）",
               "# Layer C — 进程内 Cordis `ctx.*` 服务面",
               "## C.1 机制", "## C.2 覆盖度", "## C.3 服务目录", "## C.4 方法索引",
               "Layer C 是类型化抽取，不是反推"):
    print("MD marker", repr(marker[:30]), "OK" if marker in txt else "MISSING")
print("stale placeholder present:", "not-in-scope-this-pass" in txt or "（未覆盖）" in txt or "C 待补" in txt)
