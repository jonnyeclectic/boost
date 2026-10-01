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
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from boost_cli.core import lockfile, paths, projectlock, scopes, store


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A project directory that looks like a git repo, cd'd into."""
    d = tmp_path / "myrepo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


@pytest.fixture()
def plain_dir(tmp_path, monkeypatch):
    """A project directory with no VCS marker at or above it, cd'd into.

    Every seam in `audit-project-scope-seams` only reproduces here, because
    `install --local` resolves its base with `scopes.resolve_base` (which falls
    back to the cwd) while the query commands asked `scopes.project_root`
    (which stops at the filesystem root and answers None). The precondition is
    asserted rather than assumed: a checkout above `tmp_path` on some other
    machine would make every test below pass for the wrong reason.
    """
    d = tmp_path / "plain"
    d.mkdir()
    monkeypatch.chdir(d)
    assert scopes.project_root(d) is None, (
        "a VCS marker at or above %s — these tests would assert nothing" % d)
    return d.resolve()


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


def test_uninstall_local_names_the_lock_row_it_refused(boost, tapped, repo):
    """The user has to learn their committed lock was edited.

    Being inside the repo was the whole guard, so a row of `src/core`
    passed it and `boost uninstall --local` removed the source tree. The
    directory now survives — but surviving silently is its own failure: the
    row is still in a committed file, so a user who sees a clean "removed"
    panel has no reason to look.
    """
    boost("install", "brainstorming", "--local")
    victim = Path(repo) / "src" / "core"
    victim.mkdir(parents=True)
    (victim / "main.py").write_text("print(1)\n", encoding="utf-8")
    entry = projectlock.get_skill(repo, "brainstorming")
    entry["materializations"] = [{"agent": "claude-code", "path": "src/core"}]
    projectlock.set_skill(repo, "brainstorming", entry)

    res = boost("uninstall", "brainstorming", "--local", expect=0)

    assert (victim / "main.py").read_text(encoding="utf-8") == "print(1)\n"
    assert "src/core" in res.out
    assert "left alone" in res.out
    # Every row was refused, so nothing came off disk — and the panel used to
    # say "removed from <repo>" regardless. A green line over a tampered lock
    # is the one outcome this whole change exists to stop the user trusting.
    assert "nothing removed from" in res.out
    # The remedy, not just the complaint — and it must name the paths boost
    # removes *here* rather than a `<repo>/<dotdir>/skills/<name>` shape. The
    # shape hardcoded a leaf that comes from the agent's config, so under a
    # renamed skills dir it told the user their path was not one an install
    # writes directly above a shape that path matched.
    assert ".claude/skills/brainstorming" in res.out
    assert "<agent dotdir>" not in res.out


def test_uninstall_local_reports_a_removal_a_row_did_not_attribute(
        boost, tapped, repo):
    """"removed from <repo>" must follow the disk, not the agent list.

    `unlinked` names agents, and a lock row need not name one; the delete
    above it is not gated on `agent` and must not be, since an agentless row
    at a legal path is still the skill's own directory. Reading the success
    line off that list therefore told a user with such a row that nothing had
    been removed while the directory was gone — the round-2 fix for the
    opposite lie, told backwards.
    """
    boost("install", "brainstorming", "--local")
    landed = Path(repo) / ".claude" / "skills" / "brainstorming"
    entry = projectlock.get_skill(repo, "brainstorming")
    entry["materializations"] = [{"path": ".claude/skills/brainstorming"}]
    projectlock.set_skill(repo, "brainstorming", entry)

    res = boost("uninstall", "brainstorming", "--local", expect=0)

    assert not landed.exists(), "the delete must not depend on `agent`"
    flat = " ".join(res.out.split())
    assert "removed from" in flat
    assert "nothing removed from" not in flat


@pytest.mark.skipif(sys.platform == "win32",
                    reason="install cannot stage a copy through a relative directory "
                           "symlink on Windows; the guard itself is covered "
                           "there by the two ancestor tests, which symlink "
                           "after the install")
