# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Kind-conformance sweep: every command treats all three item kinds alike.

The lock file has three sections — skills, rules, workflows — and for a long
time most commands read only the skills one, so ``boost verify house-style``
said "not installed" about a rule that ``boost list`` displayed. This module is
the recurrence stopper: it installs one of each kind into a single sandbox and
sweeps the CLI surface, so the next command added (or regressed) cannot quietly
be skill-only again.

Two sweeps, one meta-guard:

* ``NEVER_DENY`` — commands that take an installed item's NAME. Run against
  the rule and the workflow, each must either handle the item (rc 0) or
  decline truthfully by naming the kind ("X is a rule — ..."). It must never
  crash, never print "not installed", and never succeed silently.
* ``ALL_CLEAR`` — commands that report over the whole environment. Each must
  account for all three installed items (or name what it excludes) so a
  skill-only tally cannot read as a clean bill of health.
* The meta-guard cross-checks both tables against ``boost_cli.cli.COMMANDS``,
  so renaming or removing a swept command fails here until the table is
  updated — and the tables stay internally consistent.

ADDING THE NEXT COMMAND: if it accepts an installed NAME, add a row to
``NEVER_DENY`` — steps are argv tuples with a ``{name}`` placeholder, and any
state a step mutates must be restored by a later step in the same row (see the
pin/unpin and quarantine/--release rows). If it summarizes the environment,
add a row to ``ALL_CLEAR`` with output fragments proving all three kinds are
counted or the exclusion is stated. Nothing else to update: the meta-guard
derives the swept-command set from the tables.

Deliberately NOT swept, and why:

* ``install``/``uninstall``/``reinstall``/``update``/``sync`` — they would
  mutate the module-scoped trio; their kind coverage lives in
  ``test_cli_pkg.py``.
* ``export``/``bundle``/``snapshot``/``profile``/``adapt``/``run`` — package
  or transform skills and state their rule/workflow omissions explicitly;
  covered by ``test_cli_pkg.py`` and ``test_cli_team.py``.
* ``search``/``discover``/``recommend``/``browse``/``trending``/``index`` —
  catalog-facing; they never claim anything about installed items.
* ``distill``/``simulate``/``evolve``/``focus``/``impact``/``context`` — their
  kind-naming declines are asserted in ``test_cli_intelligence.py``.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

SKILL = "brainstorming"
RULE = "house-style"
WORKFLOW = "ship-it"

# (command names the row exercises, argv steps run in order; a step's first
# token must be one of the row's command names — the meta-guard enforces it)
NEVER_DENY = (
    (("info",), (("info", "{name}"),)),
    (("cat",), (("cat", "{name}"),)),
    (("preview",), (("preview", "{name}"),)),
    (("explain",), (("explain", "{name}"),)),
    (("verify",), (("verify", "{name}"),)),
    (("drift",), (("drift", "{name}"),)),
    (("attest",), (("attest", "{name}", "--verify"),)),
    (("pin", "unpin"), (("pin", "{name}"), ("unpin", "{name}"))),
    (("quarantine",), (("quarantine", "{name}"),
                       ("quarantine", "--release", "{name}"))),
    (("stats",), (("stats", "{name}"),)),
    (("log",), (("log", "{name}"),)),
    (("home",), (("home", "{name}", "--print"),)),
    (("who",), (("who", "{name}"),)),
    (("deps",), (("deps", "{name}"),)),
    (("changelog",), (("changelog", "{name}"),)),
    (("test",), (("test", "{name}"),)),
    (("edit",), (("edit", "{name}"),)),
    (("tag",), (("tag", "{name}"),)),
)

# (command name, argv, stdout fragments that prove all three kinds count)
ALL_CLEAR = (
    ("list", ("list",), (SKILL, RULE, WORKFLOW)),
    ("count", ("count",),
     ("installed 3 (1 skills · 1 rules · 1 workflows)",)),
    ("policy", ("policy", "check"),
     ("policy check passed (1 skill, 1 rule, 1 workflow)",)),
    ("doctor", ("doctor",),
     ("1 skill present in store with agent links",
      "1 rule and 1 workflow fully materialized")),
    ("audit", ("audit",),
     ("safety audit — 3 items", "no safety findings across 3 items")),
    ("fingerprint", ("fingerprint", "--verbose"),
     (SKILL, "rule/" + RULE, "workflow/" + WORKFLOW)),
)


