"""Ant Design 拆表 + 数据表/筛选表 区分: assert_table 选表与读列."""
from __future__ import annotations

from types import SimpleNamespace

from core.runtime.execution.script_helpers import (
    collect_ant_merged_row_cells,
    collect_ant_table_row_at_index,
    perform_table_column_assert,
)


class _FakeTbodies:
    def __init__(self, rows_per_body: list[list[list[str]]]) -> None:
        self._rows_per_body = rows_per_body

    def count(self) -> int:
        return len(self._rows_per_body)

    def nth(self, index: int) -> "_FakeBody":
        return _FakeBody(self._rows_per_body[index])


class _FakeBody:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def locator(self, sel: str) -> "_FakeRows":
        assert sel == "tr"
        return _FakeRows(self._rows)


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

    def locator(self, sel: str) -> "_FakeCells":
        assert sel == "td"
        return _FakeCells(self._cells)


class _FakeCells:
    def __init__(self, cells: list[str]) -> None:
        self._cells = cells

    def count(self) -> int:
        return len(self._cells)

    def nth(self, i: int) -> SimpleNamespace:
        return SimpleNamespace(inner_text=lambda **_: self._cells[i])

    def all_inner_texts(self) -> list[str]:
        return self._cells


class _FakeTheads:
    def __init__(self, header_rows: list[list[str]]) -> None:
        self._header_rows = header_rows

    def count(self) -> int:
        return len(self._header_rows)

    def nth(self, i: int) -> "_FakeThead":
        return _FakeThead(self._header_rows[i])


class _FakeThead:
    def __init__(self, headers: list[str]) -> None:
        self._headers = headers

    def locator(self, sel: str) -> "_FakeThs":
        assert sel == "th"
        return _FakeThs(self._headers)


class _FakeThs:
    def __init__(self, headers: list[str]) -> None:
        self._headers = headers

    def count(self) -> int:
        return len(self._headers)

    def nth(self, i: int) -> SimpleNamespace:
        return SimpleNamespace(inner_text=lambda **_: self._headers[i])

    def all_inner_texts(self) -> list[str]:
        return list(self._headers)


class _FakeHtmlTable:
    def __init__(self, headers: list[str], rows: list[list[str]]) -> None:
        self._headers = headers
        self._rows = rows

    def locator(self, sel: str):
        if sel == "thead th, thead td":
            return _FakeThs(self._headers)
        if sel == "tbody tr":
            return _FakeRows(self._rows)
        raise AssertionError(sel)


class _FakeLocatorList:
    def __init__(self, items: list) -> None:
        self._items = items

    def count(self) -> int:
        return len(self._items)

    def nth(self, i: int):
        return self._items[i]


class _FakeAntContainer:
    def __init__(self, header_groups: list[list[str]], rows_per_body: list[list[list[str]]]) -> None:
        self._header_groups = header_groups
        self._rows_per_body = rows_per_body

    def locator(self, sel: str):
        if sel == ".ant-table-thead":
            return _FakeTheads(self._header_groups)
        if sel == ".ant-table-tbody":
            return _FakeTbodies(self._rows_per_body)
        if sel == ".ant-table-thead th, thead.ant-table-thead th":
            flat = [h for g in self._header_groups for h in g]
            return _FakeThs(flat)
        raise AssertionError(sel)


class _FakePage:
    def __init__(
        self,
        *,
        ant_headers: list[str] | None = None,
        ant_header_groups: list[list[str]] | None = None,
        ant_rows: list[list[str]] | None = None,
        ant_rows_per_body: list[list[list[str]]] | None = None,
        html_tables: list[tuple[list[str], list[list[str]]]] | None = None,
    ) -> None:
        self._ant_headers = ant_headers or []
        self._ant_header_groups = ant_header_groups or (
            [ant_headers] if ant_headers else []
        )
        self._ant_rows = ant_rows or []
        self._ant_rows_per_body = ant_rows_per_body or (
            [ant_rows] if ant_rows else []
        )
        self._html_tables = html_tables or []

    def locator(self, sel: str):
        if sel == ".ant-table":
            if self._ant_header_groups and self._ant_rows_per_body:
                return _FakeLocatorList([
                    _FakeAntContainer(self._ant_header_groups, self._ant_rows_per_body)
                ])
            return _FakeLocatorList([])
        if sel == ".ant-table-thead":
            return _FakeTheads(self._ant_header_groups or (
                [self._ant_headers] if self._ant_headers else []
            ))
        if sel == "thead.ant-table-thead":
            return _FakeTheads([])
        if sel == ".ant-table-tbody":
            return _FakeTbodies(self._ant_rows_per_body or (
                [self._ant_rows] if self._ant_rows else []
            ))
        if sel == "table":
            return _FakeLocatorList(
                [_FakeHtmlTable(h, r) for h, r in self._html_tables]
            )
        raise AssertionError(sel)


