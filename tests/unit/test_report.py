# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The check collector that lets one command speak prose or JSON.

Every assertion here is a bug that would otherwise ship silently, because both
of this module's failure modes are quiet ones: prose that drifts from what the
command printed before, and a JSON payload that disagrees with the exit code
the same run returned.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import output as out
from boost_cli.core import report

# --------------------------------------------------------------- prose mode

def test_prose_mode_prints_the_same_glyphs_the_commands_printed_before(capsys):
    """Prose is the default and must be byte-identical to the old `out.*` calls.

    The whole sweep rests on this: `doctor` keeps its existing tests only
    because routing through the collector changes nothing a reader sees.
    """
    rep = report.Report()
    rep.ok("git", "git on PATH")
    rep.issue("lock", "lock file is corrupt")
    rep.note("crashes", "2 crash reports")
    rep.verdict(False, "1 issue needs attention")

    assert capsys.readouterr().out == (
        "  ✓ git on PATH\n"
        "  ! lock file is corrupt\n"
        "  2 crash reports\n"
        "  ● 1 issue needs attention\n"
    )


def test_json_mode_prints_nothing_at_all(capsys):
    """A single stray line makes the payload unparseable, so silence is the
    contract — not "mostly quiet"."""
    rep = report.Report(as_json=True)
    rep.ok("git", "git on PATH")
    rep.issue("lock", "lock file is corrupt")
    rep.note("crashes", "2 crash reports")
    rep.verdict(False, "1 issue needs attention")

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("status", ["issue", "warn", "note"])
def test_wrap_is_off_by_default_and_forwarded_when_asked(status, capsys):
    """`wrap` is opt-in per call site, and both directions are load-bearing.

    Defaulting it on would fold the lines that must stay whole — a hash, a
    path, a copy-pasteable command — which is why `out.warn`/`out.info` take it
    opt-in in the first place. Dropping it on the way through would leave
    doctor's prose hints running past the pane they were fitted to. (`ok` is
    absent on purpose: `out.ok` takes no `wrap`, and passing one would be a
    TypeError on a path a health check reaches.)
    """
    rep = report.Report()

    getattr(rep, status)("x", "a " * 60)
    assert len(capsys.readouterr().out.splitlines()) == 1

    getattr(rep, status)("x", "a " * 60, wrap=True)
    assert len(capsys.readouterr().out.splitlines()) > 1


# ------------------------------------------------------------ issue counting

def test_only_issues_raise_the_count():
    """The distinction doctor already makes and must not lose.

    Foreign symlinks, foreign hooks and crash reports are reported with
    `out.info` **on purpose**: boost will not fix them and `heal` deliberately
    leaves them, so counting them would leave doctor permanently red on
    something no boost command can clear. If `note` ever incremented, that
    design decision would be silently reversed.
    """
    rep = report.Report()
    rep.ok("a", "fine")
    rep.note("b", "history, not a fault")
    rep.ok("c", "also fine")
    assert rep.issues == 0

    rep.issue("d", "actually broken")
    assert rep.issues == 1
    rep.issue("e", "also broken")
    assert rep.issues == 2


def test_exit_code_follows_the_issue_count_not_the_check_count():
    """`1 if issues else 0` is doctor's contract; a run of pure `ok`s exits 0
    however many checks it ran."""
    rep = report.Report()
    for i in range(5):
        rep.ok("check-%d" % i, "fine")
    assert rep.exit_code() == 0

    rep.issue("bad", "broken")
    assert rep.exit_code() == 1


# ------------------------------------------------------------------- payload

def test_payload_records_every_check_in_order_with_its_status():
    rep = report.Report(as_json=True)
    rep.ok("git", "git on PATH")
    rep.issue("lock", "lock file is corrupt", hint="boost replay")
    rep.note("crashes", "2 crash reports")

    payload = rep.payload()
    assert payload["checks"] == [
        {"name": "git", "status": "ok", "message": "git on PATH", "hint": None},
        {"name": "lock", "status": "issue", "message": "lock file is corrupt",
         "hint": "boost replay"},
        {"name": "crashes", "status": "info", "message": "2 crash reports",
         "hint": None},
    ]


def test_payload_ok_agrees_with_the_exit_code():
    """A payload saying `ok: true` beside a non-zero exit is the one failure a
    CI consumer cannot detect for itself."""
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    assert rep.payload()["ok"] is True and rep.exit_code() == 0

    rep.issue("b", "broken")
    p = rep.payload()
    assert p["ok"] is False and p["issues"] == 1 and rep.exit_code() == 1


def test_payload_carries_the_verdict_text_and_survives_json_dumps():
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    rep.verdict(True, "healthy")
    payload = rep.payload()
    assert payload["verdict"] == "healthy"
    # The round trip is the actual product: a payload that cannot serialize is
    # worse than no --json at all.
    assert json.loads(json.dumps(payload)) == payload


