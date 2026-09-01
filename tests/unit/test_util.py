# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/util.py — time, hashing, versions, scoring."""
from __future__ import annotations

import argparse
import hashlib
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from boost_cli.core import util

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

# An arbitrary but FIXED instant. `iso_ago` measures back from it and the
# frozen_clock fixture makes rel_time read the same one, so the two reads
# cannot drift apart. See the fixture for why that matters.
FROZEN_NOW = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


class _FrozenDatetime(datetime):
    """``datetime`` with ``now()`` pinned to :data:`FROZEN_NOW`.

    Subclassed rather than mocked so ``strptime``/``replace``/arithmetic all
    keep working inside ``rel_time`` untouched — only ``now()`` changes.
    """

    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW if tz is not None else FROZEN_NOW.replace(tzinfo=None)


@pytest.fixture
def frozen_clock(monkeypatch):
    """Pin ``util``'s clock so bucket-boundary assertions are exact.

    Without this the test measured a moving target: ``iso_ago`` truncates to
    whole seconds, so the stamp is always <= the true instant, and ``rel_time``
    then calls ``now()`` a SECOND time and floors the difference. The delta is
    therefore ``n + frac(first_now) + runtime``, which tips into the next bucket
    whenever that sum reaches 1.0 — rare on an idle laptop, routine on a loaded
    runner. The boundary cases are the ones that bite: ``iso_ago(59)`` reads
    "1m ago" and ``iso_ago(59 * 60)`` reads "1h ago", changing the UNIT rather
    than a neighbouring number, which is why it looked like random redness.
    Observed on CI as `assert '1m ago' == '59s ago'`. One frozen instant makes
    every case below deterministic.
    """
    monkeypatch.setattr(util, "datetime", _FrozenDatetime)
    return FROZEN_NOW


def iso_ago(seconds: float) -> str:
    """An ISO stamp exactly ``seconds`` before :data:`FROZEN_NOW`."""
    return (FROZEN_NOW - timedelta(seconds=seconds)).strftime(ISO_FMT)


class TestNowIso:
    def test_format(self):
        s = util.now_iso()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s)
        # parses back and is (approximately) now, in UTC
        parsed = datetime.strptime(s, ISO_FMT).replace(tzinfo=UTC)
        delta = abs((datetime.now(UTC) - parsed).total_seconds())
        assert delta < 5


class TestUser:
    def test_returns_getpass_user(self, monkeypatch):
        monkeypatch.setattr(util.getpass, "getuser", lambda: "alice")
        assert util.user() == "alice"

    def test_falls_back_to_unknown_when_getpass_raises(self, monkeypatch):
        def boom():
            raise KeyError("no login")
        monkeypatch.setattr(util.getpass, "getuser", boom)
        assert util.user() == "unknown"


@pytest.mark.usefixtures("frozen_clock")
class TestRelTime:
    def test_just_now_floors_to_one_second(self):
        assert util.rel_time(iso_ago(0)) == "1s ago"

    def test_30_seconds(self):
        assert util.rel_time(iso_ago(30)) == "30s ago"

    def test_59_seconds_still_seconds_bucket(self):
        assert util.rel_time(iso_ago(59)) == "59s ago"

    def test_90_seconds_is_one_minute(self):
        assert util.rel_time(iso_ago(90)) == "1m ago"

    def test_59_minutes(self):
        assert util.rel_time(iso_ago(59 * 60)) == "59m ago"

    def test_two_hours(self):
        assert util.rel_time(iso_ago(2 * 3600)) == "2h ago"

    def test_23_hours_is_hours_bucket(self):
        assert util.rel_time(iso_ago(23 * 3600)) == "23h ago"

    def test_25_hours_is_one_day(self):
        assert util.rel_time(iso_ago(25 * 3600)) == "1d ago"

    def test_six_days(self):
        assert util.rel_time(iso_ago(6 * 86400)) == "6d ago"

    def test_eight_days_is_one_week(self):
        assert util.rel_time(iso_ago(8 * 86400)) == "1w ago"

    def test_55_days_is_seven_weeks(self):
        assert util.rel_time(iso_ago(55 * 86400)) == "7w ago"

    def test_exactly_60_seconds_rolls_to_minutes(self):
        # the seconds bucket is `secs < 60`; at 60 it must roll to minutes.
        # (Pins the 60 boundary literal — a 61 would keep it "60s ago".)
        assert util.rel_time(iso_ago(60)) == "1m ago"

    def test_exactly_3600_seconds_rolls_to_hours(self):
        # the minutes bucket is `secs < 3600`; at one hour it rolls to hours.
        # (Pins the 3600 boundary — a 3601 would say "60m ago".)
        assert util.rel_time(iso_ago(3600)) == "1h ago"

    def test_60_days_is_absolute_date_not_weeks(self):
        # past the `secs < 604800 * 8` (eight-week) cutoff, output is a date, not
        # "8w ago". (Pins the *8 multiplier — a *9 would extend weeks to 60 days.)
        # Measured from FROZEN_NOW, like every case above: reading the real clock
        # here would compare against the frozen one and never agree.
        then = FROZEN_NOW - timedelta(days=60)
        assert util.rel_time(then.strftime(ISO_FMT)) == then.strftime("%Y-%m-%d")

    def test_100_days_is_absolute_date(self):
        then = FROZEN_NOW - timedelta(days=100)
        assert util.rel_time(then.strftime(ISO_FMT)) == then.strftime("%Y-%m-%d")

    def test_junk_passthrough(self):
        assert util.rel_time("not-a-date") == "not-a-date"

    def test_empty_becomes_question_mark(self):
        assert util.rel_time("") == "?"

    def test_none_becomes_question_mark(self):
        assert util.rel_time(None) == "?"