def test_collect_ant_merged_row_cells_merges_split_tbodies():
    tbodies = _FakeTbodies([
        [["146816731", "待自审"]],
        [["大学", "大学化学"]],
    ])
    cells = collect_ant_merged_row_cells(tbodies, 0)
    assert cells == ["146816731", "待自审", "大学", "大学化学"]


def test_collect_ant_table_row_at_index_first_data_row():
    tbodies = _FakeTbodies([
        [["146816731", "待自审", "大学", "大学化学"]],
    ])
    rows = collect_ant_table_row_at_index(tbodies, 1, 0)
    assert rows[0][0][1] == "待自审"


def test_perform_table_column_assert_merged_fixed_and_scroll_headers():
    """固定列 thead(状态) + 滚动列 thead(学段/学科) 应对齐合并."""
    page = _FakePage(
        ant_header_groups=[["状态", "题目ID"], ["学段", "学科", "来源"]],
        ant_rows_per_body=[
            [["待自审", "59989148"]],
            [["大学", "大学化学", "策略投放"]],
        ],
    )
    ok, msg = perform_table_column_assert(
        page,
        target_col="状态",
        expected="待自审",
        use_first_row=True,
        display_key="第一行",
    )
    assert ok, msg


def test_perform_table_column_assert_prefers_data_list_over_form_table():
    page = _FakePage(
        ant_header_groups=[["状态", "题目ID"], ["学段", "学科", "来源", "上传时间"]],
        ant_rows_per_body=[
            [["待自审", "59989148"]],
            [["大学", "大学化学", "策略投放", "2026-06-27"]],
        ],
        html_tables=[
            (["状态", "学段", "学科"], [["", "", ""]]),
        ],
    )
    ok, msg = perform_table_column_assert(
        page,
        target_col="学段",
        expected="大学",
        use_first_row=True,
        display_key="第一行",
    )
    assert ok, msg

    ok2, msg2 = perform_table_column_assert(
        page,
        target_col="学科",
        expected="大学化学",
        use_first_row=True,
        display_key="第一行",
    )
    assert ok2, msg2


def test_perform_table_column_assert_missing_column_in_data_list():
    page = _FakePage(
        ant_headers=["题目ID", "学段", "学科"],
        ant_rows=[["59989148", "大学", "大学化学"]],
    )
    ok, msg = perform_table_column_assert(
        page,
        target_col="状态",
        expected="待自审",
        use_first_row=True,
        display_key="第一行",
    )
    assert not ok
    assert "不存在列 '状态'" in msg


def test_perform_table_column_assert_skips_measure_row():
    page = _FakePage(
        ant_headers=["题目ID", "学段", "学科"],
        ant_rows=[
            [""] * 3,  # ant-table-measure-row
            ["59989148", "大学", "大学化学"],
        ],
    )
    ok, msg = perform_table_column_assert(
        page,
        target_col="学段",
        expected="大学",
        use_first_row=True,
        display_key="第一行",
    )
    assert ok, msg


def test_perform_table_column_assert_rejects_form_table_without_row_key_column():
    """仅筛选项列名、无主键列的 html 假表不应覆盖真实 ant 数据表."""
    page = _FakePage(
        ant_headers=["题目ID", "学段", "学科", "来源"],
        ant_rows=[["59989148", "大学", "大学化学", "策略投放"]],
        html_tables=[
            (["状态", "学段", "学科"], [["", "", ""]]),
        ],
    )
    ok, msg = perform_table_column_assert(
        page,
        target_col="学段",
        expected="大学",
        use_first_row=True,
        display_key="第一行",
    )
    assert ok, msg
