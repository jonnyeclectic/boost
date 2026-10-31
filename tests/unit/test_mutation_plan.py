# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the mutation planner (scripts/mutation_plan.py) and its CI wiring.

The planner decides what every mutation shard runs, once, so the properties
worth pinning are the ones a shard cannot check for itself:

* the full plan is *exactly* the committed pack, because ``merge --shards N``
  re-derives that pack to know which shard owned which file;
* an empty plan yields an empty matrix, and an empty shard yields a failure
  rather than an empty argv (``mutmut run`` with no pattern runs everything);
* the required ``mutation`` check goes red when the planner does, rather than
  reading a missing plan as "nothing to do".
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mp = _load("mutation_plan", "mutation_plan.py")
ms = _load("mutation_shards_for_plan", "mutation_shards.py")


def _tree_is_mutated() -> bool:
    """Inside mutmut's rewritten copy, packing ROOT parses 16 MB of mutants.

    Same guard as ``test_mutation_shard_count.py``'s: the planner reads
    ``scripts/`` only, which is never mutated, so skipping the real-tree pack
    there kills no fewer mutants and saves every shard minutes of preamble.
    """
    store = ROOT / "boost_cli" / "core" / "store.py"
    try:
        return "__mutmut_" in store.read_text(encoding="utf-8")
    except OSError:
        return True


real_tree_only = pytest.mark.skipif(
    _tree_is_mutated(), reason="tree rewritten by mutmut; packing it is slow")


@pytest.fixture
def needs_mutmut():
    """Skip a test that reaches mutmut where mutmut is not installed.

    Per test, never per module: the `tests` cells install
    requirements/test-tools.txt (PyYAML, no mutmut), and the tests that need
    only the stdlib and PyYAML must keep running there. The mutmut-backed ones
    run in `mutation-plan`, whose venv is requirements/mutation-tools.txt,
    under BOOST_REQUIRE_MUTMUT=1: there a missing mutmut is an error, so the
    one place these tests run cannot quietly skip them all.
    """
    if os.environ.get("BOOST_REQUIRE_MUTMUT") == "1":
        import mutmut

        return mutmut
    return pytest.importorskip("mutmut")


def write_plan(tmp_path: Path, sets: dict, gate_set: str | None = "full") -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"gate_set": gate_set, "reasons": ["test"],
                                "sets": sets}), encoding="utf-8")
    return str(path)


