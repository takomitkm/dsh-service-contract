#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage a clean GitHub repo tree from the local deliverables + extraction scripts.

Does NOT touch GitHub. Only copies files and writes README/LICENSE/.gitignore
into the target directory so `git init` + `gh repo create --push` can run after.
"""
import os
import shutil
import sys

SRC_CONTRACT = r"S:\apps\llm\agentwork\dsh-contract"
SRC_TMP = r"S:\apps\llm\agentwork\.tmp"
OUT = r"S:\apps\llm\agentwork\dsh-service-contract"

# (source path, destination relative path)
FILES = [
    (os.path.join(SRC_CONTRACT, "contract.json"), "contract.json"),
    (os.path.join(SRC_CONTRACT, "dsh-service-contract.md"), "dsh-service-contract.md"),
    (os.path.join(SRC_TMP, "fetch_dsh_src.py"), "fetch_dsh_src.py"),
    (os.path.join(SRC_TMP, "extract-typert.mjs"), "extract_typert.mjs"),
    (os.path.join(SRC_TMP, "extract_layerc.py"), "extract_layerc.py"),
    (os.path.join(SRC_TMP, "build_contract.py"), "build_contract.py"),
    (os.path.join(SRC_TMP, "validate_contract.py"), "validate_contract.py"),
]

README = r"""# dsh-service-contract

DSH（DeepSeek Harness）插件实际依赖的**服务面契约**。

## 背景

DSH 侧没有正式的服务面 spec。要把一个 DSH 插件"一模一样"地对接，得先把它实际依赖的
服务面梳理成显式契约：哪些方法、什么 payload。本仓库就是这个显式契约，以及生成它的
可复现脚本。

## 三层服务面

| 层 | 服务面 | 取源 | 覆盖范围 |
|---|---|---|---|
| A | SDK JSON-RPC | `dsh-sdk-protocol` 的 README | 16 方法（8 client→server + 8 server→client） |
| B | Typert Remote（Host↔Client RPC） | 由 Host FaceModel 生成器产出 | 38 服务 / 193 端点 / 全 `direct` 调用 |
| C | 进程内 Cordis `ctx.*` | `deepseek-ai/deepseek-harness` @ `dsh-v0.2.2-rc.1` 公开 `.ts` | 148 生产键 / 1284 方法签名 |

## 取源版本（锁定）

全部基于 tag **`dsh-v0.2.2-rc.1`**（commit `66491b05e3f05ad35bcdd4f6cd7ed26041d9e3db`），
即本机正运行的 DSH 桌面 `0.2.2-rc.1`。**未用** `master`、也未用 `rc.2`/`rc.3`/`alpha` 等其它标签。

## Layer C 是类型化抽取，不是反推

服务键的提供类型**直接读公开仓库的 `.ts` 声明合并**：

```ts
declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }
```

运行期注册（`ctx.provide` / `ctx.reflect.provide` / `static inject`）再用**本地 asar 编译后
的 `.js`** 交叉核对。npm 不发 `.ts` 源码、同一包的 `.d.ts` 在本地 asar 里也缺失，所以并非
从 `.js` 反推。npm 上的 `.d.ts` 仅作独立参考。

## 文件

- `contract.json` — 机器可读契约（`meta` + `layerA_sdk_jsonrpc` + `layerB_typert_remote` + `layerC_cordis_ctx`）。
- `dsh-service-contract.md` — 人工可读契约（与 JSON 同源生成）。
- `fetch_dsh_src.py` — 下载 rc.1 源码树（codeload 全量 tarball）。
- `extract_typert.mjs` — Layer B Typert 端点抽取。
- `extract_layerc.py` — Layer C Cordis `ctx.*` 抽取（声明合并 + asar 交叉核对）。
- `build_contract.py` — 汇编成 `contract.json` + `dsh-service-contract.md`。
- `validate_contract.py` — 校验交付物（键/覆盖度/标记/陈旧占位符）。

## 重新生成

```powershell
# 1) 拉 rc.1 源码（首次）
& python.exe fetch_dsh_src.py

# 2) 抽 Layer B（Node ESM）
node extract_typert.mjs <@deepseek-ai 目录> typert-contract.json

# 3) 抽 Layer C（读本地源码树 + asar）
& python.exe extract_layerc.py

# 4) 组装
& python.exe build_contract.py

# 5) 校验
& python.exe validate_contract.py
```

## 诚实度（honesty）

- **Layer B** schema 精确（由 Host FaceModel 生成器产出）；`result.schemaError` 缺失是生成器
  限制（dict/union/void 等），非源数据缺失。
- **Layer A** payload 形状从协议 README 转录（TS 类型在 shipped `.js` 里被擦除）。
- **Layer C** 类型化抽取自官方 rc.1 `.ts`，交叉核对本地 asar `.js`（135/148 生产键可见）。

## 未覆盖（机制事实，非建议）

协议版本协商（DSH 明说没有）；cancel / session-close（DSH 明说没有）。个别生成器未导出的
运行期动态方法可能未列全。

## 许可

本仓库的契约文本与脚本以 **MIT** 许可发布。契约内容 derived from
[`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness)（MIT）
在 tag `dsh-v0.2.2-rc.1` 的公开源码；本仓库不重新分发上游源码。
"""

LICENSE = (
    "MIT License\n\n"
    "Copyright (c) 2026 takomitkm\n\n"
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    "of this software and associated documentation files (the \"Software\"), to deal\n"
    "in the Software without restriction, including without limitation the rights\n"
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
    "copies of the Software, and to permit persons to whom the Software is\n"
    "furnished to do so, subject to the following conditions:\n\n"
    "The above copyright notice and this permission notice shall be included in all\n"
    "copies or substantial portions of the Software.\n\n"
    "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n"
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n"
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n"
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n"
    "SOFTWARE.\n"
)

GITIGNORE = "# 不提交本地巨量源码树 / 临时产物\n.tmp/\n*.tar.gz\nnode_modules/\n"


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, dst in FILES:
        if not os.path.exists(src):
            print("MISSING: %s" % src, file=sys.stderr)
            sys.exit(1)
        dest = os.path.join(OUT, dst)
        shutil.copyfile(src, dest)
        print("copied: %s -> %s (%d bytes)" % (src, dst, os.path.getsize(src)))
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)
    with open(os.path.join(OUT, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(LICENSE)
    with open(os.path.join(OUT, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(GITIGNORE)
    print("STAGED at: %s" % OUT)


if __name__ == "__main__":
    main()
