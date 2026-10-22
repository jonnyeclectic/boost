# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: a missing required argument is a usage error, exit 2.

These checks were hand-rolled ``BoostError`` raises, which exit 1 — the code
for "the operation failed" — while argparse and the sibling ``p.error`` checks
(`tap`, `replay show`, `cohort create`) exit 2. A script could not tell
"I called it wrong" from "the write was refused".
"""
from __future__ import annotations

import pytest

CASES = [
    (("quarantine",),
     "specify a skill to quarantine, --release NAME, or --list",
     "e.g. `boost quarantine cowboy-coding`"),
    (("config", "set"), "config set requires a KEY",
     "e.g. `boost config set ai.enabled`"),
    (("config", "set", "foo"), "config set requires a VALUE",
     "e.g. `boost config set ai.enabled false`"),
    (("config", "get"), "config get requires a KEY",
     "e.g. `boost config get ai.enabled`"),
    (("config", "unset"), "config unset requires a KEY",
     "e.g. `boost config unset ai.enabled`"),
    (("policy", "set"), "policy set requires a KEY", "keys: "),
    (("policy", "unset"), "policy unset requires a KEY", "keys: "),
    (("policy", "set", "min_quality_score"), "policy set requires a VALUE",
     "e.g. `boost policy set min_quality_score 60`"),
    (("tag",), "skill name required",
     "`boost tag NAME +tag -tag`, or `boost tag --list`"),
    (("hooks", "add"), "hooks add needs an EVENT",
     "e.g. boost hooks add SessionStart -c '<cmd>' -n <name>"),
    (("hooks", "add", "SessionStart", "-n", "x"), "hooks add needs --command",
     "the shell command Claude should run for this hook"),
    (("hooks", "add", "SessionStart", "-c", "true"), "hooks add needs --name",
     "a stable name so the hook can be removed later"),
    (("hooks", "remove", "nosuch"), "hooks remove needs --name",
     "the name you gave the hook when adding it"),
    (("snapshot", "restore"), "restore needs a snapshot id",
     "see `boost snapshot list`"),
    (("trust", "add"), "trust add requires NAME and KEY",
     "`boost trust add acme ./acme.pub`"),
    (("trust", "add", "acme"), "trust add requires NAME and KEY",
     "`boost trust add acme ./acme.pub`"),
    (("trust", "remove"), "trust remove requires a NAME",
     "see the names with `boost trust list`"),
]


@pytest.mark.parametrize(("argv", "message", "hint"), CASES,
                         ids=[" ".join(c[0]) for c in CASES])
def test_missing_argument_exits_2_with_hint_and_usage(boost, sandbox, argv,
                                                      message, hint):
    r = boost(*argv, expect=2)
    assert r.out == ""
    lines = r.err.splitlines()
    assert lines[0] == "Error: " + message
    assert lines[1].startswith("  hint: " + hint)
    # The usage line names the subcommand that was called wrong.
    assert "usage: boost %s " % argv[0] in r.err
