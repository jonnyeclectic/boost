# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`--json` on a write action is refused, never accepted and ignored.

`quarantine`, `snapshot`, `hooks` and `context` each take `--json` for their
listing action only, but argparse accepted the flag on every action — so
`boost quarantine x --json | jq` performed the write, exited 0, and handed jq
a line of prose. `boost update --json` (without --shards) already set the
precedent these follow: a usage error, rc 2, the message on stderr, nothing on
stdout, and — because the refusal precedes any work — nothing written.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import lockfile, paths

REFUSED = [
    (("quarantine", "brainstorming", "--json"),
     "--json is only supported with --list"),
    (("quarantine", "--release", "brainstorming", "--json"),
     "--json is only supported with --list"),
    (("snapshot", "save", "--json"),
     "--json is only supported with `snapshot list`"),
    (("snapshot", "restore", "snap-x", "--json"),
     "--json is only supported with `snapshot list`"),
    (("hooks", "add", "SessionStart", "-c", "true", "-n", "t1", "--json"),
     "--json is only supported with `hooks list`"),
    (("hooks", "remove", "--name", "nosuch", "--json"),
     "--json is only supported with `hooks list`"),
    (("context", "--json", "map", "feature/*", "brainstorming"),
     "--json is only supported with `context status`"),
    (("context", "--json", "enable"),
     "--json is only supported with `context status`"),
    (("context", "--json", "unmap", "feature/*"),
     "--json is only supported with `context status`"),
    (("context", "--json", "apply"),
     "--json is only supported with `context status`"),
]


@pytest.mark.parametrize(("argv", "message"), REFUSED,
                         ids=["-".join(a).replace("/", "") for a, _ in REFUSED])
def test_json_on_a_write_action_is_a_usage_error(boost, tapped, argv, message):
    boost("install", "brainstorming")
    r = boost(*argv, expect=2)
    assert r.out == ""
    assert message in r.err
    # Refused before any work: nothing was quarantined or snapshotted.
    assert not lockfile.find_any("brainstorming")[1].get("quarantined")
    assert not list(paths.snapshots_dir().glob("snap-*"))


def test_hooks_add_with_json_writes_no_settings(boost, sandbox):
    boost("hooks", "add", "SessionStart", "-c", "true", "-n", "t1", "--json",
          expect=2)
    assert json.loads(boost("hooks", "list", "--json").out) == {"hooks": []}


@pytest.mark.parametrize("argv", [
    ("quarantine", "--list", "--json"),
    ("snapshot", "list", "--json"),
    ("hooks", "list", "--json"),
    ("context", "--json"),
    ("context", "status", "--json"),
])
def test_json_on_the_listing_action_still_parses(boost, sandbox, argv):
    assert isinstance(json.loads(boost(*argv).out), dict | list)
