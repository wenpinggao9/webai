# 业务资产目录规范（QA 主维护）

业务用例、环境、动作规划、加速记忆放在 `business/` 下，可打包交付；执行排查产物在 `output/`，不传递。

---

## 零基础上手（本地未装 Playwright）

以下假设你只有 **Python 3.11+** 和本仓库 `web_automation` 源码，尚未安装任何依赖。完整跑通一条用例约需 10 分钟。

### 1. 获取工程

```bash
cd /path/to/web_automation    # 克隆或解压后的仓库根目录
```

框架代码（`core/`、`prompts/`、`run.py`、`config.yaml`）**只在本仓库**，不要从别的目录复制覆盖。

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install --with-deps chromium
```

| 步骤 | 作用 |
|------|------|
| `pip install` | 安装 Playwright Python 包、FastAPI、LLM SDK 等 |
| `playwright install chromium` | 下载 Chromium 浏览器（框架默认用 `chromium`） |

macOS 若 `playwright install --with-deps` 报系统库缺失，可先试 `playwright install chromium`；仍失败再按 Playwright 官方文档补系统依赖。

### 3. 配置 LLM（必做）

编辑仓库根目录 `config.yaml` 的 `llm` 区块，选择可用的 `provider`（ / `minimax` / `opus`）并填好 `base_url`、`api_key`、`model`。

- 公司内网代理：按 README 示例使用 `minimax` 或 `opus`等，需能访问对应网关（前提：已申请llm平台权限，主要是替换api_key和模型）。

**没有可用 LLM 时无法跑「规划 + 执行」**；若已有 `actions/*.json`，可先用 `--from-actions` 跳过规划 LLM（定位环节仍可能调 LLM）。

### 4. 将QA给到的项目用例/动作规划、记忆文件、测试资源复制到对应业务下

源目录（以题库的vip视频业务的大学增加前审项目作为示例）：
大学增加前审文件夹

拷贝到目标目录（示例）：

```
web_automation/business/tiku/tiku_video/
```

修改.env
`.env` 字段须与用例里 `角色:` 一致，例如：

```env
ENV=test
BASE_URL=https://www-gwp11-bc.suanshubang.com/video
VPSAPI_BASE_URL=https://www-gwp11-bc.suanshubang.com
VPSCORE_BASE_URL=https://wendamis-gwp11-cc.suanshubang.cc

admin_USERNAME=18600638431
admin_VERIFY_CODE=111111

teacherA_USERNAME=13621190002
teacherA_VERIFY_CODE=111111
teacherA_UID=1001636

teacherB_USERNAME=13621190001
teacherB_VERIFY_CODE=111111
teacherB_UID=1001635

teacherC_k12_USERNAME=18810812516
teacherC_k12_VERIFY_CODE=111111

recording_USERNAME=15212240001
recording_VERIFY_CODE=111111
```

### 5. 验证安装

```bash
# 在仓库根目录、虚拟环境已激活
python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md
```

成功标志：

- 终端无 Python 依赖 / Playwright 浏览器缺失报错
- 浏览器窗口打开（`config.yaml` 里 `playwright.headless: false` 时）
- 生成 `output/ui_runs/<时间戳>/` 与 `business/.../reports/<时间戳>/`

已有规划、想跳过规划 LLM：

```bash
python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md --from-actions
```

---

## QA ↔ 研发协作

```
QA 交付 cases/  →  研发 run.py（规划+执行，写入 actions/）  →  调试用例或改规划复跑  →  全绿 export_handoff  →  QA 按 delivery/ 验收
```

| 角色 | 要点 |
|------|------|
| **QA** | 维护 `cases/<文件名>.md`；`.env` 不提交 Git，账号单独给研发 |
| **研发** | 完成上文安装与 `.env`；失败时改用例重跑，或改 `actions/*_actions.json` 后 `--from-actions` |
| **QA 验收** | 以 `delivery/<version>/` 中 cases + actions + selectors 为准，`--from-actions` 复跑并对照报告 |

**交付物**

| 路径 | 说明 |
|------|------|
| `cases/<文件名>.md` | 用例主真相源（QA 维护） |
| `actions/<文件名>_actions.json` | `run.py` 自动写入；`--from-actions` 时读取执行 |

**常用命令**（示例路径 `business/tiku/tiku_video/大学增加前审/cases/前审1.md`）

```bash
# 规划 + 执行（覆盖写入 actions/）
python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md

# 跳过规划 LLM，直接执行已保存 actions
python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md --from-actions

# 全绿后打交付包（--promote-plans 将批次规划写入 actions/）
python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 \
  --version 20260629-v1.0 --promote-plans
```

也可通过 API：`POST /api/v1/ui-test/run-preplanned`

**说明**

- 排查只看 `output/ui_runs/<时间戳>/`，不提交、不交付
- 交付后研发不再改 `prompts/`；QA 按冻结的 cases + actions + accel 验收
- `export_handoff` 默认附带最近批次报告到 `delivery/<version>/reports/`

---

## 目录结构

```
business/
├── <方向>/                         # 业务方向，如 tiku、zuoyebang（可选层级）
│   ├── .env / direction.env        # 方向级环境（可选，子业务/项目可覆盖）
│   │
│   └── <业务>/                     # 业务线，如 tiku_video、zbtiku
│       ├── .env / business.env     # 业务级环境（可选）
│       ├── domain_knowledge.md     # API、枚举、登录页（稳定）
│       ├── selectors/              # 智能加速（仅 cache/memory/structure 数据）
│       │   ├── cache/              # L1
│       │   ├── memory/             # L2 按 route 分文件
│       │   └── structure/          # L4
│       │
│       └── <项目>/                 # 如 大学增加前审
│           ├── .env / project.env  # 项目环境 + 账号（不提交 Git）
│           ├── cases/              # 用例 Markdown（QA 主维护）
│           ├── actions/            # 动作规划（或旧名 action_plans/）
│           ├── reports/            # 业务批次报告镜像
│           ├── resources/          # 测试资源
│           ├── testsuites/         # 批量编排（可选）
│           └── delivery/           # 提测冻结快照
```

旧二层结构 `business/<业务>/<项目>/` 仍兼容（无方向层时 `direction_dir` 为空）。

运行示例：

```bash
python run.py business/tiku/tiku_video/大学增加前审/cases/前审12-test.md
python run.py business/tiku/tiku_video/大学增加前审/cases/前审12-test.md --from-actions
```

---

## 环境与账号：`.env`

合并顺序（后者覆盖前者）：`<方向>/.env` → `<业务>/.env` → `<项目>/.env` → 进程环境变量。

```env
BASE_URL=https://test.example.com/video

admin_USERNAME=18600638431
admin_VERIFY_CODE=111111

teacherA_USERNAME=13621190002
teacherA_VERIFY_CODE=111111
```

- `<角色>_USERNAME` / `<角色>_VERIFY_CODE`（或 `ROLE_<角色>_USERNAME` 旧格式）
- 角色名须与用例里 `角色:` 字段一致

---

## 领域知识：`domain_knowledge.md`

放在业务系统级，描述**稳定**内容：API、登录页、枚举、session 字段。账号密码放 `.env`。

---

## 用例：`cases/*.md`

- 一个 `.md` 可含多条用例（`#### 用例ID：xxx`）；规划文件按 **md 文件名** 聚合，不按单条 case_id 分文件
- QA 主维护用例；规划由 `run.py` 自动生成或人工编辑后 `--from-actions` 执行

---

## 动作规划：`actions/<用例文件名>_actions.json`

`run.py` 每次执行后自动写入（覆盖整文件）。使用 `--from-actions` 或 API `run-preplanned` 可跳过 LLM 规划直接执行。

文件结构示例：

```json
{
  "cases": [
    {
      "case_id": "vip_前审_001",
      "module": "大学前审",
      "priority": "P0",
      "origin_case": { "preconditions": [], "steps": [], "expectations": [] },
      "actions": [ { "type": "click", "intent": "点击提交" } ]
    }
  ]
}
```

---

## 加速记忆：`selectors/`（或 `accel_memory/`）

业务系统级共享，框架执行后自动更新。交付包仅含 L2 + L4，不含 L1。

---

## 交付包：`delivery/<version>/`

```bash
python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 --version 20260623-v1.0

python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 --version v1.0 \
  --batch output/ui_runs/20260623_143022 --promote-plans
```

```
delivery/20260623-v1.0/
├── manifest.yaml
├── reports/              # 各用例文件验收 HTML（<stem>.html）
├── cases/
├── actions/              # 或 action_plans/
└── selectors/            # L2 + L4 数据（策略见 config.yaml delivery.accel）
```

交付包加速层策略在工程 `config.yaml` → `delivery.accel`（默认 L2+L4，不含 L1）；业务 `selectors/` 下不再维护 `manifest.yaml`。

---

## 与 `output/` 的边界

| 目录 | 谁维护 | 是否传递 |
|------|--------|----------|
| `business/` | QA + 研发 | 是 |
| `output/ui_runs/` | 框架自动生成 | 否（本地排查） |
| `prompts/` | 框架研发 | 提测后冻结，不进交付包 |
