"""诊断 assert_table 候选表: 登录已上传页, 枚举所有 table 候选及评分."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from core.ports.business.env import load_merged_project_env
from core.runtime.execution.script_helpers import (
    _enumerate_table_matrix_candidates,
    _pick_best_table_candidate,
    _score_table_candidate,
    collect_merged_ant_page_headers,
    perform_table_column_assert,
)
from core.runtime.session.login import login


def _dump_candidates(page, target_col: str) -> None:
    print(f"\n=== target_col={target_col!r} ===")
    page_headers = collect_merged_ant_page_headers(page)
    print(f"merged page headers ({len(page_headers)}): {page_headers[:20]}")
    best = None
    best_score = -999
    for headers, get_row_cells, row_count, kind in _enumerate_table_matrix_candidates(page):
        score = _score_table_candidate(
            headers, get_row_cells, row_count, target_col, use_first_row=True,
        )
        cells0 = get_row_cells(0) if row_count else []
        col_idx = headers.index(target_col) if target_col in headers else -1
        actual = cells0[col_idx] if 0 <= col_idx < len(cells0) else "<n/a>"
        print(
            f"  [{kind}] score={score} rows={row_count} "
            f"headers={headers[:8]}{'...' if len(headers) > 8 else ''} "
            f"row0={cells0[:8]}{'...' if len(cells0) > 8 else ''} "
            f"col[{col_idx}]={actual!r}"
        )
        if score > best_score:
            best_score = score
            best = (kind, headers, cells0, col_idx, actual)
    picked = _pick_best_table_candidate(page, target_col, use_first_row=True)
    if picked:
        h, _, rc, kind, ci = picked
        print(f"  PICKED: {kind} col_idx={ci} header={h[ci] if ci < len(h) else '?'}")
    if best:
        print(f"  BEST_SCORE: {best[0]} col={best[3]} actual={best[4]!r}")
    ok, msg = perform_table_column_assert(
        page, target_col=target_col, expected="?", use_first_row=True, display_key="第一行",
    )
    print(f"  perform_table_column_assert ok={ok} msg={msg[:120]}")


def main() -> None:
    project_dir = ROOT / "business/tiku/tiku_video/大学增加前审"
    system_dir = ROOT / "business/tiku/tiku_video"
    env = load_merged_project_env(
        system_dir, project_dir, extra_env_file=project_dir / ".env",
    )
    base_url = env.get("BASE_URL") or "https://www-gwp11-bc.suanshubang.com/video"
    username = env.get("recording_USERNAME") or env.get("admin_USERNAME") or ""
    verify_code = env.get("recording_VERIFY_CODE") or env.get("admin_VERIFY_CODE") or "111111"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        login(
            page,
            {
                "base_url": base_url,
                "username": username,
                "verify_code": verify_code,
                "phone_placeholder": "请输入手机号",
                "code_placeholder": "请输入验证码",
            },
            force=True,
            verify_code=verify_code,
        )
        page.goto(f"{base_url.rstrip('/')}/already-upload", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # 关闭可能遮挡操作的弹窗
        for sel in (
            ".ant-modal-wrap button:has-text('知道了')",
            ".ant-modal-wrap button:has-text('确定')",
            ".ant-modal-wrap .ant-modal-close",
        ):
            btn = page.locator(sel)
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=2000)
                page.wait_for_timeout(500)

        # 清状态筛选 + 提交 (与 Case 16 一致)
        clear = page.locator(
            "xpath=(//label[contains(normalize-space(.), '状态')]/following::*"
            "[contains(@class,'ant-select')][1]//*[contains(@class,'ant-select-clear') "
            "or @aria-label='close-circle'])[1]"
        )
        if clear.count():
            try:
                clear.first.click(timeout=5000)
                page.wait_for_timeout(500)
            except Exception as e:
                print(f"WARN: clear status skipped: {e}")
        submit = page.get_by_role("button", name="提 交")
        if submit.count():
            submit.first.click()
            page.wait_for_timeout(3000)

        print(f"URL: {page.url}")
        print(f"ant-table count: {page.locator('.ant-table').count()}")
        print(f"html table count: {page.locator('table').count()}")

        for col in ("状态", "学段", "学科", "题目ID"):
            _dump_candidates(page, col)

        # 深入: 第一行 td 的各种读法
        print("\n=== CELL READ METHOD COMPARISON (row 0) ===")
        row = page.locator(".ant-table-tbody tr").first
        tds = row.locator("td")
        n = tds.count()
        print(f"td count in first tbody tr: {n}")
        for i in range(min(n, 5)):
            td = tds.nth(i)
            methods = {}
            for name, fn in [
                ("inner_text", lambda t=td: t.inner_text(timeout=1000)),
                ("text_content", lambda t=td: t.text_content(timeout=1000) or ""),
                ("all_inner_texts", lambda t=td: t.locator("*").all_inner_texts()),
            ]:
                try:
                    methods[name] = fn()
                except Exception as ex:
                    methods[name] = f"ERR:{ex}"
            print(f"  td[{i}]: {methods}")

        # 用 evaluate 读 table 矩阵
        matrix = page.evaluate("""() => {
          const rows = [...document.querySelectorAll('.ant-table-tbody tr')].slice(0, 3);
          return rows.map((tr, ri) => {
            const tds = [...tr.querySelectorAll('td')];
            return {
              ri,
              tdCount: tds.length,
              cells: tds.map(td => ({
                innerText: (td.innerText || '').trim(),
                textContent: (td.textContent || '').trim(),
                html: td.innerHTML.slice(0, 120),
              })),
            };
          });
        }""")
        print("\n=== JS evaluate first 3 tbody rows ===")
        for row_info in matrix:
            print(f"  row {row_info['ri']}: tdCount={row_info['tdCount']}")
            for j, c in enumerate(row_info["cells"][:5]):
                print(f"    [{j}] innerText={c['innerText']!r} textContent={c['textContent']!r}")

        browser.close()


if __name__ == "__main__":
    main()
