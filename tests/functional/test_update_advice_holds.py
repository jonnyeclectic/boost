# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: `drift` and `outdated` name what `boost update` will do.

Both listed items `boost update` holds back on every run as plain upgrades:

* `drift` hinted `boost update` for a pinned upstream-moved skill (user or
  project), and update answered "pinned item has an update held back";
* `outdated` showed a locally edited and a quarantined skill with no mark,
  and nothing in `--json`, while update skipped both.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import paths


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t.test", "-c", "user.name=t",
                    *args], cwd=str(cwd), check=True, capture_output=True)


def _bump(src, name, old, new="9.0.0"):
    md = src / "skills" / name / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8")
                  .replace("version: %s" % old, "version: %s" % new)
                  + "\nnew upstream line\n", encoding="utf-8")
    _git(src, "commit", "-qam", "bump %s" % name)


def _row(text: str, name: str) -> str:
    return next(" ".join(line.split()) for line in text.splitlines()
                if line.split() and line.split()[0] == name)


def _said(r):
    return " ".join((r.out + r.err).split())


@pytest.fixture()
def src(boost, fixture_tap_src, tmp_path):
    copy = tmp_path / "advice-tap"
    shutil.copytree(fixture_tap_src, copy)
    boost("tap", copy)
    return copy


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    d = tmp_path / "advice-repo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d.resolve()


class TestDriftPinned:
    def test_pinned_user_row_names_unpin(self, boost, src):
        boost("install", "cowboy-coding")
        boost("pin", "cowboy-coding")
        _bump(src, "cowboy-coding", "0.1.0")
        boost("update", "--taps-only")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        row = next(r for r in rows if r["name"] == "cowboy-coding")
        assert row["status"] == "upstream-moved"
        assert row["hint"] == ("pinned — boost unpin cowboy-coding, then "
                               "boost update")
        # Following it moves the skill, where `boost update` alone held it.
        boost("unpin", "cowboy-coding")
        boost("update")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        assert next(r for r in rows
                    if r["name"] == "cowboy-coding")["status"] == "in-sync"

    def test_pinned_project_row_names_unpin_local(self, boost, src, repo):
        boost("install", "cowboy-coding")
        boost("install", "--local", "cowboy-coding")
        boost("pin", "cowboy-coding", "--local")
        boost("pin", "cowboy-coding", "--global")
        _bump(src, "cowboy-coding", "0.1.0")
        boost("update", "--taps-only")
        rows = json.loads(boost("drift", "--json").out)["skills"]
        hints = {r["scope"]: r["hint"] for r in rows
                 if r["name"] == "cowboy-coding"}
        assert hints == {
            "project": "pinned — boost unpin cowboy-coding --local, then "
                       "boost update",
            # Unscoped `unpin` is refused when both scopes hold the name.
            "user": "pinned — boost unpin cowboy-coding --global, then "
                    "boost update"}

    def test_unpinned_row_still_hints_update(self, boost, src):
        boost("install", "cowboy-coding")
        _bump(src, "cowboy-coding", "0.1.0")
        boost("update", "--taps-only")
        r = boost("drift", "cowboy-coding")
        assert _row(r.out, "cowboy-coding") == (
            "cowboy-coding upstream-moved boost update")


class TestOutdatedHolds:
    @pytest.fixture()
    def held(self, boost, src):
        boost("install", "commit-messages")
        boost("install", "cowboy-coding")
        md = paths.store_dir() / "commit-messages" / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "x\n",
                      encoding="utf-8")
        boost("quarantine", "cowboy-coding")
        _bump(src, "commit-messages", "1.0.2")
        _bump(src, "cowboy-coding", "0.1.0")
        boost("update", "--taps-only")

    def test_text_marks_and_footer(self, boost, held):
        r = boost("outdated")
        assert _row(r.out, "commit-messages").startswith(
            "commit-messages 1.0.2 (local edits) 9.0.0")
        assert _row(r.out, "cowboy-coding").startswith(
            "cowboy-coding 0.1.0 (quarantined) 9.0.0")
        assert ("2 outdated · 1 quarantined (`boost quarantine --release "
                "<name>` lets one update) · 1 with local edits (`boost "
                "update` skips them; `boost update --discard-edits` takes "
                "the update)") in _said(r)
        assert "upstream (`boost update` upgrades" not in _said(r)

    def test_json_fields(self, boost, held):
        rows = {r["name"]: r for r in json.loads(boost("outdated",
                                                       "--json").out)}
        assert (rows["commit-messages"]["local_edits"],
                rows["commit-messages"]["quarantined"]) == (True, False)
        assert (rows["cowboy-coding"]["local_edits"],
                rows["cowboy-coding"]["quarantined"]) == (False, True)

    def test_update_holds_what_outdated_marks(self, boost, held):
        said = _said(boost("update", "-y"))
        assert "commit-messages has local edits — update skipped" in said
        assert "1 quarantined item has an update held back" in said
        r = boost("outdated")
        assert "(local edits)" in _row(r.out, "commit-messages")
        assert "(quarantined)" in _row(r.out, "cowboy-coding")

    def test_plain_upgrade_is_unmarked(self, boost, src):
        boost("install", "commit-messages")
        _bump(src, "commit-messages", "1.0.2")
        boost("update", "--taps-only")
        r = boost("outdated")
        assert _row(r.out, "commit-messages").startswith(
            "commit-messages 1.0.2 9.0.0")
        assert ("1 outdated · `boost update` upgrades (pinned and "
                "quarantined items stay put)") in _said(r)
        row = json.loads(boost("outdated", "--json").out)[0]
        assert (row["local_edits"], row["quarantined"]) == (False, False)
