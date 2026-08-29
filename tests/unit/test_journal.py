# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: boost_cli/core/journal.py — the append-only pulse feed."""
from __future__ import annotations

import getpass
import json
import re

import pytest

from boost_cli.core import journal, paths


def write_lines(n, action="noise"):
    """Write n synthetic JSONL events directly (fast path for rotation)."""
    paths.ensure_dirs()
    lines = [json.dumps({"ts": "2026-01-01T00:00:00Z", "user": "u",
                         "action": action, "subject": "s%d" % i})
             for i in range(n)]
    paths.pulse_path().write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestLog:
    def test_writes_valid_jsonl_with_required_fields(self, sandbox):
        journal.log("install", "brainstorming")
        lines = paths.pulse_path().read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        e = json.loads(lines[0])
        assert e["action"] == "install"
        assert e["subject"] == "brainstorming"
        assert e["user"] == getpass.getuser()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e["ts"])

    def test_extra_fields_kept_none_dropped(self, sandbox):
        journal.log("update", "tdd-workflow", version="3.0.1", detail=None)
        e = json.loads(paths.pulse_path().read_text(encoding="utf-8"))
        assert e["version"] == "3.0.1"
        assert "detail" not in e

    def test_subject_defaults_to_empty(self, sandbox):
        journal.log("sync")
        e = json.loads(paths.pulse_path().read_text(encoding="utf-8"))
        assert e["subject"] == ""

    def test_appends_do_not_clobber(self, sandbox):
        journal.log("a", "1")
        journal.log("b", "2")
        assert len(paths.pulse_path().read_text(encoding="utf-8").splitlines()) == 2


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
        lines = paths.pulse_path().read_text(encoding="utf-8").splitlines()
        assert len(lines) == journal.ROTATE_KEEP == 2500
        assert json.loads(lines[-1])["subject"] == "the-newest"

    def test_log_at_threshold_does_not_rotate(self, sandbox):
        write_lines(4999)
        journal.log("install", "s")  # now exactly 5000 lines: no rotation
        assert len(paths.pulse_path().read_text(encoding="utf-8").splitlines()) == 5000

    def test_rotation_keeps_the_tail(self, sandbox):
        write_lines(5001)
        journal.log("install", "tail-marker")
        first = json.loads(paths.pulse_path().read_text(encoding="utf-8").splitlines()[0])
        # 5002 total, keep last 2500 -> first kept is index 2502 -> "s2502"
        assert first["subject"] == "s2502"


