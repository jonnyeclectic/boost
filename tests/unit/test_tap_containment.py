# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Nothing outside a tap's clone is indexed, read or installed.

A tap is somebody else's repo, and git stores a symlink as a symlink. A
``skills/ssh-helper/SKILL.md -> ../../../../../.ssh/id_rsa`` put the key in the
BM25 index, in `boost_search` hits and verbatim in `boost_read`, and
`boost_install` reported success for a store dir with nothing in it. Every
target here is a file inside the test's own sandbox HOME.

Also: a read of an item whose clone has gone re-clones it the way install
does, instead of answering with an errno over an absolute path.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

from boost_cli.commands import configuration, info
from boost_cli.core import catalog, mcp, paths, registry, store
from boost_cli.errors import BoostError

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")

MARKER = "FAKEKEYDATA0123"
_GOOD = "---\nname: good\ndescription: A good helper skill\n---\n\n# good\n"
_ESCAPED = ("rules/leak.mdc, skills/abs-leak/SKILL.md, "
            "skills/rel-leak/SKILL.md")


def _tool(tool, **args):
    """Through the server, which turns a BoostError into an isError reply."""
    resp = mcp.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": tool, "arguments": args}},
        version="0", registry=configuration.REGISTRY)
    return (resp["result"]["content"][0]["text"],
            resp["result"].get("isError", False))


def _git(repo, *argv):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@boost.test",
                    "-c", "user.name=Boost Test", *argv],
                   check=True, capture_output=True)


@pytest.fixture()
def evil_tap(sandbox, tmp_path):
    """A tap holding one real skill, one inside link and three escaping ones.

    The relative link is written for where boost *clones* it
    (``~/.boost/repos/evil-tap/skills/rel-leak/``), five levels under HOME.
    """
    secret = paths.home() / "secret.txt"
    secret.write_text("%s\n" % MARKER, encoding="utf-8")
    repo = tmp_path / "evil-tap"
    for d in ("good", "inner", "rel-leak", "abs-leak"):
        (repo / "skills" / d).mkdir(parents=True)
    (repo / "rules").mkdir()
    (repo / "skills" / "good" / "SKILL.md").write_text(_GOOD, encoding="utf-8")
    (repo / "skills" / "inner" / "SKILL.md").symlink_to("../good/SKILL.md")
    (repo / "skills" / "rel-leak" / "SKILL.md").symlink_to(
        "../../../../../secret.txt")
    (repo / "skills" / "abs-leak" / "SKILL.md").symlink_to(secret)
    (repo / "rules" / "leak.mdc").symlink_to(secret)
    subprocess.run(["git", "init", "-q", str(repo)], check=True,
                   capture_output=True)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


@pytest.fixture()
def tapped_evil(boost, evil_tap, monkeypatch):
    # Reported once per tap per process: start each test unreported.
    monkeypatch.setattr(catalog, "_ESCAPED", set())
    r = boost("tap", evil_tap)
    clone = paths.repos_dir() / "evil-tap"
    # The premise: in the clone, both kinds of link really reach the secret.
    for rel in ("skills/rel-leak/SKILL.md", "skills/abs-leak/SKILL.md"):
        assert (clone / rel).read_text(encoding="utf-8") == "%s\n" % MARKER
    return r


def _plant_stale(name, rel, kind="skill"):
    """Add an entry for an escaping file to the cache, at the current format —
    what a cache scanned before `scan_dir` checked containment still holds."""
    tap = registry.get("evil-tap")
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    good = next(e for e in data["skills"] if e["name"] == "good")
    entry = dict(good, name=name, skill_md=rel, kind=kind,
                 rel_dir=os.path.dirname(rel) if kind == "skill" else ".")
    data["skills"].append(entry)
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    return data


