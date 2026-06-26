"""assert_table 同工单多行: ANY 默认 + match_all 可选."""
from __future__ import annotations

from core.runtime.execution.session_ops import evaluate_table_column_assert


def _rows(*uid_and_reason: tuple[str, str]) -> list[tuple[list[str], str]]:
    # [类型, 工单ID, 任务ID, 审核老师UID, 举报原因]
    return [
        (
            ["前审", "146713400", "t1", uid, reason],
            "146713400",
        )
        for uid, reason in uid_and_reason
    ]


def test_any_matches_second_row_uid():
    rows = _rows(("1001635", "多题"), ("1001636", "多题"))
    ok, _ = evaluate_table_column_assert(
        rows, 3, "审核老师UID", "1001636", row_key="146713400",
    )
    assert ok


def test_any_matches_first_row_uid():
    rows = _rows(("1001635", "多题"), ("1001636", "多题"))
    ok, _ = evaluate_table_column_assert(
        rows, 3, "审核老师UID", "1001635", row_key="146713400",
    )
    assert ok


def test_match_all_requires_every_row():
    rows = _rows(("1001635", "多题"), ("1001636", "其他"))
    ok, msg = evaluate_table_column_assert(
        rows, 4, "举报原因", "多题", match_all=True, row_key="146713400",
    )
    assert not ok
    assert "实际" in msg


def test_match_all_passes_when_all_rows_match():
    rows = _rows(("1001635", "多题"), ("1001636", "多题"))
    ok, msg = evaluate_table_column_assert(
        rows, 4, "举报原因", "多题", match_all=True, row_key="146713400",
    )
    assert ok
    assert "2 行" in msg
