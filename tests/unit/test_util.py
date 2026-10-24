# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/util.py — time, hashing, versions, scoring."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import stat
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from boost_cli.core import util
from boost_cli.errors import BoostError

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

    def test_a_stamp_seconds_ahead_is_just_now(self):
        # Clock skew between machines sharing the feed: floored, a negative
        # age read "1s ago" however far ahead the stamp was.
        assert util.rel_time(iso_ago(-1)) == "just now"
        assert util.rel_time(iso_ago(-59)) == "just now"

    def test_a_stamp_a_minute_or_more_ahead_is_in_the_future(self):
        assert util.rel_time(iso_ago(-60)) == "in the future"
        assert util.rel_time(iso_ago(-2 * 86400)) == "in the future"

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


class TestIsoDate:
    def test_matches_git_date_short_format(self):
        # git's `--date=short` on the same instant: no time-of-day, no "ago"
        assert util.iso_date("2026-07-16T01:00:00Z") == "2026-07-16"

    def test_recent_instant_still_returns_a_date_not_ago(self):
        # the whole point: `_tap_updated`'s two branches must agree on shape
        # even when the cache was generated seconds ago — rel_time would say
        # "1s ago" here, iso_date must not.
        now = datetime.now(UTC)
        assert util.iso_date(now.strftime(ISO_FMT)) == now.strftime("%Y-%m-%d")

    def test_far_past_instant(self):
        then = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)
        assert util.iso_date(then.strftime(ISO_FMT)) == "2020-01-02"

    def test_junk_passthrough(self):
        assert util.iso_date("not-a-date") == "not-a-date"

    def test_empty_becomes_question_mark(self):
        assert util.iso_date("") == "?"

    def test_none_becomes_question_mark(self):
        assert util.iso_date(None) == "?"


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

    def test_nfc_and_nfd_spellings_give_one_slug(self):
        # Precomposed é (NFC) was dropped -> `caf`, while e + U+0301 (NFD,
        # what a macOS paste often produces) kept its e -> `cafe`: one typed
        # name saved a profile under one file and looked it up under another.
        nfc, nfd = "caf\u00e9", "cafe\u0301"
        assert util.slugify(nfc) == util.slugify(nfd) == "cafe"
        assert util.slugify("Cr\u00e8me Br\u00fbl\u00e9e") == "creme-brulee"

    def test_compatibility_forms_fold_to_ascii(self):
        assert util.slugify("\ufb01le \u2460") == "file-1"

    def test_letters_with_no_ascii_fold_still_fall_back(self):
        assert util.slugify("\u540d\u524d") == "skill"


class TestResolveSlug:
    """The shared helper for a user-typed name: slugify, refuse when there is
    nothing to slug, and never swap the name for another without saying so."""

    def test_already_a_slug_is_returned_unchanged_and_silent(self, capsys):
        assert util.resolve_slug("tdd-workflow-3") == "tdd-workflow-3"
        assert capsys.readouterr() == ("", "")

    def test_differing_slug_is_noted_on_stderr_not_stdout(self, capsys):
        # stdout may be carrying --json; the note there broke `boost profile
        # save "My Team" --json`, whose output no longer parsed.
        assert util.resolve_slug("My Great Skill") == "my-great-skill"
        cap = capsys.readouterr()
        assert cap.out == ""
        assert cap.err == "  using name 'my-great-skill' (from 'My Great Skill')\n"

    def test_what_names_the_field_in_the_note_and_the_error(self, capsys):
        util.resolve_slug("Bad Name!!", what="profile name")
        assert "profile name" in capsys.readouterr().err
        with pytest.raises(BoostError) as exc:
            util.resolve_slug("!!!", what="profile name")
        assert "profile name" in exc.value.message

    def test_a_slug_longer_than_one_path_component_is_refused(self):
        # The slug becomes a directory or file name; past 255 bytes the OS
        # raises ENAMETOOLONG from the first `exists()` that touches it.
        with pytest.raises(BoostError) as exc:
            util.resolve_slug("a" * 256, what="skill name")
        assert "skill name is too long (256 bytes, limit 255)" in exc.value.message

    def test_a_slug_at_the_limit_is_accepted(self):
        assert util.resolve_slug("a" * 255) == "a" * 255

    def test_the_limit_is_on_the_slug_not_the_raw_input(self):
        # Punctuation slugify drops does not count against the limit.
        assert util.resolve_slug("a" * 255 + "!" * 10) == "a" * 255

    def test_empty_raises_instead_of_falling_back_to_skill(self):
        with pytest.raises(BoostError) as exc:
            util.resolve_slug("")
        assert exc.value.message == "name has no letters or digits: ''"

    def test_nfd_input_is_noted_with_the_folded_slug(self, capsys):
        assert util.resolve_slug("cafe\u0301", what="profile name") == "cafe"
        assert util.resolve_slug("caf\u00e9", what="profile name") == "cafe"
        assert capsys.readouterr().err.count("using profile name 'cafe'") == 2

    def test_non_ascii_letters_are_not_called_no_letters(self):
        # `名前` is all letters; "has no letters or digits" told the user
        # their input was empty.
        with pytest.raises(BoostError) as exc:
            util.resolve_slug("\u540d\u524d", what="skill name")
        assert exc.value.message == "skill name needs ASCII letters or digits: " \
            "'\u540d\u524d'"
        assert exc.value.hint == "a name becomes a file name made of a-z, 0-9 and '-'"

    def test_punctuation_only_raises_instead_of_falling_back_to_skill(self):
        # Unlike slugify("!!!") == "skill", a user-typed name with nothing to
        # slug is a mistake to report, not a name to invent.
        with pytest.raises(BoostError):
            util.resolve_slug("!!!")

    def test_literal_skill_is_not_mistaken_for_the_fallback(self):
        # "skill" slugifies to itself, so it must not raise even though it is
        # the same string slugify() falls back to for punctuation-only input.
        assert util.resolve_slug("skill") == "skill"


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


