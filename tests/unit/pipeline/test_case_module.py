from core.pipeline.parser import parse_case
from core.pipeline.parser.schema import ParsedCase


def test_resolved_module_from_case_id_prefix():
    case = ParsedCase(case_id="大学前审_流程_011", priority="P0")
    assert case.resolved_module == "大学前审"
    assert case.priority == "P0"


def test_resolved_module_prefers_explicit_module_field(tmp_path):
    md = tmp_path / "case.md"
    md.write_text(
        """# 根

### Case 1

#### 用例ID：大学前审_流程_011

##### 模块
自定义模块

##### 优先级
P1

##### 操作步骤
1. 点击提交
""",
        encoding="utf-8",
    )
    cases = parse_case(md)
    assert len(cases) == 1
    assert cases[0].module == "自定义模块"
    assert cases[0].resolved_module == "自定义模块"
    assert cases[0].priority == "P1"
