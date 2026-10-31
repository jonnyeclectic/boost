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


def test_diff_plan_scopes_changed_functions_and_direct_callers(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    plan = plan_diff(tmp_path, git_repo, head)
    diff = plan["sets"]["diff"]
    assert plan["gate_set"] == "diff"
    assert diff["functions"] == ["boost_cli.core.m.x_a", "boost_cli.core.m.x_b"]
    patterns = sorted(p for shard in diff["shards"] for p in shard)
    assert patterns == ["boost_cli.core.m.x_a__mutmut_*",
                        "boost_cli.core.m.x_b__mutmut_*"]
    assert diff["mutants"] > 0
    assert all(diff["shards"]), "no empty shard may reach `patterns`"


def test_diff_plan_method_names_survive_into_patterns(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("2 if", "4 if")})
    plan = plan_diff(tmp_path, git_repo, head)
    (shard,) = plan["sets"]["diff"]["shards"]
    assert shard == ["boost_cli.core.m.xǁKǁm__mutmut_*"]
    # And the argv the shard gets keeps the name whole.
    assert run_cli("patterns", "--plan", str(tmp_path / "plan.json"),
                   "--set", "diff", "--index", "0") == "boost_cli.core.m.xǁKǁm__mutmut_*\n"


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


def test_diff_plan_never_emits_an_empty_shard(tmp_path, git_repo):
    # One function, so packing at 1 mutant/shard asks for more shards than
    # there are functions; the extra bins must not reach the matrix.
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("- 1", "- 9")})
    md = mp._load_diff()
    plan = mp.diff_plan(git_repo.root, git_repo.base, head, git_repo.stats,
                        per_shard=1)
    assert plan["sets"]["diff"]["mutants"] > 1
    assert plan["sets"]["diff"]["shards"] == [[md.pattern("boost_cli.core.m.x_c")]]


def test_shadow_plan_gates_on_full_and_runs_both(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    plan = plan_diff(tmp_path, git_repo, head, "--shadow")
    assert plan["gate_set"] == "full"
    assert set(plan["sets"]) == {"diff", "full"}
    assert plan["sets"]["full"]["shards"] == [["boost_cli.core.m.*"], []]
    assert plan["sets"]["diff"]["shards"]
    sets = {e["set"] for e in json.loads(run_cli("matrix", "--plan",
                                                 str(tmp_path / "plan.json")))}
    assert sets == {"diff", "full"}


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


def test_diff_plan_records_per_function_counts(tmp_path, git_repo):
    head = git_repo.head({"boost_cli/core/m.py": _M_BASE.replace("+ 1", "+ 2")})
    diff = plan_diff(tmp_path, git_repo, head)["sets"]["diff"]
    assert set(diff["counts"]) == {"boost_cli.core.m.x_a", "boost_cli.core.m.x_b"}
    assert sum(diff["counts"].values()) == diff["mutants"]
    assert all(n > 0 for n in diff["counts"].values())


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
# ci.yml wiring: shadow mode (full binds, diff runs alongside and is compared)
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
    # sets no `shell:` -- note: no pipefail, which is why the shadow step must
    # capture exit codes itself rather than pipe through tee.
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


def test_the_planner_takes_the_merge_base_from_the_events_own_shas(jobs):
    step = _step(jobs["mutation-plan"], step_id="plan")
    env = step["env"]
    assert env["EVENT"] == "${{ github.event_name }}"
    assert env["BASE_SHA"] == ("${{ github.event.pull_request.base.sha"
                               " || github.event.merge_group.base_sha }}")
    assert env["HEAD_SHA"] == ("${{ github.event.pull_request.head.sha"
                               " || github.event.merge_group.head_sha }}")
    assert 'git merge-base "$BASE_SHA" "$HEAD_SHA"' in step["run"]


def test_the_planner_exports_whether_the_plan_is_shadow(jobs):
    assert jobs["mutation-plan"]["outputs"]["shadow"] == "${{ steps.plan.outputs.shadow }}"


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
  *" --shadow "*) plan='{"gate_set":"full","reasons":[],"sets":{"diff":{"shards":[]},"full":{"shards":[["a"]]}}}' ;;
  *" none "*) plan='{"gate_set":null,"reasons":["n"],"sets":{}}' ;;
  *) plan='{"gate_set":"full","reasons":[],"sets":{"full":{"shards":[["a"]]}}}' ;;
