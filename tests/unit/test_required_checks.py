"""Unit tests: scripts/check_required_checks.py — the required-check drift gate.

The gate's whole job is to fail when the required-status-check list stops
matching reality, so the tests drive it against synthetic workflow trees rather
than only asserting that the real repo currently passes — a gate that can only
say "yes" is the failure mode this file exists to prevent.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_required_checks.py"


def load(monkeypatch, root: Path):
    """Import the gate with its ROOT/WORKFLOWS/CONFIG pointed at ``root``."""
    spec = importlib.util.spec_from_file_location("check_required_checks", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "WORKFLOWS", root / ".github" / "workflows")
    monkeypatch.setattr(mod, "CONFIG", root / ".github" / "required-checks.txt")
    return mod


def workflow(root: Path, name: str, jobs: str, on_pr: bool = True) -> None:
    d = root / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    trigger = "on:\n  push:\n" + ("  pull_request:\n" if on_pr else "")
    (d / name).write_text("name: %s\n%s\njobs:\n%s" % (name[:-4], trigger, jobs),
                          encoding="utf-8")


def config(root: Path, body: str) -> None:
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "required-checks.txt").write_text(body, encoding="utf-8")


class TestPassing:
    def test_matching_list_passes(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# comment\n\nlint\n")
        mod = load(monkeypatch, tmp_path)
        assert mod.main([]) == 0
        assert "no ambiguity" in capsys.readouterr().out

    def test_matrix_leg_resolves_to_its_job(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  tests:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "tests (ubuntu-latest, 3.9)\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_reusable_workflow_prefix_resolves(self, tmp_path, monkeypatch):
        workflow(tmp_path, "osv.yml", "  scan-pr:\n    uses: ./x.yml\n")
        config(tmp_path, "scan-pr / osv-scan\n")
        assert load(monkeypatch, tmp_path).main([]) == 0

    def test_explicit_name_overrides_the_job_id(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    name: Lint everything\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "Lint everything\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestDrift:
    def test_required_name_with_no_job_fails(self, tmp_path, monkeypatch, capsys):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\nmutation\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "'mutation'" in capsys.readouterr().err

    def test_job_that_does_not_run_on_pr_cannot_be_required(self, tmp_path, monkeypatch, capsys):
        # A nightly-only job can never gate a PR, so requiring it would block
        # every merge forever.
        workflow(tmp_path, "nightly.yml", "  slow:\n    runs-on: ubuntu-latest\n",
                 on_pr=False)
        config(tmp_path, "slow\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        assert "pull_request" in capsys.readouterr().err

    def test_renamed_job_is_caught(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint-v2:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1


class TestAmbiguity:
    def test_duplicate_check_name_across_workflows_fails(self, tmp_path, monkeypatch, capsys):
        # The real bug: `lint` existed in three workflows, so branch protection
        # could not require it unambiguously.
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "markdownlint.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1
        err = capsys.readouterr().err
        assert "ambiguous" in err and "ci.yml" in err and "markdownlint.yml" in err

    def test_ambiguity_is_reported_even_when_not_required(self, tmp_path, monkeypatch):
        # A collision is a latent trap whether or not the name is required today.
        workflow(tmp_path, "a.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "b.yml", "  audit:\n    runs-on: ubuntu-latest\n")
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main([]) == 1

    def test_same_name_in_one_workflow_is_not_a_collision(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml",
                 "  lint:\n    runs-on: ubuntu-latest\n  tests:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\ntests\n")
        assert load(monkeypatch, tmp_path).main([]) == 0


class TestRefusesToPassVacuously:
    def test_no_workflow_files_is_an_error(self, tmp_path, monkeypatch):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="no workflow files"):
            load(monkeypatch, tmp_path).main([])

    def test_parsing_zero_jobs_is_an_error_not_a_pass(self, tmp_path, monkeypatch):
        # If the parser stops matching, the gate must fail loudly rather than
        # report "no problems found".
        d = tmp_path / ".github" / "workflows"
        d.mkdir(parents=True)
        (d / "ci.yml").write_text("name: ci\non:\n  pull_request:\n", encoding="utf-8")
        config(tmp_path, "lint\n")
        with pytest.raises(SystemExit, match="parsed 0 jobs"):
            load(monkeypatch, tmp_path).main([])

    def test_empty_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "# only comments\n\n")
        with pytest.raises(SystemExit, match="lists no checks"):
            load(monkeypatch, tmp_path).main([])

    def test_missing_config_is_an_error(self, tmp_path, monkeypatch):
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        with pytest.raises(SystemExit, match="missing"):
            load(monkeypatch, tmp_path).main([])


class TestPrintApi:
    def test_payload_requires_checks_but_not_reviews(self, tmp_path, monkeypatch, capsys):
        import json
        workflow(tmp_path, "ci.yml", "  lint:\n    runs-on: ubuntu-latest\n")
        config(tmp_path, "lint\n")
        assert load(monkeypatch, tmp_path).main(["--print-api"]) == 0
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{"):])
        assert payload["required_status_checks"]["contexts"] == ["lint"]
        assert payload["required_status_checks"]["strict"] is True
        # Reviews stay off on purpose: parallel loop/* branches self-merge, and
        # requiring a second reviewer would deadlock every one of them.
        assert payload["required_pull_request_reviews"] is None


class TestRealRepo:
    def test_the_committed_config_matches_the_real_workflows(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
