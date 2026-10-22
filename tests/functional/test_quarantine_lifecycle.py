# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional: what every command does to an item while it is quarantined.

A quarantine is lifted by `boost quarantine --release` and by nothing else:
`reinstall` and `install --force` used to lift it silently, throwing the
held copy away. A release must not overwrite a file the user wrote at the
item's path meanwhile, nor report success over a held copy that is gone.
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from boost_cli.core import lockfile, paths, store, util

RULE = "no-yolo"
WORKFLOW = "ship-it"


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture()
def rwtap(boost, fixture_tap_src, tmp_path):
    """The fixture tap plus one rule and one workflow, tapped."""
    tap = tmp_path / "rw-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / ("%s.mdc" % RULE)).write_text(
        "---\nname: %s\nversion: 1.1.0\n---\n\nNever run with --yolo.\n"
        % RULE, encoding="utf-8")
    (tap / "commands").mkdir()
    (tap / "commands" / ("%s.md" % WORKFLOW)).write_text(
        "---\nname: %s\nversion: 1.1.0\n---\n\nShip-it checklist body.\n"
        % WORKFLOW, encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm", "rule+workflow"],
                   check=True, capture_output=True)
    boost("tap", tap)
    return tap


class TestReinstallHoldsAQuarantineBack:
    def test_reinstall_all_skips_quarantined_items(self, boost, rwtap):
        boost("install", "brainstorming", "tdd-workflow", RULE)
        boost("quarantine", "brainstorming")
        boost("quarantine", RULE)
        held = store.held_copy_dir("brainstorming") / "SKILL.md"
        held.write_text(held.read_text(encoding="utf-8") + "\nmy edit\n",
                        encoding="utf-8")
        r = boost("reinstall", "--all")
        assert "reinstalled tdd-workflow" in r.out
        assert "reinstalled brainstorming" not in r.out
        assert "reinstalled rule %s" % RULE not in r.out
        assert "Reinstalled 1 skill" in r.out
        assert ("2 quarantined items held back — `boost quarantine --release "
                "<name>` lets one be reinstalled") in _flat(r.out)
        entry = lockfile.get_skill("brainstorming")
        assert entry["quarantined"] is True and store.is_held(entry)
        assert "my edit" in held.read_text(encoding="utf-8")
        assert not os.path.lexists(
            paths.home() / ".claude" / "skills" / "brainstorming")
        assert lockfile.get_rule(RULE)["quarantined"] is True
        r = boost("quarantine", "--list")
        assert "brainstorming" in r.out and RULE in r.out

    def test_reinstall_all_says_one_item_in_the_singular(self, boost, rwtap):
        boost("install", "brainstorming", "tdd-workflow")
        boost("quarantine", "brainstorming")
        r = boost("reinstall", "--all")
        assert ("1 quarantined item held back — `boost quarantine --release "
                "<name>` lets one be reinstalled") in _flat(r.out)

    @pytest.mark.parametrize("name", ["brainstorming", RULE])
    def test_a_named_reinstall_is_refused(self, boost, rwtap, name):
        boost("install", name)
        boost("quarantine", name)
        r = boost("reinstall", name, expect=1)
        label = name if name == "brainstorming" else "rule %s" % name
        assert ("%s is quarantined — not reinstalled — `boost quarantine "
                "--release %s` first" % (label, name)) in _flat(r.err)
        assert "reinstalled" not in r.out
        assert lockfile.find_any(name)[1]["quarantined"] is True

    @pytest.mark.parametrize("force", [(), ("--force",)])
    def test_install_names_the_release_not_reinstall(self, boost, rwtap,
                                                     force):
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        r = boost("install", "brainstorming", *force, expect=1)
        both = _flat(r.out + r.err)
        assert "brainstorming is quarantined — not reinstalled" in both
        assert "`boost quarantine --release brainstorming` first" in both
        assert "boost reinstall" not in both
        assert lockfile.get_skill("brainstorming")["quarantined"] is True

    def test_release_then_reinstall_works(self, boost, rwtap):
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        boost("quarantine", "--release", "brainstorming")
        r = boost("reinstall", "brainstorming")
        assert "reinstalled brainstorming" in r.out


class TestReleaseWithALostHeldCopy:
    def test_release_fails_and_doctor_names_the_way_back(self, boost, rwtap):
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        util.rmtree(store.held_copy_dir("brainstorming"))
        r = boost("doctor", expect=None)
        assert ("skill brainstorming is quarantined, but its held copy is "
                "gone — `boost uninstall brainstorming` drops the record, "
                "then `boost install brainstorming` fetches it again"
                ) in _flat(r.out + r.err)
        assert "run `boost heal`" not in _flat(r.out + r.err)
        r = boost("quarantine", "--release", "brainstorming", expect=1)
        assert "brainstorming has no held copy to release" in _flat(r.err)
        assert "`boost uninstall brainstorming` drops the record" in _flat(
            r.err)
        assert "released" not in r.out
        for agent in (".claude", ".cursor", ".windsurf"):
            assert not os.path.lexists(
                paths.home() / agent / "skills" / "brainstorming")
        assert lockfile.get_skill("brainstorming")["quarantined"] is True
        # The way back it names works.
        boost("uninstall", "brainstorming")
        boost("install", "brainstorming")
        assert (paths.home() / ".claude" / "skills" / "brainstorming"
                / "SKILL.md").is_file()


