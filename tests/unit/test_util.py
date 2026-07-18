"""Unit tests: boost_cli/core/util.py — time, hashing, versions, scoring."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest

from boost_cli.core import util

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def iso_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(seconds=seconds)).strftime(ISO_FMT)


class TestNowIso:
    def test_format(self):
        s = util.now_iso()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s)
        # parses back and is (approximately) now, in UTC
        parsed = datetime.strptime(s, ISO_FMT).replace(tzinfo=timezone.utc)
        delta = abs((datetime.now(timezone.utc) - parsed).total_seconds())
        assert delta < 5


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

    def test_100_days_is_absolute_date(self):
        then = datetime.now(timezone.utc) - timedelta(days=100)
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
            p.write_text(content)

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
        (tmp_path / "x.md").write_text("two")
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
    (d / "SKILL.md").write_text(text)
    for name, content in (extra_files or {}).items():
        (d / name).write_text(content)
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


class TestAtomicWriteText:
    def test_writes_content(self, tmp_path):
        p = tmp_path / "f.txt"
        util.atomic_write_text(p, "hello")
        assert p.read_text() == "hello"

    def test_overwrites_existing(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("old")
        util.atomic_write_text(p, "new")
        assert p.read_text() == "new"

    def test_creates_missing_parents(self, tmp_path):
        p = tmp_path / "a" / "b" / "f.txt"
        util.atomic_write_text(p, "deep")
        assert p.read_text() == "deep"

    def test_leaves_no_temp_files(self, tmp_path):
        util.atomic_write_text(tmp_path / "f.txt", "x")
        leftovers = [q.name for q in tmp_path.iterdir() if q.name != "f.txt"]
        assert leftovers == []

    def test_honours_encoding(self, tmp_path):
        p = tmp_path / "f.txt"
        util.atomic_write_text(p, "café", encoding="utf-8")
        assert p.read_bytes() == "café".encode("utf-8")

    def test_replace_failure_cleans_temp_and_raises(self, tmp_path, monkeypatch):
        import os as _os
        p = tmp_path / "f.txt"
        p.write_text("original")

        def boom(_src, _dst):
            raise OSError("replace failed")

        monkeypatch.setattr(_os, "replace", boom)
        with pytest.raises(OSError, match="replace failed"):
            util.atomic_write_text(p, "new")
        # original untouched, and no temp turd left behind
        assert p.read_text() == "original"
        leftovers = [q.name for q in tmp_path.iterdir() if q.name != "f.txt"]
        assert leftovers == []