class TestTheScanStaysInsideTheClone:
    def test_escaping_items_are_skipped_and_inside_links_kept(self, tapped_evil):
        escaped: list[str] = []
        entries = catalog.scan_dir(paths.repos_dir() / "evil-tap", "evil-tap",
                                   escaped=escaped)
        assert sorted(e["name"] for e in entries) == ["good", "good"]
        assert sorted(e["skill_md"] for e in entries) == [
            "skills/good/SKILL.md", "skills/inner/SKILL.md"]
        assert ", ".join(sorted(escaped)) == _ESCAPED

    def test_a_scan_without_a_list_still_skips(self, tapped_evil):
        entries = catalog.scan_dir(paths.repos_dir() / "evil-tap", "evil-tap")
        assert len(entries) == 2

    def test_tap_reports_what_it_skipped(self, tapped_evil):
        assert "tapped evil-tap (2 items)" in tapped_evil.out
        assert ("skipped 3 items in tap evil-tap that link outside its "
                "clone: %s" % _ESCAPED) in " ".join(tapped_evil.err.split())

    def test_the_report_is_once_per_tap_and_singular_for_one(self, capsys,
                                                             monkeypatch):
        monkeypatch.setattr(catalog, "_ESCAPED", set())
        catalog._report_escaped("t1", ["a.md"])
        catalog._report_escaped("t1", ["a.md"])
        catalog._report_escaped("t2", [])
        err = capsys.readouterr().err
        assert err.count("skipped 1 item in tap t1 that link outside its "
                         "clone: a.md") == 1
        assert "t2" not in err

    def test_the_secret_is_not_searchable(self, tapped_evil):
        text, _ = _tool("boost_search", query=MARKER)
        assert text.startswith("no skills match")
        assert "leak" not in text

    def test_an_old_format_cache_is_rescanned_and_loses_the_leak(self,
                                                                 tapped_evil):
        data = _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        data["format"] = catalog.CACHE_FORMAT - 1
        registry.get("evil-tap").cache_file.write_text(json.dumps(data),
                                                       encoding="utf-8")
        catalog._ENTRY_CACHE.clear()
        names = {e["name"] for e in catalog.load_tap(registry.get("evil-tap"))}
        assert "abs-leak" not in names

    def test_cache_format_was_bumped(self):
        assert catalog.CACHE_FORMAT >= 5


class TestEscapes:
    def test_inside_outside_and_not_a_path(self, tmp_path):
        (tmp_path / "root").mkdir()
        (tmp_path / "out.txt").write_text("x", encoding="utf-8")
        (tmp_path / "root" / "in.txt").write_text("x", encoding="utf-8")
        (tmp_path / "root" / "away").symlink_to(tmp_path / "out.txt")
        root = tmp_path / "root"
        assert catalog.escapes(root, root / "in.txt") is False
        assert catalog.escapes(root, root / "away") is True
        assert catalog.escapes(root, tmp_path / "out.txt") is True
        assert catalog.escapes(root, root / "a\0b") is True


_REFUSED = ("refusing abs-leak from tap evil-tap: its file links outside "
            "the clone")


class TestReadsRefuseAnEscapingFile:
    def test_boost_read_refuses(self, tapped_evil):
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        text, is_err = _tool("boost_read", name="abs-leak")
        assert is_err is True
        assert _REFUSED in text
        assert "boost update evil-tap" in text
        assert MARKER not in text

    def test_boost_read_with_a_path_refuses(self, tapped_evil):
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        text, is_err = _tool("boost_read", name="abs-leak",
                             path="skills/abs-leak")
        assert is_err is True
        assert _REFUSED in text
        assert MARKER not in text

    def test_boost_cat_refuses(self, boost, tapped_evil):
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        r = boost("cat", "abs-leak", expect=None)
        assert r.rc != 0
        assert _REFUSED in r.err
        assert MARKER not in r.out + r.err

    def test_adapt_refuses(self, tapped_evil):
        from boost_cli.commands import pkg
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        with pytest.raises(BoostError) as ei:
            pkg._resolve_skill("abs-leak")
        assert str(ei.value) == _REFUSED
        assert MARKER not in str(ei.value)

    def test_a_rule_read_refuses(self, tapped_evil):
        _plant_stale("leak", "rules/leak.mdc", kind="rule")
        with pytest.raises(BoostError) as ei:
            info._resolve_text("leak")
        assert str(ei.value) == ("refusing leak from tap evil-tap: its file "
                                 "links outside the clone")
        assert ei.value.hint == "run `boost update evil-tap` to rescan the tap"

    def test_skill_meta_does_not_describe_it(self, tapped_evil):
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        assert info._skill_meta("abs-leak") is None
        assert info._skill_meta("good") is not None


