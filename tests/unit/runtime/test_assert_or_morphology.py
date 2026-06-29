"""或断言: 通用主区布局 (table_dominant / form_dominant), 排除侧栏误判."""
from __future__ import annotations

from core.runtime.execution.assert_or import try_or_branches, try_or_heuristic
from core.runtime.execution.page_morphology import (
    MainContentMorphology,
    main_content_contains,
    token_only_in_nav,
)


class _MorphPage:
    def __init__(self, morph_data: dict, *, main_override: str = "", nav_override: str = "") -> None:
        self._morph_data = dict(morph_data)
        if main_override:
            self._morph_data["main_text"] = main_override
        if nav_override:
            self._morph_data["nav_text"] = nav_override
        self.url = "https://example.com/app/record/1"

    def evaluate(self, script: str):
        return self._morph_data

    def inner_text(self, _sel: str) -> str:
        nav = self._morph_data.get("nav_text") or "MenuA\nMenuB"
        main = self._morph_data.get("main_text") or ""
        return f"{nav}\n{main}"


def _morph(**kwargs) -> dict:
    base = {
        "main_text": "",
        "nav_text": "",
        "data_rows": 0,
        "has_table_shell": False,
        "input_count": 0,
        "choice_count": 0,
        "layout": "mixed",
        "table_score": 0,
        "form_score": 0,
    }
    base.update(kwargs)
    return base


def test_token_only_in_nav():
    morph = MainContentMorphology(
        nav_text="SidebarItemX\nOther",
        main_text="Record field value",
    )
    assert token_only_in_nav(morph, "SidebarItemX")
    assert not token_only_in_nav(morph, "Record")


def test_list_branch_fails_when_nav_token_not_in_main():
    page = _MorphPage(
        _morph(
            layout="form_dominant",
            main_text="Field A\nOption B\nSubmit",
            nav_text="SidebarItemX",
            form_score=5,
            choice_count=3,
            input_count=4,
        ),
        nav_override="SidebarItemX",
    )
    body = page.inner_text("body")
    assert "SidebarItemX" in body
    hit = try_or_branches(
        page,
        [{"intent": "验证页面回到列表页", "value": "SidebarItemX"}],
        body,
    )
    assert hit is None


def test_list_branch_passes_on_table_dominant():
    page = _MorphPage(_morph(
        layout="table_dominant",
        main_text="Col1 Col2 Col3\nv1 v2 v3\nv4 v5 v6",
        data_rows=3,
        has_table_shell=True,
        table_score=4,
        form_score=0,
    ))
    hit = try_or_branches(
        page,
        [{"intent": "验证页面回到列表页", "value": "SidebarItemX"}],
        page.inner_text("body"),
    )
    assert hit is not None
    assert hit[0]
    assert "table_dominant" in hit[1]


def test_form_branch_passes_on_form_dominant():
    page = _MorphPage(_morph(
        layout="form_dominant",
        main_text="Name\nOption1\nOption2\nSave",
        choice_count=2,
        input_count=3,
        form_score=5,
        table_score=0,
    ))
    hit = try_or_heuristic(
        page,
        "验证页面自动加载下一条记录详情页",
        branch_value="",
    )
    assert hit is not None
    assert hit[0]
    assert "form_dominant" in hit[1]


def test_main_content_rejects_nav_only_token():
    morph = MainContentMorphology(
        nav_text="SidebarItemX",
        main_text="Field content only",
        layout="form_dominant",
    )
    page = _MorphPage(_morph(layout="form_dominant", main_text="Field content only"), nav_override="SidebarItemX")
    assert not main_content_contains(page, "SidebarItemX", morphology=morph)


def test_mixed_layout_defers_to_semantic_layer():
    page = _MorphPage(_morph(
        layout="mixed",
        main_text="Both table and form",
        table_score=2,
        form_score=2,
    ))
    hit = try_or_branches(
        page,
        [{"intent": "验证页面回到列表页"}],
        page.inner_text("body"),
    )
    assert hit is None
