# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: ``boost install <tap>`` installs every skill a tap ships.

The tap's own name as NAME lists the skills, says which it leaves out and
why, and asks before writing anything. An item of that name still wins, a
skill already installed from the tap is not a failure, and rules and
workflows are never swept in.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, registry

FIXTURE_SKILLS = ["brainstorming", "commit-messages", "cowboy-coding",
                  "jira-integration", "tdd-workflow"]


def _tap_name() -> str:
    taps = [t.name for t in registry.list_taps() if t.name != "boost/builtin"]
    assert len(taps) == 1, taps
    return taps[0]


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True)


def _variant(fixture_tap_src, dest, files: dict[str, str]):
    """The fixture tap copied to ``dest`` with ``files`` added and committed."""
    shutil.copytree(fixture_tap_src, dest)
    for rel, text in files.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(dest, "add", "-A")
    _git(dest, "-c", "user.email=t@boost.test", "-c", "user.name=t",
         "commit", "-qm", "variant")
    return dest


def _skill_md(name, desc, body="Body."):
    return ("---\nname: %s\ndescription: %s\nversion: 1.0.0\n---\n\n%s\n"
            % (name, desc, body))


def _installed() -> list[str]:
    return sorted(lockfile.installed())


def test_tap_name_lists_then_installs_every_skill(boost, tapped):
    tap = _tap_name()
    r = boost("install", tap)
    assert "%s: 5 skills to install" % tap in r.out
    for name in FIXTURE_SKILLS:
        assert name in r.out
    assert _installed() == FIXTURE_SKILLS
    assert all(lockfile.get_skill(n)["tap"] == tap for n in FIXTURE_SKILLS)
    assert "Installed 5 new skills" in r.out


def test_without_a_terminal_or_yes_it_asks_and_declines(boost, tapped,
                                                        monkeypatch):
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    r = boost("install", _tap_name(), expect=1)
    assert "cancelled" in r.out
    # The list is on screen before the question, so the decline is informed.
    assert "brainstorming" in r.out
    assert _installed() == []


def test_yes_installs_without_asking(boost, tapped, monkeypatch):
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    boost("install", _tap_name(), "--yes")
    assert _installed() == FIXTURE_SKILLS


def test_answering_yes_at_the_prompt_installs(boost, tapped, monkeypatch):
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    from boost_cli.core import output
    asked = []
    monkeypatch.setattr(output, "stdin_is_tty", lambda *a: True)
    monkeypatch.setattr("builtins.input",
                        lambda prompt: asked.append(prompt) or "y")
    boost("install", _tap_name())
    assert asked == ["install 5 skills? [y/N] "]
    assert _installed() == FIXTURE_SKILLS


def test_dry_run_does_not_ask_and_writes_nothing(boost, tapped, monkeypatch):
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    r = boost("install", _tap_name(), "--dry-run")
    assert r.out.count("would install ") == 5
    assert "cancelled" not in r.out
    assert _installed() == []


def test_a_second_run_has_nothing_to_install_and_exits_0(boost, tapped):
    tap = _tap_name()
    boost("install", tap)
    r = boost("install", tap)
    assert "%s: 0 skills to install" % tap in r.out
    assert "already installed (5)" in r.out
    assert "nothing to install" in r.out


def test_only_the_skills_not_yet_installed_are_installed(boost, tapped):
    tap = _tap_name()
    boost("install", "brainstorming")
    r = boost("install", tap)
    assert "%s: 4 skills to install" % tap in r.out
    assert "already installed (1): brainstorming" in r.out
    assert "Installed 4 new skills" in r.out
    assert _installed() == FIXTURE_SKILLS


def test_force_reinstalls_what_is_already_there(boost, tapped):
    tap = _tap_name()
    boost("install", tap)
    r = boost("install", tap, "--force")
    assert "%s: 5 skills to install" % tap in r.out
    assert "Upgraded 5 skills" in r.out


def test_a_tap_named_beside_one_of_its_skills_installs_it_once(boost, tapped):
    r = boost("install", _tap_name(), "brainstorming")
    assert "Installed 5 new skills" in r.out
    assert "already installed" not in r.out + r.err


def test_an_item_of_that_name_wins_over_the_tap(boost, tapped,
                                                fixture_tap_src, tmp_path):
    # A tap whose name is also a skill's: the name keeps installing the
    # skill, as it did before a tap name meant anything to install.
    boost("tap", shutil.copytree(fixture_tap_src, tmp_path / "brainstorming"))
    assert registry.named("brainstorming") is not None
    r = boost("install", "brainstorming")
    assert "skills to install" not in r.out
    assert _installed() == ["brainstorming"]


