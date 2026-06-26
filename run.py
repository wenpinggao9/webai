"""UI 自动化框架 CLI 入口.

单用例:  python run.py business/tiku/tiku_video/大学增加前审/cases/前审1.md
批量目录: python run.py business/tiku/tiku_video/大学增加前审/cases/

默认: 每次执行均走动作规划 + 执行，规划结果写入 actions/<用例文件名>_actions.json
预规划执行: python run.py .../cases/测试用例.md --from-actions
API 预规划: POST /api/v1/ui-test/run-preplanned
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from core.agent import UITestAgent
from core.business_loader import BusinessLoader
from core.ports.business.plan_store import load_preplanned_map_for_file


def load_config(path: Path) -> dict:
    """读取 YAML 配置文件, 供 Agent 初始化 LLM、浏览器和运行参数."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def discover_cases(path: Path) -> list[Path]:
    """支持传入单个 .md 用例文件, 或传入目录批量发现目录下的 .md 用例."""
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.md") if p.is_file())
    raise FileNotFoundError(path)


def _prepare_from_actions(agent: UITestAgent, case_file: Path, env_file: str | None) -> bool:
    """加载 actions/<stem>_actions.json 到 agent，供预规划执行."""
    biz = BusinessLoader()
    if not biz.discover(str(case_file), env_file=env_file) or not biz.project_dir:
        print(f"无法发现业务目录: {case_file}", file=sys.stderr)
        return False
    stem = case_file.stem
    plan_map = load_preplanned_map_for_file(biz.project_dir, stem)
    if not plan_map:
        from core.ports.business.plan_store import case_file_actions_path
        expected = case_file_actions_path(biz.project_dir, stem)
        print(f"未找到预规划文件: {expected}", file=sys.stderr)
        return False
    agent._file_preplanned_map = plan_map
    agent._from_actions_mode = True
    print(f"预规划模式: 已加载 {len(plan_map)} 条用例动作 ({stem}_actions.json)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="用例文件(.md)或目录")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument(
        "--env-file",
        default=None,
        help="Override project.env path for this run",
    )
    ap.add_argument(
        "--from-actions",
        action="store_true",
        help="从 actions/<用例文件名>_actions.json 读取规划并执行，跳过 LLM 规划",
    )
    args = ap.parse_args()

    root = Path(__file__).parent
    config = load_config(root / args.config)

    cases = discover_cases(Path(args.target))
    if not cases:
        print(f"未发现 .md 用例: {args.target}", file=sys.stderr)
        return 2

    agent = UITestAgent(config, project_root=root)

    any_failed = False
    for case_file in cases:
        agent._file_preplanned_map = {}
        agent._from_actions_mode = False
        agent._preplanned_actions = None
        if args.from_actions:
            if not _prepare_from_actions(agent, case_file, args.env_file):
                return 2
        summary = agent.run_tests(str(case_file), env_file=args.env_file)
        if summary["失败数"] > 0:
            any_failed = True

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
