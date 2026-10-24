# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: git runs with English messages whatever the user's locale.

boost reads git's stderr for its meaning — the ``fatal:`` line it reports, the
credential and transport markers, the heading over the files ``sparse-checkout
reapply`` kept — and git translates all of it. Under LC_ALL=de_DE.UTF-8 a
failed fetch was reported as "und das Repository existiert." and ``compact``
said "compacted" over a locally modified file still on disk.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import gitutil, paths
from boost_cli.errors import BoostError

_DE = "de_DE.UTF-8"
_ID = ["-c", "user.email=t@t", "-c", "user.name=t"]


def _git_speaks_german() -> bool:
    if not gitutil.has_git():
        return False
    env = os.environ | {"LC_ALL": _DE}
    env.pop("LANGUAGE", None)
    proc = subprocess.run(["git", "-C", "/nonexistent-boost-probe", "status"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, check=False)
    return proc.stderr.startswith("Schwerwiegend:")


german = pytest.mark.skipif(not _git_speaks_german(),
                            reason="git has no German catalog here")


class TestGitEnv:
    def test_lc_all_is_dropped_and_its_value_kept_for_the_rest(self):
        env = gitutil.git_env({"LC_ALL": _DE, "LANG": "fr_FR.UTF-8",
                               "LC_CTYPE": "C", "PATH": "/bin"})
        assert env == {
            "LANG": "fr_FR.UTF-8", "PATH": "/bin",
            "LC_CTYPE": _DE, "LC_COLLATE": _DE, "LC_NUMERIC": _DE,
            "LC_TIME": _DE, "LC_MONETARY": _DE,
            "LC_MESSAGES": "C", "LANGUAGE": "C",
            "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}

    def test_without_lc_all_only_messages_change(self):
        env = gitutil.git_env({"LANG": _DE, "LC_CTYPE": "en_US.UTF-8",
                               "LANGUAGE": "de", "LC_MESSAGES": "de_DE"})
        assert env == {"LANG": _DE, "LC_CTYPE": "en_US.UTF-8",
                       "LC_MESSAGES": "C", "LANGUAGE": "C",
                       "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}

    def test_an_empty_lc_all_is_dropped_and_sets_nothing(self):
        env = gitutil.git_env({"LC_ALL": ""})
        assert env == {"LC_MESSAGES": "C", "LANGUAGE": "C",
                       "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}

    def test_it_defaults_to_os_environ_and_leaves_it_alone(self, monkeypatch):
        monkeypatch.setenv("LC_ALL", _DE)
        monkeypatch.setenv("BOOST_LOCALE_PROBE", "x")
        env = gitutil.git_env()
        assert env["BOOST_LOCALE_PROBE"] == "x"
        assert "LC_ALL" not in env
        assert env["LC_CTYPE"] == _DE
        assert os.environ["LC_ALL"] == _DE

    def test_read_blob_runs_under_it(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LC_ALL", _DE)
        seen: dict = {}

        def fake(argv, **kw):
            seen.update(kw["env"])
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        monkeypatch.setattr(gitutil, "_exec", fake)
        assert gitutil.read_blob(tmp_path, "HEAD", "x") == b""
        assert seen == gitutil.git_env()


@german
class TestUnderAGermanLocale:
    def test_a_failure_names_its_cause_in_english(self, sandbox, monkeypatch,
                                                  tmp_path):
        monkeypatch.setenv("LC_ALL", _DE)
        monkeypatch.delenv("LANGUAGE", raising=False)
        missing = tmp_path / "gone"
        with pytest.raises(BoostError) as err:
            gitutil.run(["-C", str(missing), "status"])
        assert err.value.message.startswith(
            "git status failed: fatal: cannot change to '%s'" % missing)

    def test_a_non_ascii_path_survives(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setenv("LC_ALL", _DE)
        repo = tmp_path / "répo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        (repo / "café.md").write_text("x\n", encoding="utf-8")
        gitutil.run(["-C", str(repo), "add", "-A"])
        proc = gitutil.run(["-c", "core.quotepath=false", "-C", str(repo),
                            "ls-files"])
        assert proc.stdout == "café.md\n"
        assert Path(gitutil.run(["-C", str(repo), "rev-parse",
                                 "--show-toplevel"]).stdout.strip()).name \
            == "répo"

    def _dirty_clone(self, up: Path, clone: Path) -> Path:
        (up / "skills" / "demo").mkdir(parents=True)
        (up / "skills" / "demo" / "SKILL.md").write_text(
            "---\nname: demo\ndescription: d\n---\nbody\n", encoding="utf-8")
        (up / "assets").mkdir()
        (up / "assets" / "big.bin").write_bytes(b"x" * 64)
        subprocess.run(["git", "init", "-q", str(up)], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(up), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(up), *_ID, "commit", "-qm", "i"],
                       check=True, capture_output=True)
        clone.parent.mkdir(parents=True, exist_ok=True)
        gitutil.clone_shallow(str(up), clone)
        subprocess.run(["git", "-C", str(clone), "sparse-checkout", "disable"],
                       check=True, capture_output=True)
        big = clone / "assets" / "big.bin"
        big.write_bytes(b"y" * 64)
        return big

    def test_narrow_still_sees_the_files_git_kept(self, sandbox, monkeypatch,
                                                  tmp_path):
        clone = tmp_path / "elsewhere"
        big = self._dirty_clone(tmp_path / "up", clone)
        monkeypatch.setenv("LC_ALL", _DE)
        monkeypatch.delenv("LANGUAGE", raising=False)
        with pytest.raises(BoostError) as err:
            gitutil.narrow(clone)
        assert err.value.message == ("git kept 1 locally modified file outside "
                                     "the sparse cone: assets/big.bin")
        assert big.read_bytes() == b"y" * 64

    def test_narrow_restores_and_removes_in_an_owned_clone(
            self, sandbox, monkeypatch, tmp_path):
        clone = paths.repos_dir() / "t"
        big = self._dirty_clone(tmp_path / "up", clone)
        monkeypatch.setenv("LC_ALL", _DE)
        monkeypatch.delenv("LANGUAGE", raising=False)
        gitutil.narrow(clone)
        assert not big.exists()
        assert (clone / "skills" / "demo" / "SKILL.md").exists()
