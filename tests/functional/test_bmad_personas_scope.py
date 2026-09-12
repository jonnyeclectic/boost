# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost bmad personas` must not report installed personas as missing.

It defaulted to the global scope, so after a *project* install it read
``~/.claude/agents``, found nothing, and called seven personas sitting on disk
"not installed" — contradicting `boost bmad status` run a moment later in the
same directory. `--help` even says the default should be project ("on/off
default: global; others: project").

Flipping the default would only have moved the false statement to the global
install, so the command now reports BOTH scopes when none is named, the way
`bmad status` always has.
"""
from __future__ import annotations

HEADING = "BMAD personas — %s"


def _section(text, scope):
    """The block of `boost bmad personas` output belonging to one scope."""
    head = HEADING % scope
    assert head in text, "no %r section in:\n%s" % (head, text)
    rest = text.split(head, 1)[1]
    other = HEADING % ("project" if scope == "global" else "global")
    return rest.split(other, 1)[0]


class TestPersonasNeverDeniesAnInstall:
    def test_a_project_install_is_reported_by_a_bare_call(self, boost, tmp_path,
                                                          monkeypatch):
        proj = tmp_path / "bmadproj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("bmad", "on", "--scope", "project")

        bare = boost("bmad", "personas").out
        assert "not installed" not in _section(bare, "project")

    def test_a_global_install_is_reported_by_a_bare_call(self, boost, tmp_path,
                                                         monkeypatch):
        """The mirror case — the one the old default happened to get right."""
        proj = tmp_path / "bmadproj2"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("bmad", "on", "--scope", "global")

        bare = boost("bmad", "personas").out
        assert "not installed" not in _section(bare, "global")

    def test_a_bare_call_reports_both_scopes(self, boost, tmp_path, monkeypatch):
        proj = tmp_path / "bmadproj3"
        proj.mkdir()
        monkeypatch.chdir(proj)
        r = boost("bmad", "personas")
        assert HEADING % "global" in r.out
        assert HEADING % "project" in r.out

    def test_it_agrees_with_status(self, boost, tmp_path, monkeypatch):
        """The two commands answered the same question differently."""
        proj = tmp_path / "bmadproj4"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("bmad", "on", "--scope", "project")

        assert "not installed" not in _section(boost("bmad", "personas").out,
                                               "project")
        status = boost("bmad", "status").out
        assert "autopilot=on" in status

    def test_an_explicit_scope_still_reports_only_that_scope(self, boost, tmp_path,
                                                             monkeypatch):
        """Fixing the default must not take the flag away."""
        proj = tmp_path / "bmadproj5"
        proj.mkdir()
        monkeypatch.chdir(proj)
        boost("bmad", "on", "--scope", "project")

        r = boost("bmad", "personas", "--scope", "global")
        assert HEADING % "global" in r.out
        assert HEADING % "project" not in r.out
        assert "not installed" in r.out
