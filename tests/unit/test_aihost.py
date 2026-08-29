# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The AI bridge must reach whichever assistant CLI the user actually has.

`core/ai.py` knew one backend: the `claude` CLI, or ANTHROPIC_API_KEY. Every
AI-assisted command -- `explain`, `search --smart`, `distill`, `infer`,
`absorb`, `evolve`, `simulate` -- therefore degraded to its heuristic fallback
for someone running Gemini CLI, even though Gemini exposes the same headless
contract (`-p`, `-m`, `-o text`). Skills, MCP, rules, workflows and hooks all
fan out across hosts; this was the last surface that did not, and it is the one
a user notices, because the fallback is visibly worse prose.

The table lives apart from the calling code for the same reason `hookhost` does:
a per-backend fact is data, and a test can assert on data without running a
subprocess or spending a token.
"""
from __future__ import annotations

import pytest

from boost_cli.core import aihost


class TestTable:
    def test_claude_is_first(self):
        """Preference order is behaviour: Claude must keep winning.

        Someone with both CLIs installed had Claude answering before this
        existed. Reordering would silently change every AI result they get.
        """
        assert aihost.backends()[0] == aihost.CLAUDE

    def test_every_backend_is_complete(self):
        for name in aihost.backends():
            spec = aihost.spec(name)
            assert spec["cli"], name
            assert spec["prompt_flag"], name
            assert spec["label"], name

    def test_unknown_backend_names_the_alternatives(self):
        with pytest.raises(Exception) as e:
            aihost.spec("copilot")
        # BoostError keeps the actionable half in `hint`, not in str(); a test
        # that only reads str() would pass on an error with no way forward.
        hint = getattr(e.value, "hint", "") or ""
        assert "claude" in hint and "gemini" in hint, hint


class TestArgv:
    def test_claude_argv_is_byte_for_byte_what_it_always_was(self):
        """The existing command line is a contract; a refactor must not move it."""
        argv = aihost.argv(aihost.CLAUDE, model="sonnet", system="SYS")
        assert argv[:2] == ["claude", "-p"]
        assert "--model" in argv and "sonnet" in argv
        assert "--output-format" in argv and "text" in argv
        assert "--append-system-prompt" in argv and "SYS" in argv

    def test_gemini_argv_uses_its_own_flags(self):
        argv = aihost.argv(aihost.GEMINI, model=None, system=None)
        assert argv[0] == "gemini"
        assert "-p" in argv
        assert "-o" in argv and "text" in argv

    def test_a_backend_without_a_system_flag_never_invents_one(self):
        """Gemini has no --append-system-prompt; the caller must fold it in.

        Passing an unknown flag would make every call fail with a usage error
        rather than degrade, which is the one outcome worse than no AI at all.
        """
        argv = aihost.argv(aihost.GEMINI, model=None, system="SYS")
        assert "--append-system-prompt" not in argv
        assert "SYS" not in argv

    def test_a_claude_model_id_is_never_handed_to_gemini(self):
        """`ai.model` defaults to a Claude id; passing it to gemini is an error."""
        argv = aihost.argv(aihost.GEMINI, model="claude-sonnet-4-5", system=None)
        assert "claude-sonnet-4-5" not in argv


class TestFolding:
    def test_system_is_folded_into_the_prompt_when_unsupported(self):
        folded = aihost.fold_system(aihost.GEMINI, "SYS", "ASK")
        assert "SYS" in folded and "ASK" in folded
        assert folded.index("SYS") < folded.index("ASK")

    def test_system_is_left_alone_when_the_backend_takes_a_flag(self):
        assert aihost.fold_system(aihost.CLAUDE, "SYS", "ASK") == "ASK"


class TestModelRule:
    """"Not another vendor's", not "one of mine" — an override must survive."""

    def test_an_unknown_id_reaches_the_backend(self):
        """A custom alias or pinned snapshot is the user's business, not ours.

        The first version of this rule asked "does this backend own the id",
        which silently dropped `--model m-x` on Claude. An existing test caught
        it; this pins the corrected rule.
        """
        assert aihost.accepts_model(aihost.CLAUDE, "m-x") is True
        assert "m-x" in aihost.argv(aihost.CLAUDE, model="m-x", system=None)

    def test_another_vendors_id_is_withheld(self):
        assert aihost.accepts_model(aihost.GEMINI, "claude-sonnet-4-5") is False
        assert aihost.accepts_model(aihost.CLAUDE, "gemini-2.5-pro") is False

    def test_its_own_id_is_accepted(self):
        assert aihost.accepts_model(aihost.GEMINI, "gemini-2.5-pro") is True
        assert aihost.accepts_model(aihost.CLAUDE, "claude-opus-4") is True