esac
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
            return plans[0], log, _outputs(out)
        return run

    @pytest.mark.parametrize("event", ["pull_request", "merge_group"])
    def test_prs_and_the_queue_plan_diff_in_shadow(self, planner, event):
        plan, log, outputs = planner(event)
        assert plan.startswith(".venv/bin/python scripts/mutation_plan.py diff "), plan
        assert " --shadow " in plan + " "
        assert " --shards 24 " in plan
        # The branch point comes from the event's own base and head ...
        assert "git merge-base basetip0 prhead0" in log
        assert " --base forkpoint0 " in plan
        # ... but the far end is the commit every shard checks out and the
        # stats were taken at. The PR head would count mutants of a tree no
        # shard mutates, and the gate refuses a shortfall as INCOMPLETE.
        assert " --head mergecommit0 " in plan
        assert " --stats mutants/mutmut-stats.json " in plan
        assert outputs["shadow"] == "true"
        assert outputs["gate_set"] == "full"

    @pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch"])
    def test_everything_else_plans_full(self, planner, event):
        plan, log, outputs = planner(event)
        assert "python3 scripts/mutation_plan.py full --shards 24 " in plan
        assert not any("merge-base" in line for line in log)
        assert outputs["shadow"] == "false"
        assert outputs["gate_set"] == "full"

    def test_no_merge_base_falls_back_to_full(self, planner):
        # A missing or unfetched base must widen the gate, never empty it.
        plan, _, outputs = planner("pull_request", MB_FAIL="1")
        assert "scripts/mutation_plan.py full --shards 24 " in plan
        assert outputs["shadow"] == "false"

    @pytest.mark.parametrize("event", ["pull_request", "push"])
    def test_an_irrelevant_change_plans_nothing(self, planner, event):
        plan, log, outputs = planner(event, relevant="false")
        assert "scripts/mutation_plan.py none " in plan
        assert not any("merge-base" in line for line in log)
        assert outputs["gate_set"] == ""
        assert outputs["shadow"] == "false"


FULL2 = '[{"set":"full","index":0},{"set":"full","index":1}]'
SHADOW3 = ('[{"set":"full","index":0},{"set":"full","index":1},'
           '{"set":"diff","index":0}]')


@needs_bash
@pytest.mark.parametrize("plan, shards, matrix, gate_set, shadow, rc", [
    # nothing mutable changed: the only green with no shards
    ("success", "skipped", "[]", "", "false", 0),
    # the planner did not finish: its empty outputs must not read as "none"
    ("failure", "skipped", "", "", "", 1),
    ("cancelled", "skipped", "", "", "", 1),
    # push: full plan
    ("success", "success", FULL2, "full", "false", 0),
    ("success", "failure", FULL2, "full", "false", 1),
    ("success", "cancelled", FULL2, "full", "false", 1),
    # PR / merge_group: shadow plan. A failed DIFF shard is red too -- the
    # matrix is one job, and a comparison with a hole in it is not one.
    ("success", "success", SHADOW3, "full", "true", 0),
    ("success", "failure", SHADOW3, "full", "true", 1),
    ("success", "cancelled", SHADOW3, "full", "true", 1),
    # a full gate with nothing to score
    ("success", "skipped", "[]", "full", "false", 1),
    # `diff` is legal in the plan but nothing here binds on it yet
    ("success", "success", '[{"set":"diff","index":0}]', "diff", "false", 1),
    ("success", "skipped", "[]", "diff", "false", 1),
    # unknown, and a shadow plan that would not gate on the full set
    ("success", "success", FULL2, "bogus", "false", 1),
    ("success", "success", SHADOW3, "", "true", 1),
])
def test_the_gate_is_conclusive_for_every_upstream_outcome(
        jobs, tmp_path, plan, shards, matrix, gate_set, shadow, rc):
    step = _step(jobs["mutation"], name="upstream jobs must be conclusive")
    assert "if" not in step, "the conclusive check must never be skipped"
    assert step["env"]["SHADOW"] == "${{ needs.mutation-plan.outputs.shadow }}"
    proc = _bash(step, tmp_path, {"PLAN": plan, "SHARDS": shards, "MATRIX": matrix,
                                  "GATE_SET": gate_set, "SHADOW": shadow})
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
    assert full["if"] == "needs.mutation-plan.outputs.gate_set == 'full'"
    assert diff["if"] == "needs.mutation-plan.outputs.shadow == 'true'"
    # Every consumer reads the dir its set landed in.
    merge = _step(job, runs="mutation_shards.py merge")["run"]
    assert "--source %s " % full_dir in merge
    assert "--prefix mutation-full-shard-" in merge
    shadow = _step(job, step_id="shadow")["run"]
    assert "--full-source %s " % full_dir in shadow
    assert "--diff-source %s " % diff_dir in shadow
    assert "--source %s " % diff_dir in shadow
    assert "--prefix mutation-diff-shard-" in shadow
    # The gate and compare read the plan the shards ran from.
    assert downloads["mutation-plan"]["if"] == "needs.mutation-plan.outputs.shadow == 'true'"