def test_uninstall_local_does_not_contradict_itself_on_a_redirect(
        boost, tapped, repo):
    """A redirected row is in the remedy list, so it cannot borrow the words.

    `<repo>/.cursor -> config/cursor` is an ordinary in-repo dotfile layout.
    Install writes through it — `ensure_in_base` is containment only — and
    uninstall will not delete through it, because a committed symlink is
    input and this is byte-identical to `.claude/skills -> ../src`.

    That trade is deliberate. What is not acceptable is how it read: the row
    is in the derived set by construction, so reporting it as `refused`
    printed "not a path boost removes here" three lines above a list
    containing that exact string.
    """
    (Path(repo) / "config" / "cursor").mkdir(parents=True)
    (Path(repo) / ".cursor").symlink_to("config/cursor",
                                        target_is_directory=True)
    boost("install", "brainstorming", "--local")
    landed = Path(repo) / "config" / "cursor" / "skills" / "brainstorming"
    assert landed.is_dir(), "install did not write through the symlink"

    res = boost("uninstall", "brainstorming", "--local", expect=0)

    # Folded to the pane, so match on the unwrapped text. The `rm -rf ...`
    # span stays on a line of its own whatever the width — a backtick span is
    # one atomic token, and a command split across two lines does not run.
    flat = " ".join(res.out.split())
    assert ".cursor/skills/brainstorming" in flat
    assert "will not delete through a symlink it did not create" in flat
    assert "rm -rf" in flat
    # The two messages this row must NOT get: `refused`'s, which contradicts
    # the remedy list, and the remedy list itself, which names this very row.
    assert "is not a path boost removes here" not in flat
    assert "boost only removes" not in flat
    # Left behind on purpose, and the printed remedy really does remove it —
    # `rm` follows the committed symlink exactly as the install did.
    assert landed.is_dir()
    # One redirect is not a veto: every other agent's copy still goes, so the
    # run is not a "nothing removed" run.
    assert not (Path(repo) / ".claude" / "skills" / "brainstorming").exists()
    assert "nothing removed from" not in flat


def test_uninstall_local_reports_a_row_that_escapes_the_repo(
        boost, tapped, repo):
    """The most hostile row was the one that produced no output at all.

    An absolute path or one climbing out with `..` is stopped by the
    containment check, which is right — but it then fell through every
    branch to a bare `continue`, so boost printed a clean "removed" panel
    and said nothing. Being refused silently is the same failure as
    surviving silently.
    """
    boost("install", "brainstorming", "--local")
    outside = Path(repo).parent / "not-mine"
    outside.mkdir(exist_ok=True)
    (outside / "x").write_text("theirs", encoding="utf-8")
    entry = projectlock.get_skill(repo, "brainstorming")
    entry["materializations"] = [{"agent": "claude-code",
                                  "path": "../not-mine"}]
    projectlock.set_skill(repo, "brainstorming", entry)

    res = boost("uninstall", "brainstorming", "--local", expect=0)

    assert (outside / "x").read_text(encoding="utf-8") == "theirs"
    assert "../not-mine" in res.out
    assert "outside this repo" in res.out


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


