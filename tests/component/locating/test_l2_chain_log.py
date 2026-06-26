"""L2 定位链日志: selectors/memory/ 统一为 L2记忆, 不拆分精确/通用."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.locating.memory import SelectorMemory
from core.locating.resolver import LocatorResolver


def _l2_statuses(chain) -> list[str]:
    return [s["status"] for s in chain.steps if s.get("level") == "L2记忆"]


def test_l2_logs_single_miss_when_page_and_generic_fail(monkeypatch, tmp_path):
    memory = SelectorMemory(tmp_path / "mem.json")
    page = MagicMock()
    page.url = "https://x.com/check-history"
    monkeypatch.setattr(
        "core.locating.resolver.validate_selector",
        lambda _p, _info: False,
    )
    monkeypatch.setattr(
        "core.locating.resolver.extract_semantic_items",
        lambda *_a, **_k: [{"class": "ant-form-item"}],
    )
    monkeypatch.setattr(
        "core.locating.skill_resolver.resolve_component_type",
        lambda *_a, **_k: None,
    )

    resolver = LocatorResolver(decider=MagicMock(), cache=None, memory=memory, learner=None)
    from core.locating.resolve_trace import ResolveChain

    chain = ResolveChain(intent="在筛选区点击'审核行为'下拉框", action_type="click")
    hit = resolver._resolve_acceleration_layers(
        page, "在筛选区点击'审核行为'下拉框", "click", set(), None, False, chain,
    )
    assert hit is None
    assert _l2_statuses(chain) == ["未命中"]
    assert not any("通用" in s for s in _l2_statuses(chain))


def test_l2_generic_hit_without_miss_or_generic_note(monkeypatch, tmp_path):
    memory = SelectorMemory(tmp_path / "mem.json")
    memory.put_generic(
        "ant-design",
        "select_trigger",
        "(//div[contains(@class,'ant-form-item')][.//label[contains(normalize-space(.), '{text}')]]//div[contains(@class,'ant-select')])[1]",
    )
    page = MagicMock()
    page.url = "https://x.com/check-history"
    monkeypatch.setattr(
        "core.locating.resolver.validate_selector",
        lambda _p, _info: True,
    )
    monkeypatch.setattr(
        "core.locating.resolver.extract_semantic_items",
        lambda *_a, **_k: [{"class": "ant-select"}],
    )
    monkeypatch.setattr(
        "core.locating.skill_resolver.resolve_component_type",
        lambda *_a, **_k: "select_trigger",
    )
    monkeypatch.setattr(
        "core.locating.skill_resolver.extract_target_text_from_intent",
        lambda _intent: "审核行为",
    )
    monkeypatch.setattr(
        "core.locating.resolver.LocatorResolver._detect_component_library",
        lambda _self: "ant-design",
    )

    from core.locating.resolve_trace import ResolveChain

    resolver = LocatorResolver(decider=MagicMock(), cache=None, memory=memory, learner=None)
    chain = ResolveChain(intent="在筛选区点击'审核行为'下拉框", action_type="click")
    hit = resolver._resolve_acceleration_layers(
        page, "在筛选区点击'审核行为'下拉框", "click", set(), None, False, chain,
    )
    assert hit is not None
    assert chain.hit_level == "L2记忆"
    assert chain.hit_note is None
    assert "未命中" not in _l2_statuses(chain)
    assert not any("通用" in (s or "") for s in _l2_statuses(chain))
