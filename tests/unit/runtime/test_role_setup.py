from unittest.mock import MagicMock

from core.runtime.session.role_setup import _resolve_url, apply_role_setup


def test_resolve_url_with_video_base():
    base = "https://www-gwp11-bc.suanshubang.com/video"
    assert _resolve_url("/video/wait-upload", base) == (
        "https://www-gwp11-bc.suanshubang.com/video/wait-upload"
    )


def test_apply_role_setup_injects_cookies_and_runs_steps():
    page = MagicMock()
    page.context = MagicMock()
    page.url = "https://www-gwp11-bc.suanshubang.com/video"

    knowledge = {
        "role_setup": {
            "recording": {
                "cookies": [{"name": "QCefClient", "value": "1"}],
                "steps": [
                    {"goto": "/video/wait-upload"},
                    {"click": "返回首页"},
                    {"reload": True},
                ],
            }
        },
    }

    apply_role_setup(
        page,
        "recording",
        knowledge,
        "https://www-gwp11-bc.suanshubang.com/video",
    )

    page.context.add_cookies.assert_called_once()
    cookies = page.context.add_cookies.call_args[0][0]
    assert cookies[0]["name"] == "QCefClient"
    assert cookies[0]["value"] == "1"
    assert cookies[0]["domain"] == "www-gwp11-bc.suanshubang.com"

    page.goto.assert_called_once()
    page.reload.assert_called_once()


def test_apply_role_setup_skips_unknown_role():
    page = MagicMock()
    page.context = MagicMock()

    apply_role_setup(page, "admin", {"role_setup": {}}, "https://example.com")

    page.context.add_cookies.assert_not_called()
