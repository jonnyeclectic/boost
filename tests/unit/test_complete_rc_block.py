# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: the managed block `boost completions --install` writes to an rc file.

An rc file is the user's own hand-written config, so it is the worst file boost
owns an edit to. Three states the old marker handling got wrong, all of them
reachable from an ordinary hand-edit:

**A start marker with no end (data loss).** ``_merge_rc`` fell through to its
append branch, leaving two start markers. The *next* install then matched the
first start against the second block's end and deleted everything between —
the user's own lines — while reporting ``✓ wired boost completions``. The
inverse function ``_strip_rc`` already refused this exact input ("no end
marker: malformed, leave the file untouched"); only the writer did not.

**Two blocks (a silent lie).** ``--uninstall`` removed the first and left the
second, so boost said "removed" while the shell still ran completions. Same
shape as the `sync` defect fixed in #515: a command reporting success for work
it declined to do.

**An end marker with no start** is harmless — the append path handles it and
converges — and is pinned here so a future "tighten the parser" change does not
start rejecting a file that works.

`--dry-run` exists so all of this is answerable before anything is written.
"""
from __future__ import annotations

import os

import pytest

from boost_cli.core import complete
from boost_cli.errors import BoostError

START = complete._RC_START
END = complete._RC_END


def _write(sandbox, text, shell="zsh"):
    rc = sandbox / complete.RC_FILE[shell]
    rc.write_text(text, encoding="utf-8")
    return rc


class TestDanglingStartMarkerIsRefused:
    """The data-loss case: never append a second block beside an orphan start."""

    def test_install_refuses_rather_than_appending(self, sandbox):
        rc = _write(sandbox, "export BEFORE=1\n" + START + "\nexport KEEP=me\n")

        with pytest.raises(BoostError):
            complete.install("zsh")

        assert rc.read_text(encoding="utf-8").count(START) == 1, (
            "a second start marker is what the next run deletes user lines between")

    def test_the_users_content_is_still_there_afterwards(self, sandbox):
        rc = _write(sandbox, "export BEFORE=1\n" + START + "\nexport KEEP=me\n"
                             "alias deploy='./scripts/deploy.sh'\n")

        with pytest.raises(BoostError):
            complete.install("zsh")

        text = rc.read_text(encoding="utf-8")
        assert "KEEP=me" in text and "deploy" in text

    def test_the_error_names_the_file_and_what_to_do(self, sandbox):
        _write(sandbox, START + "\nexport KEEP=me\n")

        with pytest.raises(BoostError) as excinfo:
            complete.install("zsh")

        said = excinfo.value.message + " " + (excinfo.value.hint or "")
        assert ".zshrc" in said, "the user has to know which file to open"
        assert END in said, "name the marker that is missing, not just 'malformed'"

    def test_repeated_installs_never_start_deleting(self, sandbox):
        """The old bug needed two runs to bite; prove the second is safe too."""
        rc = _write(sandbox, START + "\nexport KEEP=me\n")

        for _ in range(3):
            with pytest.raises(BoostError):
                complete.install("zsh")

        assert "KEEP=me" in rc.read_text(encoding="utf-8")

    def test_uninstall_refuses_too(self, sandbox):
        """`_strip_rc` was careful only when the orphan start was the *only*
        marker. With a well-formed block after it, uninstall matched the orphan
        start against that block's end and deleted the user's lines between —
        the same data loss as install, from the mirror-image precondition."""
        rc = _write(sandbox,
                    "export A=1\n" + START + "\nexport KEEP=me\n"
                    "alias deploy='./scripts/deploy.sh'\n\n"
                    + complete._rc_block("zsh") + "\n")
        before = rc.read_text(encoding="utf-8")

        with pytest.raises(BoostError):
            complete.uninstall("zsh")

        assert rc.read_text(encoding="utf-8") == before
        assert "KEEP=me" in rc.read_text(encoding="utf-8")

    def test_uninstall_refuses_when_the_orphan_is_the_only_marker(self, sandbox):
        rc = _write(sandbox, "export A=1\n" + START + "\nexport KEEP=me\n")
        before = rc.read_text(encoding="utf-8")

        with pytest.raises(BoostError):
            complete.uninstall("zsh")

        assert rc.read_text(encoding="utf-8") == before


class TestDuplicateBlocksCollapse:
    def test_install_leaves_exactly_one_block(self, sandbox):
        block = complete._rc_block("zsh")
        rc = _write(sandbox, "export A=1\n\n" + block + "\n\n" + block + "\n")

        complete.install("zsh")

        assert rc.read_text(encoding="utf-8").count(START) == 1

    def test_uninstall_removes_every_block_not_just_the_first(self, sandbox):
        block = complete._rc_block("zsh")
        rc = _write(sandbox, "export A=1\n\n" + block + "\n\n" + block + "\n")

        complete.uninstall("zsh")

        text = rc.read_text(encoding="utf-8")
        assert START not in text, (
            "boost reported 'removed' while the shell still ran completions")
        assert "export A=1" in text

    def test_user_content_between_two_blocks_survives(self, sandbox):
        block = complete._rc_block("zsh")
        rc = _write(sandbox,
                    block + "\nexport MIDDLE=1\n" + block + "\nexport TAIL=1\n")

        complete.install("zsh")

        text = rc.read_text(encoding="utf-8")
        assert "MIDDLE=1" in text and "TAIL=1" in text


class TestOrphanEndMarkerStaysHarmless:
    def test_install_succeeds_and_is_idempotent(self, sandbox):
        rc = _write(sandbox, "export A=1\n" + END + "\nexport B=2\n")

        complete.install("zsh")
        once = rc.read_text(encoding="utf-8")
        complete.install("zsh")

        assert rc.read_text(encoding="utf-8") == once
        assert once.count(START) == 1
        assert "export A=1" in once and "export B=2" in once


class TestOrdinaryPathsUnchanged:
    """The behaviour that already worked, pinned against the rewrite."""

    def test_create_then_install_again_is_a_fixed_point(self, sandbox):
        complete.install("zsh")
        once = (sandbox / ".zshrc").read_text(encoding="utf-8")
        complete.install("zsh")
        assert (sandbox / ".zshrc").read_text(encoding="utf-8") == once

    def test_install_then_uninstall_round_trips(self, sandbox):
        rc = _write(sandbox, "line one\nline two\n")
        complete.install("zsh")
        complete.uninstall("zsh")
        assert rc.read_text(encoding="utf-8") == "line one\nline two\n"

    def test_content_after_the_block_is_preserved(self, sandbox):
        block = complete._rc_block("zsh")
        rc = _write(sandbox, block + "\nexport AFTER=1\n")
        complete.install("zsh")
        assert "AFTER=1" in rc.read_text(encoding="utf-8")


class TestPlanDescribesTheChangeWithoutWriting:
    """What `--dry-run` reports. A validation that writes is not a validation."""

    def test_plan_on_a_clean_file_says_it_would_add(self, sandbox):
        _write(sandbox, "export A=1\n")

        plan = complete.plan_install("zsh")

        assert plan.action == "add"
        assert plan.changes is True

    def test_plan_writes_nothing(self, sandbox):
        rc = _write(sandbox, "export A=1\n")

        complete.plan_install("zsh")

        assert rc.read_text(encoding="utf-8") == "export A=1\n"

    def test_plan_on_a_missing_file_does_not_create_it(self, sandbox):
        assert not (sandbox / ".zshrc").exists()

        plan = complete.plan_install("zsh")

        assert plan.action == "create"
        assert not (sandbox / ".zshrc").exists()

    def test_plan_reports_no_change_when_already_wired(self, sandbox):
        complete.install("zsh")

        plan = complete.plan_install("zsh")

        assert plan.action == "none"
        assert plan.changes is False

    def test_plan_reports_the_collapse_of_duplicates(self, sandbox):
        block = complete._rc_block("zsh")
        _write(sandbox, block + "\n\n" + block + "\n")

        plan = complete.plan_install("zsh")

        assert plan.action == "replace"
        assert plan.changes is True

    def test_uninstall_plan_reports_no_change_when_absent(self, sandbox):
        _write(sandbox, "export A=1\n")

        plan = complete.plan_uninstall("zsh")

        assert plan.action == "none"
        assert plan.changes is False

    def test_a_dry_run_surfaces_the_malformed_file_too(self, sandbox):
        """The whole point: find out before writing, not after."""
        _write(sandbox, START + "\nexport KEEP=me\n")

        with pytest.raises(BoostError):
            complete.plan_install("zsh")

    def test_a_no_op_apply_does_not_rewrite_the_file(self, sandbox):
        """Identical bytes written back still moves the mtime, which shows up
        as a change in every backup and file-watcher the user runs."""
        rc = sandbox / ".zshrc"
        complete.install("zsh")
        os.utime(rc, (1_000_000, 1_000_000))

        complete.install("zsh")

        assert rc.stat().st_mtime == 1_000_000

    def test_plan_and_apply_agree(self, sandbox):
        """A dry run that predicts something else is worse than none."""
        _write(sandbox, "export A=1\n")
        predicted = complete.plan_install("zsh").after

        complete.install("zsh")

        assert (sandbox / ".zshrc").read_text(encoding="utf-8") == predicted


class TestEveryMarkerArrangement:
    """Exhaustive property check over every arrangement of up to 4 fragments.

    Example-based tests pin the states someone thought of. This enumerates all
    672 orderings of {user line, stray start, stray end, real block} and asserts
    the three invariants that matter, whatever the input:

      * a user line boost does not own is never lost,
      * a successful uninstall never leaves a block behind,
      * a refusal never modifies the file.

    Against the pre-fix implementation this reports 220 violations (198 of the
    second, 22 of the first); it is here so a future rewrite has to stay honest.
    """

    @staticmethod
    def _owned(lines):
        """Line indexes boost owns: a start that closes before the next opens.
        An orphan start owns nothing — resolving that ambiguity is the bug."""
        spans, i = [], 0
        while i < len(lines):
            if lines[i] == START:
                j = i + 1
                while j < len(lines) and lines[j] not in (START, END):
                    j += 1
                if j < len(lines) and lines[j] == END:
                    spans.append((i, j))
                    i = j + 1
                    continue
            i += 1
        owned = set()
        for a, b in spans:
            owned.update(range(a, b + 1))
        return owned

    @classmethod
    def _user_lines(cls, text):
        lines = text.splitlines()
        owned = cls._owned(lines)
        return sum(1 for k, ln in enumerate(lines)
                   if k not in owned and ln.strip() == "export USER_LINE=1")

    def test_no_arrangement_loses_a_line_or_lies(self, sandbox):
        import itertools

        rc = sandbox / ".zshrc"
        frags = ["export USER_LINE=1\n", START + "\n", END + "\n",
                 complete._rc_block("zsh") + "\n"]
        failures = []
        for n in (2, 3, 4):
            for combo in itertools.product(frags, repeat=n):
                text = "".join(combo)
                want = self._user_lines(text)
                for op in ("install", "uninstall"):
                    rc.write_text(text, encoding="utf-8")
                    try:
                        getattr(complete, op)("zsh")
                    except BoostError:
                        if rc.read_text(encoding="utf-8") != text:
                            failures.append(("wrote despite refusing", op, text))
                        continue
                    after = rc.read_text(encoding="utf-8")
                    if self._user_lines(after) < want:
                        failures.append(("lost a user line", op, text))
                    if op == "uninstall" and START in after:
                        failures.append(("uninstall left a block", op, text))

        assert not failures, "%d violation(s), e.g. %r" % (
            len(failures), failures[:3])


class TestCommandSurface:
    def test_dry_run_install_writes_nothing_and_says_so(self, boost, sandbox):
        (sandbox / ".zshrc").write_text("export A=1\n", encoding="utf-8")

        res = boost("completions", "zsh", "--install", "--dry-run")

        assert "would" in res.out.lower()
        assert (sandbox / ".zshrc").read_text(encoding="utf-8") == "export A=1\n"

    def test_dry_run_uninstall_writes_nothing(self, boost, sandbox):
        boost("completions", "zsh", "--install")
        before = (sandbox / ".zshrc").read_text(encoding="utf-8")

        res = boost("completions", "zsh", "--uninstall", "--dry-run")

        assert "would" in res.out.lower()
        assert (sandbox / ".zshrc").read_text(encoding="utf-8") == before

    def test_dry_run_reports_a_no_op_as_a_no_op(self, boost, sandbox):
        boost("completions", "zsh", "--install")

        res = boost("completions", "zsh", "--install", "--dry-run")

        assert "no change" in res.out.lower()

    def test_a_malformed_rc_fails_the_command_with_guidance(self, boost, sandbox):
        (sandbox / ".zshrc").write_text(START + "\nexport KEEP=me\n",
                                        encoding="utf-8")

        res = boost("completions", "zsh", "--install", expect=1)

        assert ".zshrc" in (res.out + res.err)
        assert "KEEP=me" in (sandbox / ".zshrc").read_text(encoding="utf-8")

    def test_dry_run_alone_is_a_usage_error(self, boost, sandbox):
        """It qualifies --install/--uninstall; on its own it means nothing."""
        res = boost("completions", "zsh", "--dry-run", expect=2)

        assert "--install" in (res.out + res.err)
