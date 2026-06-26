from core.ports.business.plan_store import (
    build_plan_entry,
    load_preplanned_map_for_file,
    save_case_file_actions,
)
from core.pipeline.parser.schema import ParsedCase


def test_case_file_actions_roundtrip(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    case = ParsedCase(case_id="vip_前审_001", priority="P0")
    entry = build_plan_entry(
        case,
        {"preconditions": [], "steps": ["点击提交"], "expectations": []},
        [{"type": "click", "intent": "点击提交"}],
    )
    path = save_case_file_actions(project, "测试用例", [entry])
    assert path.name == "测试用例_actions.json"
    plan_map = load_preplanned_map_for_file(project, "测试用例")
    assert "vip_前审_001" in plan_map
    assert plan_map["vip_前审_001"][0].intent == "点击提交"
