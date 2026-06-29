"""LLMAdapter: 按环节 (stage) 路由不同 provider."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.foundation.llm.adapter import LLMAdapter, resolve_stage_provider

_CFG = {
    "provider": "deepseek-v4-pro",
    "max_tokens": 100,
    "temperature": 0,
    "stages": {
        "action_plan": "opus",
    },
    "opus": {
        "base_url": "https://example.com/opus/v1",
        "api_key": "k-opus",
        "model": "claude-opus",
    },
    "deepseek-v4-pro": {
        "base_url": "https://example.com/ds/v1",
        "api_key": "k-ds",
        "model": "deepseek-v4-pro",
    },
}


def test_resolve_stage_provider():
    assert resolve_stage_provider(_CFG, "action_plan") == "opus"
    assert resolve_stage_provider(_CFG, "element_decide") == "deepseek-v4-pro"
    assert resolve_stage_provider(_CFG, "") == "deepseek-v4-pro"


def test_resolve_stage_provider_from_prompts_node():
    cfg = {
        "provider": "deepseek-v4-pro",
        "prompts": {"semantic_assert": {"provider": "opus"}},
        "opus": {"base_url": "https://x/v1", "api_key": "k", "model": "opus"},
        "deepseek-v4-pro": {"base_url": "https://y/v1", "api_key": "k", "model": "ds"},
    }
    assert resolve_stage_provider(cfg, "semantic_assert") == "opus"
    cfg["stages"] = {"semantic_assert": "deepseek-v4-pro"}
    assert resolve_stage_provider(cfg, "semantic_assert") == "deepseek-v4-pro"


def test_complete_json_uses_stage_provider_model():
    adapter = LLMAdapter(_CFG, max_retries=0)
    mock_create = MagicMock()
    mock_create.return_value.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]

    with patch.object(adapter, "_runtime_for_stage") as mock_rt:
        opus_rt = MagicMock()
        opus_rt.model = "claude-opus"
        opus_rt.use_response_format = True
        opus_rt.client = MagicMock()
        opus_rt.client.chat.completions.create = mock_create
        mock_rt.return_value = opus_rt

        adapter.complete_json("action_plan", "sys", '请输出 {"ok": true} 的 JSON')
        mock_rt.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["model"] == "claude-opus"

    with patch.object(adapter, "_runtime_for_stage") as mock_rt:
        ds_rt = MagicMock()
        ds_rt.model = "deepseek-v4-pro"
        ds_rt.use_response_format = True
        ds_rt.client = MagicMock()
        ds_rt.client.chat.completions.create = mock_create
        mock_rt.return_value = ds_rt

        adapter.complete_json("element_decide", "sys", '请输出 {"ok": true} 的 JSON')
        _, kwargs = mock_create.call_args
        assert kwargs["model"] == "deepseek-v4-pro"
