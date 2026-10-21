# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost lint` judges a skill's name and description the way install does.

Lint only asked whether `name`/`description` were truthy, so a name `boost
import` refuses (`My Fancy Skill`), one a tap install slugs into something the
SKILL.md never says, and a `description:` written as a map (which the catalog
reads as "" and replaces with the body's first line) all passed at 80/100.
The rule now: a lint pass means import takes the skill as written, and a name
import refuses is a lint error.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import catalog, store, util
from boost_cli.errors import BoostError

BODY = ("# Title\n\n## Steps\n\n1. Do the first thing carefully.\n"
        "2. Then the second.\n" + "More detail here. " * 15 + "\n")
DESC = "Review a pull request diff and report the findings back"


def skill(root: Path, dirname: str, name_line: str,
          desc_block: str = "description: %s\n" % DESC) -> Path:
    d = root / dirname
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\n%s\n%sversion: 1.0.0\n---\n\n%s" % (name_line, desc_block, BODY),
        encoding="utf-8")
    return d


class TestStringFieldError:
    @pytest.mark.parametrize("meta, want", [
        ({}, "missing required field: name"),
        ({"name": ""}, "missing required field: name"),
        ({"name": "   "}, "missing required field: name"),
        ({"name": True}, "`name` must be a string, not a boolean"),
        ({"name": False}, "`name` must be a string, not a boolean"),
        ({"name": ["a", "b"]}, "`name` must be a string, not a list"),
        ({"name": {"en": "x"}}, "`name` must be a string, not a map"),
        ({"name": 3}, "`name` must be a string, not a number"),
        ({"name": 2.5}, "`name` must be a string, not a number"),
        ({"name": b"x"}, "`name` must be a string, not bytes"),
        ({"name": "ok"}, None),
    ])
    def test_reports_each_shape(self, meta, want):
        assert util.string_field_error(meta, "name") == want


class TestItemNameError:
    @pytest.mark.parametrize("name", ["My Fancy Skill", "../x", ".", "..", "a/b"])
    def test_unsafe_names_are_errors(self, name):
        assert util.item_name_error(name) == "invalid skill name %r" % name

    def test_safe_name_is_none(self):
        assert util.item_name_error("ok_name-1.2") is None

    def test_too_long_name_is_an_error(self):
        err = util.item_name_error("a" * 300)
        assert err is not None and err.startswith("skill name is too long")

    def test_check_item_name_hints_the_rule(self):
        with pytest.raises(BoostError) as exc:
            util.check_item_name("My Skill", "rule")
        assert str(exc.value) == "invalid rule name 'My Skill'"
        assert exc.value.hint == util.NAME_RULE_HINT


class TestFrontmatterName:
    def test_absent_or_empty_falls_back(self):
        assert util.frontmatter_name({}, "dir") == "dir"
        assert util.frontmatter_name({"name": ""}, "dir") == "dir"
        assert util.frontmatter_name({"name": "  "}, "dir") == "dir"

    def test_string_is_stripped(self):
        assert util.frontmatter_name({"name": " x "}, "dir") == "x"

    @pytest.mark.parametrize("val, kind", [
        (True, "a boolean"), (["a", "b"], "a list"), ({"k": "v"}, "a map")])
    def test_non_string_raises(self, val, kind):
        with pytest.raises(BoostError) as exc:
            util.frontmatter_name({"name": val}, "dir")
        assert str(exc.value) == "frontmatter `name` must be a string, not %s" % kind


class TestLintErrors:
    def test_unsafe_name(self, tmp_path):
        d = skill(tmp_path, "upper", "name: My Fancy Skill")
        assert util.lint_errors(d) == ["invalid skill name 'My Fancy Skill'"]

    def test_bool_name(self, tmp_path):
        d = skill(tmp_path, "nametrue", "name: true")
        assert util.lint_errors(d) == ["`name` must be a string, not a boolean"]

    def test_list_name(self, tmp_path):
        d = skill(tmp_path, "namelist", "name: [a, b]")
        assert util.lint_errors(d) == ["`name` must be a string, not a list"]

    def test_map_description(self, tmp_path):
        d = skill(tmp_path, "descmap", "name: descmap",
                  "description:\n  en: %s\n" % DESC)
        assert util.lint_errors(d) == ["`description` must be a string, not a map"]

    def test_mismatched_dir_is_not_an_error(self, tmp_path):
        d = skill(tmp_path, "mismatch", "name: other-name")
        assert util.lint_errors(d) == []