class TestLineEndingBlindHash:
    """A CRLF checkout (core.autocrlf) of a copy is not an edit to it."""

    @staticmethod
    def _tree(root, data: bytes):
        root.mkdir()
        (root / "SKILL.md").write_bytes(data)
        return root

    def test_hashed_bytes_folds_crlf_in_text_only(self):
        assert util.hashed_bytes(b"a\r\nb\r\n") == b"a\nb\n"
        assert util.hashed_bytes(b"a\nb") == b"a\nb"
        # A lone CR is not a line-ending conversion git makes.
        assert util.hashed_bytes(b"a\rb") == b"a\rb"
        assert util.hashed_bytes(b"\0a\r\n") == b"\0a\r\n"

    def test_the_binary_sniff_window_is_exact(self):
        assert util.BINARY_SNIFF == 8000
        inside = b"x" * (util.BINARY_SNIFF - 1) + b"\0\r\n"
        past = b"x" * util.BINARY_SNIFF + b"\0\r\n"
        assert util.hashed_bytes(inside) == inside
        assert util.hashed_bytes(past) == past[:-2] + b"\n"

    def test_updatediff_sniffs_the_same_window(self):
        from boost_cli.core import updatediff
        assert updatediff._SNIFF == util.BINARY_SNIFF

    def test_crlf_and_lf_trees_hash_alike(self, tmp_path):
        lf = self._tree(tmp_path / "lf", b"---\nname: x\n---\nbody\n")
        crlf = self._tree(tmp_path / "crlf", b"---\r\nname: x\r\n---\r\nbody\r\n")
        assert util.sha256_dir(crlf) == util.sha256_dir(lf)
        assert util.sha256_dir(crlf, raw=True) != util.sha256_dir(lf, raw=True)

    def test_an_lf_tree_hashes_as_the_raw_bytes_did(self, tmp_path):
        # Why most existing lock rows need nothing: no CRLF, same digest.
        lf = self._tree(tmp_path / "lf", b"body\n")
        want = hashlib.sha256(b"SKILL.md\0body\n\0").hexdigest()
        assert util.sha256_dir(lf) == want
        assert util.sha256_dir(lf, raw=True) == want

    def test_raw_hashes_crlf_as_written(self, tmp_path):
        crlf = self._tree(tmp_path / "c", b"body\r\n")
        assert util.sha256_dir(crlf, raw=True) == hashlib.sha256(
            b"SKILL.md\0body\r\n\0").hexdigest()
        assert util.sha256_dir(crlf) == hashlib.sha256(
            b"SKILL.md\0body\n\0").hexdigest()

    def test_a_binary_file_keeps_its_bytes(self, tmp_path):
        a = self._tree(tmp_path / "a", b"\0bin\r\n")
        b = self._tree(tmp_path / "b", b"\0bin\n")
        assert util.sha256_dir(a) != util.sha256_dir(b)

    def test_matches_a_normalised_or_a_raw_digest(self, tmp_path):
        crlf = self._tree(tmp_path / "c", b"body\r\n")
        assert util.sha256_matches(crlf, util.sha256_dir(crlf)) is True
        # A row recorded from these CRLF bytes before the hash folded them.
        assert util.sha256_matches(crlf, util.sha256_dir(crlf, raw=True)) is True
        lf = self._tree(tmp_path / "l", b"body\n")
        assert util.sha256_matches(crlf, util.sha256_dir(lf)) is True

    def test_matches_rejects_an_edit_and_an_empty_digest(self, tmp_path):
        a = self._tree(tmp_path / "a", b"body\r\n")
        recorded = util.sha256_dir(a)
        (a / "SKILL.md").write_bytes(b"bodY\r\n")
        assert util.sha256_matches(a, recorded) is False
        assert util.sha256_matches(a, "") is False
        assert util.sha256_matches(a, None) is False


