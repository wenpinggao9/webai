# 业务资产目录规范（QA 主维护）

业务用例、环境、动作规划、加速记忆放在 `business/` 下，可打包交付；执行排查产物在 `output/`，不传递。

---

## QA ↔ 研发 协作流程

```
① QA 提供用例（或预跑规划供先行 check）
        ↓
② 研发 python run.py .../cases/<用例文件>.md  （每次规划 + 执行，写入 actions/<文件名>_actions.json）
        ↓
③ 与需求不一致时：研发改用例后重新 run.py；或改规划后用 --from-actions 复跑
        ↓
④ 全绿后 export_handoff --promote-plans --batch ...  → 交付 QA 提测（此后研发不改 prompts/）
```

### ① QA 侧

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 用例（必） | `cases/<文件名>.md` | 主真相源，一个文件可含多条 case |
| 规划（自动） | `actions/<文件名>_actions.json` | `run.py` 每次规划后自动写入；`--from-actions` 时读取执行 |

```bash
# 默认：每次规划 + 执行，结果写入 actions/测试用例_actions.json
python run.py business/tiku/tiku_video/大学增加前审/cases/测试用例.md

# 使用已保存的规划直接执行（跳过 LLM 规划）
python run.py business/tiku/tiku_video/大学增加前审/cases/测试用例.md --from-actions
```

或通过 API：`POST /api/v1/ui-test/run-preplanned`

### ② 研发侧：跑用例

```bash
python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md
```

| 命令 | 行为 |
|------|------|
| `run.py cases/测试用例.md` | 每次 LLM 动作规划 → 执行 → 覆盖写入 `actions/测试用例_actions.json` |
| `run.py ... --from-actions` | 读取 `actions/测试用例_actions.json`，跳过规划 LLM |

### ③ 研发调试迭代

- 改**用例**：直接 `run.py` 重跑，会自动重新规划并更新 `actions/<文件名>_actions.json`
- 改**规划**：编辑 `actions/<文件名>_actions.json` 中对应 case 的 `actions`，再 `--from-actions` 复跑

排查产物只看 `output/ui_runs/<时间戳>/`，**不提交、不交付**。

### ④ 提测交付

全绿后，把本批次规划晋升并打交付包：

```bash
python tools/export_handoff.py business/tiku/tiku_video/大学增加前审 \
  --version 20260623-v1.0 \
  --promote-plans
```

- `--promote-plans`：将批次 `planned_actions.json` 写入项目 `actions/`
- 默认附带 `output/ui_runs` 中各用例文件最近一次跑测报告（`reports/<用例文件>.html`）
- 交付后 **研发不再改 `prompts/`**；QA 按冻结的 cases + actions + accel 复跑验收
- 提测版本号写入 `delivery/<version>/`，QA 以此为准

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