def test_only_the_shadow_step_continues_on_error(jobs):
    job = jobs["mutation"]
    lenient = [s for s in job["steps"] if s.get("continue-on-error")]
    assert [s.get("id") for s in lenient] == ["shadow"]
    shadow = lenient[0]
    assert shadow["continue-on-error"] is True
    assert shadow["if"] == "needs.mutation-plan.outputs.shadow == 'true'"
    run = shadow["run"]
    assert ".venv/bin/python scripts/mutation_diff.py compare " in run
    assert ".venv/bin/python scripts/mutation_diff.py gate " in run
    assert '--root "$GITHUB_WORKSPACE"' in run
    # Nowhere else: in shadow the diff gate is data, never the verdict.
    others = "\n".join(s.get("run", "") for s in job["steps"] if s is not shadow)
    assert "mutation_diff.py" not in others


def test_the_binding_gate_is_the_one_gate_set_names(jobs):
    job = jobs["mutation"]
    gate = _step(job, runs="scripts/mutation_gate.py")
    assert gate["if"] == "needs.mutation-plan.outputs.gate_set == 'full'"
    assert "continue-on-error" not in gate
    # The merge it scores comes from full shards only, and is what the weights
    # are measured from: a diff run's partial weights would repack on a sliver.
    assert "--into mutants " in _step(job, runs="mutation_shards.py merge")["run"]
    weights = _uploads(job)["mutation-weights"]
    assert weights["if"] == "needs.mutation-plan.outputs.gate_set == 'full'"
    assert "--source mutants" in _step(job, runs="mutation_shards.py weights")["run"]


def test_the_shadow_report_is_summarised_and_uploaded(jobs):
    job = jobs["mutation"]
    run = _step(job, step_id="shadow")["run"]
    assert "Diff-gate shadow" in run
    assert '>> "$GITHUB_STEP_SUMMARY"' in run
    report = _uploads(job)["mutation-shadow-report"]
    assert report["with"]["path"] == "mutation-shadow-report.md"
    assert report["if"] == "needs.mutation-plan.outputs.shadow == 'true'"
    assert "continue-on-error" not in report
    # After the shadow step, before the merge: a red full gate is exactly the
    # run whose report is worth reading.
    names = [s.get("id") or s.get("name") or s.get("uses") for s in job["steps"]]
    order = [names.index("shadow"), names.index(report.get("name")),
             names.index(_step(job, runs="mutation_shards.py merge")["name"])]
    assert order == sorted(order)