class TestDirSize:
    def test_empty_dir_is_zero(self, tmp_path):
        assert util.dir_size(tmp_path) == 0

    def test_sums_nested_files(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"x" * 10)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_bytes(b"y" * 32)
        assert util.dir_size(tmp_path) == 42

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="symlinks need a privilege on Windows")
    def test_a_symlink_is_not_its_target(self, tmp_path):
        # du's answer: a link to a file (inside the tree or outside it) is
        # not that file's bytes again. `compact` measured freed space as
        # before-minus-after and counted a link's target on one side only.
        outside = tmp_path / "outside.bin"
        outside.write_bytes(b"o" * 1000)
        tree = tmp_path / "tree"
        tree.mkdir()
        (tree / "real.txt").write_bytes(b"r" * 10)
        (tree / "inner").symlink_to("real.txt")
        (tree / "outer").symlink_to(outside)
        (tree / "dangling").symlink_to("gone.txt")
        assert util.dir_size(tree) == 10



@pytest.mark.skipif(sys.platform == "win32",
                    reason="symlinks need a privilege on Windows")
class TestCopiedFiles:
    """What install will copy — checked against install's own copytree."""

    @staticmethod
    def _tree(tmp_path):
        shared = tmp_path / "shared"
        (shared / "docs").mkdir(parents=True)
        (shared / "docs" / "y.md").write_bytes(b"y" * 800)
        (shared / "b.md").write_bytes(b"b" * 300)
        skill = tmp_path / "skill"
        (skill / "real").mkdir(parents=True)
        (skill / "real" / "x.md").write_bytes(b"x" * 600)
        (skill / "SKILL.md").symlink_to(shared / "b.md")      # file link
        (skill / "docs").symlink_to(shared / "docs")           # dir link out
        (skill / "alias").symlink_to("real")                   # dir link in
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__" / "x.pyc").write_bytes(b"c" * 900)
        (skill / "real" / ".DS_Store").write_bytes(b"d" * 400)  # IGNORED, deep
        return skill

    def test_matches_what_install_copies(self, tmp_path):
        import shutil
        skill = self._tree(tmp_path)
        dest = tmp_path / "copy"
        shutil.copytree(skill, dest,
                        ignore=shutil.ignore_patterns(*util.IGNORED))
        want = {p.relative_to(dest): p.stat().st_size
                for p in dest.rglob("*") if p.is_file()}
        got = {p.relative_to(skill): p.stat().st_size
               for p in util.copied_files(skill)}
        assert got == want
        assert sum(got.values()) == 300 + 800 + 600 + 600

    def test_a_dangling_link_copies_nothing(self, tmp_path):
        (tmp_path / "SKILL.md").write_bytes(b"s" * 5)
        (tmp_path / "gone").symlink_to("nowhere.txt")
        assert util.copied_files(tmp_path) == [tmp_path / "SKILL.md"]

    def test_a_link_cycle_is_walked_once(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "f.md").write_bytes(b"f")
        (tmp_path / "a" / "loop").symlink_to("..")
        files = util.copied_files(tmp_path)
        assert [p.name for p in files] == ["f.md"]


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


