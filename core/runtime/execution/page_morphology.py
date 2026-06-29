"""主内容区布局识别 —— 仅结构特征 (table_dominant / form_dominant), 无业务文案."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .assert_scope import extract_page_regions


_MORPHOLOGY_JS = r"""() => {
  const main = document.querySelector(
    'main, [role="main"], .ant-layout-content, .ant-pro-page-container'
  ) || document.body;
  const nav = document.querySelector(
    'nav, aside, [role="navigation"], [role="complementary"], .ant-layout-sider'
  );

  const clip = (el, n) => ((el && el.innerText) || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const mainText = clip(main, 4000);
  const navText = clip(nav, 2000);

  let dataRows = 0;
  let hasTableShell = false;
  let hasEmptyPlaceholder = false;
  main.querySelectorAll('.ant-table-tbody, table tbody').forEach(tb => {
    hasTableShell = true;
    tb.querySelectorAll('tr').forEach(tr => {
      if (tr.classList.contains('ant-table-measure-row')) return;
      if (tr.classList.contains('ant-table-placeholder')) {
        hasEmptyPlaceholder = true;
        return;
      }
      const t = (tr.innerText || '').replace(/\s+/g, ' ').trim();
      if (t && !/暂无数据|无数据|no data/i.test(t)) dataRows += 1;
    });
  });

  const inputs = main.querySelectorAll(
    'input:not([type=hidden]), textarea, select, [role="combobox"], [role="spinbutton"]'
  ).length;
  const choiceControls = main.querySelectorAll(
    'input[type=radio], input[type=checkbox], .ant-radio-wrapper, .ant-checkbox-wrapper, [role="radio"], [role="checkbox"]'
  ).length;
  const buttons = main.querySelectorAll('button, [role="button"], .ant-btn, a.ant-btn').length;

  let tableScore = 0;
  if (hasTableShell) tableScore += 1;
  if (dataRows >= 2) tableScore += 3;
  else if (dataRows === 1) tableScore += 2;
  else if (hasEmptyPlaceholder) tableScore += 1;

  let formScore = 0;
  if (inputs >= 4) formScore += 2;
  else if (inputs >= 1) formScore += 1;
  if (choiceControls >= 1) formScore += 2;
  if (buttons >= 1) formScore += 1;

  let layout = 'mixed';
  if (tableScore >= 3 && formScore <= 2) {
    layout = 'table_dominant';
  } else if (formScore >= 3 && tableScore <= 2) {
    layout = 'form_dominant';
  } else if (tableScore >= 3 && formScore >= 3) {
    layout = dataRows >= 1 ? 'table_dominant' : 'form_dominant';
  }

  return {
    main_text: mainText,
    nav_text: navText,
    data_rows: dataRows,
    has_table_shell: hasTableShell,
    input_count: inputs,
    choice_count: choiceControls,
    layout,
    table_score: tableScore,
    form_score: formScore,
  };
}"""


@dataclass
class MainContentMorphology:
    main_text: str = ""
    nav_text: str = ""
    data_rows: int = 0
    has_table_shell: bool = False
    input_count: int = 0
    choice_count: int = 0
    layout: LayoutKind = "mixed"
    table_score: int = 0
    form_score: int = 0

    @property
    def is_table_dominant(self) -> bool:
        return self.layout == "table_dominant"

    @property
    def is_form_dominant(self) -> bool:
        return self.layout == "form_dominant"

    @property
    def is_list_page(self) -> bool:
        return self.is_table_dominant

    @property
    def is_detail_page(self) -> bool:
        return self.is_form_dominant


def detect_main_content_morphology(page: Any) -> MainContentMorphology:
    """主内容区布局: 数据表主导 vs 表单/单记录面板主导."""
    try:
        raw = page.evaluate(_MORPHOLOGY_JS)
        if isinstance(raw, dict):
            layout = str(raw.get("layout") or "mixed")
            if layout not in ("table_dominant", "form_dominant", "mixed"):
                layout = "mixed"
            return MainContentMorphology(
                main_text=str(raw.get("main_text") or ""),
                nav_text=str(raw.get("nav_text") or ""),
                data_rows=int(raw.get("data_rows") or 0),
                has_table_shell=bool(raw.get("has_table_shell")),
                input_count=int(raw.get("input_count") or 0),
                choice_count=int(raw.get("choice_count") or 0),
                layout=layout,  # type: ignore[arg-type]
                table_score=int(raw.get("table_score") or 0),
                form_score=int(raw.get("form_score") or 0),
            )
    except Exception:
        pass
    regions = extract_page_regions(page)
    return MainContentMorphology(
        main_text=(regions.get("main") or regions.get("body") or "")[:4000],
        nav_text=(regions.get("nav") or "")[:2000],
    )


def token_only_in_nav(morph: MainContentMorphology, token: str) -> bool:
    """token 仅出现在侧栏/导航, 不在主内容区 —— 禁止作为断言依据."""
    t = (token or "").strip()
    if not t or len(t) < 2:
        return False
    in_nav = t in (morph.nav_text or "")
    in_main = t in (morph.main_text or "")
    return in_nav and not in_main


def main_content_contains(
    page: Any,
    needle: str,
    *,
    morphology: MainContentMorphology | None = None,
) -> bool:
    """仅在主内容区文本中查找."""
    target = (needle or "").strip()
    if not target:
        return False
    morph = morphology or detect_main_content_morphology(page)
    if token_only_in_nav(morph, target):
        return False
    hay = morph.main_text
    if not hay:
        regions = extract_page_regions(page)
        hay = regions.get("main") or regions.get("main_left") or ""
    return target in hay