class TestReleaseKeepsAFileTheUserWrote:
    @pytest.mark.parametrize(("name", "rel"), [
        (WORKFLOW, (".claude", "commands", "%s.md" % WORKFLOW)),
        (RULE, (".cursor", "rules", "%s.mdc" % RULE)),
    ])
    def test_release_leaves_it_and_records_it_foreign(self, boost, rwtap,
                                                       name, rel):
        boost("install", name)
        boost("quarantine", name)
        mine = paths.home().joinpath(*rel)
        assert not mine.exists()
        mine.parent.mkdir(parents=True, exist_ok=True)
        mine.write_text("MY OWN file - do not lose\n", encoding="utf-8")
        r = boost("quarantine", "--release", name)
        kind = "workflow" if name == WORKFLOW else "rule"
        agent = "claude-code" if name == WORKFLOW else "cursor"
        assert ("not written: %s exists and is not managed by boost — left "
                "alone; move it aside, then `boost sync` writes it"
                % paths.tilde(mine)) in _flat(r.out + r.err)
        released = next(line for line in r.out.splitlines()
                        if "released %s %s" % (kind, name) in line)
        assert agent not in released
        assert mine.read_text(encoding="utf-8") == "MY OWN file - do not lose\n"
        entry = lockfile.find_any(name)[1]
        assert entry["quarantined"] is False
        assert str(mine) not in [m["path"] for m in entry["materializations"]]
        assert [f["path"] for f in store.foreign_rows(entry)] == [str(mine)]
        assert store.foreign_rows(entry)[0]["agent"] == agent
        # Other agents were restored.
        assert entry["materializations"]
        for m in entry["materializations"]:
            if not lockfile.is_skill_copy(m) and m.get("mode") != "claude":
                assert os.path.isfile(m["path"])
        # Uninstall never takes the user's file with it.
        boost("uninstall", name)
        assert mine.read_text(encoding="utf-8") == "MY OWN file - do not lose\n"

    def test_the_stashed_text_itself_is_restored_over(self, boost, rwtap):
        boost("install", WORKFLOW)
        cmd = paths.home() / ".claude" / "commands" / ("%s.md" % WORKFLOW)
        before = cmd.read_text(encoding="utf-8")
        boost("quarantine", WORKFLOW)
        # An interrupted quarantine leaves exactly the stashed text behind.
        cmd.write_text(before, encoding="utf-8")
        r = boost("quarantine", "--release", WORKFLOW)
        assert "not written" not in r.out + r.err
        entry = lockfile.get_workflow(WORKFLOW)
        assert str(cmd) in [m["path"] for m in entry["materializations"]]
        assert not store.foreign_rows(entry)


class TestOneQuarantineLabelForEveryKind:
    def test_verify_and_drift_label_skill_and_rule_alike(self, boost, rwtap):
        import json
        boost("install", "brainstorming", RULE)
        boost("quarantine", "brainstorming")
        boost("quarantine", RULE)
        r = boost("verify")
        rows = {line.split()[0]: line.split()[1] for line in r.out.splitlines()
                if line.startswith("  ") and line.split()[0] != "✓"}
        assert rows == {"brainstorming": "quarantined", RULE: "quarantined"}
        rows = json.loads(boost("verify", "--json").out)["skills"]
        skill = next(x for x in rows if x["name"] == "brainstorming")
        assert skill["status"] == "quarantined"
        assert skill["quarantined"] is True and skill["passed"] is True
        drift = json.loads(boost("drift", "--json").out)["skills"]
        assert {d["name"]: d["status"] for d in drift} == {
            "brainstorming": "quarantined", RULE: "quarantined"}
        assert next(d for d in drift if d["name"] == "brainstorming")[
            "hint"] == ("boost quarantine --release brainstorming to restore")

    def test_an_edited_held_copy_fails_verify_drift_and_doctor(self, boost,
                                                               rwtap):
        import json
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        md = store.held_copy_dir("brainstorming") / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "edit\n",
                      encoding="utf-8")
        r = boost("verify", "brainstorming", expect=1)
        line = next(x for x in r.out.splitlines() if "brainstorming" in x)
        assert line.split()[1] == "modified"
        assert "quarantined" in line
        assert "`boost quarantine --list` to review it" in line
        drift = json.loads(boost("drift", "--json").out)["skills"]
        assert drift[0]["status"] == "local-edits"
        r = boost("doctor", expect=None)
        assert r.rc != 0
        assert ("quarantined skill brainstorming modified since install (its "
                "held copy) — run `boost quarantine --list` to review it"
                ) in _flat(r.out + r.err)
        assert "healthy" not in r.out.splitlines()[-1]

    def test_a_lost_held_copy_drifts_to_the_way_back(self, boost, rwtap):
        import json
        boost("install", "brainstorming")
        boost("quarantine", "brainstorming")
        util.rmtree(store.held_copy_dir("brainstorming"))
        drift = json.loads(boost("drift", "--json").out)["skills"]
        assert drift[0]["status"] == "store-missing"
        assert drift[0]["hint"] == (
            "boost uninstall brainstorming drops the record, then boost "
            "install brainstorming fetches it again")
