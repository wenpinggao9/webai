"""assert_table 首行语义: row_position / intent 归一化与行序取数."""
from __future__ import annotations

from types import SimpleNamespace

from core.runtime.execution.script_helpers import FIRST_TABLE_ROW_KEY
from core.runtime.execution.session_ops import (
    assert_table_row_position,
    collect_table_row_at_index,
    evaluate_table_column_assert,
    normalize_assert_table_first_row,
)


class _FakeRows:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def count(self) -> int:
        return len(self._rows)

    def nth(self, index: int) -> "_FakeRow":
        return _FakeRow(self._rows[index])


class _FakeRow:
    def __init__(self, cells: list[str]) -> None:
        self._cells = cells

    def locator(self, _sel: str) -> "_FakeCells":
        return _FakeCells(self._cells)


class _FakeCells:
    def __init__(self, cells: list[str]) -> None:
        self._cells = cells

    def all_inner_texts(self) -> list[str]:
        return self._cells


def _action(**kwargs):
    defaults = {"type": "assert_table", "value": "", "intent": "", "extras": {}}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_normalize_row_index_to_first_row():
    act = _action(
        value="1",
        intent="验证列表第一行数据的状态为待自审",
        extras={"column": "状态", "expected": "待自审", "row_index": 1},
    )
    assert normalize_assert_table_first_row(act) is True
    assert act.value == FIRST_TABLE_ROW_KEY
    assert act.extras["row_position"] == "first"


def test_assert_table_row_position_from_intent():
    act = _action(
        intent="验证列表第一行数据的学科为大学化学",
        extras={"column": "学科", "expected": "大学化学"},
    )
    assert assert_table_row_position(act) == 0


def test_collect_table_row_at_index_skips_empty_marker():
    body = _FakeRows([
        ["暂无数据"],
        ["待自审", "大学", "大学化学"],
    ])
    rows = collect_table_row_at_index(body, 0)
    assert len(rows) == 1
    cells, _ = rows[0]
    assert cells[0] == "待自审"


def test_collect_table_row_at_index_skips_ant_measure_row():
    """Ant Design measure-row: 全空单元格, 不应当作首行数据."""
    from core.runtime.execution.script_helpers import _is_empty_table_row_cells

    measure_cells = [""] * 17
    assert _is_empty_table_row_cells(measure_cells) is True

    body = _FakeRows([
        measure_cells,
        ["59989148", "大学", "-", "大学化学", "策略投放"],
    ])
    rows = collect_table_row_at_index(body, 0)
    assert len(rows) == 1
    cells, _ = rows[0]
    assert cells[0] == "59989148"
    assert cells[1] == "大学"


def test_evaluate_first_row_column_assert():
    rows = [(["待自审", "大学", "大学化学"], "row0")]
    ok, msg = evaluate_table_column_assert(
        rows, 1, "学段", "大学", row_key="第一行",
    )
    assert ok
    assert "大学" in msg
