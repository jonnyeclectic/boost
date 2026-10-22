# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""store.duplicate_rule_blocks / collapse_rule_block: which rows are read,
and that collapsing keeps the first copy's text."""
from __future__ import annotations

import pytest

from boost_cli.core import integrity, lockfile, paths, rules, store


def _file(name="CLAUDE.md", copies=2, body="Keep me."):
    p = paths.home() / ".claude" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    block = rules.merge_block("", "r", body).rstrip("\n")
    p.write_text("top\n" + "\nmid\n".join([block] * copies) + "\n",
                 encoding="utf-8")
    return p


def _row(path, **extra):
    m = {"agent": "claude-code", "mode": "claude", "path": str(path)}
    m.update(extra)
    return m


def _rule(*rows, **extra):
    entry = {"version": "1", "tap": "t", "materializations": list(rows)}
    entry.update(extra)
    lockfile.set_rule("r", entry)


class TestDuplicateRuleBlocks:
    def test_a_doubled_block_is_named_with_its_count(self, sandbox):
        p = _file(copies=3)
        _rule(_row(p))
        assert store.duplicate_rule_blocks() == [("r", str(p), 3)]

    def test_one_block_is_not(self, sandbox):
        _rule(_row(_file(copies=1)))
        assert store.duplicate_rule_blocks() == []

    @pytest.mark.parametrize("extra", [
        {"mode": "file"}, {"unwritable": True}, {"agent": "no-such-agent"}])
    def test_rows_that_hold_no_written_block_are_skipped(self, sandbox, extra):
        _rule(_row(_file(), **extra))
        assert store.duplicate_rule_blocks() == []

    def test_a_quarantined_rule_is_skipped(self, sandbox):
        _rule(_row(_file()), quarantined=True)
        assert store.duplicate_rule_blocks() == []

    def test_each_file_once_and_a_missing_one_is_no_fault(self, sandbox):
        p = _file()
        _rule(_row(p), _row(p, agent="gemini"),
              _row(paths.home() / ".codex" / "AGENTS.md", agent="codex"))
        assert store.duplicate_rule_blocks() == [("r", str(p), 2)]

    def test_the_line_names_count_file_and_remedy(self, sandbox):
        assert store.duplicate_block_line(
            "r", str(paths.home() / ".claude" / "CLAUDE.md"), 2) == (
            "rule r's block appears 2 times in ~/.claude/CLAUDE.md — the "
            "agent reads every copy; `boost heal` keeps the first")


class TestCollapse:
    def test_keeps_the_first_copy_and_the_users_text(self, sandbox):
        p = _file()
        _rule(_row(p))
        assert store.collapse_rule_block("r", str(p)) is True
        block = rules.merge_block("", "r", "Keep me.").rstrip("\n")
        assert p.read_text(encoding="utf-8") == "top\n%s\nmid\n" % block
        assert store.collapse_rule_block("r", str(p)) is False

    def test_integrity_reads_a_doubled_block_as_modified(self, sandbox):
        import hashlib
        p = _file()
        sha = hashlib.sha256(b"Keep me.").hexdigest()
        _rule(_row(p, sha256=sha))
        entry = lockfile.get_rule("r")
        assert integrity.materialized_status("r", entry, "rule") == (
            integrity.STATUS_MODIFIED)
        store.collapse_rule_block("r", str(p))
        assert integrity.materialized_status("r", entry, "rule") == (
            integrity.STATUS_OK)