class TestScoreReadsLikeTheCatalog:
    def test_map_description_earns_no_description_points(self, tmp_path):
        good = skill(tmp_path, "good", "name: good")
        bad = skill(tmp_path, "descmap", "name: descmap",
                    "description:\n  en: %s\n" % DESC)
        good_score, _ = util.score_skill(good)
        bad_score, notes = util.score_skill(bad)
        # 10 for a description, 5 for one over 40 chars.
        assert good_score - bad_score == 15
        assert "frontmatter missing `description`" in notes

    def test_map_name_earns_no_name_points(self, tmp_path):
        bad = skill(tmp_path, "namemap", "name:\n  en: x")
        _score, notes = util.score_skill(bad)
        assert "frontmatter missing `name`" in notes

    def test_catalog_text_is_the_shared_reader(self):
        meta = {"description": {"en": "x"}, "name": " n ", "v": True}
        for key in meta:
            assert catalog._text(meta, key) == util.frontmatter_text(meta, key)
        assert util.frontmatter_text(meta, "description") == ""
        assert util.frontmatter_text(meta, "name") == "n"


class TestLabelAndNote:
    def test_label_is_the_frontmatter_name(self, tmp_path):
        d = skill(tmp_path, "mismatch", "name: other-name")
        assert util.lint_label(d) == "other-name"
        assert util.name_dir_note(d) == (
            "name 'other-name' differs from its directory 'mismatch'"
            " — it installs as 'other-name'")

    def test_matching_dir_has_no_note(self, tmp_path):
        d = skill(tmp_path, "same", "name: same")
        assert util.lint_label(d) == "same"
        assert util.name_dir_note(d) is None

    @pytest.mark.parametrize("text", [
        "no frontmatter\n", "---\nname: x\nno closing fence\n",
        "---\nname: true\n---\nbody\n"])
    def test_label_falls_back_to_the_dir(self, tmp_path, text):
        d = tmp_path / "fallback"
        d.mkdir()
        (d / "SKILL.md").write_text(text, encoding="utf-8")
        assert util.lint_label(d) == "fallback"

    def test_label_without_skill_md_is_the_dir(self, tmp_path):
        d = tmp_path / "bare"
        d.mkdir()
        assert util.lint_label(d) == "bare"


class TestLintAgreesWithImport:
    """Both directions: a lint pass imports; an import refusal fails lint."""

    @pytest.mark.parametrize("dirname, name_line, desc_block", [
        ("upper", "name: My Fancy Skill", None),
        ("nametrue", "name: true", None),
        ("namelist", "name: [a, b]", None),
    ])
    def test_import_refusal_is_a_lint_failure(self, sandbox, dirname,
                                              name_line, desc_block):
        kw = {} if desc_block is None else {"desc_block": desc_block}
        d = skill(sandbox / "src", dirname, name_line, **kw)
        with pytest.raises(BoostError):
            store.install_from_path(d)
        score, _ = util.score_skill(d)
        assert util.lint_failed(d, score)

    @pytest.mark.parametrize("dirname, name_line, want", [
        ("good", "name: good", "good"),
        ("mismatch", "name: other-name", "other-name"),
        ("dotted", "name: ok_name-1.2", "ok_name-1.2"),
    ])
    def test_lint_pass_imports_under_the_label(self, sandbox, dirname,
                                               name_line, want):
        d = skill(sandbox / "src", dirname, name_line)
        score, _ = util.score_skill(d)
        assert not util.lint_failed(d, score)
        assert util.lint_label(d) == want
        store.install_from_path(d)
        assert (store.skill_store_dir(want) / "SKILL.md").is_file()
        assert store.import_name(d) == want
