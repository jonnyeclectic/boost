# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost recommend` prints a causal column; it has to be caused.

Every row carries `because: <keyword>`, which is a claim about *why* this skill
suits this project. Scored on substrings, the claim was false often enough to
be the normal case: a `.github/workflows/` directory made boost recommend a
pasta-recipe skill "because: ci".
"""
from __future__ import annotations

import json
import subprocess

import pytest


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *list(args)], cwd=str(cwd), check=True, capture_output=True)


def _tap_of(root, *pairs):
    """Build a one-off tap of (name, description) skills and return its path.

    `boost tap` clones, so the source has to be a real repo with a commit.
    """
    root.mkdir(parents=True, exist_ok=True)
    for name, desc in pairs:
        d = root / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            "---\nname: %s\ndescription: %s\n---\n\n# %s\n\nBody.\n"
            % (name, desc, name), encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


@pytest.fixture()
def ci_project(boost, tmp_path):
    """A project whose ONLY stack signal is a CI workflow, plus a tap of
    skills that merely contain the letters `ci`."""
    src = _tap_of(
        tmp_path / "kwtap",
        ("pasta-recipes", "Delicious Italian pasta recipes"),
        ("brainstorming-x", "Structured ideation and divergent-thinking facilitation"),
        ("commit-messages-x", "Conventional, atomic commit message discipline"),
        ("ci-pipelines", "Set up CI pipelines that fail loudly"),
    )
    boost("tap", str(src))
    proj = tmp_path / "ciproj"
    (proj / ".github" / "workflows").mkdir(parents=True)
    (proj / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    return proj


class TestBecauseIsCausal:
    def test_ci_does_not_mean_recipes(self, boost, ci_project):
        r = boost("recommend", "--path", str(ci_project))
        assert "pasta-recipes" not in r.out
        assert "brainstorming-x" not in r.out
        assert "commit-messages-x" not in r.out

    def test_the_skill_that_really_is_about_ci_survives(self, boost, ci_project):
        r = boost("recommend", "--path", str(ci_project))
        assert "ci-pipelines" in r.out
        assert "because: ci" in r.out

    def test_json_carries_the_same_verdict(self, boost, ci_project):
        r = boost("recommend", "--path", str(ci_project), "--json")
        payload = json.loads(r.out)
        assert payload["stack"]["keywords"] == ["ci"]
        names = [x["name"] for x in payload["recommendations"]]
        assert "ci-pipelines" in names
        assert "pasta-recipes" not in names
        for row in payload["recommendations"]:
            assert row["because"] == ["ci"]

    def test_a_stack_with_no_honest_match_says_so(self, boost, tmp_path):
        """Better to recommend nothing than to invent a reason.

        Before this, the fallback branch was unreachable for any keyword short
        enough to appear inside a word — which is most of them.
        """
        src = _tap_of(tmp_path / "onlypasta",
                      ("pasta-recipes", "Delicious Italian pasta recipes"))
        boost("tap", str(src))
        proj = tmp_path / "ciproj2"
        (proj / ".github" / "workflows").mkdir(parents=True)
        (proj / ".github" / "workflows" / "ci.yml").write_text("on: push\n",
                                                               encoding="utf-8")
        r = boost("recommend", "--path", str(proj))
        assert "pasta-recipes" not in r.out or "because: ci" not in r.out