def test_dry_run_local_copy_list_matches_the_real_install_under_a_moved_codex(
        boost, tapped, repo, tmp_path, monkeypatch):
    """`CODEX_HOME` moves Codex's user dir; the preview and the install must
    both still name `<repo>/.codex/skills`, which is the only repo-scope root
    Codex reads.

    Preview and install derive their targets in two different modules
    (`commands/pkg.py` and `core/store.py`), so "they agree" is a property that
    has to be asserted, not assumed — and the derivation they shared was the
    one this fixes.
    """
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "moved-codex"))
    preview = boost("install", "brainstorming", "--local", "--dry-run").out
    copy_lines = sorted(x.split("→", 1)[1].strip()
                        for x in preview.splitlines() if "copy  →" in x)
    assert any(line.endswith(".codex/skills/brainstorming") for line in copy_lines)
    assert not any("moved-codex" in line for line in copy_lines)

    boost("install", "brainstorming", "--local")
    assert (repo / ".codex" / "skills" / "brainstorming" / "SKILL.md").is_file()
    assert not (repo / "moved-codex").exists()
    # And the preview named every directory the install actually created —
    # same set, not merely the same count.
    # `paths.tilde` on both sides, not `str()`: the preview renders through it
    # and it forces `/` separators "so boost's display text is stable across
    # platforms", so a raw `str(Path)` compares `C:\\Users\\…` against
    # `C:/Users/…` and the test failed on Windows for a difference the user
    # never sees. Rendering both sides the same way keeps the assertion about
    # the target set, which is what it is for.
    made = sorted(paths.tilde(d) for d in _skill_dirs(repo, "brainstorming"))
    assert made, "nothing materialized under the repo"
    assert copy_lines == made


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
    servers = json.loads(sidecar.read_text(encoding="utf-8"))[mcpdecl.SERVERS_KEY]
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
    servers = json.loads(
        (repo / mcpdecl.SIDECAR).read_text(encoding="utf-8"))[mcpdecl.SERVERS_KEY]
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
    servers = json.loads(
        (repo / mcpdecl.SIDECAR).read_text(encoding="utf-8"))[mcpdecl.SERVERS_KEY]
    assert servers["mine"] == {"command": "my-own-thing"}, \
        "boost must only reverse what boost wrote"


def test_a_user_install_writes_no_sidecar_into_the_repo(boost, tapped, repo):
    # The complement: user scope must not start scattering .mcp.json files into
    # whatever directory the install happened to run from.
    from boost_cli.core import mcpdecl
    _declare_mcp(tapped, "brainstorming")
    boost("install", "brainstorming")
    assert not (repo / mcpdecl.SIDECAR).exists()


# ── an unmarked directory is a project to every command, or to none ──────
#
# `install --local` writes there and says so. Before this, `verify`, `list`,
# `doctor` and bare `uninstall` all answered "not installed" for what it had
# just written, while `sync` could still see it and offered to re-materialize
# it. The split was `scopes.project_root` (readers) against
# `scopes.resolve_base` (writers); the fix is that everyone asks the latter.

def test_unmarked_dir_install_then_every_command_agrees(boost, tapped,
                                                        plain_dir):
    boost("install", "brainstorming", "--local")
    assert (plain_dir / ".boost" / "skill-lock.json").is_file()
    assert (plain_dir / ".claude" / "skills" / "brainstorming"
            / "SKILL.md").is_file()

    named = boost("verify", "brainstorming")
    assert "brainstorming" in named.out

    listed = boost("list", "--local")
    assert "brainstorming" in listed.out

    doc = boost("doctor")
    assert "brainstorming" in doc.out or "project skill" in doc.out

    boost("uninstall", "brainstorming")
    assert projectlock.get_skill(plain_dir, "brainstorming") is None
    assert not (plain_dir / ".claude" / "skills" / "brainstorming").exists()


def test_unmarked_dir_info_is_not_the_not_installed_card(boost, tapped,
                                                         plain_dir):
    boost("install", "brainstorming", "--local")
    res = boost("info", "brainstorming")
    assert "installed in this project" in res.out
    assert "version" in res.out


def test_unmarked_dir_verify_json_tags_the_project_scope(boost, tapped,
                                                         plain_dir):
    boost("install", "brainstorming", "--local")
    data = json.loads(boost("verify", "--json").out)
    assert {r["scope"] for r in data["skills"]} == {"project"}


def test_home_is_still_never_a_project(boost, tapped, monkeypatch):
    """Widening the read side must not widen it to `$HOME`.

    A "project" install into `$HOME` writes into exactly the directories user
    scope owns, so `resolve_base` returns None there — the one case the
    walk-up's `$HOME` stop exists for, and the reason this fix could not just
    delete `project_root`'s guard.
    """
    monkeypatch.chdir(paths.home())
    assert scopes.resolve_base(scopes.SCOPE_PROJECT) is None
    res = boost("list", "--local")
    assert "project skills" not in res.out


