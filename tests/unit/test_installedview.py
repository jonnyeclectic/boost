# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""core.installedview: the installed item's facts, kept apart from the tap HEAD's."""
from __future__ import annotations

import hashlib
import types

import pytest

from boost_cli.core import installedview, staleness


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture()
def tap(tmp_path):
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "style.mdc").write_text("v2 text", encoding="utf-8")
    return types.SimpleNamespace(path=tmp_path, name="t")


def _lk(**kw):
    return {"tap": "t", "version": "1.0.0", "source_file": "rules/style.mdc",
            "sha256": _sha("v1 text"), **kw}


def _row(version="2.0.0", kind="rule", **kw):
    return {"name": "style", "tap": "t", "kind": kind, "version": version,
            "skill_md": "rules/style.mdc", **kw}


class TestUpdateOf:
    def test_unchanged_source_is_up_to_date(self, tap):
        lk = _lk(sha256=_sha("v2 text"))
        assert installedview.update_of("rule", lk, tap, [_row()]) == (None, None)

    def test_higher_version_is_a_version_update(self, tap):
        assert installedview.update_of("rule", _lk(), tap, [_row()]) == (
            staleness.VERSION, "2.0.0")

    def test_same_version_is_a_content_update(self, tap):
        assert installedview.update_of("rule", _lk(), tap, [_row("1.0.0")]) == (
            staleness.CONTENT, "1.0.0")

    def test_lower_version_is_content_not_version(self, tap):
        assert installedview.update_of("rule", _lk(), tap, [_row("0.9.0")]) == (
            staleness.CONTENT, "0.9.0")

    def test_missing_version_installed_is_compared_as_0_0_0(self, tap):
        lk = _lk()
        del lk["version"]
        assert installedview.update_of("rule", lk, tap, [_row("0.0.1")]) == (
            staleness.VERSION, "0.0.1")

    def test_other_kind_row_gives_no_latest(self, tap):
        assert installedview.update_of(
            "rule", _lk(), tap, [_row(kind="workflow")]) == (
            staleness.CONTENT, None)

    def test_versionless_row_gives_no_latest(self, tap):
        assert installedview.update_of(
            "rule", _lk(), tap, [_row(version="")]) == (staleness.CONTENT, None)

    def test_unreadable_source_is_missing(self, tap):
        lk = _lk(source_file="rules/gone.mdc")
        assert installedview.update_of("rule", lk, tap, [_row()]) == (
            staleness.SOURCE_MISSING, None)

    def test_no_source_file_reads_the_tap_root_and_is_missing(self, tap):
        lk = _lk()
        del lk["source_file"]
        assert installedview.update_of("rule", lk, tap, [_row()]) == (
            staleness.SOURCE_MISSING, None)


class TestInstalledUpdate:
    @pytest.mark.parametrize("tap_name", [None, "", "local", "not-a-tap"])
    def test_no_comparable_tap(self, sandbox, tap_name):
        lk = _lk(tap=tap_name)
        assert installedview.installed_update("rule", lk, [_row()]) == (
            None, None)

    @pytest.mark.parametrize(("cloned", "changed", "want"),
                             [(True, False, (staleness.VERSION, "2.0.0")),
                              (False, False, (None, None)),
                              (True, True, (None, None))])
    def test_only_a_cloned_same_source_tap_is_compared(
            self, sandbox, monkeypatch, tap, cloned, changed, want):
        tap.is_cloned = cloned
        seen = []
        monkeypatch.setattr(installedview.registry, "get",
                            lambda name: seen.append(name) or tap)
        monkeypatch.setattr(installedview.registry, "source_changed",
                            lambda lk, t: changed)
        assert installedview.installed_update("rule", _lk(), [_row()]) == want
        assert seen == ["t"]


class TestSplit:
    def test_equal_upstream_is_dropped(self):
        assert installedview.split("a", "a") == ("a", "")

    def test_different_upstream_is_kept(self):
        assert installedview.split("a", "b") == ("a", "b")


class TestSkillDescription:
    def test_reads_the_installed_copy(self, tmp_path):
        (tmp_path / "SKILL.md").write_text(
            "---\nname: a\ndescription: old\n---\nbody\n", encoding="utf-8")
        assert installedview.skill_description(
            tmp_path, {"description": "new"}) == ("old", "new")
        assert installedview.skill_description(
            tmp_path, {"description": "old"}) == ("old", "")

    def test_no_copy_on_disk_is_upstream_only(self, tmp_path):
        assert installedview.skill_description(
            tmp_path, {"description": "new"}) == ("", "new")
        assert installedview.skill_description(
            None, {"description": "new"}) == ("", "new")
        assert installedview.skill_description(None, None) == ("", "")

    def test_a_directory_named_skill_md_is_not_a_copy(self, tmp_path):
        (tmp_path / "SKILL.md").mkdir()
        assert installedview.skill_description(
            tmp_path, {"description": "new"}) == ("", "new")

    def test_copy_without_a_description_reads_as_the_scanner_does(
            self, tmp_path):
        # The scanner describes a SKILL.md with no `description:` by its
        # first prose line. Reading only the frontmatter reported a fresh,
        # unchanged install as having no description and an "upstream" one.
        (tmp_path / "SKILL.md").write_text(
            "---\nname: a\n---\n# a\n\nDoes a thing.\n", encoding="utf-8")
        assert installedview.skill_description(
            tmp_path, {"description": "Does a thing."}) == ("Does a thing.", "")
        assert installedview.skill_description(
            tmp_path, {"description": "new"}) == ("Does a thing.", "new")
        (tmp_path / "SKILL.md").write_text("---\nname: a\n---\n# a\n",
                                           encoding="utf-8")
        assert installedview.skill_description(
            tmp_path, {"description": "new"}) == ("", "new")
        assert installedview.skill_description(tmp_path, {}) == ("", "")


class TestMaterializedDescription:
    def test_lock_description_wins(self):
        lk = {"description": "old"}
        assert installedview.materialized_description(
            lk, {"description": "new"}, staleness.VERSION) == ("old", "new")
        assert installedview.materialized_description(
            lk, {"description": "old"}, None) == ("old", "")

    def test_empty_lock_description_is_still_the_lock_answer(self):
        assert installedview.materialized_description(
            {"description": ""}, {"description": "new"}, None) == ("", "new")
        assert installedview.materialized_description(
            {"description": None}, None, None) == ("", "")

    def test_old_lock_trusts_the_catalog_only_while_unchanged(self):
        cat = {"description": "tap"}
        assert installedview.materialized_description({}, cat, None) == (
            "tap", "")
        for reason in (staleness.VERSION, staleness.CONTENT,
                       staleness.SOURCE_MISSING):
            assert installedview.materialized_description(
                {}, cat, reason) == ("", "tap")
        assert installedview.materialized_description({}, None, None) == (
            "", "")
