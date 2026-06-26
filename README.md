# ui_automation

用中文 Markdown 写 UI 用例，框架自动完成登录、导航、动作规划、元素定位、执行与报告。测试人员无需写选择器或 Playwright 代码。

---

## 安装

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

---

## 配置

编辑根目录 `config.yaml`：

| 区块 | 作用 |
|------|------|
| `llm` | 模型提供商（`ollama` / `minimax` / `opus`）及 API |
| `target` | 无业务 `project.env` 时的兜底登录页与账号 |
| `playwright` | 浏览器类型、`headless`、超时 |
| `runner` | 就绪检查、后校验、跨用例会话等开关 |
| `acceleration` | L1/L4 加速层参数 |
| `locating` | L5 大模型 DOM 窗口大小 |

环境与多角色账号优先写在业务项目的 `project.env`（见 [business/README.md](business/README.md)），不必写进 `config.yaml`。

---

## 跑第一条用例

```bash
# 单个用例
python run.py business/vip_video/大学增加前审/cases/前审1.md

# 整个 cases 目录
python run.py business/vip_video/大学增加前审/cases/

# 指定本次使用的 project.env
python run.py business/vip_video/大学增加前审/cases/前审1.md \
  --env-file business/vip_video/大学增加前审/project.env
```

运行后在 `output/ui_runs/<时间戳>/` 生成报告、追踪、截图等（不纳入业务交付）。

---

## 常用命令

```bash
# 单元 / 组件测试（跳过需浏览器的集成测试）
pytest -m "not integration"

# 导出研发 → QA 交付包
python tools/export_handoff.py business/vip_video/大学增加前审 --version 20260623-v1.0

# 附带验收报告并晋升动作规划
python tools/export_handoff.py business/vip_video/大学增加前审 --version v1.0 \
  --batch output/ui_runs/20260623_143022 --promote-plans

# 启动 HTTP 服务（可选）
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

---

## 用例怎么写（极简）

```markdown
#### 用例ID：前审_001

##### 操作步骤
1. 在「待领取」列表点击第一条「领取」

##### 预期结果
- 任务状态变为「待审核」
```

完整格式见 [docs/框架说明.md](docs/框架说明.md) 步骤①，或参考 `business/*/cases/` 下现有用例。

---

## 文档索引

| 文档 | 读者 | 内容 |
|------|------|------|
| [docs/框架说明.md](docs/框架说明.md) | 研发 | 流水线、五级定位、后校验、设计取舍 |
| [docs/目录规范.md](docs/目录规范.md) | 研发 + QA | `business/`、`core/`、`output/` 目录结构 |
| [business/README.md](business/README.md) | QA | `project.env`、`action_plans/`、交付包协作 |

---

## 许可证

最佳实践：回归默认走 Hash；发版验收走 --from-actions；大版本 UI 改版后先 --force-plan 一轮再回归。