# ── verify: a named project skill does not drag in user scope ────────────

def test_verify_named_project_skill_ignores_user_scope(boost, tapped, repo):
    """`[]` means "no user-scope items", not "all of them".

    `cmd_verify` drops names the user lock cannot resolve, so a project-only
    name leaves the filter empty — and a truthiness test read that as "grade
    everything", failing the run on an item the user never named.
    """
    boost("install", "commit-messages")                 # user scope
    boost("install", "brainstorming", "--local")        # project scope
    store_md = paths.store_dir() / "commit-messages" / "SKILL.md"
    store_md.write_text("TAMPERED\n", encoding="utf-8")

    # Unnamed still grades both, and still fails on the tampered one.
    every = boost("verify", expect=1)
    assert "commit-messages" in every.out

    res = boost("verify", "brainstorming")
    assert "brainstorming" in res.out
    assert "commit-messages" not in res.out
    assert "no skills installed" not in res.out


def test_verify_named_project_skill_json_holds_only_that_name(boost, tapped,
                                                              repo):
    boost("install", "commit-messages")
    boost("install", "brainstorming", "--local")
    data = json.loads(boost("verify", "brainstorming", "--json").out)
    assert [r["name"] for r in data["skills"]] == ["brainstorming"]
    assert data["failed"] == 0


# ── list --local: project scope holds all three kinds ────────────────────

def test_list_local_shows_a_project_rule(boost, tapped, repo):
    """The card's premise was that project scope is skills-only. It is not.

    A rule installed with `--local` materializes into the repo but is recorded
    in the USER lock with scope+base, because a project lock has no rules
    section. `--local` used to clear that dict, so the one command that should
    have shown the rule was the one that denied it.
    """
    lockfile.set_rule("house-style", {
        "kind": "rule", "version": "1.0.0", "tap": "acme/rules",
        "scope": "project", "base": str(repo),
        "materializations": [{"agent": "claude-code", "mode": "claude"}]})
    res = boost("list", "--local", "--kind", "rule")
    assert "house-style" in res.out
    assert "no rules installed" not in res.out


def test_list_local_hides_another_repos_rule(boost, tapped, repo, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    lockfile.set_rule("theirs", {
        "kind": "rule", "version": "1.0.0", "tap": "acme/rules",
        "scope": "project", "base": str(other),
        "materializations": [{"agent": "claude-code", "mode": "claude"}]})
    res = boost("list", "--local", "--kind", "rule")
    assert "theirs" not in res.out


def test_list_local_hides_a_user_scope_rule(boost, tapped, repo):
    lockfile.set_rule("mine", {
        "kind": "rule", "version": "1.0.0", "tap": "acme/rules",
        "materializations": [{"agent": "claude-code", "mode": "claude"}]})
    res = boost("list", "--local", "--kind", "rule")
    assert "mine" not in res.out
    # ...and plain `list` still shows it.
    assert "mine" in boost("list", "--kind", "rule").out


def test_list_local_json_keeps_the_four_key_shape(boost, tapped, repo):
    lockfile.set_workflow("ship-it", {
        "kind": "workflow", "version": "1.0.0", "tap": "acme/wf",
        "slot": "commands", "scope": "project", "base": str(repo),
        "materializations": [{"agent": "claude-code", "slot": "commands"}]})
    data = json.loads(boost("list", "--local", "--json").out)
    assert set(data) == {"skills", "rules", "workflows", "project"}
    assert "ship-it" in data["workflows"]
    assert data["skills"] == {}


# ── uninstall --local: the flag that installed it can undo it ────────────
#
# These drive a REAL install rather than a synthesized lock row, because the
# bug was that two commands read two different files for one answer: a
# hand-written row can agree with whichever of them the test happens to call.


@pytest.fixture()
def trio_tap(boost, fixture_tap_src, tmp_path):
    """The fixture tap plus one rule and one workflow, tapped.

    The session fixture ships skills only, and the kinds that reproduce this
    are the two a project lock cannot hold.
    """
    tap = tmp_path / "trio-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "house.mdc").write_text(
        "---\nname: house-style\nversion: 1.0.0\n---\n\nAlways write tests first.\n",
        encoding="utf-8")
    (tap / "commands").mkdir()
    (tap / "commands" / "ship-it.md").write_text(
        "---\nname: ship-it\nversion: 1.0.0\n---\n\nShip-it checklist body.\n",
        encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=tap, check=True, capture_output=True)
    run("git", "add", "-A")
    run("git", "commit", "-qm", "add a rule and a workflow")
    boost("tap", str(tap))
    return tap


