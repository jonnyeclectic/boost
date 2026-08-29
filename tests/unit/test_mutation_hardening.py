# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Precision tests written against surviving mutmut mutants.

Each test here exists to kill a specific class of survivor: exact boundary
values, exact user-facing strings, encoding robustness, and forced-color
output. See `make mutation`.
"""
from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta

import pytest

from boost_cli.core import (
    ai,
    aihost,
    catalog,
    frontmatter,
    gitutil,
    journal,
    store,
    util,
)
from boost_cli.core import output as out
from boost_cli.errors import BoostError


def _iso(seconds_ago: float) -> str:
    then = datetime.now(UTC) - timedelta(seconds=seconds_ago)
    return then.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestRelTimeExactBoundaries:
    """Kills the (60|3600|86400|604800) -> n+1 and < -> <= mutants."""

    def test_exactly_one_minute_is_minutes(self):
        assert util.rel_time(_iso(60.5)) == "1m ago"

    def test_just_under_one_minute_is_seconds(self):
        assert util.rel_time(_iso(59)) == "59s ago"

    def test_exactly_one_hour_is_hours(self):
        assert util.rel_time(_iso(3600.5)) == "1h ago"

    def test_just_under_one_hour_is_minutes(self):
        assert util.rel_time(_iso(3599)) == "59m ago"

    def test_exactly_one_day_is_days(self):
        assert util.rel_time(_iso(86400.5)) == "1d ago"

    def test_just_under_one_day_is_hours(self):
        assert util.rel_time(_iso(86399)) == "23h ago"

    def test_exactly_one_week_is_weeks(self):
        assert util.rel_time(_iso(604800.5)) == "1w ago"

    def test_just_under_one_week_is_days(self):
        assert util.rel_time(_iso(604799)) == "6d ago"


class TestEncodingRobustness:
    """Kills errors='replace' -> strict mutants: invalid UTF-8 must not crash."""

    BAD = b"---\nname: mangled\ndescription: caf\xff\xfe broken\n---\n\n# Body \xff\n"

    def test_catalog_scan_survives_invalid_utf8(self, tmp_path):
        d = tmp_path / "mangled"
        d.mkdir()
        (d / "SKILL.md").write_bytes(self.BAD)
        entries = catalog.scan_dir(tmp_path, "t")
        assert len(entries) == 1
        assert entries[0]["name"] == "mangled"

    def test_install_from_path_survives_invalid_utf8(self, sandbox):
        d = sandbox / "mangled"
        d.mkdir()
        (d / "SKILL.md").write_bytes(self.BAD)
        res = store.install_from_path(d)
        assert res.name == "mangled"
        assert (store.skill_store_dir("mangled") / "SKILL.md").exists()

    def test_score_skill_survives_invalid_utf8(self, tmp_path):
        (tmp_path / "SKILL.md").write_bytes(self.BAD)
        score, _notes = util.score_skill(tmp_path)
        assert score > 0


class TestExactStrings:
    """Kills string-literal mutants in user-facing messages."""

    def test_ai_fallback_note_verbatim(self):
        # The note names every CLI that would work, built from `aihost`'s
        # table rather than hardcoded: telling a Gemini user to install Claude
        # is a worse answer than saying boost could not find either. Still
        # asserted verbatim, because the point of this class is to kill
        # string-literal mutants in what the user actually reads.
        assert ai.fallback_note() == (
            "AI features need one of `claude` or `gemini` on PATH, or "
            "ANTHROPIC_API_KEY set — using the heuristic fallback")

    def test_fallback_note_names_every_backend(self):
        """A backend added to the table must appear in the note, not silently.

        The verbatim assertion above would still pass if the note were
        hardcoded; this one fails if the sentence stops being derived.
        """
        for name in aihost.backends():
            assert "`%s`" % aihost.cli(name) in ai.fallback_note(), name

    def test_missing_git_hint_verbatim(self, monkeypatch):
        monkeypatch.setattr(gitutil.shutil, "which", lambda _: None)
        with pytest.raises(BoostError) as ei:
            gitutil.run(["status"])
        assert ei.value.message == "git is required but was not found on PATH"
        assert ei.value.hint == (
            "install git, e.g. `xcode-select --install` or `brew install git`")

    def test_source_dir_missing_hint_verbatim(self, sandbox, fixture_tap_src):
        from boost_cli.core import registry
        tap = registry.add(str(fixture_tap_src))
        catalog.rebuild_tap(tap)
        entry = catalog.resolve_one("brainstorming")
        entry = dict(entry, rel_dir="skills/not-there")
        with pytest.raises(BoostError) as ei:
            store.source_dir_for(entry)
        assert ei.value.message.startswith("source for brainstorming vanished")
        assert ei.value.hint == "run `boost update %s`" % tap.name


class TestForcedColorOutput:
    """Kills c()/style mutants that NO_COLOR-based tests can't see."""

    @pytest.fixture(autouse=True)
    def force_color(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")

    def test_ok_exact_ansi(self, capsys):
        # success role -> aurora green (#4ade80) truecolor under forced color
        out.ok("done")
        assert capsys.readouterr().out == (
            "  \033[38;2;74;222;128m✓\033[0m done\n")

    def test_warn_exact_ansi(self, capsys):
        # warn role -> aurora yellow (#facc15) truecolor, marker and message
        out.warn("careful")
        assert capsys.readouterr().out == (
            "  \033[38;2;250;204;21m!\033[0m "
            "\033[38;2;250;204;21mcareful\033[0m\n")

    def test_err_exact_ansi(self, capsys):
        out.err("boom", hint="try x")
        assert capsys.readouterr().err == (
            "\033[31m\033[1mError: \033[0mboom\n"
            "\033[2m  hint: try x\033[0m\n")

    def test_heading_exact_ansi(self, capsys):
        # Aurora cyan marker (truecolor under forced color) + bold title.
        out.heading("Section")
        assert capsys.readouterr().out == (
            "\033[38;2;64;203;227m==>\033[0m \033[1mSection\033[0m\n")

    def test_c_multi_style_order(self):
        assert out.c("x", out.RED, out.BOLD) == "\033[31m\033[1mx\033[0m"


class TestSplitDirectReturns:
    """Kills mutants inside frontmatter.split's early returns (parse() masks
    them because any truthy junk block still parses to {})."""

    def test_bad_fence_returns_empty_block_exactly(self):
        text = "---abc\n---\nbody"
        assert frontmatter.split(text) == ("", text)

    def test_body_keeps_leading_indentation(self):
        # lstrip("\n") must not become lstrip(None): indented first body line
        _, body = frontmatter.parse("---\nname: x\n---\n\n    indented code\n")
        assert body == "    indented code"


class TestGitRunPlumbing:
    def test_run_uses_cwd_argument(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        proc = gitutil.run(["rev-parse", "--is-inside-work-tree"],
                           cwd=tmp_path, check=False)
        assert proc.stdout.strip() == "true"

    def test_clone_shallow_is_depth_one(self, sandbox, fixture_tap_src, tmp_path):
        dest = tmp_path / "clone"
        gitutil.clone_shallow(str(fixture_tap_src), dest)
        depth = subprocess.run(
            ["git", "-C", str(dest), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True)
        assert depth.stdout.strip() == "1"


class TestStoreJournalFields:
    """Kills journal.log(...) argument mutants in store operations."""

    @pytest.fixture()
    def ready(self, sandbox, fixture_tap_src):
        from boost_cli.core import registry
        tap = registry.add(str(fixture_tap_src))
        catalog.rebuild_tap(tap)
        return tap

    def test_install_event_fields(self, ready):
        store.install(catalog.resolve_one("brainstorming"))
        e = journal.events(1)[0]
        assert e["action"] == "install"
        assert e["subject"] == "brainstorming"
        assert e["tap"] == ready.name
        assert e["version"] == "1.4.0"

    def test_import_event_fields(self, sandbox, tmp_path):
        d = tmp_path / "imp"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: imp\nversion: 0.1.0\n---\nbody", encoding="utf-8")
        store.install_from_path(d)
        e = journal.events(1)[0]
        assert e["action"] == "import"
        assert e["subject"] == "imp"
        assert e["source"] == str(d)

    def test_uninstall_event_fields(self, ready):
        store.install(catalog.resolve_one("brainstorming"))
        store.uninstall("brainstorming")
        e = journal.events(1)[0]
        assert e["action"] == "uninstall"
        assert e["subject"] == "brainstorming"

    def test_sync_apply_actions_verbatim(self, ready):
        store.install(catalog.resolve_one("brainstorming"))
        from boost_cli.core import paths
        link = paths.home() / ".claude" / "skills" / "brainstorming"
        link.unlink()
        actions = store.sync_apply(store.sync_plan())
        assert actions == ["linked brainstorming → claude-code"]
        e = journal.events(1)[0]
        assert e["action"] == "sync"
        assert e["subject"] == "1 fixes"

    def test_install_from_path_lock_entry_exact(self, sandbox, tmp_path):
        d = tmp_path / "imp2"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: imp2\nversion: 2.5.0\n---\n\n# T\n\nbody text\n", encoding="utf-8")
        store.install_from_path(d, tap_label="side")
        from boost_cli.core import lockfile
        entry = lockfile.get_skill("imp2")
        assert entry["version"] == "2.5.0"
        assert entry["tap"] == "side"
        assert entry["source_dir"] == str(d)
        assert entry["commit"] == ""
        assert entry["pinned"] is False
        assert entry["quarantined"] is False
        assert entry["tags"] == []
        assert len(entry["sha256"]) == 64
        assert entry["sha256"] == util.sha256_dir(store.skill_store_dir("imp2"))


class TestCatalogDescriptionFallback:
    def test_truncates_at_exactly_160(self, tmp_path):
        d = tmp_path / "long"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: long\n---\n\n" + "x" * 500 + "\n", encoding="utf-8")
        (e,) = catalog.scan_dir(tmp_path, "t")
        assert e["description"] == "x" * 160

    def test_search_empty_entries_returns_empty(self):
        assert catalog.search("anything", entries=[]) == []