@pytest.fixture(scope="module")
def trio(tmp_path_factory, fixture_tap_src):
    """One sandbox HOME with one of each kind installed from a real tap."""
    from boost_cli.cli import main
    from boost_cli.core import logs

    mp = pytest.MonkeyPatch()
    base = tmp_path_factory.mktemp("kind-conformance")
    home = base / "home"
    home.mkdir()
    mp.setenv("HOME", str(home))
    for var in ("BOOST_HOME", "BOOST_AGENTS_STORE", "BOOST_DEBUG",
                "BOOST_LOG_LEVEL", "BOOST_NO_LOG", "VOYAGE_API_KEY",
                "OPENAI_API_KEY", "BOOST_NO_EMBED"):
        mp.delenv(var, raising=False)
    mp.setenv("BOOST_NO_AI", "1")
    mp.setenv("NO_COLOR", "1")
    mp.setenv("BOOST_ASSUME_YES", "1")
    logs.reset()   # rebind the diagnostic log under the sandbox HOME

    tap = base / "trio-tap"
    shutil.copytree(fixture_tap_src, tap)
    (tap / "rules").mkdir()
    (tap / "rules" / "house.mdc").write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nAlways write tests first.\n"
        % RULE, encoding="utf-8")
    (tap / "commands").mkdir()
    (tap / "commands" / ("%s.md" % WORKFLOW)).write_text(
        "---\nname: %s\nversion: 1.0.0\n---\n\nShip-it checklist body.\n"
        % WORKFLOW, encoding="utf-8")
    subprocess.run(["git", "-C", str(tap), "add", "-A"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tap), "commit", "-qm",
                    "add rule and workflow"],
                   check=True, capture_output=True)

    for argv in (("tap", str(tap)), ("install", SKILL),
                 ("install", RULE), ("install", WORKFLOW)):
        rc = main(list(argv))
        assert rc == 0, "trio setup failed: boost %s -> rc=%d" \
            % (" ".join(argv), rc)
    yield {"skill": SKILL, "rule": RULE, "workflow": WORKFLOW}
    mp.undo()


@pytest.fixture()
def run(trio, capsys):
    """In-process CLI runner against the trio sandbox: (rc, out, err)."""
    from boost_cli.cli import main

    def _run(*argv):
        try:
            rc = main([str(a) for a in argv])
        except SystemExit as e:   # argparse usage error escaping a parser
            rc = e.code if isinstance(e.code, int) else 0
        cap = capsys.readouterr()
        return int(rc or 0), cap.out, cap.err

    capsys.readouterr()   # drop anything buffered before the first command
    return _run


# ── sweep 1: commands naming an installed item never deny it exists ──────

@pytest.mark.parametrize("kind", ("rule", "workflow"))
@pytest.mark.parametrize("commands,steps", NEVER_DENY,
                         ids=["+".join(cmds) for cmds, _steps in NEVER_DENY])
def test_named_commands_never_deny_the_item(run, trio, kind, commands, steps):
    name = trio[kind]
    for step in steps:
        argv = tuple(a.format(name=name) for a in step)
        label = "boost " + " ".join(argv)
        rc, out_text, err_text = run(*argv)
        blob = out_text + err_text
        assert blob.strip(), "%s said nothing — a silent rc=%d is not an " \
            "answer about an installed %s" % (label, rc, kind)
        assert "not installed" not in blob.lower(), \
            "%s denies an installed %s exists:\n%s" % (label, kind, blob)
        assert rc in (0, 1), "%s crashed (rc=%d):\n%s" % (label, rc, blob)
        if rc == 1:
            # rc 1 is only acceptable as a truthful kind-naming decline.
            assert "%s is a %s" % (name, kind) in blob, \
                "%s failed (rc=1) without naming the kind:\n%s" \
                % (label, blob)


# ── sweep 2: environment-wide commands may not give a skill-only all-clear ─

@pytest.mark.parametrize("command,argv,needles", ALL_CLEAR,
                         ids=[cmd for cmd, _argv, _needles in ALL_CLEAR])
def test_environment_commands_count_all_three_kinds(run, trio, command,
                                                    argv, needles):
    label = "boost " + " ".join(argv)
    rc, out_text, err_text = run(*argv)
    assert rc == 0, "%s -> rc=%d with the trio healthy:\n%s%s" \
        % (label, rc, out_text, err_text)
    for needle in needles:
        assert needle in out_text, \
            "%s output omits %r — a skill-only tally reads as a false " \
            "all-clear:\n%s" % (label, needle, out_text)


# ── sweep 3: the meta-guard ──────────────────────────────────────────────

def test_swept_commands_still_exist_in_the_cli():
    """A renamed/removed command must update this sweep, not orphan it."""
    from boost_cli.cli import COMMANDS
    real = {name for name, _group, _module, _summary in COMMANDS}
    swept = {c for cmds, _steps in NEVER_DENY for c in cmds}
    swept |= {cmd for cmd, _argv, _needles in ALL_CLEAR}
    missing = sorted(swept - real)
    assert not missing, "swept commands no longer in COMMANDS " \
        "(renamed or removed?): %s — update the tables in this module" \
        % ", ".join(missing)


def test_sweep_tables_are_internally_consistent():
    """Every declared command is exercised and every step is declared."""
    for cmds, steps in NEVER_DENY:
        exercised = {step[0] for step in steps}
        assert exercised == set(cmds), \
            "NEVER_DENY row %r: declared commands %r but steps exercise %r" \
            % (cmds, sorted(cmds), sorted(exercised))
    for cmd, argv, needles in ALL_CLEAR:
        assert argv[0] == cmd, \
            "ALL_CLEAR row %r runs %r — the declared name must match argv" \
            % (cmd, argv[0])
        assert needles, "ALL_CLEAR row %r asserts nothing" % cmd
