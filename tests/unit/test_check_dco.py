# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: scripts/check_dco.py — the Developer Certificate of Origin gate.

The gate exists to enforce an *assertion by the contributor*, so the test that
matters most is the one proving a sign-off naming somebody else is rejected. A
checker that accepted any `Signed-off-by:` line at all would pass a history
backfilled by a third party, which certifies nothing and would turn a legal
record into a checkbox — see the module docstring in the script.

Tests drive real git repositories in a tmpdir rather than only asserting that
this repo currently passes, because a gate that can only say "yes" is the
failure mode.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_dco.py"

AUTHOR = ("Ada Lovelace", "ada@example.com")


@pytest.fixture(scope="module")
def dco():
    spec = importlib.util.spec_from_file_location("check_dco", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def git(repo: Path, *args: str, **env: str) -> str:
    base = {
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": AUTHOR[0], "GIT_AUTHOR_EMAIL": AUTHOR[1],
        "GIT_COMMITTER_NAME": AUTHOR[0], "GIT_COMMITTER_EMAIL": AUTHOR[1],
        "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
        "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }
    base.update(env)
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True, env=base).stdout


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    """A throwaway git repo, with the process cwd moved into it.

    ``check()`` shells out to plain ``git`` with no ``-C``, because that is how
    the workflow invokes it — from the repository root. The chdir is what makes
    the tests exercise that same path instead of a second, test-only one.
    """
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(r, "add", "seed.txt")
    git(r, "commit", "-q", "-m", "seed")
    monkeypatch.chdir(r)
    return r


def commit(repo: Path, name: str, message: str, **env: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    git(repo, "add", name, **env)
    git(repo, "commit", "-q", "-m", message, **env)
    return git(repo, "rev-parse", "HEAD").strip()


def signed(message: str, who=AUTHOR) -> str:
    return "%s\n\nSigned-off-by: %s <%s>" % (message, who[0], who[1])


class TestAccepts:
    def test_signed_off_by_the_author_passes(self, dco, repo):
        commit(repo, "a.txt", signed("add a"))
        assert dco.check("HEAD~1..HEAD") == []

    def test_every_commit_in_a_multi_commit_range_is_checked(self, dco, repo):
        commit(repo, "a.txt", signed("add a"))
        commit(repo, "b.txt", signed("add b"))
        assert dco.check("HEAD~2..HEAD") == []

    def test_email_comparison_is_case_insensitive(self, dco, repo):
        commit(repo, "a.txt",
               "add a\n\nSigned-off-by: Ada Lovelace <ADA@EXAMPLE.COM>")
        assert dco.check("HEAD~1..HEAD") == []

    def test_extra_trailers_alongside_the_signoff_are_fine(self, dco, repo):
        commit(repo, "a.txt",
               signed("add a") + "\nCo-Authored-By: Someone <s@example.com>")
        assert dco.check("HEAD~1..HEAD") == []

    def test_empty_range_passes(self, dco, repo):
        assert dco.check("HEAD..HEAD") == []


class TestRejects:
    def test_missing_signoff_fails(self, dco, repo):
        sha = commit(repo, "a.txt", "add a")
        failures = dco.check("HEAD~1..HEAD")
        assert [f[0] for f in failures] == [sha]
        assert failures[0][1] == "add a"

    def test_signoff_naming_someone_else_is_rejected(self, dco, repo):
        """The point of the whole gate.

        A third party signing off on another person's commit certifies nothing:
        the DCO is the *contributor* asserting they may submit the work. A
        checker that accepted this would pass a backfilled history while
        recording an assertion nobody made.
        """
        sha = commit(repo, "a.txt",
                     signed("add a", ("Commit Reviewer", "reviewer@example.com")))
        assert [f[0] for f in dco.check("HEAD~1..HEAD")] == [sha]

    def test_right_name_wrong_email_is_rejected(self, dco, repo):
        sha = commit(repo, "a.txt",
                     signed("add a", (AUTHOR[0], "someone.else@example.com")))
        assert [f[0] for f in dco.check("HEAD~1..HEAD")] == [sha]

    def test_only_the_unsigned_commit_is_reported(self, dco, repo):
        commit(repo, "a.txt", signed("add a"))
        sha = commit(repo, "b.txt", "add b")
        assert [f[0] for f in dco.check("HEAD~2..HEAD")] == [sha]

    def test_trailer_must_be_its_own_line(self, dco, repo):
        sha = commit(repo, "a.txt",
                     "add a, Signed-off-by: Ada Lovelace <ada@example.com>")
        assert [f[0] for f in dco.check("HEAD~1..HEAD")] == [sha]


class TestExemptions:
    def test_bot_authors_are_exempt(self, dco, repo):
        commit(repo, "a.txt", "bump a", GIT_AUTHOR_NAME="dependabot[bot]",
               GIT_AUTHOR_EMAIL="49699333+dependabot[bot]@users.noreply.github.com")
        assert dco.check("HEAD~1..HEAD") == []

    def test_any_bracket_bot_suffix_is_exempt(self, dco, repo):
        commit(repo, "a.txt", "auto", GIT_AUTHOR_NAME="some-new-thing[bot]",
               GIT_AUTHOR_EMAIL="new@example.com")
        assert dco.check("HEAD~1..HEAD") == []

    def test_a_human_is_not_exempt_by_a_bot_like_email(self, dco, repo):
        """The exemption keys on the author, not on a substring anywhere."""
        sha = commit(repo, "a.txt", "sneaky", GIT_AUTHOR_NAME="Real Person",
                     GIT_AUTHOR_EMAIL="person@bot.example.com")
        assert [f[0] for f in dco.check("HEAD~1..HEAD")] == [sha]


class TestCli:
    def test_exit_zero_and_ok_line_when_clean(self, dco, repo, capsys):
        commit(repo, "a.txt", signed("add a"))
        monkeyed = subprocess.run(
            ["python3", str(SCRIPT), "HEAD~1..HEAD"], cwd=repo,
            capture_output=True, text=True)
        assert monkeyed.returncode == 0
        assert "OK" in monkeyed.stdout

    def test_exit_one_and_names_the_fix_when_dirty(self, repo):
        commit(repo, "a.txt", "add a")
        run = subprocess.run(["python3", str(SCRIPT), "HEAD~1..HEAD"], cwd=repo,
                             capture_output=True, text=True)
        assert run.returncode == 1
        # The failure has to be actionable: the offending subject, the exact
        # trailer to add, and the command that adds it.
        assert "add a" in run.stdout
        assert "Signed-off-by: Ada Lovelace <ada@example.com>" in run.stdout
        assert "--signoff" in run.stdout

    def test_a_bad_range_fails_loudly_rather_than_passing_vacuously(self, repo):
        run = subprocess.run(["python3", str(SCRIPT), "no-such-ref..HEAD"],
                             cwd=repo, capture_output=True, text=True)
        assert run.returncode == 1
        assert "git failed" in run.stdout
