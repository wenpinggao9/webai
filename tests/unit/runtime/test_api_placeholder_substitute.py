"""API 模板占位符与步骤 ${var} 引用的通用对齐."""
from __future__ import annotations

import pytest

from core.foundation.profile import ApiTemplate, SystemProfile
from core.foundation.variable_substitution import (
    collect_placeholder_bindings,
    extract_explicit_api_params,
    resolve_placeholder_alias,
)
from core.runtime.integration.api_client import (
    APIClient,
    has_unresolved_placeholder,
    substitute_with_refs,
)


def test_collect_placeholder_bindings_from_text():
    ctx = {"orderId7": "146943042", "other": "x"}
    refs = collect_placeholder_bindings(
        "调用超时接口，入参为${orderId7}",
        context=ctx,
    )
    assert refs == {"orderId7": "146943042"}


def test_resolve_placeholder_alias_base_plus_suffix():
    refs = {"orderId7": "146943042"}
    assert resolve_placeholder_alias("orderId", refs) == "146943042"
    assert resolve_placeholder_alias("orderId7", refs) == "146943042"


def test_resolve_placeholder_alias_ambiguous_returns_none():
    refs = {"orderId7": "1", "orderId8": "2"}
    assert resolve_placeholder_alias("orderId", refs) is None


def test_substitute_with_refs_maps_template_to_step_var():
    out = substitute_with_refs(
        {"orderId": "${orderId}", "op": 7},
        context={},
        var_refs={"orderId7": "146943042"},
    )
    assert out == {"orderId": "146943042", "op": 7}


def test_build_params_resolves_via_var_refs():
    profile = SystemProfile(
        name="test",
        base_url="https://example.com",
        apis={
            "timeout": ApiTemplate(
                method="GET",
                url="https://example.com/mis/process",
                params={"orderId": "${orderId}", "op": 7},
                keywords=["超时"],
            ),
        },
    )
    client = APIClient(profile)
    preview = client.preview_request(
        "timeout",
        context={"orderId7": "146943042"},
        var_refs={"orderId7": "146943042"},
    )
    assert preview["params"] == {"orderId": "146943042", "op": 7}
    assert not has_unresolved_placeholder(preview["params"])


def test_extract_explicit_api_params_from_case_line():
    got = extract_explicit_api_params("调用超时接口，传参 orderId=146943468")
    assert got == {"orderId": 146943468}


def test_explicit_params_override_template_without_context():
    from core.runtime.integration.api_runner import ApiRunner

    profile = SystemProfile(
        name="test",
        base_url="https://example.com",
        apis={
            "timeout": ApiTemplate(
                method="GET",
                url="https://example.com/mis/process",
                params={"orderId": "${orderId}", "op": 7},
                keywords=["超时"],
            ),
        },
    )
    runner = ApiRunner(APIClient(profile), profile)
    runner.context = {}
    line = "调用超时接口，传参 orderId=146943468"
    api_name, tpl = runner._match_api(line)
    flat = runner._extract_params(line, tpl)
    wrapped = runner._wrap_call_extra(tpl, flat)
    preview = runner.client.preview_request(api_name, wrapped, {}, var_refs={})
    assert preview["params"] == {"orderId": 146943468, "op": 7}


def test_run_preconditions_marks_executed_when_returns_empty(monkeypatch):
    from core.runtime.integration.api_runner import ApiRunner

    profile = SystemProfile(
        name="test",
        base_url="https://example.com",
        apis={
            "timeout": ApiTemplate(
                method="GET",
                url="https://example.com/mis/process",
                params={"orderId": "${orderId}", "op": 7},
                returns=[],
                keywords=["超时"],
            ),
        },
    )
    runner = ApiRunner(APIClient(profile), profile)
    runner.context = {}

    def fake_call(api_name, call_extra, context, *, var_refs=None):
        return {
            "errNo": 0,
            "errMsg": "succ",
            "data": {"desc": "stage:分发,splitStatus:waitSplit"},
        }

    monkeypatch.setattr(runner.client, "call", fake_call)
    ctx = runner.run_preconditions(["调用超时接口，传参 orderId=146943468"])
    assert ctx == {}
    assert runner._last_api_execution == {
        "api_name": "timeout",
        "executed": True,
        "response": "errNo=0, errMsg=succ, data.desc=stage:分发,splitStatus:waitSplit",
    }