@needs_bash
@pytest.mark.parametrize("gate_rc, compare_rc, rc", [
    (0, 0, 0),
    (1, 0, 0),   # the diff gate says FAIL: data for the comparison, not an error
    (0, 1, 1),   # a killed/not-killed disagreement: the step goes red, visibly
    (0, 2, 1),   # an incomplete comparison
    (2, 2, 1),   # unrun diff results
    (2, 0, 1),
])
def test_the_shadow_step_fails_visibly_on_disagreement(
        jobs, tmp_path, gate_rc, compare_rc, rc):
    step = _step(jobs["mutation"], step_id="shadow")
    _stub(tmp_path / ".venv" / "bin" / "python", r'''
case "$*" in
  *"mutation_diff.py gate "*)
    echo "mutation diff gate: stub"
    [ -n "$GITHUB_STEP_SUMMARY" ] && echo "### Mutation (diff scope): STUB" >> "$GITHUB_STEP_SUMMARY"
    exit "$GATE_RC" ;;
  *"mutation_diff.py compare "*)
    echo "agree 7, disagree 0, excluded-timeouts 0"
    exit "$COMPARE_RC" ;;
esac
exit 99
''')
    summary = tmp_path / "summary.md"
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    proc = _bash(step, tmp_path, {
        "GATE_RC": str(gate_rc), "COMPARE_RC": str(compare_rc),
        "GITHUB_STEP_SUMMARY": str(summary), "RUNNER_TEMP": str(runner_temp),
        "GITHUB_WORKSPACE": str(tmp_path)})
    assert proc.returncode == rc, proc.stdout + proc.stderr
    report = (tmp_path / "mutation-shadow-report.md").read_text(encoding="utf-8")
    assert report.startswith("## Diff-gate shadow\n")
    assert "agree 7, disagree 0, excluded-timeouts 0" in report
    # The diff gate's own summary lands in the report, not as a top-level
    # verdict in the job summary a reader would take for the binding one.
    assert "### Mutation (diff scope): STUB" in report
    assert summary.read_text(encoding="utf-8") == report


@needs_bash
@pytest.mark.parametrize("present, rc", [
    (["full/mutation-full-shard-0", "full/mutation-full-shard-1",
      "diff/mutation-diff-shard-0"], 0),
    (["full/mutation-full-shard-0", "full/mutation-full-shard-1"], 1),
    (["full/mutation-full-shard-0", "diff/mutation-diff-shard-0"], 1),
])
def test_every_planned_shard_must_have_uploaded(jobs, tmp_path, present, rc):
    job = jobs["mutation"]
    step = _step(job, name="every planned shard uploaded results")
    assert step["if"] == "needs.mutation-plan.outputs.gate_set == 'full'"
    assert "continue-on-error" not in step
    root = Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    for rel in present:
        (tmp_path / root / rel).mkdir(parents=True)
    proc = _bash(step, tmp_path, {"MATRIX": SHADOW3})
    assert proc.returncode == rc, proc.stdout + proc.stderr


@needs_bash
def test_a_lone_shard_downloaded_flat_is_put_back_under_its_name(jobs, tmp_path):
    # download-artifact (v8.0.2, src/download-artifact.ts) writes a pattern
    # download that matches ONE artifact straight into `path:`, with no
    # <artifact-name>/ level -- `artifacts.length === 1 ? resolvedPath : ...`.
    # One diff shard is the commonest diff plan, so without this every such
    # PR would read "no results from diff shard 0" and go red.
    job = jobs["mutation"]
    step = _step(job, name="every planned shard uploaded results")
    root = tmp_path / Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    for i in range(2):
        (root / "full" / ("mutation-full-shard-%d" % i)).mkdir(parents=True)
    (root / "diff").mkdir()
    (root / "diff" / "m.py.meta").write_text("{}", encoding="utf-8")
    proc = _bash(step, tmp_path, {"MATRIX": SHADOW3})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (root / "diff" / "mutation-diff-shard-0" / "m.py.meta").is_file()
    assert not (root / "diff" / "m.py.meta").exists()


@needs_bash
def test_a_flat_download_of_several_planned_shards_stays_red(jobs, tmp_path):
    # Two planned, one arrived (flat, because it was the only match): which
    # shard it was is unknowable, so nothing is moved and the check fails.
    job = jobs["mutation"]
    step = _step(job, name="every planned shard uploaded results")
    root = tmp_path / Path(_downloads(job)["mutation-full-shard-*"]["with"]["path"]).parent
    (root / "full").mkdir(parents=True)
    (root / "full" / "m.py.meta").write_text("{}", encoding="utf-8")
    (root / "diff" / "mutation-diff-shard-0").mkdir(parents=True)
    proc = _bash(step, tmp_path, {"MATRIX": SHADOW3})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert not (root / "full" / "mutation-full-shard-0").exists()