class TestLintErrors:
    def test_missing_skill_md(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert util.lint_errors(d) == ["missing SKILL.md"]

    def test_clean_skill_has_no_errors(self, tmp_path):
        d = make_skill(tmp_path, full_text())
        assert util.lint_errors(d) == []

    def test_missing_name_and_description(self, tmp_path):
        d = make_skill(tmp_path, "just a plain markdown body\n")
        errors = util.lint_errors(d)
        assert "missing required field: name" in errors
        assert "missing required field: description" in errors

    def test_missing_name_only(self, tmp_path):
        d = make_skill(tmp_path, "---\ndescription: has one\n---\nbody\n")
        assert util.lint_errors(d) == ["missing required field: name"]

    def test_unclosed_frontmatter_is_one_error(self, tmp_path):
        d = make_skill(tmp_path, "---\nname: x\nno closing fence\n")
        assert util.lint_errors(d) == ["frontmatter is not closed (no terminating ---)"]

    def test_missing_frontmatter_entirely_reports_both_fields(self, tmp_path):
        # No `---` at all parses as an empty frontmatter dict rather than the
        # unclosed-fence short circuit — both required fields read absent.
        d = make_skill(tmp_path, "no frontmatter fence here at all\n")
        assert util.lint_errors(d) == [
            "missing required field: name", "missing required field: description"]


class TestLintFailed:
    def test_high_score_but_missing_description_still_fails(self, tmp_path):
        # The bug this closes: `boost test` used to trust the score alone, so
        # a skill scoring 85 with no `description` passed `test` while
        # `boost lint` failed it outright.
        d = make_skill(tmp_path, full_text(desc=""))
        score, _notes = util.score_skill(d)
        assert score >= 40
        assert util.lint_failed(d, score, min_score=40)

    def test_low_score_with_no_errors_fails_on_score_alone(self, tmp_path):
        # name and description both present (no hard errors), but a huge
        # frontmatter field trips the oversized-file penalty hard enough to
        # drop the score under the floor on its own.
        text = ("---\nname: test-skill\ndescription: %s\npadding: %s\n---\n\nhi\n"
                % ("d" * 10, "x" * 49_000))
        d = make_skill(tmp_path, text)
        score, _notes = util.score_skill(d)
        assert score < 40
        assert util.lint_errors(d) == []
        assert util.lint_failed(d, score, min_score=40)

    def test_clean_high_score_passes(self, tmp_path):
        d = make_skill(tmp_path, full_text())
        score, _notes = util.score_skill(d)
        assert not util.lint_failed(d, score, min_score=40)

    def test_min_score_shifts_the_floor(self, tmp_path):
        text = ("---\nname: test-skill\ndescription: %s\npadding: %s\n---\n\nhi\n"
                % ("d" * 10, "x" * 49_000))
        d = make_skill(tmp_path, text)
        score, _notes = util.score_skill(d)
        assert util.lint_failed(d, score, min_score=40)
        assert not util.lint_failed(d, score, min_score=0)


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

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="a 255-byte name under tmp_path passes MAX_PATH")
    def test_temp_name_fits_the_component_limit(self, tmp_path, monkeypatch):
        # A legal 255-byte target used to get a 269-byte temp name and fail
        # ENAMETOOLONG; the cut must not split a multi-byte character either.
        import tempfile
        seen = []
        real = tempfile.mkstemp

        def spy(*a, **k):
            fd, tmp = real(*a, **k)
            seen.append(Path(tmp).name.encode("utf-8"))
            return fd, tmp
        monkeypatch.setattr(tempfile, "mkstemp", spy)
        short, ascii_, wide = "a" * 200, "b" * 255, "\u00e9" * 127 + "x"
        for name in (short, ascii_, wide):
            util.atomic_write_text(tmp_path / name, name)
            assert (tmp_path / name).read_text(encoding="utf-8") == name
        # The temp is named for boost, not for the target, so its length does
        # not grow with the name beside it.
        assert len(seen) == 3
        assert len(set(map(len, seen))) == 1
        for tmp in seen:
            assert tmp.startswith(util.TEMP_PREFIX.encode())
            assert tmp.endswith(b".tmp")
            assert len(tmp) < 32

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


class TestNonemptyStr:
    """`util.nonempty_str` — the argparse type behind every NAME/path flag."""

    def test_a_real_value_round_trips_unchanged(self):
        assert util.nonempty_str("brainstorming") == "brainstorming"
        # Inner and edge whitespace is the caller's business, not stripped.
        assert util.nonempty_str(" a b ") == " a b "

    @pytest.mark.parametrize("value", ["", " ", "\t\n"])
    def test_empty_or_blank_rejected_with_exact_message(self, value):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.nonempty_str(value)
        assert str(exc.value) == "must not be empty"


