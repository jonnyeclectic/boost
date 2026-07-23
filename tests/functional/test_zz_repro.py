from __future__ import annotations

import shutil

import pytest

from boost_cli.core import agents, projectlock


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    d = tmp_path / "myrepo"
    (d / ".git").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


def test_what_agents(boost, tapped, repo):
    print("ENABLED:", agents.enabled_agents())


def test_scenario_A_edited_committed_copy(boost, tapped, repo):
    """Multi-agent project install; team edits the committed .claude copy;
    .cursor is gitignored so it's missing on a fresh clone; plain `boost sync`."""
    boost("install", "brainstorming", "--local")
    print("DIRS:", sorted(str(p) for p in repo.rglob("skills/brainstorming")))
    claude = repo / ".claude" / "skills" / "brainstorming" / "SKILL.md"
    claude.write_text("---\nname: brainstorming\n---\nTEAM-EDIT-SENTINEL\n",
                      encoding="utf-8")
    # a second agent dir that the repo gitignores -> absent after clone
    others = [p for p in repo.rglob("skills/brainstorming")
              if ".claude" not in str(p)]
    print("OTHERS:", others)
    for o in others:
        shutil.rmtree(o)
    res = boost("sync")
    print("SYNC OUT:", res.out)
    txt = claude.read_text(encoding="utf-8")
    print("TEAM EDIT SURVIVED:", "TEAM-EDIT-SENTINEL" in txt)


def test_scenario_B_handwritten_dir_for_unrecorded_agent(boost, tapped, repo):
    """Install scoped to one agent only; a hand-written skill of the same name
    for another agent; the recorded one goes missing -> plain `boost sync`."""
    enabled = list(agents.enabled_agents())
    print("ENABLED:", enabled)
    boost("install", "brainstorming", "--local", "--agent", enabled[-1])
    entry = projectlock.get_skill(repo, "brainstorming")
    print("LOCK:", entry["materializations"])
    mine = repo / ".claude" / "skills" / "brainstorming"
    mine.mkdir(parents=True, exist_ok=True)
    (mine / "SKILL.md").write_text("HAND-WRITTEN-SENTINEL\n", encoding="utf-8")
    recorded = [p for p in repo.rglob("skills/brainstorming")
                if ".claude" not in str(p)]
    print("RECORDED DIRS:", recorded)
    for r in recorded:
        shutil.rmtree(r)
    res = boost("sync", "--diff")
    print("DIFF OUT:", res.out)
    res = boost("sync")
    print("SYNC OUT:", res.out)
    surv = (mine / "SKILL.md").read_text(encoding="utf-8")
    print("SENTINEL SURVIVED:", "HAND-WRITTEN-SENTINEL" in surv)
