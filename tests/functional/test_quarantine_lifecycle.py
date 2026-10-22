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