def test_path_is_refused_for_a_tap(boost, tapped):
    r = boost("install", _tap_name(), "--path", "skills/x", expect=1)
    assert "not a tap's worth" in r.err
    assert _installed() == []


def test_an_untapped_repo_gets_the_tap_step(boost, tapped):
    r = boost("install", "nobody/nothing", expect=1)
    assert "no skill named 'nobody/nothing'" in r.err
    assert "`boost tap nobody/nothing` first" in r.err


def test_an_untapped_repo_among_several_names_says_so_too(boost, tapped):
    r = boost("install", "nobody/nothing", "brainstorming", expect=1)
    assert "`boost tap nobody/nothing` first" in r.out + r.err
    assert _installed() == ["brainstorming"]


def test_rules_and_workflows_are_left_out(boost, fixture_tap_src, tmp_path):
    src = _variant(fixture_tap_src, tmp_path / "mixed", {
        "rules/house.mdc": "---\nname: house\ndescription: House style.\n"
                           "version: 1.0.0\n---\n\nUse tabs.\n",
        "commands/ship.md": "---\ndescription: Ship it.\n---\n\nShip.\n",
    })
    boost("tap", src)
    r = boost("install", _tap_name())
    assert "not included: 1 rule, 1 workflow" in r.out
    assert _installed() == FIXTURE_SKILLS
    assert lockfile.installed_rules() == {}
    assert lockfile.installed_workflows() == {}


def test_a_tap_with_no_skills_says_what_it_does_ship(boost, tmp_path):
    root = tmp_path / "rules-only"
    (root / "rules").mkdir(parents=True)
    (root / "rules" / "house.mdc").write_text(
        "---\nname: house\ndescription: House style.\nversion: 1.0.0\n---\n\n"
        "Use tabs.\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=t@boost.test", "-c", "user.name=t",
         "commit", "-qm", "rules")
    boost("tap", root)
    r = boost("install", _tap_name(), expect=1)
    assert "ships no skills" in r.err
    assert "it ships 1 rule" in r.err


def test_differing_copies_of_one_name_are_skipped_not_failed(
        boost, fixture_tap_src, tmp_path):
    src = _variant(fixture_tap_src, tmp_path / "dupes", {
        "skills/dup/SKILL.md": _skill_md("dup", "First copy."),
        "plugins/p/skills/dup/SKILL.md": _skill_md("dup", "Second copy."),
    })
    boost("tap", src)
    r = boost("install", _tap_name())
    assert "dup: skipped — ships 2 different copies" in r.out + r.err
    assert "--path" in r.out + r.err
    assert _installed() == FIXTURE_SKILLS


def test_identical_vendored_copies_count_once(boost, fixture_tap_src,
                                              tmp_path):
    same = _skill_md("dup", "One skill, vendored.")
    src = _variant(fixture_tap_src, tmp_path / "vendored", {
        "skills/dup/SKILL.md": same,
        "plugins/p/skills/dup/SKILL.md": same,
    })
    boost("tap", src)
    r = boost("install", _tap_name())
    assert "6 skills to install" in r.out
    assert lockfile.get_skill("dup")["source_dir"] == "skills/dup"


def test_a_skill_installed_from_another_tap_is_skipped(boost, rival_tap):
    boost("install", "%s:brainstorming" % rival_tap)
    tap = next(t.name for t in registry.list_taps()
               if t.name not in (rival_tap, "boost/builtin"))
    r = boost("install", tap)
    assert "brainstorming: skipped — brainstorming is already installed" \
        in r.out + r.err
    assert "4 skills to install" in r.out
    assert lockfile.get_skill("brainstorming")["tap"] == rival_tap


def test_a_pinned_skill_from_the_tap_counts_as_installed(boost, tapped):
    tap = _tap_name()
    boost("install", "brainstorming")
    boost("pin", "brainstorming")
    r = boost("install", tap)
    assert "already installed (1): brainstorming" in r.out
    assert "is pinned" not in r.out + r.err


def test_project_scope_installs_into_the_repo(boost, tapped, sandbox):
    tap = _tap_name()
    r = boost("install", tap, "--local")
    assert "5 skills to install" in r.out
    assert _installed() == []
    lock = json.loads((sandbox.parent / "cwd" / ".boost" /
                       "skill-lock.json").read_text(encoding="utf-8"))
    assert sorted(lock["skills"]) == FIXTURE_SKILLS