class TestHumanSize:
    @pytest.mark.parametrize("n,expected", [
        (0, "0B"),
        (1, "1B"),
        (512, "512B"),
        (1023, "1023B"),
        (1024, "1.0KB"),
        (1536, "1.5KB"),
        (1024 * 1024 - 512, "1023.5KB"),
        (1024 * 1024, "1.0MB"),
        (1024 ** 3, "1.0GB"),
        (1024 ** 3 * 11 // 2, "5.5GB"),
        (1024 ** 4, "1024.0GB"),
    ])
    def test_boundaries(self, n, expected):
        assert util.human_size(n) == expected


class TestSlugify:
    def test_spaces_become_dashes(self):
        assert util.slugify("hello world") == "hello-world"

    def test_uppercase_lowered(self):
        assert util.slugify("My Great Skill") == "my-great-skill"

    def test_specials_collapse_to_single_dash(self):
        assert util.slugify("a!!@@b??c") == "a-b-c"

    def test_underscore_is_special(self):
        assert util.slugify("snake_case_name") == "snake-case-name"

    def test_leading_trailing_stripped(self):
        assert util.slugify("  --wrapped--  ") == "wrapped"

    def test_empty_falls_back_to_skill(self):
        assert util.slugify("") == "skill"

    def test_all_specials_fall_back_to_skill(self):
        assert util.slugify("!!!") == "skill"

    def test_digits_and_dashes_kept(self):
        assert util.slugify("tdd-workflow-3") == "tdd-workflow-3"


class TestSha256Dir:
    def _make(self, root, files):
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")

    def test_empty_dir_is_sha256_of_nothing(self, tmp_path):
        assert util.sha256_dir(tmp_path) == hashlib.sha256().hexdigest()

    def test_deterministic_and_order_independent(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(), b.mkdir()
        self._make(a, {"x.md": "one", "y.md": "two"})
        # create in the opposite order in b
        self._make(b, {"y.md": "two", "x.md": "one"})
        assert util.sha256_dir(a) == util.sha256_dir(a)  # stable
        assert util.sha256_dir(a) == util.sha256_dir(b)  # content-addressed

    def test_content_change_changes_hash(self, tmp_path):
        self._make(tmp_path, {"x.md": "one"})
        before = util.sha256_dir(tmp_path)
        (tmp_path / "x.md").write_text("two", encoding="utf-8")
        assert util.sha256_dir(tmp_path) != before

    def test_rename_changes_hash(self, tmp_path):
        self._make(tmp_path, {"x.md": "same content"})
        before = util.sha256_dir(tmp_path)
        (tmp_path / "x.md").rename(tmp_path / "z.md")
        assert util.sha256_dir(tmp_path) != before

    def test_nested_files_counted(self, tmp_path):
        self._make(tmp_path, {"x.md": "one"})
        before = util.sha256_dir(tmp_path)
        self._make(tmp_path, {"sub/deep.md": "nested"})
        assert util.sha256_dir(tmp_path) != before

    def test_ignores_git_pycache_dsstore(self, tmp_path):
        clean, noisy = tmp_path / "clean", tmp_path / "noisy"
        clean.mkdir(), noisy.mkdir()
        self._make(clean, {"SKILL.md": "body"})
        self._make(noisy, {
            "SKILL.md": "body",
            ".git/config": "[core]",
            ".git/objects/ab": "blob",
            "__pycache__/mod.pyc": "bytecode",
            ".DS_Store": "junk",
        })
        assert util.sha256_dir(noisy) == util.sha256_dir(clean)


class TestDirSize:
    def test_empty_dir_is_zero(self, tmp_path):
        assert util.dir_size(tmp_path) == 0

    def test_sums_nested_files(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"x" * 10)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_bytes(b"y" * 32)
        assert util.dir_size(tmp_path) == 42


class TestSemver:
    @pytest.mark.parametrize("v,expected", [
        ("1.10.0", (1, 10, 0)),
        ("2.0", (2, 0, 0)),
        ("1", (1, 0, 0)),
        ("v1.2.3", (1, 2, 3)),
        ("1.2.3.4", (1, 2, 3)),   # extra segments dropped
        ("", (0, 0, 0)),
        (None, (0, 0, 0)),
        ("junk", (0, 0, 0)),
        (0, (0, 0, 0)),
    ])
    def test_semver_tuple(self, v, expected):
        assert util.semver_tuple(v) == expected

    def test_gt_1_10_beats_1_9_9(self):
        assert util.semver_gt("1.10.0", "1.9.9") is True

    def test_gt_2_0_beats_1_9_9(self):
        assert util.semver_gt("2.0", "1.9.9") is True

    def test_gt_equal_is_false(self):
        assert util.semver_gt("1.2.3", "1.2.3") is False

    def test_gt_lower_is_false(self):
        assert util.semver_gt("1.9.9", "1.10.0") is False

    def test_gt_junk_tolerated(self):
        assert util.semver_gt("junk", "0.0.1") is False
        assert util.semver_gt("0.0.1", "junk") is True


GOOD_DESC = "A thorough description that is definitely forty characters or more."
GOOD_BODY = (
    "# Test Skill\n\n"
    "Use this skill when working on structured tasks in this repo.\n\n"
    "## Steps\n\n"
    "1. Do the first thing carefully and deliberately.\n"
    "- Also consider these bullet points.\n\n"
    "```bash\necho example\n```\n\n"
    "Additional prose so the body is comfortably over two hundred characters.\n"
)


def make_skill(root, text, extra_files=None):
    d = root / "skill"
    d.mkdir(exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    for name, content in (extra_files or {}).items():
        (d / name).write_text(content, encoding="utf-8")
    return d


def full_text(desc=GOOD_DESC, version="1.2.3", body=GOOD_BODY):
    return "---\nname: test-skill\ndescription: %s\nversion: %s\n---\n\n%s" % (
        desc, version, body)


class TestScoreSkill:
    def test_missing_skill_md(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert util.score_skill(d) == (0, ["missing SKILL.md"])

    def test_unreadable_skill_md(self, tmp_path):
        d = tmp_path / "skill"
        (d / "SKILL.md").mkdir(parents=True)  # a dir: exists but unreadable
        score, notes = util.score_skill(d)
        assert score == 0
        assert len(notes) == 1
        assert notes[0].startswith("unreadable SKILL.md: ")

    def test_perfect_lone_file_scores_95(self, tmp_path):
        d = make_skill(tmp_path, full_text())
        assert util.score_skill(d) == (95, [])

    def test_license_and_extras_cap_at_100(self, tmp_path):
        d = make_skill(tmp_path, full_text(),
                       extra_files={"LICENSE": "MIT"})
        # 95 + 5 (license) + 5 (extra files) = 105, capped
        assert util.score_skill(d) == (100, [])

    def test_minimal_body_scores_25_with_all_notes(self, tmp_path):
        d = make_skill(tmp_path, "hi")
        score, notes = util.score_skill(d)
        assert score == 25
        assert notes == [
            "frontmatter missing `name`",
            "frontmatter missing `description`",
            "frontmatter missing `version`",
            "body is short (<200 chars)",
            "no markdown headings in body",
            "no examples, steps, or code blocks",
        ]

    def test_thin_description_39_chars(self, tmp_path):
        d = make_skill(tmp_path, full_text(desc="d" * 39))
        score, notes = util.score_skill(d)
        assert score == 90  # lost only the +5 depth bonus
        assert "description is thin (<40 chars)" in notes

    def test_description_exactly_40_chars_gets_bonus(self, tmp_path):
        d = make_skill(tmp_path, full_text(desc="d" * 40))
        assert util.score_skill(d) == (95, [])

    def test_non_semver_version_penalized(self, tmp_path):
        d = make_skill(tmp_path, full_text(version="banana"))
        score, notes = util.score_skill(d)
        assert score == 90  # +10 version present, -5 not semver
        assert "version is not semver-ish" in notes

    def test_two_segment_version_is_semver_ish(self, tmp_path):
        d = make_skill(tmp_path, full_text(version="1.0"))
        assert util.score_skill(d) == (95, [])

    def test_body_exactly_200_chars_gets_length_points(self, tmp_path):
        d = make_skill(tmp_path, "---\nname: x\n---\n" + "B" * 200)
        score, notes = util.score_skill(d)
        # 20 + 10 name + 15 body + 5 no-TODO
        assert score == 50
        assert "body is short (<200 chars)" not in notes

    def test_body_199_chars_is_short(self, tmp_path):
        d = make_skill(tmp_path, "---\nname: x\n---\n" + "B" * 199)
        score, notes = util.score_skill(d)
        assert score == 35
        assert "body is short (<200 chars)" in notes

    def test_todo_costs_5_and_notes(self, tmp_path):
        d = make_skill(tmp_path, full_text(body=GOOD_BODY + "\nTODO: finish\n"))
        score, notes = util.score_skill(d)
        assert score == 90
        assert notes == ["contains TODO/FIXME"]

    def test_fixme_also_flagged(self, tmp_path):
        d = make_skill(tmp_path, full_text(body=GOOD_BODY + "\nFIXME later\n"))
        _, notes = util.score_skill(d)
        assert "contains TODO/FIXME" in notes

    def test_no_headings_note(self, tmp_path):
        body = "plain prose. " * 20 + "\n- a bullet so examples still pass\n"
        d = make_skill(tmp_path, full_text(body=body))
        score, notes = util.score_skill(d)
        assert score == 85
        assert notes == ["no markdown headings in body"]

    def test_no_examples_note(self, tmp_path):
        body = "# Heading\n\n" + "plain prose without lists or code. " * 8
        d = make_skill(tmp_path, full_text(body=body))
        score, notes = util.score_skill(d)
        assert score == 85
        assert notes == ["no examples, steps, or code blocks"]

    def test_license_in_frontmatter_counts(self, tmp_path):
        text = "---\nlicense: MIT\n---\nhi"
        d = make_skill(tmp_path, text)
        score, notes = util.score_skill(d)
        assert score == 30  # 20 + 5 no-TODO + 5 license
        assert "frontmatter missing `name`" in notes

    def test_extra_files_bonus(self, tmp_path):
        d = make_skill(tmp_path, "hi", extra_files={"reference.md": "notes"})
        score, _ = util.score_skill(d)
        assert score == 30  # minimal 25 + 5 extras

    def test_ignored_names_are_not_extras(self, tmp_path):
        d = make_skill(tmp_path, "hi", extra_files={".DS_Store": "junk"})
        score, _ = util.score_skill(d)
        assert score == 25  # no extras bonus

    def test_oversized_skill_md_penalized(self, tmp_path):
        d = make_skill(tmp_path, full_text(body=GOOD_BODY + "P" * 48_000))
        score, notes = util.score_skill(d)
        assert score == 85  # 95 - 10
        assert notes == ["very large SKILL.md (>48KB) — consider splitting"]

    def test_48kb_exactly_is_not_penalized(self, tmp_path):
        base = full_text()
        text = base + "P" * (48_000 - len(base))
        assert len(text) == 48_000
        d = make_skill(tmp_path, text)
        assert util.score_skill(d) == (95, [])

    def test_48001_chars_is_penalized(self, tmp_path):
        # one char over the 48_000 cutoff (`> 48_000`) crosses into the penalty;
        # pins the boundary against a `> 48_001` off-by-one.
        base = full_text()
        text = base + "P" * (48_001 - len(base))
        assert len(text) == 48_001
        d = make_skill(tmp_path, text)
        score, notes = util.score_skill(d)
        assert score == 85
        assert "very large SKILL.md (>48KB) — consider splitting" in notes

    def test_heading_on_a_later_line_still_counts(self, tmp_path):
        # the heading probe uses re.MULTILINE, so a heading below the first line
        # must still register (no "no markdown headings" note). Pins re.M — a
        # dropped flag would only match a heading at the very start of the body.
        body = ("Intro prose that runs on for a while so the body clears the two "
                "hundred character minimum comfortably and then some more.\n\n"
                "## Later Heading\n\n- a bullet keeps the examples check happy.\n")
        d = make_skill(tmp_path, full_text(body=body))
        _score, notes = util.score_skill(d)
        assert "no markdown headings in body" not in notes

    def test_code_fence_alone_satisfies_examples(self, tmp_path):
        # a ``` fence with NO numbered list and NO bullet must satisfy the
        # examples check. Pins the leading `"```" in body or ...` term (an `and`
        # or a corrupted literal would demand a list too).
        body = ("# Heading\n\nProse padding to exceed two hundred characters so the "
                "length bonus applies and nothing else trips a note here today.\n\n"
                "```bash\necho hello\n```\n")
        d = make_skill(tmp_path, full_text(body=body))
        _score, notes = util.score_skill(d)
        assert "no examples, steps, or code blocks" not in notes

    def test_numbered_list_below_first_line_satisfies_examples(self, tmp_path):
        # a numbered list (not on the first line, no fence, no bullet) satisfies
        # the examples check via re.MULTILINE. Pins the `^\d+\. ` probe + its flag.
        body = ("# Heading\n\nSome prose padding to comfortably exceed the two "
                "hundred character minimum for the length bonus to apply now.\n\n"
                "1. The first and only concrete step in this body.\n")
        d = make_skill(tmp_path, full_text(body=body))
        _score, notes = util.score_skill(d)
        assert "no examples, steps, or code blocks" not in notes

    def test_license_file_on_disk_adds_five_over_a_plain_extra(self, tmp_path):
        # a LICENSE *file* (not just frontmatter) earns the license +5 on top of
        # the extras +5 any sidecar earns. Isolating vs a plain extra pins the
        # "LICENSE" filename literal against a corrupted/renamed check.
        # minimal bodies keep both scores well below the 100 cap so the +5 shows
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        licensed = make_skill(tmp_path / "a", "hi",
                              extra_files={"LICENSE": "MIT\n"})
        plain = make_skill(tmp_path / "b", "hi",
                          extra_files={"notes.md": "x\n"})
        assert util.score_skill(licensed)[0] - util.score_skill(plain)[0] == 5

    def test_description_over_1024_chars_penalized_and_noted(self, tmp_path):
        d = make_skill(tmp_path, full_text(desc="d" * 1025))
        score, notes = util.score_skill(d)
        assert score == 85  # 95 - 10 for the length penalty
        assert "description exceeds 1024 chars — agent hosts truncate it" in notes

    def test_description_exactly_1024_chars_is_not_penalized(self, tmp_path):
        d = make_skill(tmp_path, full_text(desc="d" * 1024))
        score, notes = util.score_skill(d)
        assert score == 95
        assert not any("truncate" in n for n in notes)

    def test_unclosed_frontmatter_is_one_note_not_three(self, tmp_path):
        # A SKILL.md that opens `---` and never closes it used to score like a
        # file missing name/description/version separately (three notes for
        # one cause), because `frontmatter.parse` silently degrades to "no
        # frontmatter" for this exact input.
        d = make_skill(tmp_path,
                       "---\nname: x\ndescription: y\nversion: 1.0.0\n"
                       "no closing fence\n")
        assert util.score_skill(d) == (
            0, ["frontmatter is not closed (no terminating ---)"])

    def test_missing_frontmatter_entirely_is_unaffected(self, tmp_path):
        # The un-fenced case must still fall through to the ordinary
        # missing-field notes — only a file that *opens* a fence and never
        # closes it gets the single-note short circuit.
        d = make_skill(tmp_path, "just a plain markdown body\n")
        score, notes = util.score_skill(d)
        assert score == 25
        assert "frontmatter missing `name`" in notes
        assert "frontmatter is not closed (no terminating ---)" not in notes


class TestAtomicWriteText:
    def test_writes_content(self, tmp_path):
        p = tmp_path / "f.txt"
        util.atomic_write_text(p, "hello")
        assert p.read_text(encoding="utf-8") == "hello"

    def test_overwrites_existing(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("old", encoding="utf-8")
        util.atomic_write_text(p, "new")
        assert p.read_text(encoding="utf-8") == "new"

    def test_creates_missing_parents(self, tmp_path):
        p = tmp_path / "a" / "b" / "f.txt"
        util.atomic_write_text(p, "deep")
        assert p.read_text(encoding="utf-8") == "deep"

    def test_leaves_no_temp_files(self, tmp_path):
        util.atomic_write_text(tmp_path / "f.txt", "x")
        leftovers = [q.name for q in tmp_path.iterdir() if q.name != "f.txt"]
        assert leftovers == []

    def test_honours_encoding(self, tmp_path):
        p = tmp_path / "f.txt"
        util.atomic_write_text(p, "café", encoding="utf-8")
        assert p.read_bytes() == "café".encode()

    def test_replace_failure_cleans_temp_and_raises(self, tmp_path, monkeypatch):
        import os as _os
        p = tmp_path / "f.txt"
        p.write_text("original", encoding="utf-8")

        def boom(_src, _dst):
            raise OSError("replace failed")

        monkeypatch.setattr(_os, "replace", boom)
        with pytest.raises(OSError, match="replace failed"):
            util.atomic_write_text(p, "new")
        # original untouched, and no temp turd left behind
        assert p.read_text(encoding="utf-8") == "original"
        leftovers = [q.name for q in tmp_path.iterdir() if q.name != "f.txt"]
        assert leftovers == []


class TestTryLock:
    """A lock that silently fails open is worse than no lock at all, so both
    answers are pinned: who gets True, who gets False, and what is left behind."""

    def test_taken_lock_yields_true_and_cleans_up(self, tmp_path):
        lock = tmp_path / "x.lock"
        with util.try_lock(lock) as got:
            assert got is True
            assert lock.is_file()
        assert not lock.exists()

    def test_second_holder_is_refused_rather_than_queued(self, tmp_path):
        lock = tmp_path / "x.lock"
        with util.try_lock(lock) as first, util.try_lock(lock) as second:
            assert first is True
            assert second is False

    def test_the_loser_does_not_delete_the_winners_lock(self, tmp_path):
        # The nastiest failure mode: a refused caller cleaning up on its way
        # out would hand the lock to whoever asked next, while the holder is
        # still working.
        lock = tmp_path / "x.lock"
        with util.try_lock(lock):
            with util.try_lock(lock) as second:
                assert second is False
            assert lock.is_file()

    def test_lock_is_released_when_the_body_raises(self, tmp_path):
        lock = tmp_path / "x.lock"
        with pytest.raises(ValueError), util.try_lock(lock):
            raise ValueError("boom")
        assert not lock.exists()

    def test_stale_lock_is_stolen(self, tmp_path):
        import os as _os
        lock = tmp_path / "x.lock"
        lock.write_text("999999", encoding="utf-8")
        old = time.time() - 600
        _os.utime(lock, (old, old))
        with util.try_lock(lock, stale_after=300.0) as got:
            assert got is True          # the holder died; don't wedge forever

    def test_fresh_lock_is_not_stolen(self, tmp_path):
        lock = tmp_path / "x.lock"
        lock.write_text("999999", encoding="utf-8")
        with util.try_lock(lock, stale_after=300.0) as got:
            assert got is False
        assert lock.is_file()           # and it is left for its owner

    def test_a_vanished_lock_reads_as_free(self, tmp_path):
        assert util._lock_is_stale(tmp_path / "never-existed", 300.0) is True

    def test_unusable_path_refuses_instead_of_raising(self, tmp_path):
        # Failing to take a lock must never be worse than the race it guards.
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        with util.try_lock(blocker / "sub" / "x.lock") as got:
            assert got is False

    def test_the_holder_records_its_pid(self, tmp_path):
        import os as _os
        lock = tmp_path / "x.lock"
        with util.try_lock(lock):
            assert lock.read_text(encoding="utf-8") == str(_os.getpid())


class TestSafeComponent:
    """A catalog name becomes a path component, so it is attacker-controlled
    input on the way to an install path (a tap writes its own frontmatter)."""

    @pytest.mark.parametrize("name", [
        "plain", "with-dash", "with_underscore", "dotted.name", "v1.2.3", "A-Z_0-9",
    ])
    def test_accepts_ordinary_names(self, name):
        assert util.is_safe_component(name) is True
        # and passes them through byte-for-byte — slugify would mangle these
        assert util.safe_component(name) == name

    @pytest.mark.parametrize("name", [
        "../../../../.ssh/authorized_keys", "..", ".", "a/b", "a\\b", "with space",
        "", "lead/../esc", "/abs/path", "nul\x00byte", "tab\tname",
    ])
    def test_rejects_unsafe_names(self, name):
        assert util.is_safe_component(name) is False

    @pytest.mark.parametrize("name", [
        "../../../../.ssh/authorized_keys", "..", ".", "a/b", "/abs/path",
    ])
    def test_rewrites_unsafe_names_to_a_single_component(self, name):
        got = util.safe_component(name)
        assert util.is_safe_component(got), got
        assert "/" not in got and got not in {".", ".."}

    def test_traversal_slug_keeps_no_parent_segments(self):
        assert util.safe_component("../../../../.ssh/authorized_keys") == "ssh-authorized-keys"

    def test_dot_names_do_not_become_empty(self):
        # slugify("..") -> "skill" rather than "", which would rejoin as the
        # parent directory itself.
        assert util.safe_component("..") == "skill"
        assert util.safe_component(".") == "skill"


class TestPositiveInt:
    """`util.positive_int` — the argparse type behind every -n/--limit flag."""

    def test_accepts_one_and_above_exactly(self):
        assert util.positive_int("1") == 1
        assert util.positive_int("20") == 20

    def test_zero_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.positive_int("0")
        assert str(exc.value) == "must be >= 1"

    def test_negative_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.positive_int("-1")
        assert str(exc.value) == "must be >= 1"

    def test_non_numeric_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.positive_int("abc")
        assert str(exc.value) == "invalid int value: 'abc'"


class TestRemoveItems:
    """`util.remove_items` — the counter `boost clean` reports and journals.

    A caller must be able to trust ``removed_count`` as "actually gone", not
    "attempted": the bug this replaces counted every candidate as removed
    regardless of whether the unlink/rmtree call raised.
    """

    def test_all_succeed(self, tmp_path):
        a = tmp_path / "a"
        a.write_bytes(b"1234")
        b = tmp_path / "b"
        b.write_bytes(b"123")
        items = [(a, "file", 4), (b, "file", 3)]

        removed, freed, failures = util.remove_items(items)

        assert removed == 2
        assert freed == 7
        assert failures == []
        assert not a.exists() and not b.exists()

    def test_a_failure_is_not_counted_removed_and_freed_excludes_it(self, tmp_path, monkeypatch):
        keep = tmp_path / "locked"
        keep.write_bytes(b"12345")
        gone = tmp_path / "gone"
        gone.write_bytes(b"12")
        real_unlink = Path.unlink

        def _unlink(self, *a, **k):
            if self == keep:
                raise OSError(13, "Permission denied")
            return real_unlink(self, *a, **k)

        monkeypatch.setattr(Path, "unlink", _unlink)
        items = [(keep, "file", 5), (gone, "file", 2)]

        removed, freed, failures = util.remove_items(items)

        assert removed == 1
        assert freed == 2                    # the failed item's bytes are not freed
        assert len(failures) == 1
        assert failures[0][0] == keep
        assert "Permission denied" in failures[0][1]
        assert keep.exists()                 # the failure left it in place
        assert not gone.exists()

    def test_a_directory_is_removed_via_rmtree(self, tmp_path):
        d = tmp_path / "adir"
        d.mkdir()
        (d / "f").write_text("x", encoding="utf-8")

        removed, freed, failures = util.remove_items([(d, "old snapshot", 1)])

        assert removed == 1
        assert freed == 1
        assert failures == []
        assert not d.exists()

    def test_a_path_that_is_neither_file_nor_dir_is_skipped_not_counted(self, tmp_path):
        missing = tmp_path / "never-existed"

        removed, freed, failures = util.remove_items([(missing, "ghost", 9)])

        assert removed == 0
        assert freed == 0
        assert failures == []

    def test_empty_input_reports_nothing(self):
        assert util.remove_items([]) == (0, 0, [])