def run_cli(*argv: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert mp.main(list(argv)) == 0
    return out.getvalue()


# --------------------------------------------------------------------------
# full / none
# --------------------------------------------------------------------------

@real_tree_only
def test_full_plan_reuses_the_committed_pack(tmp_path):
    out = tmp_path / "plan.json"
    assert mp.main(["full", "--shards", "24", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["gate_set"] == "full"
    shards = plan["sets"]["full"]["shards"]
    assert len(shards) == 24
    assert shards == [ms.patterns_for_bin(ROOT, b) for b in ms.pack(ROOT, 24)]
    assert plan["sets"]["full"]["mutants"] is None
    assert plan["reasons"], "a plan must say why it is the plan it is"


def test_full_plan_on_a_small_tree(tmp_path):
    # The same contract on a tree this test controls, so it also runs inside
    # mutants/ where the real-tree test above is skipped.
    src = tmp_path / "boost_cli" / "core"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (src / "b.py").write_text("def g():\n    return 2\n", encoding="utf-8")
    out = tmp_path / "plan.json"
    assert mp.main(["full", "--shards", "2", "--root", str(tmp_path),
                    "--reason", "core changed", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan["gate_set"] == "full"
    assert plan["reasons"] == ["core changed"]
    assert plan["sets"]["full"]["mutants"] is None
    # One file per shard; which shard gets which is the packer's business.
    # __init__.py has no addressable pattern and must not leak a None/"" in.
    assert sorted(plan["sets"]["full"]["shards"]) == [["boost_cli.core.a.*"],
                                                      ["boost_cli.core.b.*"]]


def test_full_refuses_zero_shards(tmp_path):
    with pytest.raises(SystemExit):
        mp.main(["full", "--shards", "0", "--out", str(tmp_path / "p.json")])


def test_full_shards_is_the_committed_count():
    assert mp.FULL_SHARDS == ms.SHARDS == 24


def test_none_plan_has_an_empty_matrix(tmp_path):
    out = tmp_path / "plan.json"
    assert mp.main(["none", "--reason", "docs only", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert plan == {"gate_set": None, "reasons": ["docs only"], "sets": {}}
    assert run_cli("matrix", "--plan", str(out)) == "[]\n"


# --------------------------------------------------------------------------
# matrix / patterns
# --------------------------------------------------------------------------

def test_matrix_lists_every_set_and_index(tmp_path):
    plan = write_plan(tmp_path, {"full": {"shards": [["a*"], ["b*"]]},
                                 "diff": {"shards": [["c*"]]}})
    assert json.loads(run_cli("matrix", "--plan", plan)) == [
        {"set": "full", "index": 0}, {"set": "full", "index": 1},
        {"set": "diff", "index": 0}]


def test_matrix_is_one_compact_line(tmp_path):
    # Written to $GITHUB_OUTPUT as `matrix=<json>`: a newline inside the value
    # would end it, so the whole matrix must be one line.
    plan = write_plan(tmp_path, {"full": {"shards": [["a*"], ["b*"]]}})
    out = run_cli("matrix", "--plan", plan)
    assert out.count("\n") == 1
    assert " " not in out


def test_matrix_keeps_an_empty_shard(tmp_path):
    # Dropping it would make its slice nobody's job; keeping it makes that
    # shard's own `patterns` call fail at once.
    plan = write_plan(tmp_path, {"full": {"shards": [["a*"], []]}})
    assert json.loads(run_cli("matrix", "--plan", plan)) == [
        {"set": "full", "index": 0}, {"set": "full", "index": 1}]


def test_patterns_prints_one_shard_space_joined(tmp_path):
    plan = write_plan(tmp_path, {"full": {"shards": [["a.*", "b.x_f__mutmut_*"], ["c.*"]]}})
    assert run_cli("patterns", "--plan", plan, "--set", "full", "--index", "0") \
        == "a.* b.x_f__mutmut_*\n"
    assert run_cli("patterns", "--plan", plan, "--set", "full", "--index", "1") \
        == "c.*\n"


def test_patterns_refuse_an_empty_shard(tmp_path, capsys):
    plan = write_plan(tmp_path, {"full": {"shards": [["a*"], []]}})
    assert mp.main(["patterns", "--plan", plan, "--set", "full", "--index", "1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no patterns" in captured.err


@pytest.mark.parametrize("name, index", [("diff", 0), ("full", 2), ("full", -1)])
def test_patterns_refuse_an_unknown_set_or_index(tmp_path, capsys, name, index):
    plan = write_plan(tmp_path, {"full": {"shards": [["a*"], ["b*"]]}})
    assert mp.main(["patterns", "--plan", plan, "--set", name,
                    "--index", str(index)]) == 1
    assert capsys.readouterr().out == ""


def test_a_missing_plan_is_an_error_not_an_empty_matrix(tmp_path):
    # A missing plan must not read as `[]` — that is the "nothing to do" answer.
    with pytest.raises(FileNotFoundError):
        mp.main(["matrix", "--plan", str(tmp_path / "absent.json")])


# --------------------------------------------------------------------------
# diff
# --------------------------------------------------------------------------

_M_BASE = (
    "def a(x):\n    return x + 1\n\n\n"
    "def b(x):\n    return a(x) * 2\n\n\n"
    "def c(x):\n    return x - 1\n\n\n"
    "class K:\n    def m(self):\n        return 2 if self else 3\n"
)


def _git(repo: Path, *args: str) -> str:
    # Identity and config come from here, never from the machine's global or
    # system config, so the fixture behaves the same on any runner. The
    # GIT_CONFIG_COUNT injection conftest makes (maintenance.auto=false) is
    # inherited from os.environ untouched.
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
    })
    return subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false",
                           *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


class GitRepo:
    """A two-commit repo: ``base`` holds ``boost_cli/core/m.py``; ``head(files)``
    commits ``files`` on top of it and returns the new SHA."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir()
        _git(root, "init", "-q", "-b", "main")
        self.write({
            "setup.cfg": "[mutmut]\nsource_paths = boost_cli/core/\n",
            "boost_cli/__init__.py": "",
            "boost_cli/core/__init__.py": "",
            "boost_cli/core/m.py": _M_BASE,
        })
        self.base = self._commit("base")
        # mutmut's dependency map: callee -> callers, already qualified.
        self.stats = root.parent / "mutmut-stats.json"
        self.stats.write_text(json.dumps({"function_dependencies": {
            "boost_cli.core.m.x_a": ["boost_cli.core.m.x_b"]}}), encoding="utf-8")

    def write(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            if text is None:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def _commit(self, msg: str) -> str:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", msg)
        return _git(self.root, "rev-parse", "HEAD")

    def head(self, files: dict) -> str:
        self.write(files)
        return self._commit("head")


@pytest.fixture
def git_repo(tmp_path):
    return GitRepo(tmp_path / "repo")


def plan_diff(tmp_path, repo: GitRepo, head: str, *extra: str) -> dict:
    out = tmp_path / "plan.json"
    assert mp.main(["diff", "--base", repo.base, "--head", head,
                    "--stats", str(repo.stats), "--root", str(repo.root),
                    "--shards", "2", "--out", str(out), *extra]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_diff_plan_with_a_trigger_is_full(tmp_path, git_repo):
    head = git_repo.head({"scripts/mutation_new.py": "x = 1\n",
                          "boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    plan = plan_diff(tmp_path, git_repo, head)
    assert plan["gate_set"] == "full"
    assert plan["reasons"] == ["scripts/mutation_new.py changed"]
    assert list(plan["sets"]) == ["full"]
    assert plan["sets"]["full"]["shards"] == [["boost_cli.core.m.*"], []]


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_with_no_core_change_has_zero_shards(tmp_path, git_repo):
    head = git_repo.head({"README.md": "docs\n",
                          "tests/unit/test_m.py": "def test(): pass\n",
                          # a comment is not a change to mutmut's AST hash
                          "boost_cli/core/m.py": "# note\n" + _M_BASE})
    plan = plan_diff(tmp_path, git_repo, head)
    assert plan["gate_set"] == "diff"
    assert plan["sets"]["diff"]["shards"] == []
    assert plan["sets"]["diff"]["mutants"] == 0
    assert plan["reasons"]
    assert run_cli("matrix", "--plan", str(tmp_path / "plan.json")) == "[]\n"


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_scopes_changed_functions_and_direct_callers(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    plan = plan_diff(tmp_path, git_repo, head)
    diff = plan["sets"]["diff"]
    assert plan["gate_set"] == "diff"
    # The diff set alone: the full run no longer rides along on a PR.
    assert list(plan["sets"]) == ["diff"]
    assert diff["functions"] == ["boost_cli.core.m.x_a", "boost_cli.core.m.x_b"]
    patterns = sorted(p for shard in diff["shards"] for p in shard)
    assert patterns == ["boost_cli.core.m.x_a__mutmut_*",
                        "boost_cli.core.m.x_b__mutmut_*"]
    assert diff["mutants"] > 0
    assert all(diff["shards"]), "no empty shard may reach `patterns`"


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_method_names_survive_into_patterns(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("2 if", "4 if")})
    plan = plan_diff(tmp_path, git_repo, head)
    (shard,) = plan["sets"]["diff"]["shards"]
    assert shard == ["boost_cli.core.m.xǁKǁm__mutmut_*"]
    # And the argv the shard gets keeps the name whole.
    assert run_cli("patterns", "--plan", str(tmp_path / "plan.json"),
                   "--set", "diff", "--index", "0") == "boost_cli.core.m.xǁKǁm__mutmut_*\n"


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_new_file_and_deleted_function(tmp_path, git_repo):
    head = git_repo.head({
        "boost_cli/core/m.py": _M_BASE.replace(
            "def c(x):\n    return x - 1\n", "def c(x):\n    pass\n"),
        "boost_cli/core/n.py": "def z(y):\n    return y == 1\n",
    })
    plan = plan_diff(tmp_path, git_repo, head)
    patterns = [p for shard in plan["sets"]["diff"]["shards"] for p in shard]
    # c changed but has no mutants left: listed in scope, never a pattern
    # (a pattern matching nothing makes mutmut assert and the shard die).
    assert "boost_cli.core.m.x_c" in plan["sets"]["diff"]["functions"]
    assert patterns == ["boost_cli.core.n.x_z__mutmut_*"]


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_never_emits_an_empty_shard(tmp_path, git_repo):
    # One function, so packing at 1 mutant/shard asks for more shards than
    # there are functions; the extra bins must not reach the matrix.
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("- 1", "- 9")})
    md = mp._load_diff()
    plan = mp.diff_plan(git_repo.root, git_repo.base, head, git_repo.stats,
                        per_shard=1)
    assert plan["sets"]["diff"]["mutants"] > 1
    assert plan["sets"]["diff"]["shards"] == [[md.pattern("boost_cli.core.m.x_c")]]


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_runs_as_a_script(tmp_path, git_repo):
    # CI runs it as `python scripts/mutation_plan.py diff`, a fresh process
    # where nothing else has imported mutation_diff first.
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    out = tmp_path / "plan.json"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "mutation_plan.py"),
                    "diff", "--base", git_repo.base, "--head", head,
                    "--stats", str(git_repo.stats), "--root", str(git_repo.root),
                    "--out", str(out)], check=True, capture_output=True)
    assert json.loads(out.read_text(encoding="utf-8"))["gate_set"] == "diff"


def test_diff_plan_has_no_shadow_mode(tmp_path, git_repo):
    # It planned the full set beside the diff set and gated on the full one,
    # so the two could be compared before the diff gate was trusted to bind.
    # It binds now, and a plan that gates on full would quietly undo that.
    with pytest.raises(SystemExit):
        mp.main(["diff", "--shadow", "--base", git_repo.base, "--head", git_repo.base,
                 "--stats", str(git_repo.stats), "--root", str(git_repo.root),
                 "--out", str(tmp_path / "plan.json")])
    assert not (tmp_path / "plan.json").exists()


@pytest.mark.usefixtures("needs_mutmut")
def test_diff_plan_records_per_function_counts(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    diff = plan_diff(tmp_path, git_repo, head)["sets"]["diff"]
    assert set(diff["counts"]) == {"boost_cli.core.m.x_a", "boost_cli.core.m.x_b"}
    assert sum(diff["counts"].values()) == diff["mutants"]
    assert all(n > 0 for n in diff["counts"].values())


def _shard_results(tmp_path: Path, spec: dict, survivor: str | None = None) -> Path:
    """What the diff shards would upload for ``spec``: one ``m.py.meta`` per
    shard at the artifact's root (the upload root is ``mutants/boost_cli/core``),
    holding every in-scope mutant killed -- bar ``survivor`` -- and ``None``
    for the file's out-of-scope functions, as a real shard writes them."""
    source = tmp_path / "shard-results" / "diff"
    for index, shard in enumerate(spec["shards"]):
        codes: dict = {"boost_cli.core.m.x_c__mutmut_1": None,
                       "boost_cli.core.m.xǁKǁm__mutmut_1": None}
        for pat in shard:
            q = pat[: -len("__mutmut_*")]
            codes.update({"%s__mutmut_%d" % (q, n): 1
                          for n in range(1, spec["counts"][q] + 1)})
        if survivor in codes:
            codes[survivor] = 0
        meta = source / ("mutation-diff-shard-%d" % index) / "m.py.meta"
        meta.parent.mkdir(parents=True)
        meta.write_text(json.dumps({"exit_code_by_key": codes}), encoding="utf-8")
    return source


@pytest.mark.usefixtures("needs_mutmut")
@pytest.mark.parametrize("survivor, rc, verdict", [
    (None, 0, "PASS"),
    # Under ten mutants in scope, so one survivor fails it.
    ("boost_cli.core.m.x_a__mutmut_1", 1, "FAIL"),
])
def test_the_gate_scores_what_the_planner_actually_writes(
        tmp_path, git_repo, monkeypatch, capsys, survivor, rc, verdict):
    # The gate's own tests write plans by hand. This one feeds it the plan
    # `diff` really writes, so a field the planner stops writing -- or starts
    # writing in a shape the gate refuses -- fails here and not on a PR
    # (Task 6 review N-3).
    md = mp._load_diff()
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    plan = plan_diff(tmp_path, git_repo, head)
    spec, problems = md.validate_plan(plan)
    assert problems == []
    assert spec is not None and spec["mutants"] < 10
    source = _shard_results(tmp_path, spec, survivor)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert md.main(["gate", "--plan", str(tmp_path / "plan.json"),
                    "--source", str(source), "--prefix", "mutation-diff-shard-",
                    "--root", str(git_repo.root)]) == rc
    out = capsys.readouterr().out
    assert "mutation diff gate: %s" % verdict in out
    assert "%d/%d killed" % (spec["mutants"] - bool(survivor), spec["mutants"]) in out
    assert "### Mutation (diff scope): %s" % verdict in summary.read_text(encoding="utf-8")
    warnings = [line for line in out.splitlines() if line.startswith("::warning")]
    if survivor:
        # At `def a` in the head checkout: the line a reviewer acts on.
        assert warnings == ["::warning file=boost_cli/core/m.py,line=1::"
                            "boost_cli.core.m.x_a: 1 mutants not killed: "
                            "%s (survived)" % survivor]
    else:
        assert warnings == []


@pytest.mark.usefixtures("needs_mutmut")
def test_the_gate_passes_the_planners_empty_scope_with_no_artifacts(
        tmp_path, git_repo, capsys):
    md = mp._load_diff()
    head = git_repo.head({"tests/unit/test_m.py": "def test(): pass\n"})
    plan = plan_diff(tmp_path, git_repo, head)
    assert md.validate_plan(plan) == (plan["sets"]["diff"], [])
    assert md.main(["gate", "--plan", str(tmp_path / "plan.json"),
                    "--source", str(tmp_path / "absent"), "--prefix",
                    "mutation-diff-shard-", "--root", str(git_repo.root)]) == 0
    assert "mutation diff gate: PASS" in capsys.readouterr().out


def test_diff_plan_refuses_an_unreadable_blob(tmp_path, git_repo):
    # A path that is in the tree but whose blob git cannot produce (a partial
    # clone whose lazy fetch failed; here, a deleted loose object) must not
    # read as "file deleted" -> empty scope -> pass (review M-3).
    head = git_repo.head({"boost_cli/core/n.py": "def z(y):\n    return y == 13579\n"})
    blob = _git(git_repo.root, "rev-parse", head + ":boost_cli/core/n.py")
    (git_repo.root / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    with pytest.raises(subprocess.CalledProcessError):
        mp.diff_plan(git_repo.root, git_repo.base, head, git_repo.stats)


def test_diff_plan_refuses_an_unknown_revision(tmp_path, git_repo):
    # A bad SHA must not read as "every file missing" -> empty scope -> pass.
    with pytest.raises(subprocess.CalledProcessError):
        mp.main(["diff", "--base", "0" * 40, "--head", git_repo.base,
                 "--stats", str(git_repo.stats), "--root", str(git_repo.root),
                 "--out", str(tmp_path / "plan.json")])


def test_diff_plan_refuses_stats_without_dependencies(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    git_repo.stats.write_text("{}", encoding="utf-8")
    with pytest.raises(KeyError):
        mp.diff_plan(git_repo.root, git_repo.base, head, git_repo.stats)


# --------------------------------------------------------------------------
# base: what the diff planner diffs against
# --------------------------------------------------------------------------

class MergedRepo:
    """``c0`` on main; ``feature`` adds ``c1``; main moves on to ``c2``; then
    ``merge`` is c1 merged into c2, the shape of a PR's ``refs/pull/N/merge``."""

    def __init__(self, root: Path):
        root.mkdir()
        self.root = root
        _git(root, "init", "-q", "-b", "main")
        self.c0 = self._commit("a.txt", "0")
        _git(root, "checkout", "-q", "-b", "feature")
        self.c1 = self._commit("b.txt", "1")
        _git(root, "checkout", "-q", "main")
        self.c2 = self._commit("c.txt", "2")
        _git(root, "merge", "-q", "--no-ff", "-m", "merge", "feature")
        self.merge = _git(root, "rev-parse", "HEAD")
        # The same two commits merged the other way round: main into the
        # branch, so the PR head is the FIRST parent and main the second.
        _git(root, "checkout", "-q", "-b", "reversed", self.c1)
        _git(root, "merge", "-q", "--no-ff", "-m", "reversed", self.c2)
        self.reversed = _git(root, "rev-parse", "HEAD")
        _git(root, "checkout", "-q", "main")

    def _commit(self, name: str, text: str) -> str:
        (self.root / name).write_text(text, encoding="utf-8")
        _git(self.root, "add", name)
        _git(self.root, "commit", "-q", "-m", name)
        return _git(self.root, "rev-parse", "HEAD")


@pytest.fixture
def merged(tmp_path):
    return MergedRepo(tmp_path / "merged")


def test_a_pr_merge_commit_diffs_against_its_first_parent(merged):
    # The PR's own change, exactly as applied to the commit the shards test.
    # base.sha is deliberately stale (c0): the merge commit's parent wins.
    base, why = mp.diff_base(merged.root, "pull_request", merged.merge,
                             base_sha=merged.c0, head_sha=merged.c1)
    assert base == merged.c2
    assert "first parent" in why


def test_a_merge_whose_second_parent_is_not_the_pr_head_falls_back(merged):
    # Parents reversed: trusting parents[0] would make the PR head the base,
    # and the scope would be main's interim changes with the PR's own dropped
    # -- narrower, silently, under a gate that binds (Task 7 review M2).
    base, why = mp.diff_base(merged.root, "pull_request", merged.reversed,
                             base_sha=merged.c2, head_sha=merged.c1)
    assert base == merged.c0
    assert "merge base" in why
    assert "second parent" in why


def test_a_merge_of_some_other_head_falls_back(merged):
    # Two parents, but the second is not the head the event names (a stale
    # head.sha, or a merge commit built from a different push).
    base, why = mp.diff_base(merged.root, "pull_request", merged.merge,
                             base_sha=merged.c2, head_sha=merged.c2)
    assert base == merged.c2      # merge-base(c2, c2)
    assert "merge base" in why


def test_an_abbreviated_head_sha_still_matches_the_second_parent(merged):
    base, why = mp.diff_base(merged.root, "pull_request", merged.merge,
                             base_sha=merged.c0, head_sha=merged.c1[:12])
    assert base == merged.c2
    assert "first parent" in why


def test_a_pr_sha_that_is_no_merge_falls_back_to_the_merge_base(merged):
    # Not two parents (a checkout of the head itself, say): the wider merge
    # base of the event's base and head, and the reason says so.
    base, why = mp.diff_base(merged.root, "pull_request", merged.c1,
                             base_sha=merged.c2, head_sha=merged.c1)
    assert base == merged.c0
    assert "merge base" in why


def test_the_merge_queue_diffs_against_its_base_sha(merged):
    base, why = mp.diff_base(merged.root, "merge_group", merged.merge,
                             base_sha=merged.c2, head_sha=merged.merge)
    assert base == merged.c2
    assert "base_sha" in why


@pytest.mark.parametrize("event", ["push", "schedule", ""])
def test_no_other_event_has_a_diff_base(merged, event):
    with pytest.raises(ValueError):
        mp.diff_base(merged.root, event, merged.merge, base_sha=merged.c2,
                     head_sha=merged.c1)


@pytest.mark.parametrize("event, sha, base_sha, head_sha", [
    ("pull_request", "0" * 40, "c2", "c1"),     # the commit under test is unknown
    ("pull_request", "c1", "", "c1"),           # no merge commit, and no base to widen to
    # A merge commit, but no head to check its second parent against: the
    # first parent is no longer taken on trust, and there is nothing to widen to.
    ("pull_request", "merge", "c2", ""),
    ("pull_request", "merge", "c2", "0" * 40),
    ("merge_group", "merge", "", "c1"),         # the queue sent no base
    ("merge_group", "merge", "0" * 40, "c1"),   # or one this clone lacks
])
def test_an_unusable_sha_is_an_error_never_a_guess(merged, event, sha, base_sha, head_sha):
    sha = getattr(merged, sha, sha)
    base_sha = getattr(merged, base_sha, base_sha)
    head_sha = getattr(merged, head_sha, head_sha)
    with pytest.raises(subprocess.CalledProcessError):
        mp.diff_base(merged.root, event, sha, base_sha=base_sha, head_sha=head_sha)


def test_base_prints_the_sha_alone_and_logs_why(merged, capsys):
    assert mp.main(["base", "--root", str(merged.root), "--event", "pull_request",
                    "--sha", merged.merge, "--base-sha", merged.c0,
                    "--head-sha", merged.c1]) == 0
    out, err = capsys.readouterr()
    assert out == merged.c2 + "\n"        # captured by $(...) in ci.yml
    assert "first parent" in err


def test_base_failure_prints_nothing_on_stdout(merged, capsys):
    assert mp.main(["base", "--root", str(merged.root), "--event", "push",
                    "--sha", merged.merge, "--base-sha", "", "--head-sha", ""]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "no diff base" in err


# --------------------------------------------------------------------------
# ci.yml wiring
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def jobs():
    # Guarded here rather than at module level, so the planner tests above
    # still run where PyYAML is absent; only the workflow tests need it.
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]


def _run_text(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job.get("steps", []))


def test_the_gate_always_runs(jobs):
    assert jobs["mutation"]["if"] == "always()"
    assert set(jobs["mutation"]["needs"]) == {"mutation-plan", "mutation-shard"}


def test_the_gate_fails_when_the_planner_did_not_succeed(jobs):
    # A failed planner leaves its outputs empty, and an empty matrix is the
    # "nothing to run" answer — so the gate must look at the planner's RESULT,
    # not only at its matrix.
    for step in jobs["mutation"]["steps"]:
        env = step.get("env", {})
        if any("needs.mutation-plan.result" in str(v) for v in env.values()):
            var = next(k for k, v in env.items()
                       if "needs.mutation-plan.result" in str(v))
            run = step["run"]
            assert '"$%s" != "success"' % var in run
            after = run.split('"$%s" != "success"' % var, 1)[1]
            assert "exit 1" in after.split("fi", 1)[0]
            assert "if" not in step, "the conclusive check must never be skipped"
            return
    pytest.fail("no step in `mutation` inspects needs.mutation-plan.result")


def test_the_gate_fails_when_a_shard_did_not_succeed(jobs):
    run = _run_text(jobs["mutation"])
    assert "needs.mutation-shard.result" in json.dumps(jobs["mutation"])
    assert "a mutation shard did not succeed" in run


def test_no_shard_restores_a_cache(jobs):
    for step in jobs["mutation-shard"]["steps"]:
        assert not step.get("uses", "").startswith("actions/cache"), step


def test_the_shard_matrix_comes_from_the_plan(jobs):
    shard = jobs["mutation-shard"]
    assert "needs.mutation-plan.outputs.matrix" in shard["strategy"]["matrix"]["include"]
    assert "needs.mutation-plan.outputs.matrix" in shard["if"]
    assert "'[]'" in shard["if"]
    assert shard["needs"] == "mutation-plan" or shard["needs"] == ["mutation-plan"]


def test_each_shard_restores_the_stats_before_running(jobs):
    # The whole saving: without the stats file in mutants/, mutmut re-runs
    # the full `Running stats` phase in every shard.
    run = _run_text(jobs["mutation-shard"])
    copy = run.index("mutmut-stats.json")
    assert copy < run.index("mutmut run"), "stats must be in place before mutmut runs"
    assert "mutation_plan.py patterns" in run


def test_the_planner_uploads_plan_and_stats(jobs):
    uploads = {s["with"]["name"]: s["with"]
               for s in jobs["mutation-plan"]["steps"]
               if s.get("uses", "").startswith("actions/upload-artifact")}
    assert set(uploads) == {"mutation-plan", "mutation-stats"}
    for spec in uploads.values():
        assert spec["if-no-files-found"] == "error"


def test_the_planner_and_shards_share_one_environment(jobs):
    # Stats collected under a different Python or install set can collect a
    # different test set; a shard then sees "new" test ids and re-collects,
    # silently undoing the whole point of the planner.
    def python(job):
        return [s["with"]["python-version"] for s in job["steps"]
                if s.get("uses", "").startswith("actions/setup-python")]

    def installs(job):
        return sorted(line.strip() for line in _run_text(job).splitlines()
                      if "pip -q install" in line)

    plan, shard = jobs["mutation-plan"], jobs["mutation-shard"]
    assert python(plan) == python(shard) != []
    assert installs(plan) == installs(shard) != []


def _stats_mutant(jobs) -> str:
    for step in jobs["mutation-plan"]["steps"]:
        name = step.get("env", {}).get("STATS_MUTANT")
        if name:
            return name
    pytest.fail("the planner's stats step has no STATS_MUTANT")


def test_the_stats_mutant_is_one_exact_name(jobs):
    # A glob never matches a key of mutmut's tests_by_mangled_function_name,
    # so its clean run falls back to the whole unit suite: measured, 27.4 min
    # for the planner instead of 15.1.
    name = _stats_mutant(jobs)
    assert not set("*?[") & set(name), name
    assert name.rpartition("__mutmut_")[2].isdigit(), name


def test_the_stats_mutant_names_a_real_function(jobs):
    # mutmut asserts "Filtered for specific mutants, but nothing matches" on a
    # name with no mutant, so renaming this function would red every PR's
    # planner. Pin it here, where the rename shows up as a one-line failure.
    name = _stats_mutant(jobs)
    head = name.rpartition("__mutmut_")[0]
    module, _, mangled = head.rpartition(".")
    assert mangled.startswith("x_"), name
    func = mangled[len("x_"):]
    path = ROOT / (module.replace(".", "/") + ".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = [n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert func in names, "%s names no top-level function in %s" % (name, path)


def test_shard_artifacts_are_named_by_set(jobs):
    shard_uploads = [s["with"]["name"] for s in jobs["mutation-shard"]["steps"]
                     if s.get("uses", "").startswith("actions/upload-artifact")]
    assert shard_uploads == ["mutation-${{ matrix.set }}-shard-${{ matrix.index }}"]
    downloads = [s["with"].get("pattern") for s in jobs["mutation"]["steps"]
                 if s.get("uses", "").startswith("actions/download-artifact")]
    assert "mutation-full-shard-*" in downloads
    assert "--prefix mutation-full-shard-" in _run_text(jobs["mutation"])
    assert "mutation-diff-shard-*" in downloads


# --------------------------------------------------------------------------
# ci.yml wiring: the gate the plan names binds (diff on PRs, full elsewhere)
# --------------------------------------------------------------------------
#
# The static checks pin where things are; the bash-driven ones below run the
# steps' own shell, with stubs for python and git, because what matters is the
# exit code each combination of upstream results produces, and a regex over a
# `case` statement cannot tell `exit 1` in the wrong arm from the right one.

needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or not shutil.which("bash") or not shutil.which("jq"),
    reason="runs a workflow step's bash, which needs bash and jq (ubuntu runners have both)")

MUTATION_JOBS = ("mutation-plan", "mutation-shard", "mutation")


def _step(job: dict, *, name: str | None = None, step_id: str | None = None,
          runs: str | None = None) -> dict:
    found = [s for s in job["steps"]
             if (name is None or s.get("name") == name)
             and (step_id is None or s.get("id") == step_id)
             and (runs is None or runs in s.get("run", ""))]
    assert len(found) == 1, "expected one step (name=%r id=%r runs=%r), found %d" % (
        name, step_id, runs, len(found))
    return found[0]


def _uploads(job: dict) -> dict:
    return {s["with"]["name"]: s for s in job["steps"]
            if s.get("uses", "").startswith("actions/upload-artifact")}


def _downloads(job: dict) -> dict:
    return {s["with"].get("pattern") or s["with"].get("name"): s for s in job["steps"]
            if s.get("uses", "").startswith("actions/download-artifact")}


def _stub(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _bash(step: dict, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    # `bash -e {0}` is what an ubuntu runner runs a `run:` with when the job
    # sets no `shell:` -- note: no pipefail, which is why a step must capture
    # an exit code itself rather than read it through a pipe.
    script = cwd / "step.sh"
    script.write_text(step["run"], encoding="utf-8")
    full = {"PATH": os.environ["PATH"], "HOME": str(cwd)}
    full.update(env)
    return subprocess.run(["bash", "-e", str(script)], cwd=cwd, env=full,
                          capture_output=True, text=True)


def _outputs(path: Path) -> dict:
    return dict(line.split("=", 1) for line in
                path.read_text(encoding="utf-8").splitlines() if "=" in line)


def test_no_mutation_job_expands_an_expression_inside_run(jobs):
    # zizmor's template-injection class, wholesale: every `${{ }}` a `run:`
    # needs goes through `env:` -- matrix values and job outputs included.
    for name in MUTATION_JOBS:
        for step in jobs[name]["steps"]:
            assert "${{" not in step.get("run", ""), (name, step.get("name"))


def test_the_planner_checkout_has_every_object(jobs):
    # The diff planner reads base and head blobs with `git show`; a shallow
    # or blob-filtered clone makes that fail (or, worse, a lazy fetch fail).
    (checkout,) = [s for s in jobs["mutation-plan"]["steps"]
                   if s.get("uses", "").startswith("actions/checkout")]
    assert checkout["with"]["fetch-depth"] == 0
    assert "filter" not in checkout["with"]


def test_the_planner_asks_mutation_plan_base_for_the_diff_base(jobs):
    # The choice (merge commit's first parent, else the merge base; the
    # queue's base_sha) lives in `mutation_plan.py base`, unit-tested above;
    # the step only hands it the event's facts.
    step = _step(jobs["mutation-plan"], step_id="plan")
    env = step["env"]
    assert env["EVENT"] == "${{ github.event_name }}"
    assert env["BASE_SHA"] == ("${{ github.event.pull_request.base.sha"
                               " || github.event.merge_group.base_sha }}")
    assert env["HEAD_SHA"] == ("${{ github.event.pull_request.head.sha"
                               " || github.event.merge_group.head_sha }}")
    assert ('python3 scripts/mutation_plan.py base --event "$EVENT" --sha "$GITHUB_SHA"'
            ' --base-sha "$BASE_SHA" --head-sha "$HEAD_SHA"') in " ".join(
        w for w in step["run"].split() if w != "\\")   # line continuations
    assert "git merge-base" not in step["run"]


def test_the_shadow_run_is_gone(jobs):
    # The diff gate binds on PRs now; the full run that ran beside it, the
    # per-mutant comparison and its report were the evidence for that switch
    # and are not run any more. Nothing may keep planning or reading them.
    assert "shadow" not in jobs["mutation-plan"]["outputs"]
    assert "--shadow" not in _run_text(jobs["mutation-plan"])
    text = CI.read_text(encoding="utf-8")
    assert "mutation_diff.py compare" not in text
    assert "mutation-shadow-report" not in text
    assert "outputs.shadow" not in text
    assert "--no-annotations" not in text


class TestPlannerByEvent:
    """Run the `write the plan` step's bash with python and git stubbed."""

    @pytest.fixture
    def planner(self, jobs, tmp_path):
        step = _step(jobs["mutation-plan"], step_id="plan")
        bin_dir = tmp_path / "bin"
        calls = tmp_path / "calls.log"
        # One stub for both interpreters: it logs which one ran ($0) and writes
        # a plan of the shape the real subcommand would, so the step's own jq
        # and matrix lines run against something real.
        stub = r'''
echo "$0 $*" >> "$CALLS"
out=""; prev=""
for a in "$@"; do [ "$prev" = "--out" ] && out="$a"; prev="$a"; done
case " $* " in
  *" matrix "*) echo '[{"set":"full","index":0}]'; exit 0 ;;
  *"mutation_plan.py base "*) [ -n "$BASE_FAIL" ] && exit 1; echo forkpoint0; exit 0 ;;
  *"mutation_plan.py diff "*) plan='{"gate_set":"diff","reasons":["d"],"sets":{"diff":{"shards":[["a"]],"mutants":3}}}' ;;
  *" none "*) plan='{"gate_set":null,"reasons":["n"],"sets":{}}' ;;
  *) plan='{"gate_set":"full","reasons":[],"sets":{"full":{"shards":[["a"]]}}}' ;;
esac
[ -n "$PLAN_OVERRIDE" ] && plan="$PLAN_OVERRIDE"
[ -n "$out" ] && echo "$plan" > "$out"
exit 0
'''
        _stub(bin_dir / "python3", stub)
        _stub(tmp_path / ".venv" / "bin" / "python", stub)
        _stub(bin_dir / "git", r'''
echo "git $*" >> "$CALLS"
if [ "$1" = merge-base ]; then
  [ -n "$MB_FAIL" ] && exit 128
  echo forkpoint0; exit 0
fi
exit 0
''')

        def run(event: str, relevant: str = "true", **extra: str):
            out = tmp_path / "github_output"
            out.write_text("", encoding="utf-8")
            env = {"PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
                   "CALLS": str(calls), "GITHUB_OUTPUT": str(out),
                   "GITHUB_SHA": "mergecommit0", "EVENT": event, "RELEVANT": relevant,
                   "BASE_SHA": "basetip0" if event != "push" else "",
                   "HEAD_SHA": "prhead0" if event != "push" else ""}
            env.update(extra)
            proc = _bash(step, tmp_path, env)
            assert proc.returncode == 0, proc.stdout + proc.stderr
            log = calls.read_text(encoding="utf-8").splitlines()
            calls.unlink()
            plans = [line for line in log if "--out mutation-plan.json" in line]
            assert len(plans) == 1, log
            # The helper owns every git question; the step asks none itself.
            assert not any(line.startswith("git ") for line in log), log
            return plans[0], log, _outputs(out)
        return run

    @pytest.mark.parametrize("event", ["pull_request", "merge_group"])
    def test_prs_and_the_queue_plan_diff_and_bind_on_it(self, planner, event):
        plan, log, outputs = planner(event)
        assert plan.startswith(".venv/bin/python scripts/mutation_plan.py diff "), plan
        # No shadow: the diff set alone, and the gate binds on it.
        assert "--shadow" not in plan
        # The full set's width when a trigger in the diff forces the full run.
        assert " --shards 24 " in plan
        # The base comes from `mutation_plan.py base`, given the event's facts ...
        assert any("mutation_plan.py base --event %s --sha mergecommit0 --base-sha basetip0 "
                   "--head-sha prhead0" % event in line for line in log), log
        assert " --base forkpoint0 " in plan
        # ... but the far end is the commit every shard checks out and the
        # stats were taken at. The PR head would count mutants of a tree no
        # shard mutates, and the gate refuses a shortfall as INCOMPLETE.
        assert " --head mergecommit0 " in plan
        assert " --stats mutants/mutmut-stats.json " in plan
        assert outputs["gate_set"] == "diff"
        assert "shadow" not in outputs

    @pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
    def test_everything_else_plans_full(self, planner, event):
        plan, log, outputs = planner(event)
        assert "python3 scripts/mutation_plan.py full --shards 24 " in plan
        assert not any("mutation_plan.py base " in line for line in log)
        assert outputs["gate_set"] == "full"

    def test_no_diff_base_falls_back_to_full(self, planner):
        # A missing or unfetched base must widen the gate, never empty it.
        plan, _, outputs = planner("pull_request", BASE_FAIL="1")
        assert "scripts/mutation_plan.py full --shards 24 " in plan
        assert outputs["gate_set"] == "full"

    @pytest.mark.parametrize("event", ["pull_request", "push"])
    def test_an_irrelevant_change_plans_nothing(self, planner, event):
        plan, log, outputs = planner(event, relevant="false")
        assert "scripts/mutation_plan.py none " in plan
        assert not any("mutation_plan.py base " in line for line in log)
        assert outputs["gate_set"] == ""

    def test_a_proven_push_plans_nothing_and_names_the_run(self, planner):
        # `proven` said this tree is the one a green PR run tested: no shards,
        # and a reason that says which run, not "nothing changed".
        plan, _, outputs = planner("push", relevant="false", PROVEN="true",
                                   PR_RUN_ID="4242")
        assert "scripts/mutation_plan.py none --reason proven by PR run 4242 " in plan
        assert outputs["gate_set"] == ""

    def test_an_unproven_irrelevant_push_keeps_its_old_reason(self, planner):
        plan, _, _ = planner("push", relevant="false")
        # The tail only: the stub logs its own path, which holds the test name.
        reason = plan.split(" none ", 1)[1]
        assert "proven" not in reason
        assert reason.startswith("--reason no change under boost_cli/")

    @pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
    def test_a_whole_codebase_run_plans_full_and_says_so(self, planner, event):
        plan, _, outputs = planner(event)
        assert "python3 scripts/mutation_plan.py full --shards 24 " in plan
        assert "whole-codebase run (%s)" % event in plan
        assert outputs["gate_set"] == "full"

    def test_the_plan_reason_is_one_line_for_the_gate_summary(self, planner):
        _, _, outputs = planner("push", relevant="false")
        assert outputs["reason"] == "n"

    def test_a_reason_with_a_newline_cannot_start_another_output(self, planner, tmp_path):
        # A raw newline in `reason=` would end that output and let the rest of
        # the line set any other one, e.g. gate_set.
        plan = {"gate_set": None, "sets": {},
                "reasons": ["a\ngate_set=full", "b\r", "x" * 600]}
        _, _, outputs = planner("push", relevant="false",
                                PLAN_OVERRIDE=json.dumps(plan))
        assert outputs["gate_set"] == ""
        assert outputs["reason"].startswith("a gate_set=full; b ; xxx")
        assert len(outputs["reason"]) == 500
        out = (tmp_path / "github_output").read_text(encoding="utf-8")
        assert sum(line.startswith("gate_set=") for line in out.splitlines()) == 1


class TestScopeByEvent:
    """Run the `can the mutation score have changed?` step's bash, stubbed."""

    @pytest.fixture
    def scope(self, jobs, tmp_path):
        step = _step(jobs["mutation-plan"], step_id="scope")
        bin_dir = tmp_path / "bin"
        calls = tmp_path / "calls.log"
        _stub(bin_dir / "git", 'echo "git $*" >> "$CALLS"\nexit 0\n')
        _stub(bin_dir / "python3", 'echo "python3 $*" >> "$CALLS"\necho true\n')

        def run(event: str, **extra: str):
            out = tmp_path / "github_output"
            out.write_text("", encoding="utf-8")
            calls.write_text("", encoding="utf-8")
            env = {"PATH": "%s%s%s" % (bin_dir, os.pathsep, os.environ["PATH"]),
                   "CALLS": str(calls), "GITHUB_OUTPUT": str(out), "EVENT": event,
                   "BASE": "base0" if event != "schedule" else "", "HEAD": "head0"}
            env.update(extra)
            proc = _bash(step, tmp_path, env)
            assert proc.returncode == 0, proc.stdout + proc.stderr
            return _outputs(out), calls.read_text(encoding="utf-8").splitlines()
        return run

    def test_the_step_reads_proven_through_env(self, jobs):
        env = _step(jobs["mutation-plan"], step_id="scope")["env"]
        assert env["EVENT"] == "${{ github.event_name }}"
        assert env["SKIP"] == "${{ needs.proven.outputs.skip }}"
        assert env["PR_RUN_ID"] == "${{ needs.proven.outputs.pr_run_id }}"

    def test_a_proven_push_collects_nothing(self, scope):
        # relevant=false is what skips the stats run, the planner tests and
        # the stats upload: the 15 minutes this push does not need.
        outputs, calls = scope("push", SKIP="true", PR_RUN_ID="4242")
        assert outputs == {"relevant": "false", "proven": "true"}
        assert calls == []

    @pytest.mark.parametrize("skip", ["false", ""])
    def test_an_unproven_push_asks_the_diff(self, scope, skip):
        outputs, calls = scope("push", SKIP=skip)
        assert outputs == {"relevant": "true"}
        assert any("mutation_shards.py scope" in c for c in calls), calls

    @pytest.mark.parametrize("event", ["pull_request", "merge_group"])
    def test_skip_means_nothing_off_a_push(self, scope, event):
        # `proven` never runs there, so a stray value must not be trusted.
        outputs, _ = scope(event, SKIP="true", PR_RUN_ID="1")
        assert "proven" not in outputs
        assert outputs["relevant"] == "true"

    @pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
    def test_a_whole_codebase_run_is_always_relevant(self, scope, event):
        # Decided by the event, not by `github.event.before` happening to be
        # empty: even with a base to diff against, the nightly runs it all.
        outputs, calls = scope(event, BASE="base0")
        assert outputs == {"relevant": "true"}
        assert calls == []


FULL2 = '[{"set":"full","index":0},{"set":"full","index":1}]'
DIFF1 = '[{"set":"diff","index":0}]'
DIFF2 = '[{"set":"diff","index":0},{"set":"diff","index":1}]'
#: The plan the old shadow mode ran: both sets in one matrix. Nothing plans it
#: now, and the conclusive step refuses it rather than gate on half of it.
MIXED = '[{"set":"full","index":0},{"set":"diff","index":0}]'

GATES = "needs.mutation-plan.outputs.gate_set == '%s'"
FULL_OR_DIFF = "%s || %s" % (GATES % "full", GATES % "diff")


@needs_bash
@pytest.mark.parametrize("plan, shards, matrix, gate_set, rc", [
    # nothing mutable changed: no shards, and the plan gates on nothing
    ("success", "skipped", "[]", "", 0),
    # the planner did not finish: its empty outputs must not read as "none"
    ("failure", "skipped", "", "", 1),
    ("cancelled", "skipped", "", "", 1),
    # push / schedule / dispatch, or a PR with a full-run trigger: full
    ("success", "success", FULL2, "full", 0),
    ("success", "failure", FULL2, "full", 1),
    ("success", "cancelled", FULL2, "full", 1),
    # a full gate with nothing to score
    ("success", "skipped", "[]", "full", 1),
    # PR / merge_group: the diff gate binds
    ("success", "success", DIFF1, "diff", 0),
    ("success", "failure", DIFF1, "diff", 1),
    ("success", "cancelled", DIFF2, "diff", 1),
    # no core function with mutants changed: the planner's empty scope
    ("success", "skipped", "[]", "diff", 0),
    # shards with no gate to score them would go green ungated (T1 M3 / T7 M1)
    ("success", "success", FULL2, "", 1),
    ("success", "success", DIFF1, "", 1),
    # unknown gate sets, and a matrix holding a set the gate does not score
    ("success", "success", FULL2, "bogus", 1),
    ("success", "skipped", "[]", "bogus", 1),
    ("success", "success", MIXED, "full", 1),
    ("success", "success", MIXED, "diff", 1),
    ("success", "success", DIFF1, "full", 1),
    # an unreadable matrix is not an empty one
    ("success", "success", "not json", "diff", 1),
])
def test_the_gate_is_conclusive_for_every_upstream_outcome(
        jobs, tmp_path, plan, shards, matrix, gate_set, rc):
    step = _step(jobs["mutation"], name="upstream jobs must be conclusive")
    assert "if" not in step, "the conclusive check must never be skipped"
    assert "continue-on-error" not in step
    assert "SHADOW" not in step["env"]
    proc = _bash(step, tmp_path, {"PLAN": plan, "SHARDS": shards, "MATRIX": matrix,
                                  "GATE_SET": gate_set})
    assert proc.returncode == rc, proc.stdout + proc.stderr
    if rc:
        assert "::error::" in proc.stdout


def test_full_and_diff_results_download_to_separate_dirs(jobs):
    job = jobs["mutation"]
    downloads = _downloads(job)
    full, diff = downloads["mutation-full-shard-*"], downloads["mutation-diff-shard-*"]
    full_dir, diff_dir = full["with"]["path"], diff["with"]["path"]
    assert full_dir != diff_dir
    assert not full_dir.startswith(diff_dir) and not diff_dir.startswith(full_dir)
    assert full["if"] == GATES % "full"
    assert diff["if"] == GATES % "diff"
    # Every consumer reads the dir its set landed in.
    merge = _step(job, runs="mutation_shards.py merge")["run"]
    assert "--source %s " % full_dir in merge
    assert "--prefix mutation-full-shard-" in merge
    gate = _step(job, runs="mutation_diff.py gate")["run"]
    assert "--source %s " % diff_dir in gate
    assert "--prefix mutation-diff-shard-" in gate
    # The diff gate reads the plan the shards ran from; the summary reads it
    # in either mode.
    assert downloads["mutation-plan"]["if"] == FULL_OR_DIFF
    assert '--plan "$RUNNER_TEMP/mutation-plan/mutation-plan.json"' in gate


def test_no_mutation_step_continues_on_error(jobs):
    # The gate `gate_set` names is the verdict. A lenient step anywhere in the
    # three jobs is a way for a failure to read as green.
    for name in MUTATION_JOBS:
        lenient = [s.get("name") or s.get("uses") for s in jobs[name]["steps"]
                   if s.get("continue-on-error")]
        assert lenient == [], (name, lenient)


def test_the_diff_gate_binds_when_the_plan_gates_on_diff(jobs):
    job = jobs["mutation"]
    gate = _step(job, runs="mutation_diff.py gate")
    assert gate["if"] == GATES % "diff"
    assert "continue-on-error" not in gate
    run = " ".join(w for w in gate["run"].split() if w != "\\")
    assert run.startswith(".venv/bin/python scripts/mutation_diff.py gate ")
    # Binding, so survivors are annotated at their `def` in this checkout.
    assert '--root "$GITHUB_WORKSPACE"' in run
    assert "--no-annotations" not in run
    # Its verdict is the step's exit code: no `|| true`, no `set +e`.
    assert "||" not in run and "set +e" not in run
    # The one step of the job that runs it.
    others = "\n".join(s.get("run", "") for s in job["steps"] if s is not gate)
    assert "mutation_diff.py" not in others


def test_the_binding_gate_is_the_one_gate_set_names(jobs):
    job = jobs["mutation"]
    gate = _step(job, runs="scripts/mutation_gate.py")
    assert gate["if"] == GATES % "full"
    assert "continue-on-error" not in gate
    # The merge it scores comes from full shards only, and is what the weights
    # are measured from: a diff run's partial weights would repack on a sliver.
    assert "--into mutants " in _step(job, runs="mutation_shards.py merge")["run"]
    assert _step(job, runs="mutation_shards.py merge")["if"] == GATES % "full"
    weights = _uploads(job)["mutation-weights"]
    assert weights["if"] == GATES % "full"
    assert _step(job, runs="mutation_shards.py weights")["if"] == GATES % "full"
    assert "--source mutants" in _step(job, runs="mutation_shards.py weights")["run"]


def test_both_gates_get_the_checkout_and_venv_they_run_in(jobs):
    job = jobs["mutation"]
    steps = job["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    python = next(s for s in steps if s.get("uses", "").startswith("actions/setup-python"))
    venv = _step(job, runs="requirements/mutation-tools.txt")
    for step in (checkout, python, venv):
        assert step["if"] == FULL_OR_DIFF, step
    first_gate = min(steps.index(_step(job, runs="mutation_diff.py gate")),
                     steps.index(_step(job, runs="mutation_shards.py merge")))
    assert max(steps.index(s) for s in (checkout, python, venv)) < first_gate


def _diff_gate_tree(tmp_path: Path) -> Path:
    """A workspace where the gate step's own command runs the real gate:
    ``.venv/bin/python`` is this interpreter, ``scripts/`` the repo's."""
    _stub(tmp_path / ".venv" / "bin" / "python", 'exec "%s" "$@"\n' % sys.executable)
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    runner_temp = tmp_path / "runner-temp"
    (runner_temp / "mutation-plan").mkdir(parents=True)
    return runner_temp


@needs_bash
@pytest.mark.parametrize("case, rc, verdict", [
    ("empty scope", 0, "PASS"),        # zero shards: nothing to score
    ("all killed", 0, "PASS"),
    ("survivor", 1, "FAIL"),           # under ten mutants, so one fails it
    ("shard missing", 2, "INCOMPLETE"),
])
def test_the_diff_gate_step_is_the_verdict(jobs, tmp_path, request, case, rc, verdict):
    if case in ("all killed", "survivor"):
        request.getfixturevalue("needs_mutmut")   # scoring reads mutmut's statuses
    step = _step(jobs["mutation"], runs="mutation_diff.py gate")
    runner_temp = _diff_gate_tree(tmp_path)
    q = "boost_cli.core.m.x_a"
    if case == "empty scope":
        spec = {"shards": [], "mutants": 0, "functions": [], "counts": {}}
    else:
        spec = {"shards": [[q + "__mutmut_*"]], "mutants": 2, "functions": [q],
                "counts": {q: 2}}
    (runner_temp / "mutation-plan" / "mutation-plan.json").write_text(json.dumps(
        {"gate_set": "diff", "reasons": ["test"], "sets": {"diff": spec}}),
        encoding="utf-8")
    if case in ("all killed", "survivor"):
        diff_dir = _downloads(jobs["mutation"])["mutation-diff-shard-*"]["with"]["path"]
        meta = tmp_path / diff_dir / "mutation-diff-shard-0" / "m.py.meta"
        meta.parent.mkdir(parents=True)
        meta.write_text(json.dumps({"exit_code_by_key": {
            q + "__mutmut_1": 1, q + "__mutmut_2": 0 if case == "survivor" else 1}}),
            encoding="utf-8")
        core = tmp_path / "boost_cli" / "core"
        core.mkdir(parents=True)
        (core / "m.py").write_text("def a(x):\n    return x + 1\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    proc = _bash(step, tmp_path, {"RUNNER_TEMP": str(runner_temp),
                                  "GITHUB_WORKSPACE": str(tmp_path),
                                  "GITHUB_STEP_SUMMARY": str(summary)})
    assert proc.returncode == rc, proc.stdout + proc.stderr
    assert "mutation diff gate: %s" % verdict in proc.stdout
    # The binding verdict is the summary's own heading now, not a section
    # inside an advisory report.
    assert "### Mutation (diff scope): %s" % verdict in summary.read_text(encoding="utf-8")
    if case == "survivor":
        assert "::warning file=boost_cli/core/m.py,line=1::" in proc.stdout


def _summary(jobs, tmp_path: Path, plan: dict, matrix: str, reason: str) -> str:
    step = _step(jobs["mutation"], name="what the plan runs")
    runner_temp = tmp_path / "runner-temp"
    (runner_temp / "mutation-plan").mkdir(parents=True)
    (runner_temp / "mutation-plan" / "mutation-plan.json").write_text(
        json.dumps(plan), encoding="utf-8")
    summary = tmp_path / "summary.md"
    proc = _bash(step, tmp_path, {"RUNNER_TEMP": str(runner_temp),
                                  "GITHUB_STEP_SUMMARY": str(summary),
                                  "GATE_SET": plan["gate_set"] or "",
                                  "MATRIX": matrix, "REASON": reason})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return summary.read_text(encoding="utf-8")


def test_the_summary_step_reads_the_plan_through_env(jobs):
    step = _step(jobs["mutation"], name="what the plan runs")
    assert step["if"] == FULL_OR_DIFF
    assert step["env"] == {"GATE_SET": "${{ needs.mutation-plan.outputs.gate_set }}",
                           "MATRIX": "${{ needs.mutation-plan.outputs.matrix }}",
                           "REASON": "${{ needs.mutation-plan.outputs.reason }}"}
    # Before the completeness check and either gate, so a missing shard or a
    # red gate still leaves the plan in the summary; after the plan arrives.
    job = jobs["mutation"]
    steps = job["steps"]
    at = steps.index(step)
    assert steps.index(_downloads(job)["mutation-plan"]) < at
    for later in (_step(job, name=COMPLETE), _step(job, runs="mutation_diff.py gate"),
                  _step(job, runs="mutation_shards.py merge")):
        assert at < steps.index(later), later.get("name")


@needs_bash
def test_the_summary_names_mode_reasons_mutants_and_shards(jobs, tmp_path):
    plan = {"gate_set": "diff", "reasons": ["diff scope: 36 mutants in 2 functions"],
            "sets": {"diff": {"shards": [["a"], ["b"]], "mutants": 36}}}
    text = _summary(jobs, tmp_path, plan, DIFF2, "diff scope: 36 mutants in 2 functions")
    assert "Mutation plan: diff" in text
    assert "diff scope: 36 mutants in 2 functions" in text
    assert "**Mutants:** 36" in text
    assert "**Shards:** 2" in text
    assert "no core function changed" not in text


@needs_bash
def test_an_empty_diff_scope_says_no_core_function_changed(jobs, tmp_path):
    plan = {"gate_set": "diff", "reasons": ["diff scope: no boost_cli/core function changed"],
            "sets": {"diff": {"shards": [], "mutants": 0}}}
    text = _summary(jobs, tmp_path, plan, "[]", plan["reasons"][0])
    assert "**Mutants:** 0" in text
    assert "**Shards:** 0" in text
    assert "no core function changed" in text


@needs_bash
def test_a_full_plan_says_its_mutants_are_not_counted(jobs, tmp_path):
    # The planner never generates the full set's mutants, so it has no count;
    # the summary must not print that as 0.
    plan = {"gate_set": "full", "reasons": ["whole-codebase run (schedule)"],
            "sets": {"full": {"shards": [["x"], ["y"]], "mutants": None}}}
    text = _summary(jobs, tmp_path, plan, FULL2, "whole-codebase run (schedule)")
    assert "Mutation plan: full" in text
    assert "**Mutants:** not counted" in text
    assert "**Shards:** 2" in text


COMPLETE = "every planned shard uploaded results"


@needs_bash
@pytest.mark.parametrize("matrix, present, rc", [
    (FULL2, ["full/mutation-full-shard-0", "full/mutation-full-shard-1"], 0),
    (FULL2, ["full/mutation-full-shard-0"], 1),
    (DIFF2, ["diff/mutation-diff-shard-0", "diff/mutation-diff-shard-1"], 0),
    (DIFF2, ["diff/mutation-diff-shard-1"], 1),
    # zero diff shards: nothing was planned, so nothing is missing
    ("[]", [], 0),
])
def test_every_planned_shard_must_have_uploaded(jobs, tmp_path, matrix, present, rc):
    job = jobs["mutation"]
    step = _step(job, name=COMPLETE)
    assert step["if"] == FULL_OR_DIFF
    assert "continue-on-error" not in step
    root = Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    for rel in present:
        (tmp_path / root / rel).mkdir(parents=True)
    proc = _bash(step, tmp_path, {"MATRIX": matrix})
    assert proc.returncode == rc, proc.stdout + proc.stderr


@needs_bash
def test_an_unreadable_matrix_is_red_not_an_empty_check(jobs, tmp_path):
    # jq ran inside `< <(...)`, whose exit status nothing sees: a jq failure
    # read as "no shards planned" and the step passed (Task 7 review M4).
    proc = _bash(_step(jobs["mutation"], name=COMPLETE), tmp_path, {"MATRIX": "not json"})
    assert proc.returncode != 0, proc.stdout + proc.stderr


@needs_bash
@pytest.mark.parametrize("set_name, matrix", [("diff", DIFF1), ("full", '[{"set":"full","index":0}]')])
def test_a_lone_shard_downloaded_flat_is_put_back_under_its_name(
        jobs, tmp_path, set_name, matrix):
    # download-artifact (v8.0.2, src/download-artifact.ts) writes a pattern
    # download that matches ONE artifact straight into `path:`, with no
    # <artifact-name>/ level -- `artifacts.length === 1 ? resolvedPath : ...`.
    # One diff shard is the commonest diff plan, so without this every such
    # PR's binding gate would read "no artifact at ...shard-0" and go red.
    job = jobs["mutation"]
    step = _step(job, name=COMPLETE)
    root = tmp_path / Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    (root / set_name).mkdir(parents=True)
    (root / set_name / "m.py.meta").write_text("{}", encoding="utf-8")
    proc = _bash(step, tmp_path, {"MATRIX": matrix})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    shard = root / set_name / ("mutation-%s-shard-0" % set_name)
    assert (shard / "m.py.meta").is_file()
    assert not (root / set_name / "m.py.meta").exists()


@needs_bash
@pytest.mark.parametrize("set_name, matrix", [("diff", DIFF2), ("full", FULL2)])
def test_a_flat_download_of_several_planned_shards_stays_red(
        jobs, tmp_path, set_name, matrix):
    # Two planned, one arrived (flat, because it was the only match): which
    # shard it was is unknowable, so nothing is moved and the check fails.
    job = jobs["mutation"]
    step = _step(job, name=COMPLETE)
    root = tmp_path / Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    (root / set_name).mkdir(parents=True)
    (root / set_name / "m.py.meta").write_text("{}", encoding="utf-8")
    proc = _bash(step, tmp_path, {"MATRIX": matrix})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not (root / set_name / ("mutation-%s-shard-0" % set_name)).exists()


def test_the_planner_runs_the_mutmut_backed_tests(jobs):
    # They skip in every `tests` cell, which has no mutmut; this is the one
    # place in CI they run, against the same venv the shards mutate with, and
    # BOOST_REQUIRE_MUTMUT turns a skip there into a failure.
    steps = jobs["mutation-plan"]["steps"]
    step = _step(jobs["mutation-plan"], runs="-m pytest")
    assert step["run"].strip() == (".venv/bin/python -m pytest -q "
                                   "tests/unit/test_mutation_diff.py "
                                   "tests/unit/test_mutation_plan.py")
    assert step["env"] == {"BOOST_REQUIRE_MUTMUT": "1"}
    assert step["if"] == "steps.scope.outputs.relevant == 'true'"
    assert "continue-on-error" not in step
    stats = steps.index(_step(jobs["mutation-plan"], name="collect mutmut stats once"))
    plan = steps.index(_step(jobs["mutation-plan"], step_id="plan"))
    # After the stats run, so nothing it writes can reach mutmut's view of the
    # checkout; before the planner, which leans on what these tests pin.
    assert stats < steps.index(step) < plan


@needs_bash
def test_a_required_mutmut_is_an_error_not_a_skip(tmp_path):
    # The fixture's contract, checked from the outside: with mutmut blocked
    # and BOOST_REQUIRE_MUTMUT=1, a mutmut-backed test errors instead of
    # skipping.
    probe = tmp_path / "sitecustomize.py"
    probe.write_text("import sys\nsys.modules['mutmut'] = None\n", encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(tmp_path), BOOST_REQUIRE_MUTMUT="1")
    target = "tests/unit/test_mutation_diff.py::test_body_edit_is_a_change"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                           "-p", "no:cacheprovider", target],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode != 0, proc.stdout
    assert "ERROR " + target in proc.stdout, proc.stdout
    assert "ModuleNotFoundError" in proc.stdout, proc.stdout
    env.pop("BOOST_REQUIRE_MUTMUT")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                           "-p", "no:cacheprovider", "-rs", target],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
    assert "could not import 'mutmut'" in proc.stdout, proc.stdout