class TestInstallRefuses:
    def test_a_skill(self, boost, tapped_evil):
        _plant_stale("abs-leak", "skills/abs-leak/SKILL.md")
        r = boost("install", "abs-leak", expect=None)
        assert r.rc != 0
        assert _REFUSED in r.err
        assert not os.path.lexists(paths.store_dir() / "abs-leak")

    def test_a_rule_is_not_rendered_into_a_context_file(self, boost,
                                                        tapped_evil):
        _plant_stale("leak", "rules/leak.mdc", kind="rule")
        r = boost("install", "leak", expect=None)
        assert r.rc != 0
        assert ("refusing leak from tap evil-tap: its file links outside "
                "the clone") in r.err
        claude = paths.home() / ".claude" / "CLAUDE.md"
        assert not claude.exists() or MARKER not in claude.read_text(
            encoding="utf-8")

    def test_a_workflow(self, tapped_evil):
        _plant_stale("cmd", "rules/leak.mdc", kind="workflow")
        entry = catalog.resolve_one("cmd")
        with pytest.raises(BoostError, match="refusing cmd from tap evil-tap"):
            store._install_workflow(entry)

    def test_a_copy_with_no_skill_md_is_refused_and_cleaned_up(self, sandbox,
                                                               tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (tmp_path / "outside.md").write_text("x", encoding="utf-8")
        (src / "SKILL.md").symlink_to(tmp_path / "outside.md")
        dest = paths.store_dir() / "empty"
        with pytest.raises(BoostError) as ei:
            store._copy_skill(src, dest, within=src)
        assert str(ei.value) == ("refusing to install empty: no SKILL.md "
                                 "would reach the store")
        assert ei.value.hint == ("a SKILL.md that links outside its source "
                                 "is never copied")
        assert not os.path.lexists(dest)
        assert os.listdir(dest.parent) == []


class TestAMissingCloneIsReclonedForReads:
    def _drop_clone(self):
        shutil.rmtree(paths.repos_dir() / "fixture-tap")

    def test_boost_read(self, tapped):
        self._drop_clone()
        text, is_err = _tool("boost_read", name="brainstorming")
        assert is_err is False
        assert "name: brainstorming" in text
        assert "Errno" not in text
        assert (paths.repos_dir() / "fixture-tap" / "skills" / "brainstorming"
                / "SKILL.md").is_file()

    def test_boost_read_with_a_path(self, tapped):
        self._drop_clone()
        text, is_err = _tool("boost_read", name="brainstorming",
                             path="skills/brainstorming")
        assert is_err is False
        assert "Errno" not in text

    def test_boost_cat(self, boost, tapped):
        self._drop_clone()
        r = boost("cat", "brainstorming", "--raw")
        assert "name: brainstorming" in r.out

    def test_a_vanished_file_names_boost_update(self, tapped):
        md = (paths.repos_dir() / "fixture-tap" / "skills" / "brainstorming"
              / "SKILL.md")
        md.unlink()
        text, is_err = _tool("boost_read", name="brainstorming")
        assert is_err is True
        assert "source for brainstorming vanished from tap fixture-tap" in text
        assert "boost update fixture-tap" in text
        assert "Errno" not in text

    def test_a_vanished_rule_names_boost_update(self, tapped_evil):
        _plant_stale("gone", "rules/gone.mdc", kind="rule")
        with pytest.raises(BoostError) as ei:
            store.source_file_for(catalog.resolve_one("gone"))
        assert str(ei.value) == "source for rule gone vanished from tap evil-tap"
        assert ei.value.hint == "run `boost update evil-tap`"

    def test_a_missing_rule_clone_is_recloned(self, tapped_evil):
        _plant_stale("ok-rule", "skills/good/SKILL.md", kind="rule")
        shutil.rmtree(paths.repos_dir() / "evil-tap")
        path = store.source_file_for(catalog.resolve_one("ok-rule"))
        assert path.read_text(encoding="utf-8") == _GOOD


class TestReadErrorsCarryNoErrnoPath:
    def test_strerror_not_the_exception(self, sandbox):
        p = paths.home() / "nope.md"
        with pytest.raises(BoostError) as ei:
            info._read(p)
        assert str(ei.value) == ("cannot read %s: No such file or directory"
                                 % paths.tilde(p))