class TestScoreInt:
    """`util.score_int` — the argparse type behind `lint --min` (0-100)."""

    def test_accepts_the_full_0_to_100_range(self):
        assert util.score_int("0") == 0
        assert util.score_int("40") == 40
        assert util.score_int("100") == 100

    def test_negative_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.score_int("-1")
        assert str(exc.value) == "must be between 0 and 100"

    def test_above_100_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.score_int("500")
        assert str(exc.value) == "must be between 0 and 100"

    def test_non_numeric_rejected_with_exact_message(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            util.score_int("abc")
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


# The retry hook only runs once an operation has already FAILED, so every test
# here has to engineer a real failure first. A directory at 0o500 is the lever:
# it permits lookup and refuses unlink, which is precisely the read-only case
# the hook exists for. Root ignores the mode, and Windows has neither these
# semantics nor unprivileged symlinks, so both are skipped rather than asserted
# vacuously.
requires_posix_modes = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission semantics")
requires_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the 0o500 that makes the operation fail")


@pytest.fixture
def sealed(tmp_path):
    """Yield a callable that seals a directory at 0o500, unsealing at teardown.

    The unseal has to happen even when the test fails, or pytest's own tmp_path
    reaper inherits a tree it cannot delete and poisons a later run.
    """
    sealed_dirs = []

    def seal(d):
        d.chmod(0o500)
        sealed_dirs.append(d)
        return d

    yield seal
    for d in sealed_dirs:
        with contextlib.suppress(OSError):
            d.chmod(0o700)


@requires_posix_modes
@requires_unprivileged
class TestRmtreeRetryHook:
    """`util.rmtree`'s read-only retry must not chmod through a symlink.

    `os.chmod` follows links, and the hook is handed the path that failed, so
    the unguarded version changed the mode of whatever the link pointed at —
    a file outside the tree being deleted. Nothing covered these two lines
    before; the bug was found by reading, not by a failing test.
    """

    def test_a_link_in_the_tree_does_not_change_its_target_s_mode(
            self, tmp_path, sealed):
        victim = tmp_path / "victim.txt"
        victim.write_text("do not touch\n", encoding="utf-8")
        victim.chmod(0o400)
        tree = tmp_path / "tree"
        tree.mkdir()
        (tree / "lnk").symlink_to(victim)
        sealed(tree)

        # The delete cannot succeed — that is what summons the hook at all.
        with pytest.raises(OSError):
            util.rmtree(tree)

        assert stat.S_IMODE(victim.stat().st_mode) == 0o400
        assert victim.read_text(encoding="utf-8") == "do not touch\n"

    def test_a_real_read_only_file_is_still_chmodded(self, tmp_path, sealed):
        """The guard must be `islink`, not "give up on anything that fails".

        This is the case the hook was written for, and it is what keeps the
        fix from being "stop retrying": the chmod still happens, and it is
        observable because chmod needs ownership plus search on the parent,
        not write on it. Called with no ``root``, so the sealed parent stays
        sealed and the retry fails where the chmod can be read back.
        """
        stubborn = tmp_path / "tree2"
        stubborn.mkdir()
        target = stubborn / "ro.txt"
        target.write_text("x", encoding="utf-8")
        target.chmod(0o400)
        sealed(stubborn)
        planted = PermissionError(13, "planted")

        with pytest.raises(PermissionError) as caught:
            util._clear_readonly_and_retry(os.unlink, str(target), planted)

        assert caught.value is not planted      # the retry's own failure
        assert stat.S_IMODE(stubborn.stat().st_mode) == 0o500
        # The write bit is ORed in, not the whole mode replaced by it.
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

    def test_a_read_only_directory_inside_the_tree_is_unlocked(
            self, tmp_path, sealed):
        """A skill copied from a read-only package: a 0o555 ``assets/``.

        Unlinking is gated by the parent's write bit, so chmod-ing the file
        alone retried into the same refusal and `boost uninstall` crashed
        rc 70 with the lock row kept. The parent is inside the tree, so it
        is the delete's to unlock.
        """
        tree = tmp_path / "skill"
        sub = tree / "assets"
        sub.mkdir(parents=True)
        (sub / "a.txt").write_text("x", encoding="utf-8")
        (tree / "SKILL.md").write_text("x", encoding="utf-8")
        sealed(sub)
        sealed(tree)

        util.rmtree(tree)

        assert not tree.exists()

    def test_the_root_s_own_parent_is_never_unlocked(self, tmp_path, sealed):
        """The directory holding the tree is outside it: not this delete's.

        A read-only skill store is a refusal `doctor` reports; unlocking it
        to finish one uninstall would quietly undo the user's own chmod.
        """
        holder = tmp_path / "store"
        tree = holder / "skill"
        tree.mkdir(parents=True)
        (tree / "f.txt").write_text("x", encoding="utf-8")
        sealed(holder)

        with pytest.raises(PermissionError):
            util.rmtree(tree)

        assert stat.S_IMODE(holder.stat().st_mode) == 0o500

    def test_a_parent_that_is_a_link_is_never_chmodded(self, tmp_path, sealed):
        """`os.chmod` follows links, so a linked parent's target would change."""
        real = tmp_path / "real"
        real.mkdir()
        f = real / "f.txt"
        f.write_text("x", encoding="utf-8")
        sealed(real)
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        planted = PermissionError(13, "planted")

        with pytest.raises(PermissionError):
            util._clear_readonly_and_retry(
                os.unlink, str(link / "f.txt"), planted, root=str(tmp_path))

        assert stat.S_IMODE(real.stat().st_mode) == 0o500
        assert f.exists()

    def test_inside_tree_is_lexical_and_bounded(self):
        assert util._inside_tree("/a/b", "/a/b") is True
        assert util._inside_tree("/a/b/c", "/a/b/") is True
        assert util._inside_tree("/a/bc", "/a/b") is False
        assert util._inside_tree("/a", "/a/b") is False

    def test_a_failed_retry_keeps_a_directory_listable(self, tmp_path, sealed):
        """A dir under a read-only parent keeps its read and search bits.

        Its contents go and its own ``rmdir`` fails on the parent. Setting the
        mode to exactly ``S_IWRITE`` left it ``d-w-------``, and every later
        walk of the store (`boost snapshot save`) crashed on it.
        """
        parent = tmp_path / "store"
        child = parent / "skill"
        child.mkdir(parents=True)
        (child / "SKILL.md").write_text("x", encoding="utf-8")
        child.chmod(0o755)
        sealed(parent)

        with pytest.raises(OSError):
            util.rmtree(child)

        assert stat.S_IMODE(child.stat().st_mode) == 0o755
        assert list(child.iterdir()) == []

    def test_a_failed_listing_is_raised_not_retried(self, tmp_path):
        """Only a removal is retried.

        `shutil.rmtree` reports a dir it could not open or list through the
        same hook, and calling `os.open(path)` again raised TypeError (it
        needs flags), which no caller catches: `boost sync --prune` exited 70
        halfway through a delete.
        """
        d = tmp_path / "d"
        d.mkdir()
        before = stat.S_IMODE(d.stat().st_mode)
        planted = PermissionError(13, "planted")
        for func in (os.open, os.scandir, os.lstat):
            with pytest.raises(PermissionError) as caught:
                util._clear_readonly_and_retry(func, str(d), planted)
            assert caught.value is planted
        assert stat.S_IMODE(d.stat().st_mode) == before

    def test_rmtree_of_a_symlink_refuses_instead_of_reporting_success(
            self, tmp_path):
        """The silent variant, and the reason this is more than a mode change.

        `shutil.rmtree` refuses a symlink argument by routing it through the
        error hook with `func=os.path.islink`. The unguarded hook chmodded the
        target through the link and then called `os.path.islink(path)`, which
        answers True without raising — so the hook returned and `rmtree`
        returned, having deleted nothing, while the caller was told the tree
        was gone. No 0o500 is needed here: the refusal is unconditional.
        """
        real = tmp_path / "real"
        real.mkdir()
        (real / "keep.txt").write_text("keep", encoding="utf-8")
        before = stat.S_IMODE(real.stat().st_mode)
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)

        with pytest.raises(OSError):
            util.rmtree(link)

        assert stat.S_IMODE(real.stat().st_mode) == before
        assert (real / "keep.txt").read_text(encoding="utf-8") == "keep"
        assert link.is_symlink()

    def test_the_hook_reraises_the_exception_it_was_given(self, tmp_path):
        """Not a fresh one: the caller's traceback must name the real failure.

        Called directly, because reaching a chosen exception type through
        `shutil.rmtree` would be testing shutil's dispatch instead.
        """
        link = tmp_path / "l"
        link.symlink_to(tmp_path / "nowhere")
        planted = PermissionError(13, "planted")

        with pytest.raises(PermissionError) as caught:
            util._clear_readonly_and_retry(os.unlink, str(link), planted)

        assert caught.value is planted
        assert link.is_symlink()   # and it did not delete it on the way out



