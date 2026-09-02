# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests for workspace scope — `boost install --local`.

The invariant under test everywhere here: a project install materializes REAL
directories inside the repo and records them in the repo's own lock, and never
touches the canonical store or the user lock. A symlink into
``~/.agents/skills`` would arrive dangling on a teammate's machine, which is
exactly what committing skills is supposed to fix.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, paths, projectlock, store


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "myrepo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


def _skill_dirs(repo, name):
    return sorted(p for p in repo.rglob("skills/" + name) if p.is_dir())


# ── install --local ──────────────────────────────────────────────────────

def test_local_install_writes_real_dirs_into_the_repo(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    dirs = _skill_dirs(repo, "brainstorming")
    assert dirs, "nothing materialized under the repo"
    for d in dirs:
        assert not d.is_symlink(), "%s is a symlink — it would dangle for a teammate" % d
        assert (d / "SKILL.md").is_file()


def test_local_install_lands_under_each_agent_dotdir(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()


def test_local_install_leaves_the_canonical_store_alone(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    assert not (paths.store_dir() / "brainstorming").exists()
    assert lockfile.get_skill("brainstorming") is None


def test_local_install_records_the_project_lock(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    entry = projectlock.get_skill(repo, "brainstorming")
    assert entry and entry["scope"] == "project"
    assert entry["materializations"]
    assert projectlock.lock_path(repo).is_file()


def test_scope_project_is_the_same_as_local(boost, tapped, repo):
    boost("install", "brainstorming", "--scope", "project")
    assert projectlock.get_skill(repo, "brainstorming") is not None


def test_global_is_the_default_and_uses_the_store(boost, tapped, repo):
    boost("install", "brainstorming", "--global")
    assert (paths.store_dir() / "brainstorming").is_dir()
    assert projectlock.get_skill(repo, "brainstorming") is None


def test_local_and_global_are_mutually_exclusive(boost, tapped, repo):
    res = boost("install", "brainstorming", "--local", "--global", expect=2)
    assert "not allowed with" in res.err


# ── the walk-up ──────────────────────────────────────────────────────────

def test_installing_from_a_subdir_lands_in_the_repo_root(boost, tapped, repo,
                                                         monkeypatch):
    deep = repo / "src" / "deep" / "nested"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)
    boost("install", "brainstorming", "--local")
    # The repo root, not a stray .claude three levels down.
    assert (repo / ".claude" / "skills" / "brainstorming").is_dir()
    assert not (deep / ".claude").exists()


# ── the same skill at both scopes ────────────────────────────────────────

def test_user_and_project_installs_coexist(boost, tapped, repo):
    # Two independent locks, so vendoring into a repo never fights with the
    # copy you use everywhere.
    boost("install", "brainstorming")
    boost("install", "brainstorming", "--local")
    assert lockfile.get_skill("brainstorming") is not None
    assert projectlock.get_skill(repo, "brainstorming") is not None


def test_a_second_local_install_is_refused_without_force(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    res = boost("install", "brainstorming", "--local", expect=1)
    assert "already installed in this project" in (res.out + res.err)


def test_force_reinstalls_locally(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    boost("install", "brainstorming", "--local", "--force")
    assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()


# ── list ─────────────────────────────────────────────────────────────────

def test_list_shows_a_project_section(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    res = boost("list")
    assert "project skills" in res.out
    assert "brainstorming" in res.out


def test_list_local_hides_user_skills(boost, tapped, repo):
    boost("install", "brainstorming")          # user scope
    res = boost("list", "--local")
    assert "installed skills" not in res.out


def test_list_json_carries_the_project_key(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    data = json.loads(boost("list", "--json").out)
    assert "brainstorming" in data["project"]
    assert data["skills"] == {}


# ── uninstall ────────────────────────────────────────────────────────────

def test_uninstall_local_removes_the_dirs_and_the_record(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    boost("uninstall", "brainstorming", "--local")
    assert not (repo / ".claude" / "skills" / "brainstorming").exists()
    assert projectlock.get_skill(repo, "brainstorming") is None


def test_plain_uninstall_falls_back_to_the_project(boost, tapped, repo):
    # "not installed" would be a plain falsehood while standing in the repo.
    boost("install", "brainstorming", "--local")
    boost("uninstall", "brainstorming")
    assert projectlock.get_skill(repo, "brainstorming") is None


def test_uninstall_prefers_user_scope_when_both_exist(boost, tapped, repo):
    boost("install", "brainstorming")
    boost("install", "brainstorming", "--local")
    boost("uninstall", "brainstorming")
    assert lockfile.get_skill("brainstorming") is None
    assert projectlock.get_skill(repo, "brainstorming") is not None


def test_uninstall_local_that_is_not_installed_errors(boost, tapped, repo):
    res = boost("uninstall", "brainstorming", "--local", expect=1)
    assert "not installed in this project" in (res.out + res.err)


def test_uninstall_never_deletes_outside_the_project(boost, tapped, repo,
                                                     tmp_path):
    """A doctored lock path must not walk boost out of the repo."""
    boost("install", "brainstorming", "--local")
    victim = tmp_path / "not-the-repo"
    victim.mkdir()
    (victim / "keep.txt").write_text("precious", encoding="utf-8")
    entry = projectlock.get_skill(repo, "brainstorming")
    entry["materializations"] = [{"agent": "claude-code", "path": str(victim)}]
    projectlock.set_skill(repo, "brainstorming", entry)
    store.uninstall_project("brainstorming", base=repo)
    assert (victim / "keep.txt").is_file(), "escaped the project and deleted it"


# ── dry run ──────────────────────────────────────────────────────────────

def test_dry_run_local_changes_nothing_and_names_the_repo(boost, tapped, repo):
    res = boost("install", "brainstorming", "--local", "--dry-run", expect=0)
    assert "brainstorming" in res.out
    assert not (repo / ".claude").exists()
    assert projectlock.get_skill(repo, "brainstorming") is None


def test_dry_run_local_copy_list_matches_the_real_install(boost, tapped, repo):
    # Antigravity CLI's project layout is unknown (agents.project_agents), so
    # the real `--local` install never copies for it; a dry run that read
    # `enabled_agents()` invented a fifth "copy → .../antigravity-cli/skills/…"
    # line the real install never writes.
    preview = boost("install", "brainstorming", "--local", "--dry-run").out
    copy_lines = sorted(x.split("→", 1)[1].strip()
                        for x in preview.splitlines() if "copy  →" in x)
    real = boost("install", "brainstorming", "--local").out
    real_agents = real.split("copied into this repo →", 1)[1].splitlines()[0].strip()
    assert len(copy_lines) == len(real_agents.split(" · "))
    assert not any("antigravity" in line for line in copy_lines)


def _mcp_skill_tap(fixture_tap_src, tmp_path, name="mcp-proj-skill",
                   decl="github", sidecar=None):
    """A tap holding one skill that declares an MCP server, own commit."""
    tap_dir = tmp_path / "mcp-proj-tap"
    shutil.copytree(fixture_tap_src, tap_dir)
    skill_dir = tap_dir / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: %s\ndescription: needs an MCP server to work\n"
        "version: 1.0.0\nmcp: %s\n---\n\n# %s\n\nBody.\n" % (name, decl, name),
        encoding="utf-8")
    if sidecar is not None:
        (skill_dir / ".mcp.json").write_text(json.dumps(sidecar), encoding="utf-8")
    subprocess.run(["git", "-C", str(tap_dir), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap_dir), "commit", "-qm", "add " + name],
                   check=True, capture_output=True)
    return tap_dir


def test_dry_run_local_plans_the_mcp_json_record(boost, fixture_tap_src,
                                                  tmp_path, repo):
    # The real `--local` install records a declaring skill's servers into the
    # repo's own .mcp.json (store.register_project_mcp); no dry run ever said
    # so, which made the preview silent about the one file install --local
    # actually writes beyond the skill copies themselves.
    tap_dir = _mcp_skill_tap(
        fixture_tap_src, tmp_path,
        sidecar={"mcpServers": {"github": {"command": "npx",
                                           "args": ["-y", "srv"]}}})
    boost("tap", tap_dir)
    r = boost("install", "mcp-proj-skill", "--local", "--dry-run")
    assert "mcp   → record github in .mcp.json" in r.out
    assert not (repo / ".mcp.json").exists()


# ── sync ─────────────────────────────────────────────────────────────────

def test_sync_diff_reports_a_missing_project_skill(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    # The state right after a fresh `git clone` that did not commit the dirs.
    import shutil
    shutil.rmtree(repo / ".claude" / "skills" / "brainstorming")
    res = boost("sync", "--diff")
    assert "missing from this project" in res.out


def test_sync_repairs_a_missing_project_skill(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    import shutil
    shutil.rmtree(repo / ".claude" / "skills" / "brainstorming")
    boost("sync")
    assert (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").is_file()


def test_sync_reports_but_never_deletes_an_unclaimed_dir(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    mine = repo / ".claude" / "skills" / "hand-written"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("mine\n", encoding="utf-8")
    res = boost("sync", "--diff")
    assert "unclaimed" in res.out
    boost("sync")
    assert (mine / "SKILL.md").is_file(), "deleted a file boost did not write"


# ── governance commands see project skills (project-scope-across-every-command) ──

def test_verify_sees_a_project_skill(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    res = boost("verify")
    assert "brainstorming" in res.out and "project" in res.out


def test_verify_flags_a_tampered_project_skill(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").write_text(
        "EVIL\n", encoding="utf-8")
    res = boost("verify", expect=1)
    assert "modified" in res.out
    assert "failed verification" in (res.out + res.err)


def test_verify_json_tags_scope(boost, tapped, repo):
    import json as _json
    boost("install", "brainstorming", "--local")
    data = _json.loads(boost("verify", "--json").out)
    scopes_seen = {r["scope"] for r in data["skills"]}
    assert scopes_seen == {"project"}


def test_verify_named_project_skill_does_not_error_not_installed(boost, tapped,
                                                                repo):
    # The bug this closes: a vendored skill named explicitly used to hit the
    # user-lock-only validation and wrongly report "not installed".
    boost("install", "brainstorming", "--local")
    res = boost("verify", "brainstorming")
    assert "brainstorming" in res.out


def test_verify_unknown_name_still_errors(boost, tapped, repo):
    res = boost("verify", "no-such-skill", expect=1)
    assert "not installed" in (res.out + res.err)


def test_doctor_flags_a_tampered_project_skill(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    (repo / ".claude" / "skills" / "brainstorming" / "SKILL.md").write_text(
        "EVIL\n", encoding="utf-8")
    res = boost("doctor", expect=1)
    assert "project skill brainstorming modified" in res.out


def test_doctor_reports_intact_project_skills(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    res = boost("doctor")
    assert "project skill" in res.out and "intact" in res.out


# ── declared MCP servers stay in the repo ────────────────────────────────

def _declare_mcp(tapped, skill: str, server: str = "gh"):
    """Give a skill in the tap clone an .mcp.json sidecar declaring a server."""
    from boost_cli.core import catalog, mcpdecl
    matches = catalog.find(skill)
    assert matches, skill
    src = store.source_dir_for(matches[0])
    (src / mcpdecl.SIDECAR).write_text(json.dumps(
        {mcpdecl.SERVERS_KEY: {server: {"command": "npx", "args": ["-y", server]}}}),
        encoding="utf-8")


def test_a_local_install_records_mcp_servers_in_the_repo(boost, tapped, repo):
    """THE BUG: --local promised repo-scoped and registered machine-wide.

    A project install must leave its declared servers in the repo's own
    .mcp.json — committable, reviewable, and arriving with a teammate's clone —
    rather than in this machine's user-scope host config.
    """
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming", "--local")
    sidecar = repo / mcpdecl.SIDECAR
    assert sidecar.is_file(), "no .mcp.json written into the repo"
    servers = json.loads(sidecar.read_text())[mcpdecl.SERVERS_KEY]
    assert "gh" in servers
    assert servers["gh"][mcpdecl.MARKER_KEY] == "brainstorming", \
        "the entry must name the skill that asked for it, so uninstall can reverse it"


def test_a_local_install_reports_the_recorded_mcp_servers(boost, tapped, repo):
    """THE BUG: the "recorded N servers" report is dead code on the project
    branch — `_report_result` returns before `_offer_mcp` ever runs, so a file
    the user is told to commit was edited with zero mention of it.
    """
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    res = boost("install", "brainstorming", "--local")
    assert "recorded 1 MCP server" in res.out
    assert mcpdecl.SIDECAR in res.out


def test_uninstalling_locally_removes_the_servers_it_added(boost, tapped, repo):
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming", "--local")
    boost("uninstall", "brainstorming", "--local")
    servers = json.loads((repo / mcpdecl.SIDECAR).read_text())[mcpdecl.SERVERS_KEY]
    assert "gh" not in servers, \
        "a skill removed from the repo must stop launching its server"


def test_uninstalling_locally_reports_the_removed_mcp_servers(boost, tapped, repo):
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming", "--local")
    res = boost("uninstall", "brainstorming", "--local")
    assert "removed 1 MCP server" in res.out
    assert mcpdecl.SIDECAR in res.out


def test_uninstall_leaves_a_hand_written_server_alone(boost, tapped, repo):
    from boost_cli.core import mcpdecl
    (repo / mcpdecl.SIDECAR).write_text(json.dumps(
        {mcpdecl.SERVERS_KEY: {"mine": {"command": "my-own-thing"}}}),
        encoding="utf-8")
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming", "--local")
    boost("uninstall", "brainstorming", "--local")
    servers = json.loads((repo / mcpdecl.SIDECAR).read_text())[mcpdecl.SERVERS_KEY]
    assert servers["mine"] == {"command": "my-own-thing"}, \
        "boost must only reverse what boost wrote"


def test_a_user_install_writes_no_sidecar_into_the_repo(boost, tapped, repo):
    # The complement: user scope must not start scattering .mcp.json files into
    # whatever directory the install happened to run from.
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming")
    assert not (repo / mcpdecl.SIDECAR).exists()
