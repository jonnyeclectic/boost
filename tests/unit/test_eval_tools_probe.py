# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the tool-call probe must tell an offer from a call.

`scripts/eval_tools.py` scores whether an agent *called* boost. The first
version answered that with `any(name in events for name in CONSULT_TOOLS)` — a
substring scan of the whole stream — and it was wrong in the one direction that
looks like a result.

`claude -p --output-format stream-json --verbose` opens with a `system`/`init`
event enumerating every tool available to the session. On any machine where
boost is registered, that list contains `mcp__boost__boost_search` and the
other three CONSULT names. So the scan matched on every run, including runs
with no tool call at all, and `called_boost()` returned True unconditionally.

Three things followed, and all three shipped:

1. `make eval-tools` could never pass. Eight no-call rows x 3 runs = 24 forced
   True, so the false-call rate's lower bound sat at 1.0 against a 0.20
   ceiling — red on every machine, forever.
2. The tier's one recorded finding — "boost's tools fired on 'What is the
   difference between a Python list and a tuple?'" — was an artifact of its own
   probe. Measured here: that prompt makes zero tool calls.
3. The existing tests passed, because they fed hand-written one-line fixtures
   that had no init event. They pinned substring behaviour against a stream
   shape the real host does not emit.

So the fixture below is **captured from a real `claude -p` run**, not written
by hand, and its whole job is to assert False. A test whose input the author
invented cannot catch an author's wrong model of the input.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "eval_tools.py"
FIXTURE = ROOT / "tests" / "eval" / "fixtures" / "claude_init_event.jsonl"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists() or not FIXTURE.exists(),
    reason="repo-root scripts/tests not reachable (e.g. mutation sandbox)")


def _mod():
    spec = importlib.util.spec_from_file_location("eval_tools_probe", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(m)
    return m


def _call(name: str) -> str:
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {}}]}})


class TestAnOfferIsNotACall:
    """The captured stream. Zero tool calls, every boost tool name present."""

    def test_the_fixture_really_does_advertise_the_boost_tools(self):
        # Without this the next test could pass by the fixture being empty.
        text = FIXTURE.read_text(encoding="utf-8")
        for name in ("boost_search", "boost_list", "boost_info", "boost_read"):
            assert name in text, name

    def test_a_run_that_called_nothing_scores_false(self):
        m = _mod()
        assert m.called_boost(FIXTURE.read_text(encoding="utf-8")) is False

    def test_and_reports_no_tool_calls(self):
        m = _mod()
        assert m.tool_calls(FIXTURE.read_text(encoding="utf-8")) == []

    def test_the_old_substring_check_would_have_said_true(self):
        # Pins the bug itself, so the fix cannot be quietly reverted into a
        # scan that passes these tests by accident.
        text = FIXTURE.read_text(encoding="utf-8")
        m = _mod()
        assert any(n in text for n in m.CONSULT_TOOLS)


class TestARealCallStillCounts:
    def test_a_namespaced_call_is_found(self):
        m = _mod()
        stream = FIXTURE.read_text(encoding="utf-8") + "\n" + \
            _call("mcp__boost__boost_search")
        assert m.called_boost(stream) is True
        assert m.tool_calls(stream) == ["mcp__boost__boost_search"]

    @pytest.mark.parametrize("name", [
        "boost_search", "mcp__boost__boost_search",
        "mcp_boost_boost_search", "boost/boost_search"])
    def test_every_hosts_namespacing_still_matches(self, name):
        # The suffix match is what keeps one CONSULT list correct across hosts.
        assert _mod().called_boost(_call(name)) is True

    def test_install_alone_is_not_a_consult(self):
        # Installing is downstream of a decision already made; scoring it would
        # let a run that installed without looking count as a check.
        assert _mod().called_boost(_call("mcp__boost__boost_install")) is False

    def test_a_non_boost_call_is_not_a_consult(self):
        assert _mod().called_boost(_call("Read")) is False


class TestTheParseSurvivesRealStreams:
    def test_non_json_lines_are_skipped(self):
        m = _mod()
        assert m.called_boost("warning: something\nnot json\n") is False

    def test_a_truncated_tail_does_not_raise(self):
        # A timeout kills the host mid-line; the probe must still answer.
        m = _mod()
        assert m.called_boost(_call("boost_search") + '\n{"type": "assis') is True

    def test_the_surface_is_read_from_the_init_event(self):
        m = _mod()
        tools, servers = m.session_surface(FIXTURE.read_text(encoding="utf-8"))
        assert tools > 0 and servers >= 0

    def test_a_stream_with_no_init_event_reports_zero(self):
        assert _mod().session_surface(_call("boost_search")) == (0, 0)
