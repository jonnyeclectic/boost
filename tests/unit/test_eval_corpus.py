"""Unit tests: scripts/eval_corpus.py — the corpus the required gate measures.

WHY THIS FILE EXISTS. `tests/eval/taps.txt` pinned repo NAMES, not commits, so
the gate's corpus was whatever those repos happened to contain at clone time.
Measured: the list recorded 743 entries when it was written and resolved to
**3,843** on the same 20 repos later, a 5.2x drift nobody changed a file to
cause. One repo (`affaan-m/ECC`) is 1,616 of those entries, so a single third
party can move the required number on its own.

That matters because the floor is not comfortable: BM25 scores recall@10
**0.912** against a floor of **0.85**, a margin of +0.062. Silent growth spends
that margin, and the first symptom would be a red required gate on an unrelated
PR.

These tests pin the two halves of the fix: the file format carries a SHA per
repo, and every repo in the shipped list actually has one — so a future edit
cannot quietly reintroduce an unpinned entry.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "eval_corpus.py"
_TAPS = _ROOT / "tests" / "eval" / "taps.txt"

pytestmark = pytest.mark.skipif(
    not _SCRIPT.exists(), reason="repo-root script not reachable")


def _load():
    spec = importlib.util.spec_from_file_location("eval_corpus", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path, name="origin"):
    """A real two-commit git repo, so the pin logic is exercised, not mocked."""
    path = tmp_path / name
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    for cfg in (("user.email", "t@example.test"), ("user.name", "T"),
                ("commit.gpgsign", "false")):
        _git(path, "config", *cfg)
    shas = []
    for n in ("first", "second"):
        (path / "SKILL.md").write_text("# %s\n" % n, encoding="utf-8")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", n)
        shas.append(_git(path, "rev-parse", "HEAD"))
    return path, shas


class TestParsingTheTapList:
    def test_a_pinned_line_yields_repo_and_sha(self):
        m = _load()
        sha = "a" * 40
        assert m.parse_taps("owner/repo %s\n" % sha) == [("owner/repo", sha)]

    def test_comments_and_blank_lines_are_skipped(self):
        m = _load()
        text = "# a comment\n\n   \nowner/repo %s\n" % ("b" * 40)
        assert [r for r, _s in m.parse_taps(text)] == ["owner/repo"]

    def test_extra_whitespace_is_tolerated(self):
        m = _load()
        sha = "c" * 40
        assert m.parse_taps("  owner/repo \t %s  \n" % sha) == [("owner/repo", sha)]

    def test_an_unpinned_line_still_parses(self):
        # Backward compatible on purpose: the format change must not be a flag
        # day for anyone carrying a local list.
        m = _load()
        assert m.parse_taps("owner/repo\n") == [("owner/repo", None)]

    def test_a_malformed_sha_fails_loudly(self):
        # A typo must not fall through to "unpinned" — that is the silent
        # weakening this whole change exists to prevent.
        m = _load()
        with pytest.raises(SystemExit) as ei:
            m.parse_taps("owner/repo not-a-sha\n")
        assert "owner/repo" in str(ei.value)

    def test_a_short_sha_is_rejected(self):
        m = _load()
        with pytest.raises(SystemExit):
            m.parse_taps("owner/repo %s\n" % ("d" * 7))


class TestTheShippedListIsFullyPinned:
    """The regression guard: this is what stops the drift coming back."""

    def test_every_repo_carries_a_sha(self):
        m = _load()
        unpinned = [r for r, sha in m.parse_taps(_TAPS.read_text(encoding="utf-8"))
                    if not sha]
        assert unpinned == [], "unpinned repos in taps.txt: %s" % unpinned

    def test_the_list_is_not_empty_and_has_no_duplicates(self):
        m = _load()
        repos = [r for r, _s in m.parse_taps(_TAPS.read_text(encoding="utf-8"))]
        assert len(repos) >= 20
        assert len(repos) == len(set(repos))

    def test_every_sha_is_lowercase_hex(self):
        m = _load()
        for repo, sha in m.parse_taps(_TAPS.read_text(encoding="utf-8")):
            assert re.fullmatch(r"[0-9a-f]{40}", sha or ""), (repo, sha)


class TestTheGateIsDefinedOnce:
    """`make check` claims to BE the required gate. For `eval` it was not.

    CI ran `--fail-under 0.85` and no other floor; the Makefile (and the gate
    table in CLAUDE.md) define four floors with recall at 0.78. So the required
    check was simultaneously tighter than documented on one metric — 0.863
    measured against 0.85 is a buffer of 1.15 queries out of 91 — and absent on
    the other three, which are the ones added to close the "finds it every time,
    never ranks it first" hole. A ranker could regress hit@1 to 0.000 and the
    required gate would pass.
    """

    def _flags(self, text: str):
        # The invocation is line-continued in the Makefile, so match over the
        # whole recipe/step rather than a single line.
        assert "eval_retrieval.py" in text
        floors = dict(re.findall(r"--floor\s+([\w@]+)=([\d.]+)", text))
        under = re.search(r"--fail-under\s+([\d.]+)", text)
        assert under, "no --fail-under in:\n%s" % text
        floors["recall@k"] = under.group(1)
        return floors

    @pytest.mark.skipif(not (_ROOT / "Makefile").exists(),
                        reason="repo-root Makefile not reachable")
    def test_ci_and_make_floor_the_same_metrics_at_the_same_values(self):
        makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
        recipe = makefile.split("\neval:", 1)[1].split("\n\n", 1)[0]
        ci = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        step = ci.split("retrieval quality gate", 1)[1].split("\n\n", 1)[0]
        assert self._flags(step) == self._flags(recipe)


class TestPinningAClone:
    def test_a_sha_already_present_is_checked_out_without_fetching(
            self, tmp_path, monkeypatch):
        m = _load()
        path, shas = _repo(tmp_path)
        fetched = []
        monkeypatch.setattr(m, "_fetch", lambda *a: fetched.append(a))
        m.pin_clone(path, shas[0])
        assert _git(path, "rev-parse", "HEAD") == shas[0]
        assert fetched == [], "fetched a commit the clone already had"

    def test_a_missing_sha_is_fetched_from_origin(self, tmp_path):
        # The real case in CI: `boost tap` shallow-clones, so the pinned commit
        # is usually absent until it is fetched by SHA.
        m = _load()
        origin, shas = _repo(tmp_path)
        clone = tmp_path / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1",
                        "file://%s" % origin, str(clone)], check=True)
        assert m.has_commit(clone, shas[0]) is False, "fixture is not shallow"
        m.pin_clone(clone, shas[0])
        assert _git(clone, "rev-parse", "HEAD") == shas[0]

    def test_pinning_is_idempotent(self, tmp_path):
        m = _load()
        path, shas = _repo(tmp_path)
        m.pin_clone(path, shas[0])
        m.pin_clone(path, shas[0])
        assert _git(path, "rev-parse", "HEAD") == shas[0]

    def test_an_unreachable_sha_names_the_clone_and_exits(self, tmp_path):
        m = _load()
        path, _shas = _repo(tmp_path)
        with pytest.raises(SystemExit) as ei:
            m.pin_clone(path, "e" * 40)
        assert path.name in str(ei.value)

    def test_has_commit_is_false_for_a_tree_not_a_commit(self, tmp_path):
        # `cat-file -e <sha>` alone passes for any object; the pin must reject a
        # tree or blob SHA rather than checking out something meaningless.
        m = _load()
        path, _shas = _repo(tmp_path)
        tree = _git(path, "rev-parse", "HEAD^{tree}")
        assert m.has_commit(path, tree) is False