class TestRotationConcurrency:
    """Rotation is a read-modify-write, and this repo expects concurrent
    boost processes. Every assertion here is about not losing an event."""

    def _lock_path(self):
        p = paths.pulse_path()
        return p.with_name(p.name + ".rotate.lock")

    def test_a_held_lock_skips_rotation_entirely(self, sandbox):
        # Another process is already trimming. Doing it a second time from a
        # stale read is exactly how an event goes missing.
        write_lines(5001)
        paths.ensure_dirs()
        self._lock_path().write_text("999999", encoding="utf-8")
        journal._maybe_rotate()
        assert len(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()) == 5001

    def test_the_lock_is_released_after_rotating(self, sandbox):
        write_lines(5001)
        journal._maybe_rotate()
        assert not self._lock_path().exists()
        assert len(paths.pulse_path().read_text(
            encoding="utf-8").splitlines()) == journal.ROTATE_KEEP

    def test_an_append_during_the_snapshot_survives_it(self, sandbox,
                                                       monkeypatch):
        # The lost update: a concurrent log() lands after rotation has read
        # the feed but before it swaps the trimmed file into place. The old
        # code wrote its stale snapshot over the top and the event vanished.
        write_lines(5001)
        p = paths.pulse_path()
        real_read_bytes = type(p).read_bytes

        def read_then_someone_appends(self, *a, **kw):
            # Scoped to the pulse file: this patches a method every Path in
            # the process shares, so an unscoped version hands some unrelated
            # read the feed's bytes and appends to the feed behind its back.
            data = real_read_bytes(self, *a, **kw)
            if self == p:
                with p.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": "2026-01-01T00:00:00Z",
                                        "user": "u", "action": "install",
                                        "subject": "raced-in"}) + "\n")
            return data

        monkeypatch.setattr(type(p), "read_bytes", read_then_someone_appends)
        journal._maybe_rotate()
        subjects = [json.loads(line)["subject"] for line
                    in p.read_text(encoding="utf-8").splitlines()]
        assert "raced-in" in subjects
        assert subjects[-1] == "raced-in"        # and in the right order

    def test_a_second_rotation_inside_the_lock_is_a_no_op(self, sandbox,
                                                          monkeypatch):
        # The count that gets us into the lock is taken outside it. If another
        # process rotated in between, the re-read must notice and leave the
        # already-trimmed file alone rather than trim it again.
        write_lines(5001)
        p = paths.pulse_path()
        real_read_bytes = type(p).read_bytes

        def rotated_by_someone_else(self, *a, **kw):
            if self == p:
                # Exactly at the threshold, the boundary that decides it:
                # ROTATE_AT lines is healthy, ROTATE_AT + 1 is not.
                write_lines(journal.ROTATE_AT, action="fresh")
            return real_read_bytes(self, *a, **kw)

        monkeypatch.setattr(journal, "_line_count", lambda _p: 5001)
        monkeypatch.setattr(type(p), "read_bytes", rotated_by_someone_else)
        journal._maybe_rotate()
        assert len(p.read_text(encoding="utf-8").splitlines()) == journal.ROTATE_AT

    def test_undecodable_bytes_do_not_abort_rotation(self, sandbox):
        # The feed carries user-supplied text (skill names, tap names), and a
        # torn append can leave a partial multi-byte sequence behind. Rotation
        # must trim the file anyway rather than raise and let it grow forever.
        write_lines(5001)
        p = paths.pulse_path()
        with p.open("ab") as f:
            f.write(b'{"ts": "2026-01-01T00:00:00Z", "user": "u", '
                    b'"action": "install", "subject": "caf\xe9"}\n')
        journal._maybe_rotate()
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) == journal.ROTATE_KEEP
        assert "caf" in lines[-1]          # kept, with the bad byte replaced

    def test_rotation_healthy_closes_its_handle(self, sandbox, monkeypatch):
        # It used to be a bare `p.open()` left to the garbage collector — the
        # one open in the module without a `with`. Asserted by holding a
        # reference to every handle it opens rather than by watching for a
        # ResourceWarning: that warning is raised during finalization, where
        # pytest reports it as unraisable instead of failing the test, so it
        # would not have caught this.
        write_lines(3)
        opened = []
        path_type = type(paths.pulse_path())
        real_open = path_type.open

        def tracking_open(self, *a, **kw):
            handle = real_open(self, *a, **kw)
            if self == paths.pulse_path():   # only the feed's handles are ours
                opened.append(handle)
            return handle

        monkeypatch.setattr(path_type, "open", tracking_open)
        assert journal.rotation_healthy() is True
        assert opened, "expected rotation_healthy to read the feed"
        assert all(handle.closed for handle in opened)


class TestFallbacks:
    def test_user_falls_back_to_unknown(self, sandbox, monkeypatch):
        def no_user():
            raise KeyError("no login")
        monkeypatch.setattr("boost_cli.core.util.getpass.getuser", no_user)
        journal.log("install", "x")
        assert json.loads(paths.pulse_path().read_text(encoding="utf-8"))["user"] == "unknown"

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


class TestEventsLimitGuard:
    """A negative n used to become a negative slice — see the roadmap item."""

    def test_negative_n_raises_instead_of_inverting(self, sandbox):
        for i in range(3):
            journal.log("install", "s%d" % i)
        with pytest.raises(ValueError) as exc:
            journal.events(-1)
        assert str(exc.value) == "events(n=-1): n must be >= 0"
        assert len(journal.events()) == 3

    def test_zero_n_is_empty_not_everything(self, sandbox):
        for i in range(3):
            journal.log("install", "s%d" % i)
        assert journal.events(0) == []

    def test_n_larger_than_feed_returns_all(self, sandbox):
        journal.log("install", "only")
        assert [e["subject"] for e in journal.events(9)] == ["only"]