def test_verdict_is_null_rather_than_invented_when_none_was_reached():
    """A command that returned early never rendered a verdict. Emitting an
    empty string would read as a verdict of "", and `false` would read as an
    unhealthy machine."""
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    assert rep.payload()["verdict"] is None


def test_hint_defaults_to_none_not_empty_string():
    """`None` and `""` are different answers: absent versus "there is a hint and
    it is blank". Consumers branch on the first and render the second."""
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    assert rep.payload()["checks"][0]["hint"] is None


def test_payload_is_a_snapshot_not_a_live_view():
    """Callers hold the payload and keep reporting; a shared list would grow
    under them and a later mutation would rewrite an emitted document."""
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    payload = rep.payload()
    rep.issue("b", "broken")
    assert len(payload["checks"]) == 1
    assert payload["issues"] == 0


def test_emit_prints_the_payload_only_in_json_mode(capsys):
    """The commands call one method at the end rather than each re-deciding
    how to serialize — a second `json.dumps` spelling is a second format."""
    rep = report.Report(as_json=True)
    rep.ok("a", "fine")
    rep.emit()
    assert json.loads(capsys.readouterr().out)["checks"][0]["name"] == "a"

    prose = report.Report()
    prose.ok("a", "fine")
    capsys.readouterr()
    prose.emit()
    assert capsys.readouterr().out == ""


def test_a_warn_line_wears_the_glyph_without_moving_the_exit_code(capsys):
    """doctor's closing lines restate faults already counted.

    They print with `!` when anything upstream failed, but each is a rendering
    of checks already recorded — so counting them would report the same fault
    twice and leave the issue total permanently above the number of things
    actually wrong.
    """
    rep = report.Report()
    rep.issue("real", "an actual fault")
    rep.warn("summary", "lock file integrity or log rotation needs attention")

    assert rep.issues == 1 and rep.exit_code() == 1
    assert capsys.readouterr().out == (
        "  ! an actual fault\n"
        "  ! lock file integrity or log rotation needs attention\n"
    )
    statuses = [c["status"] for c in rep.payload()["checks"]]
    assert statuses == ["issue", "warn"]


def test_a_warn_line_alone_leaves_the_run_healthy():
    """Nothing counted upstream means nothing to restate — a lone warn must not
    invent an issue."""
    rep = report.Report(as_json=True)
    rep.warn("summary", "needs attention")
    assert rep.issues == 0 and rep.exit_code() == 0
    assert rep.payload()["ok"] is True


def test_warn_records_the_name_message_and_hint_it_was_given():
    """A warn row is addressable like any other, and the payload is the only
    place its text survives.

    Prose renders `message` on the spot, so a warn row that recorded `None` for
    its name, its message or its hint would still *print* correctly and only be
    wrong for the consumer that cannot see the terminal — which is the audience
    the flag exists for.
    """
    rep = report.Report(as_json=True)
    rep.warn("integrity", "lock file integrity needs attention",
             hint="boost heal")
    assert rep.payload()["checks"] == [
        {"name": "integrity", "status": "warn",
         "message": "lock file integrity needs attention", "hint": "boost heal"},
    ]


def test_a_healthy_verdict_is_painted_differently_from_an_unhealthy_one(
        capsys, monkeypatch):
    """`ok` decides the role the whole line resolves through, and losing it
    would report a healthy machine in the warn color — a dashboard that reads
    as broken while every check passed."""
    monkeypatch.setenv("BOOST_COLOR", "always")

    report.Report().verdict(True, "healthy")
    healthy = capsys.readouterr().out
    report.Report().verdict(False, "needs attention")
    unhealthy = capsys.readouterr().out

    assert out.role("●", "success") in healthy
    assert out.role("●", "warn") in unhealthy
    assert healthy.replace("healthy", "X") != unhealthy.replace(
        "needs attention", "X")


@pytest.mark.parametrize("status", ["ok", "issue", "warn", "note"])
def test_every_status_carries_its_hint_into_the_payload(status):
    """A hint is the one field prose never shows on its own line.

    `doctor` interpolates `dense.fix_hint()` into the message it prints, so a
    dropped `hint` still reads correctly in the terminal and is missing only
    for the consumer that cannot see it — the audience `--json` exists for.
    """
    rep = report.Report(as_json=True)
    getattr(rep, status)("search-engine", "semantic search not configured",
                         hint="boost reindex --dense")
    assert rep.payload()["checks"][0]["hint"] == "boost reindex --dense"


def test_emit_pretty_prints_with_the_indent_every_other_json_flag_uses(capsys):
    """Two-space indent, one field per line — the spelling `lint --json` and
    `context status --json` already print, so a reader moving between them sees
    one format rather than three."""
    rep = report.Report(as_json=True)
    rep.ok("git", "git on PATH")
    rep.emit()
    assert capsys.readouterr().out == json.dumps(rep.payload(), indent=2) + "\n"