@requires_posix_modes
class TestRemovePath:
    """One removal that reads the link rather than through it.

    Most of these are a mutant the naive `if path.is_dir(): rmtree(path)`
    guard lets live, and together they pin the two directions it is wrong in:
    a link answers for its target, so a dangling one looks absent and a link
    to a directory looks like a directory.
    """

    def test_a_real_directory_is_removed_with_its_contents(self, tmp_path):
        d = tmp_path / "tree"
        (d / "sub").mkdir(parents=True)
        (d / "sub" / "f.txt").write_text("x", encoding="utf-8")

        assert util.remove_path(d) is True
        assert not d.exists()

    def test_a_regular_file_is_removed(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("x", encoding="utf-8")

        assert util.remove_path(f) is True
        assert not f.exists()

    def test_a_dangling_symlink_is_unlinked_rather_than_skipped(self, tmp_path):
        """`exists()` and `is_dir()` both answer False, so the old guard
        skipped it — and the next writer to that path then failed with
        `FileExistsError` for something that "does not exist"."""
        link = tmp_path / "gone"
        link.symlink_to(tmp_path / "nowhere")
        assert not link.exists()          # the reading that made it invisible

        assert util.remove_path(link) is True
        assert not link.is_symlink()

    def test_a_symlink_to_a_directory_goes_without_its_target(self, tmp_path):
        """`is_dir()` follows the link, so the old guard handed `rmtree` a
        symlink — which refuses one as its argument and raises."""
        real = tmp_path / "real"
        real.mkdir()
        (real / "keep.txt").write_text("keep", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        assert link.is_dir()              # the reading that sent it to rmtree

        assert util.remove_path(link) is True
        assert not link.is_symlink()
        assert real.is_dir()
        assert (real / "keep.txt").read_text(encoding="utf-8") == "keep"

    def test_a_symlink_to_a_file_goes_without_its_target(self, tmp_path):
        real = tmp_path / "real.txt"
        real.write_text("keep", encoding="utf-8")
        link = tmp_path / "link.txt"
        link.symlink_to(real)

        assert util.remove_path(link) is True
        assert not link.is_symlink()
        assert real.read_text(encoding="utf-8") == "keep"

    def test_a_path_that_is_not_there_returns_false(self, tmp_path):
        """False, not an exception: callers use it to mean "nothing to undo"."""
        assert util.remove_path(tmp_path / "never") is False

    def test_a_string_path_is_accepted(self, tmp_path):
        """Callers pass `Path`, but the coercion is what makes that a choice."""
        d = tmp_path / "tree"
        d.mkdir()

        assert util.remove_path(str(d)) is True
        assert not d.exists()

    @requires_unprivileged
    def test_an_oserror_propagates(self, tmp_path, sealed):
        """It raises like the call it wraps; callers that must not fail catch."""
        parent = tmp_path / "sealed"
        parent.mkdir()
        victim = parent / "f.txt"
        victim.write_text("x", encoding="utf-8")
        sealed(parent)

        with pytest.raises(OSError):
            util.remove_path(victim)


@requires_posix_modes
class TestRemovePathRefusesTheWorkingDirectory:
    """`Path("")` is `Path(".")`, and `"."` is a directory.

    The normalisation happens in the constructor, so the empty string cannot
    be told from an explicit `"."` by the time the function runs — refusing
    the value they share is the only guard available. No caller can currently
    produce one, but this is now the single place every guarded delete in the
    codebase goes through and every real caller names a child.
    """

    @pytest.mark.parametrize("arg", ["", ".", Path(""), Path("."), Path()])
    def test_a_path_meaning_here_raises_rather_than_emptying_the_cwd(
            self, arg, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "keep.txt").write_text("mine", encoding="utf-8")

        with pytest.raises(ValueError) as e:
            util.remove_path(arg)

        assert "working directory" in str(e.value)
        assert (tmp_path / "keep.txt").read_text(encoding="utf-8") == "mine"

    def test_a_relative_path_naming_a_child_still_works(
            self, tmp_path, monkeypatch):
        # The guard is about "here", not about refusing relative paths.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "f.txt").write_text("x", encoding="utf-8")

        assert util.remove_path("sub") is True

        assert not (tmp_path / "sub").exists()

    def test_the_cwd_named_absolutely_is_not_refused(
            self, tmp_path, monkeypatch):
        # `Path(tmp_path)` is not `Path(".")`, so an absolute path that
        # happens to be the cwd is a caller saying what it means. Pins that
        # the guard is a literal comparison and not a resolved one — making
        # it resolved would cost a syscall on every delete boost does.
        sub = tmp_path / "sub"
        sub.mkdir()
        monkeypatch.chdir(sub)

        assert util.remove_path(sub) is True

        assert not sub.exists()


class TestRemoveItemsUsesRemovePath:
    """`remove_items` kept its contract when its body became one call."""

    def test_a_link_a_file_and_a_tree_all_count_as_removed(self, tmp_path):
        d = tmp_path / "tree"
        d.mkdir()
        (d / "f").write_text("x", encoding="utf-8")
        f = tmp_path / "file.txt"
        f.write_text("yy", encoding="utf-8")
        link = tmp_path / "link"
        link.symlink_to(tmp_path / "nowhere")

        removed, freed, failures = util.remove_items(
            [(d, "dir", 10), (f, "file", 2), (link, "link", 1)])

        assert (removed, freed, failures) == (3, 13, [])
        assert not d.exists() and not f.exists() and not link.is_symlink()

    def test_a_missing_path_is_neither_removed_nor_a_failure(self, tmp_path):
        removed, freed, failures = util.remove_items(
            [(tmp_path / "never", "dir", 99)])

        assert (removed, freed, failures) == (0, 0, [])

    @requires_posix_modes
    @requires_unprivileged
    def test_a_failure_is_reported_and_the_rest_still_go(self, tmp_path, sealed):
        # `sealed` is a 0o500 parent, which is what makes the unlink fail.
        # Windows has no such semantics: the file deletes, both items are
        # removed, and the assertion reads (2, 12) — the test's premise gone
        # rather than the code wrong. The sibling tests in this class need no
        # mark; they turn on `remove_path` alone.
        parent = tmp_path / "sealed"
        parent.mkdir()
        stuck = parent / "f.txt"
        stuck.write_text("x", encoding="utf-8")
        sealed(parent)
        ok = tmp_path / "ok.txt"
        ok.write_text("y", encoding="utf-8")

        removed, freed, failures = util.remove_items(
            [(stuck, "file", 5), (ok, "file", 7)])

        assert (removed, freed) == (1, 7)
        assert [p for p, _ in failures] == [stuck]
        assert not ok.exists()


class TestCheckPathLength:
    """Every component of a path must fit the 255-byte ceiling, or the OS
    refuses to stat it and `Path.exists()` raises instead of answering."""

    def test_a_normal_path_is_returned_unchanged(self, tmp_path):
        p = tmp_path / "out.md"
        assert util.check_path_length(p) is p

    def test_the_last_component_is_checked(self, tmp_path):
        with pytest.raises(BoostError) as exc:
            util.check_path_length(tmp_path / ("a" * 256), what="output path")
        assert exc.value.message.startswith(
            "output path is too long (256 bytes, limit 255)")

    def test_a_parent_component_is_checked(self, tmp_path):
        with pytest.raises(BoostError):
            util.check_path_length(tmp_path / ("a" * 300) / "x.md")

    def test_exactly_255_bytes_is_fine(self, tmp_path):
        util.check_path_length(tmp_path / ("a" * 255))

    def test_bytes_not_characters_are_counted(self, tmp_path):
        # 128 two-byte characters are 256 bytes, which APFS and ext4 refuse.
        with pytest.raises(BoostError) as exc:
            util.check_path_length(tmp_path / ("é" * 128))
        assert "256 bytes" in exc.value.message

    def test_the_echo_is_exactly_forty_characters_and_an_ellipsis(self, tmp_path):
        # Any component over 255 bytes is at least 64 characters (UTF-8 is at
        # most 4 bytes a character), so the echo is always truncated; pin
        # where, so the cut cannot drift a character either way.
        with pytest.raises(BoostError) as exc:
            util.check_path_length(tmp_path / ("a" * 256))
        assert exc.value.message.endswith(": %r" % ("a" * 40 + "…"))

    def test_the_hint_names_the_filesystems_it_is_true_of(self, tmp_path):
        with pytest.raises(BoostError) as exc:
            util.check_path_length(tmp_path / ("a" * 256))
        assert exc.value.hint == ("APFS and ext4 refuse a file or directory "
                                  "name over 255 bytes")

    def test_the_message_does_not_echo_the_whole_component(self, tmp_path):
        with pytest.raises(BoostError) as exc:
            util.check_path_length(tmp_path / ("a" * 1000))
        assert len(exc.value.message) < 200


class TestWriteUnclaimed:
    """`write_unclaimed` never replaces a file it finds at the guessed name."""

    def test_writes_the_plain_name_when_free(self, tmp_path):
        dest = util.write_unclaimed(tmp_path, "evil", ".SKILL.md", "gen\n")
        assert dest == tmp_path / "evil.SKILL.md"
        assert dest.read_bytes() == b"gen\n"

    def test_an_existing_file_is_left_and_the_next_free_name_taken(self, tmp_path):
        (tmp_path / "evil.SKILL.md").write_bytes(b"precious notes\n")
        (tmp_path / "evil.1.SKILL.md").write_bytes(b"older\n")
        dest = util.write_unclaimed(tmp_path, "evil", ".SKILL.md", "gen\n")
        assert dest == tmp_path / "evil.2.SKILL.md"
        assert dest.read_bytes() == b"gen\n"
        assert (tmp_path / "evil.SKILL.md").read_bytes() == b"precious notes\n"
        assert (tmp_path / "evil.1.SKILL.md").read_bytes() == b"older\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "evil.1.SKILL.md", "evil.2.SKILL.md", "evil.SKILL.md"]

    def test_first_collision_takes_suffix_one(self, tmp_path):
        (tmp_path / "x.md").write_text("mine", encoding="utf-8")
        assert util.write_unclaimed(tmp_path, "x", ".md", "t") == tmp_path / "x.1.md"

    def test_an_unwritable_directory_is_framed_as_a_boost_error(self, tmp_path):
        missing = tmp_path / "no" / "such"
        with pytest.raises(BoostError) as exc:
            util.write_unclaimed(missing, "x", ".md", "t")
        assert exc.value.message.startswith("cannot write ")
        assert str(missing / "x.md") in exc.value.message