def test_uninstall_local_removes_the_project_rule_list_local_shows(
        boost, trio_tap, repo):
    """The card, end to end: shown by one command, denied by the other."""
    boost("install", "house-style", "--local")
    rows = [Path(m["path"])
            for m in lockfile.get_rule("house-style")["materializations"]]
    assert rows, "nothing materialized — this would assert nothing"
    assert "house-style" in boost("list", "--local", "--kind", "rule").out

    res = boost("uninstall", "house-style", "--local", "-y")

    assert lockfile.get_rule("house-style") is None
    for p in rows:
        # The claude-mode rows are a managed block in a context file boost
        # created, so the file goes with the block; the file rows are deleted
        # outright. Either way nothing the install wrote is left behind.
        assert not p.exists(), p
    assert "no rules installed" in boost("list", "--local", "--kind", "rule").out
    # The *repo*, not just the agents. `cmd_uninstall` prints "removed from
    # <agent · agent · …>" for any rule, so a bare `"removed from" in out`
    # passes with the scope and base never reaching the result at all — it
    # asserts the line this change did not add. Wrapping folds the path, so
    # compare against the unfolded output.
    flat = " ".join(res.out.split())
    assert "removed from %s" % paths.tilde(repo) in flat, flat


def test_uninstall_local_removes_a_project_workflow(boost, trio_tap, repo):
    boost("install", "ship-it", "--local")
    rows = [Path(m["path"])
            for m in lockfile.get_workflow("ship-it")["materializations"]]
    assert rows
    boost("uninstall", "ship-it", "--local", "-y")
    assert lockfile.get_workflow("ship-it") is None
    for p in rows:
        assert not p.exists(), p


def test_uninstall_local_leaves_a_user_scope_rule_alone(boost, trio_tap, repo):
    """`--local` narrows what may be removed; it never widens it.

    The rule lives in the user's own config. Removing it under a flag that
    names the repo would be the opposite of this command's contract, and the
    old message — "not installed in this project" — sent the reader to `boost
    list --local`, which correctly shows nothing. Message and remedy agreed
    with each other and not with the machine.
    """
    boost("install", "house-style")
    rows = [Path(m["path"])
            for m in lockfile.get_rule("house-style")["materializations"]]

    res = boost("uninstall", "house-style", "--local", "-y", expect=1)

    assert lockfile.get_rule("house-style") is not None
    assert all(p.exists() for p in rows)
    flat = " ".join((res.out + " " + res.err).split())
    assert "user scope" in flat
    assert "boost uninstall house-style" in flat


def test_uninstall_local_leaves_another_repos_rule_alone(boost, trio_tap, repo,
                                                         tmp_path):
    other = tmp_path / "elsewhere"
    (other / ".git").mkdir(parents=True)
    # Hand-written, because the point is a row this repo must not touch: a
    # real second install would need a second cwd and would prove no more.
    lockfile.set_rule("theirs", {
        "kind": "rule", "version": "1.0.0", "tap": "trio-tap",
        "scope": "project", "base": str(other),
        "materializations": [{"agent": "claude-code", "mode": "claude",
                              "path": str(other / "CLAUDE.local.md")}]})
    (other / "CLAUDE.local.md").write_text("their rules\n", encoding="utf-8")

    res = boost("uninstall", "theirs", "--local", "-y", expect=1)

    assert lockfile.get_rule("theirs") is not None
    assert (other / "CLAUDE.local.md").read_text(encoding="utf-8") == "their rules\n"
    flat = " ".join((res.out + " " + res.err).split())
    assert str(other) in flat


