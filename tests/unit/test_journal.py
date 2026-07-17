"""Unit tests: boost_cli/core/journal.py — the append-only pulse feed."""
from __future__ import annotations

import getpass
import json
import re

from boost_cli.core import journal, paths


def write_lines(n, action="noise"):
    """Write n synthetic JSONL events directly (fast path for rotation)."""
    paths.ensure_dirs()
    lines = [json.dumps({"ts": "2026-01-01T00:00:00Z", "user": "u",
                         "action": action, "subject": "s%d" % i})
             for i in range(n)]
    paths.pulse_path().write_text("\n".join(lines) + "\n")


class TestLog:
    def test_writes_valid_jsonl_with_required_fields(self, sandbox):
        journal.log("install", "brainstorming")
        lines = paths.pulse_path().read_text().splitlines()
        assert len(lines) == 1
        e = json.loads(lines[0])
        assert e["action"] == "install"
        assert e["subject"] == "brainstorming"
        assert e["user"] == getpass.getuser()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e["ts"])

    def test_extra_fields_kept_none_dropped(self, sandbox):
        journal.log("update", "tdd-workflow", version="3.0.1", detail=None)
        e = json.loads(paths.pulse_path().read_text())
        assert e["version"] == "3.0.1"
        assert "detail" not in e

    def test_subject_defaults_to_empty(self, sandbox):
        journal.log("sync")
        e = json.loads(paths.pulse_path().read_text())
        assert e["subject"] == ""

    def test_appends_do_not_clobber(self, sandbox):
        journal.log("a", "1")
        journal.log("b", "2")
        assert len(paths.pulse_path().read_text().splitlines()) == 2


class TestEvents:
    def test_missing_file_is_empty_list(self, sandbox):
        assert journal.events() == []

    def test_newest_first(self, sandbox):
        journal.log("install", "first")
        journal.log("install", "second")
        journal.log("uninstall", "third")
        subjects = [e["subject"] for e in journal.events()]
        assert subjects == ["third", "second", "first"]

    def test_n_limits_to_most_recent(self, sandbox):
        for i in range(5):
            journal.log("install", "s%d" % i)
        got = journal.events(n=2)
        assert [e["subject"] for e in got] == ["s4", "s3"]
        assert len(journal.events(n=1)) == 1

    def test_action_filter(self, sandbox):
        journal.log("install", "a")
        journal.log("uninstall", "b")
        journal.log("install", "c")
        got = journal.events(action="install")
        assert [e["subject"] for e in got] == ["c", "a"]
        assert journal.events(action="never") == []

    def test_subject_filter(self, sandbox):
        journal.log("install", "a")
        journal.log("uninstall", "a")
        journal.log("install", "b")
        got = journal.events(subject="a")
        assert [e["action"] for e in got] == ["uninstall", "install"]

    def test_combined_filters(self, sandbox):
        journal.log("install", "a")
        journal.log("uninstall", "a")
        journal.log("install", "b")
        got = journal.events(action="install", subject="a")
        assert len(got) == 1
        assert got[0]["action"] == "install" and got[0]["subject"] == "a"

    def test_corrupt_lines_skipped(self, sandbox):
        journal.log("install", "good")
        with paths.pulse_path().open("a") as f:
            f.write("this is not json\n")
            f.write("{\"also: broken\n")
        journal.log("install", "good2")
        subjects = [e["subject"] for e in journal.events()]
        assert subjects == ["good2", "good"]


class TestRotation:
    def test_log_over_threshold_rotates_to_2500(self, sandbox):
        write_lines(5001)
        journal.log("install", "the-newest")
        lines = paths.pulse_path().read_text().splitlines()
        assert len(lines) == journal.ROTATE_KEEP == 2500
        assert json.loads(lines[-1])["subject"] == "the-newest"

    def test_log_at_threshold_does_not_rotate(self, sandbox):
        write_lines(4999)
        journal.log("install", "s")  # now exactly 5000 lines: no rotation
        assert len(paths.pulse_path().read_text().splitlines()) == 5000

    def test_rotation_keeps_the_tail(self, sandbox):
        write_lines(5001)
        journal.log("install", "tail-marker")
        first = json.loads(paths.pulse_path().read_text().splitlines()[0])
        # 5002 total, keep last 2500 -> first kept is index 2502 -> "s2502"
        assert first["subject"] == "s2502"


class TestFallbacks:
    def test_user_falls_back_to_unknown(self, sandbox, monkeypatch):
        def no_user():
            raise KeyError("no login")
        monkeypatch.setattr("boost_cli.core.journal.getpass.getuser", no_user)
        journal.log("install", "x")
        assert json.loads(paths.pulse_path().read_text())["user"] == "unknown"

    def test_maybe_rotate_tolerates_missing_file(self, sandbox):
        assert not paths.pulse_path().exists()
        journal._maybe_rotate()  # must swallow the OSError, not raise
        assert not paths.pulse_path().exists()


class TestRotationHealthy:
    def test_missing_file_healthy(self, sandbox):
        assert journal.rotation_healthy() is True

    def test_exactly_at_limit_healthy(self, sandbox):
        write_lines(journal.ROTATE_AT)
        assert journal.rotation_healthy() is True

    def test_one_over_limit_unhealthy(self, sandbox):
        write_lines(journal.ROTATE_AT + 1)
        assert journal.rotation_healthy() is False
