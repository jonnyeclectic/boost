# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost bmad` and project scope: one root, and no error where there is none.

Two findings against the change that made project-scope hooks resolve through
`scopes.resolve_base`:

* `bmad doctor` and `bmad status` read project scope unasked, so from `$HOME`
  they died with "there is no project here" — on main both exit 0;
* `bmad on --scope project` from a repo subdirectory wrote its hooks at the
  repo root but its personas and state under the cwd, so `doctor` at the root
  and in the subdirectory disagreed about the one install.
"""
from __future__ import annotations

import pytest

from boost_cli.core import bmad as core_bmad
from boost_cli.core import claude_settings as cs


def _persona_files(agents_dir):
    return sorted(p.name for p in agents_dir.glob("bmad-*.md"))


class TestFromHome:
    def test_doctor_exits_zero(self, boost, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        r = boost("bmad", "doctor", expect=None)
        assert r.rc == 0, r.out + r.err
        assert "no project here" not in r.out + r.err
        assert "global" in r.out and "project" in r.out

    def test_status_exits_zero(self, boost, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        r = boost("bmad", "status", expect=None)
        assert r.rc == 0, r.out + r.err

    def test_global_hooks_are_not_read_as_the_projects(self, boost, sandbox,
                                                       monkeypatch):
        monkeypatch.chdir(sandbox)
        boost("bmad", "on", "--scope", "global", "--host", "claude")
        rows = {ln.split()[0]: ln for ln in boost("bmad", "doctor").out
                .splitlines() if "autopilot=" in ln}
        assert "router=on" in rows["global"]
        assert "router=off" in rows["project"]
        assert "briefing=off" in rows["project"]

    def test_startup_status_defaults_to_project_and_reports_absent(
            self, boost, sandbox, monkeypatch):
        monkeypatch.chdir(sandbox)
        boost("bmad", "on", "--scope", "global", "--host", "claude")
        r = boost("bmad", "startup", expect=None)
        assert r.rc == 0, r.out + r.err
        assert "BMAD startup — project" in r.out
        assert "absent" in r.out
        assert "present" not in r.out

    def test_on_project_refuses_before_writing_personas(self, boost, sandbox,
                                                        monkeypatch):
        monkeypatch.chdir(sandbox)
        r = boost("bmad", "on", "--scope", "project", "--host", "claude",
                  expect=None)
        assert r.rc == 1
        assert "no project here" in r.out + r.err
        assert _persona_files(sandbox / ".claude" / "agents") == []
        assert not cs.settings_path("global").exists()


class TestFromSubdirectory:
    @pytest.fixture()
    def repo(self, tmp_path, monkeypatch):
        root = tmp_path / "bmad-subdir-repo"
        deep = root / "src" / "deep"
        deep.mkdir(parents=True)
        (root / ".git").mkdir()
        monkeypatch.chdir(deep)
        return root

    def test_on_puts_hooks_personas_and_state_at_the_root(self, boost, repo,
                                                         monkeypatch):
        deep = repo / "src" / "deep"
        boost("bmad", "on", "--scope", "project", "--host", "claude")
        assert (repo / ".claude" / "settings.json").is_file()
        assert len(_persona_files(repo / ".claude" / "agents")) == len(
            core_bmad.PERSONAS)
        assert not (deep / ".claude").exists()
        from_deep = boost("bmad", "doctor").out
        monkeypatch.chdir(repo)
        from_root = boost("bmad", "doctor").out
        line = [ln for ln in from_root.splitlines()
                if ln.strip().startswith("project") and "autopilot=" in ln]
        assert line and "autopilot=on" in line[0]
        assert "router=on" in line[0]
        assert from_deep == from_root

    def test_off_from_the_root_removes_what_on_wrote_below(self, boost, repo,
                                                          monkeypatch):
        boost("bmad", "on", "--scope", "project", "--host", "claude")
        monkeypatch.chdir(repo)
        boost("bmad", "off", "--scope", "project")
        assert _persona_files(repo / ".claude" / "agents") == []
        assert _persona_files(repo / "src" / "deep" / ".claude" / "agents") == []
        assert cs.list_hooks("project") == []