def test_uninstall_local_still_denies_a_name_nothing_installed(boost, tapped,
                                                               repo):
    res = boost("uninstall", "nope", "--local", "-y", expect=1)
    flat = " ".join((res.out + " " + res.err).split())
    assert "nope is not installed in this project" in flat


# ── info on a project-scoped skill ───────────────────────────────────────

def test_info_project_skill_shows_its_identity_rows(boost, tapped, repo):
    boost("install", "brainstorming", "--local")
    res = boost("info", "brainstorming")
    assert "installed in this project" in res.out
    for row in ("version", "commit", "sha256", "installed", "agents"):
        assert row in res.out, "missing the %s row" % row
    # The value, not just the label: a card printing `scope  user` for a
    # project-only install would satisfy a substring check for "scope".
    assert re.search(r"^\s*scope\s+project\s*$", res.out, re.M), (
        "the scope row must read project:\n%s" % res.out)
    # And the version is the repo's record, not the catalog's "latest".
    entry = projectlock.get_skill(repo, "brainstorming")
    assert re.search(r"^\s*version\s+%s\s*$" % re.escape(entry["version"]),
                     res.out, re.M)


def test_info_project_skill_omits_the_user_only_rows(boost, tapped, repo):
    """Omit rather than blank: a project entry has no such keys.

    Printing `pinned no` would assert a field `store._install_project_skill`
    never writes, and there is no canonical store in a repo to point `store`
    at.
    """
    boost("install", "brainstorming", "--local")
    res = boost("info", "brainstorming")
    assert "pinned" not in res.out
    assert "quarantined" not in res.out
    assert "store" not in res.out


def test_info_user_scope_card_is_unchanged_by_the_project_read(boost, tapped,
                                                               repo):
    boost("install", "brainstorming")
    res = boost("info", "brainstorming")
    assert "pinned" in res.out and "quarantined" in res.out
    assert "store" in res.out
    assert "scope" not in res.out, "user scope needs no scope row to disambiguate"


def test_info_names_both_copies_when_both_scopes_hold_it(boost, tapped, repo):
    boost("install", "brainstorming")
    boost("install", "brainstorming", "--local")
    res = boost("info", "brainstorming")
    assert "also in this project" in res.out
    # User scope still wins the identity rows.
    assert "pinned" in res.out


# ── the confirmation names where it is about to delete from ──────────────

def _tty(monkeypatch, answers):
    """Make the prompt fire and record what it was asked."""
    asked = []
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def fake_confirm(prompt, *a, **k):
        asked.append(prompt)
        return answers.pop(0)

    monkeypatch.setattr("boost_cli.core.output.confirm", fake_confirm)
    return asked


def test_bare_uninstall_prompt_names_the_project_it_will_delete_from(
        boost, tapped, repo, monkeypatch):
    """The success line must not be the first mention of where.

    Bare `uninstall` can now act in a directory carrying a committed
    `.boost/`, including one with no VCS marker, so someone who means their
    user config has to be told which directory this is about before it goes.
    """
    boost("install", "brainstorming", "--local")
    asked = _tty(monkeypatch, [True])
    boost("uninstall", "brainstorming")
    assert asked, "the prompt never fired"
    assert "uninstall brainstorming from " in asked[0]
    assert repo.name in asked[0]
    assert projectlock.get_skill(repo, "brainstorming") is None


