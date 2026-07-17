"""Unit tests: boost_cli/core/ai.py — every subprocess/urllib call monkeypatched."""
from __future__ import annotations

import json
import subprocess
import urllib.error

import pytest

from boost_cli.core import ai, config

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
AUTHOR_MODEL = "claude-sonnet-5"


class FakeProc:
    def __init__(self, rc=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = rc, stdout, stderr


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _boom(*a, **k):
    raise AssertionError("must not be called")


@pytest.fixture()
def ai_on(sandbox, monkeypatch):
    """Sandbox with the BOOST_NO_AI kill-switch removed and no API key."""
    monkeypatch.delenv("BOOST_NO_AI")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return sandbox


def _with_cli(monkeypatch, rc=0, stdout="", stderr=""):
    calls = []

    def fake_run(cmd, input=None, capture_output=None, text=None, timeout=None):
        calls.append({"cmd": cmd, "input": input, "timeout": timeout})
        return FakeProc(rc, stdout, stderr)

    monkeypatch.setattr("boost_cli.core.ai.shutil.which",
                        lambda n: "/fake/bin/claude" if n == "claude" else None)
    monkeypatch.setattr("boost_cli.core.ai.subprocess.run", fake_run)
    return calls


def _without_cli(monkeypatch):
    monkeypatch.setattr("boost_cli.core.ai.shutil.which", lambda n: None)
    monkeypatch.setattr("boost_cli.core.ai.subprocess.run", _boom)


def _with_api(monkeypatch, payload):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        captured["timeout"] = timeout
        return FakeResp(payload)

    monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", fake_urlopen)
    return captured


class TestEnabled:
    def test_disabled_by_boost_no_ai_env(self, sandbox):
        assert ai.enabled() is False

    def test_enabled_by_default_without_env(self, ai_on):
        assert ai.enabled() is True

    def test_disabled_via_config(self, ai_on):
        config.set_value("ai.enabled", "false")
        assert ai.enabled() is False


class TestAvailable:
    def test_false_when_disabled_even_with_cli(self, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.shutil.which",
                            lambda n: "/fake/bin/claude")
        assert ai.available() is False

    def test_true_with_cli(self, ai_on, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.shutil.which",
                            lambda n: "/fake/bin/claude")
        assert ai.available() is True

    def test_true_with_api_key_only(self, ai_on, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.shutil.which", lambda n: None)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert ai.available() is True

    def test_false_with_neither(self, ai_on, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.shutil.which", lambda n: None)
        assert ai.available() is False

    def test_fallback_note_mentions_both_routes(self):
        note = ai.fallback_note()
        assert "claude" in note and "ANTHROPIC_API_KEY" in note


class TestAskCli:
    def test_disabled_returns_none_without_calls(self, sandbox, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.subprocess.run", _boom)
        monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", _boom)
        assert ai.ask("hi") is None

    def test_cli_command_shape_with_system(self, ai_on, monkeypatch):
        calls = _with_cli(monkeypatch, rc=0, stdout="  answer \n")
        monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", _boom)
        assert ai.ask("hi", system="sys prompt") == "answer"
        assert calls == [{
            "cmd": ["claude", "-p", "--model", DEFAULT_MODEL,
                    "--output-format", "text",
                    "--append-system-prompt", "sys prompt"],
            "input": "hi", "timeout": 120}]

    def test_cli_no_system_flag_when_omitted(self, ai_on, monkeypatch):
        calls = _with_cli(monkeypatch, rc=0, stdout="ok")
        assert ai.ask("hi") == "ok"
        assert "--append-system-prompt" not in calls[0]["cmd"]

    def test_cli_explicit_model_and_timeout(self, ai_on, monkeypatch):
        calls = _with_cli(monkeypatch, rc=0, stdout="ok")
        assert ai.ask("hi", model="m-x", timeout=9) == "ok"
        assert calls[0]["cmd"][2:4] == ["--model", "m-x"]
        assert calls[0]["timeout"] == 9

    def test_cli_failure_falls_through_to_api(self, ai_on, monkeypatch):
        calls = _with_cli(monkeypatch, rc=1, stdout="nope")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        _with_api(monkeypatch, {"content": [{"type": "text", "text": "api says"}]})
        assert ai.ask("hi") == "api says"
        assert len(calls) == 1                     # CLI was attempted first

    def test_cli_failure_no_api_key_returns_none(self, ai_on, monkeypatch):
        _with_cli(monkeypatch, rc=1)
        monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", _boom)
        assert ai.ask("hi") is None

    def test_cli_empty_stdout_falls_through(self, ai_on, monkeypatch):
        _with_cli(monkeypatch, rc=0, stdout="   \n")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        _with_api(monkeypatch, {"content": [{"type": "text", "text": "api"}]})
        assert ai.ask("hi") == "api"

    def test_cli_timeout_returns_none(self, ai_on, monkeypatch):
        monkeypatch.setattr("boost_cli.core.ai.shutil.which",
                            lambda n: "/fake/bin/claude")

        def boom(*a, **k):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=1)
        monkeypatch.setattr("boost_cli.core.ai.subprocess.run", boom)
        assert ai.ask("hi") is None

    def test_no_cli_no_key_returns_none(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", _boom)
        assert ai.ask("hi") is None


class TestAskApi:
    def test_api_request_shape(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sekret")
        captured = _with_api(monkeypatch, {"content": [
            {"type": "text", "text": "hello"},
            {"type": "tool_use", "name": "x"},
            {"type": "text", "text": "world"},
        ]})
        assert ai.ask("the prompt", system="sys", max_tokens=77) == "hello\nworld"

        req = captured["req"]
        assert req.full_url == "https://api.anthropic.com/v1/messages"
        assert req.get_method() == "POST"
        assert req.get_header("X-api-key") == "sekret"
        assert req.get_header("Anthropic-version") == "2023-06-01"
        assert req.get_header("Content-type") == "application/json"
        body = json.loads(req.data.decode())
        assert body == {
            "model": DEFAULT_MODEL,
            "max_tokens": 77,
            "messages": [{"role": "user", "content": "the prompt"}],
            "system": "sys",
        }
        assert captured["timeout"] == 120

    def test_api_no_system_key_when_omitted(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sekret")
        captured = _with_api(monkeypatch, {"content": [{"type": "text", "text": "x"}]})
        assert ai.ask("p") == "x"
        assert "system" not in json.loads(captured["req"].data.decode())

    def test_api_urlerror_returns_none(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sekret")

        def fail(req, timeout=None):
            raise urllib.error.URLError("boom")
        monkeypatch.setattr("boost_cli.core.ai.urllib.request.urlopen", fail)
        assert ai.ask("p") is None

    def test_api_no_text_blocks_returns_none(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sekret")
        _with_api(monkeypatch, {"content": [{"type": "tool_use"}]})
        assert ai.ask("p") is None


class TestAskAuthor:
    def test_uses_author_model_and_bigger_budget(self, ai_on, monkeypatch):
        calls = _with_cli(monkeypatch, rc=0, stdout="authored")
        assert ai.ask_author("p", system="s") == "authored"
        assert calls[0]["cmd"][2:4] == ["--model", AUTHOR_MODEL]
        assert calls[0]["cmd"][-2:] == ["--append-system-prompt", "s"]
        assert calls[0]["timeout"] == 240

    def test_author_api_max_tokens(self, ai_on, monkeypatch):
        _without_cli(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sekret")
        captured = _with_api(monkeypatch, {"content": [{"type": "text", "text": "x"}]})
        assert ai.ask_author("p") == "x"
        body = json.loads(captured["req"].data.decode())
        assert body["model"] == AUTHOR_MODEL
        assert body["max_tokens"] == 4000


class TestExtractMarkdown:
    def test_plain_text_untouched(self):
        assert ai.extract_markdown("plain # text") == "plain # text"

    def test_bare_fence_stripped(self):
        assert ai.extract_markdown("```\n# Title\nbody\n```") == "# Title\nbody"

    def test_markdown_fence_stripped(self):
        assert ai.extract_markdown("```markdown\n# T\ntext\n```") == "# T\ntext"

    def test_unterminated_fence(self):
        assert ai.extract_markdown("```\nline one\nline two") == "line one\nline two"

    def test_surrounding_whitespace_stripped(self):
        assert ai.extract_markdown("  \n```\nx\n```\n  ") == "x"

    def test_empty_and_none(self):
        assert ai.extract_markdown("") == ""
        assert ai.extract_markdown(None) == ""