@pytest.mark.parametrize("spelling", ["upper", "same"])
def test_the_tap_name_matches_case_blind(boost, tapped, spelling):
    tap = _tap_name()
    r = boost("install", tap.upper() if spelling == "upper" else tap)
    assert "Installed 5 new skills" in r.out


# ── what -y answers, and the list staying the list ─────────────────────────

def _mcp_tap(fixture_tap_src, dest):
    sidecar = {"mcpServers": {"srv": {"command": "touch", "args": ["x"]}}}
    return _variant(fixture_tap_src, dest, {
        "skills/needs-mcp/SKILL.md": "---\nname: needs-mcp\ndescription: "
                                     "Needs a server.\nversion: 1.0.0\nmcp: "
                                     "srv\n---\n\nBody.\n",
        "skills/needs-mcp/.mcp.json": json.dumps(sidecar),
    })


@pytest.fixture()
def registrations(monkeypatch):
    """Claude Code is the one MCP host on PATH; registrations are recorded."""
    from boost_cli.commands import pkg
    from boost_cli.core import mcphost
    calls = []
    real, hosts = shutil.which, {mcphost.cli(h) for h in mcphost.hosts()}
    monkeypatch.setattr("shutil.which", lambda n, *a, **kw: (
        "/usr/bin/" + n if n == "claude" else None if n in hosts
        else real(n, *a, **kw)))
    monkeypatch.setattr(pkg, "_register_mcp_server",
                        lambda name, spec, **kw: calls.append(name))
    return calls


def test_yes_does_not_also_register_mcp_servers(boost, fixture_tap_src,
                                               tmp_path, monkeypatch,
                                               registrations):
    boost("tap", _mcp_tap(fixture_tap_src, tmp_path / "mcp"))
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    r = boost("install", _tap_name(), "-y")
    assert "needs-mcp" in _installed()
    assert registrations == []
    assert "skipped — run these yourself" in r.out
    # The hint names the bypass that works for this prompt, not -y.
    assert "set BOOST_ASSUME_YES=1 to skip this prompt" in r.out
    assert "pass -y" not in r.out


def test_assume_yes_still_registers_them(boost, fixture_tap_src, tmp_path,
                                         registrations):
    boost("tap", _mcp_tap(fixture_tap_src, tmp_path / "mcp"))
    boost("install", _tap_name())
    assert registrations == ["srv"]


def test_max_skills_is_weighed_across_the_whole_tap(boost, tapped):
    boost("policy", "set", "max_skills", "2")
    r = boost("install", _tap_name())
    assert "2 skills to install" in r.out
    assert r.out.count("max_skills") + r.err.count("max_skills") == 3
    assert "Installed 2 new skills" in r.out
    assert len(_installed()) == 2


def test_a_blocked_dependency_is_skipped_before_the_prompt(boost, tapped,
                                                           monkeypatch):
    boost("policy", "set", "blocked_skills", "commit-messages")
    from boost_cli.core import output
    asked = []
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    monkeypatch.setattr(output, "stdin_is_tty", lambda *a: True)
    monkeypatch.setattr("builtins.input",
                        lambda prompt: asked.append(prompt) or "y")
    r = boost("install", _tap_name())
    # jira-integration requires commit-messages: the plan pulls it in, and
    # the same policy that skipped it from the list drops it from the plan.
    assert asked == ["install 4 skills? [y/N] "]
    assert (r.out + r.err).count("commit-messages: skipped") == 1
    assert "commit-messages" not in _installed()
    assert "Installed 4 new skills" in r.out


def test_two_taps_shipping_one_name_install_the_first_named(
        boost, fixture_tap_src, tmp_path):
    boost("tap", shutil.copytree(fixture_tap_src, tmp_path / "alpha"))
    beta = _variant(fixture_tap_src, tmp_path / "beta", {
        "skills/brainstorming/SKILL.md": _skill_md("brainstorming",
                                                   "Beta's own take."),
        "skills/only-beta/SKILL.md": _skill_md("only-beta", "Beta only."),
    })
    boost("tap", beta)
    names = {t.name.split("/")[-1]: t.name for t in registry.list_taps()}
    r = boost("install", names["alpha"], names["beta"])
    assert ("brainstorming: skipped — %s's copy is already part of this "
            "install" % names["alpha"]) in r.out + r.err
    assert lockfile.get_skill("brainstorming")["tap"] == names["alpha"]
    assert "only-beta" in _installed()