def test_bare_uninstall_prompt_stays_generic_for_a_user_scope_name(
        boost, tapped, repo, monkeypatch):
    """A user-scope removal must not be described as a repo one."""
    boost("install", "brainstorming")
    asked = _tty(monkeypatch, [True])
    boost("uninstall", "brainstorming")
    assert asked == ["uninstall brainstorming?"]


def test_bare_uninstall_prompt_names_the_subset_for_a_mixed_batch(
        boost, tapped, repo, monkeypatch):
    """One answer cannot describe two destinations.

    `commit-messages` is user-scope and `brainstorming` is project-scope.
    Saying "from <repo>" would describe the wrong half, and saying nothing
    would drop the warning for exactly the case the reader is least likely to
    expect — so the prompt names which of them comes out of the repo.
    """
    boost("install", "commit-messages")
    boost("install", "brainstorming", "--local")
    asked = _tty(monkeypatch, [True])
    boost("uninstall", "brainstorming", "commit-messages")
    assert len(asked) == 1
    assert asked[0].startswith(
        "uninstall 2 skills: brainstorming, commit-messages? (brainstorming from ")
    assert "commit-messages from" not in asked[0]
    assert repo.name in asked[0]
    assert projectlock.get_skill(repo, "brainstorming") is None
    assert lockfile.get_skill("commit-messages") is None


def test_declining_the_prompt_removes_nothing(boost, tapped, repo, monkeypatch):
    boost("install", "brainstorming", "--local")
    _tty(monkeypatch, [False])
    boost("uninstall", "brainstorming", expect=1)
    assert projectlock.get_skill(repo, "brainstorming") is not None


def _set_project_version(base, version: str) -> None:
    entry = dict(projectlock.get_skill(base, "brainstorming") or {})
    entry["version"] = version
    projectlock.set_skill(base, "brainstorming", entry)


def test_info_project_skill_behind_its_tap_gets_the_badge(boost, tapped, repo):
    """The staleness badge follows the record the card is read off.

    `relation` is computed from `lock or plock`, so the "latest" row already
    printed "(update available)" for a project-only install — but the badge
    that says the same thing sat inside the user-scope arm, so the strip
    contradicted the row two lines below it.
    """
    boost("install", "brainstorming", "--local")
    _set_project_version(repo, "1.3.0")
    res = boost("info", "brainstorming")
    assert "[update available]" in res.out, res.out
    assert re.search(r"latest\s+1\.4\.0\s+\(update available\)", res.out)


def test_info_project_skill_ahead_of_its_tap_gets_the_badge(boost, tapped,
                                                            repo):
    boost("install", "brainstorming", "--local")
    _set_project_version(repo, "1.4.1")
    res = boost("info", "brainstorming")
    assert "[ahead of tap]" in res.out, res.out
    assert "update available" not in res.out


def test_info_not_installed_card_still_has_no_staleness_badge(boost, tapped,
                                                              repo):
    # `relation` is None without a record to compare, so moving the badges out
    # of the `if lock:` arm must not start decorating a card for something
    # that is not installed anywhere.
    res = boost("info", "brainstorming")
    assert "not installed" in res.out
    assert "update available" not in res.out
    assert "ahead of tap" not in res.out


def test_doctor_summary_counts_the_project_skills_it_just_listed(
        boost, tapped, repo):
    """"0 skills installed" next to "1 project skill intact" is two answers.

    `skills` in the summary is the user store, so in a repo holding committed
    skills the one-line verdict contradicted the row three lines above it.
    They stay two numbers rather than one total: they live in different
    places and `boost uninstall` treats them differently, so summing them
    would be a different claim, not a clearer one.
    """
    boost("install", "brainstorming", "--local")
    res = boost("doctor")
    assert "1 project skill intact" in res.out
    assert "0 skills installed (+1 in this project)" in res.out


def test_doctor_summary_says_nothing_extra_without_a_project(boost, tapped):
    """A machine with no project skills reads exactly as it always did."""
    boost("install", "brainstorming")
    res = boost("doctor")
    assert "1 skill installed ·" in res.out
    assert "in this project" not in res.out
