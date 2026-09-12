# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: count flags must fail at parse time, not silently invert.

``util.positive_int`` exists precisely because "every count flag in boost ends
up as a slice bound or a ``git log -n`` argument -- where a negative silently
*inverts* the request instead of failing it". Eight flags used it; four did not,
and each of those four was reachable with a value that did the wrong thing
quietly:

* ``tap --catalog --limit 0``   selected **all 449** registries rather than none
  (``if args.limit:`` is a truthiness test), so the real branch would clone the
  whole catalogue.
* ``changelog -n 0``            claimed "no history found" for a path that has
  history, because ``git log -n 0`` prints nothing.
* ``absorb --limit -1``         dropped the last pattern off the end via
  ``hits[:-1]``, and ``--limit 0`` reported "no recurring patterns" over a
  history where five patterns each appeared four times.
* ``chat -k 0``                 same slice, same silence.

``serve --port`` is the same class with a different upper bound: an out-of-range
port reached ``socket.bind`` and surfaced as an unhandled ``OverflowError``,
exit 70, plus a crash report inviting the user to file a GitHub issue -- for a
typo.
"""
from __future__ import annotations

import pytest

# (argv, the value that used to be accepted). rc=2 is argparse's usage exit.
NONPOSITIVE = [
    pytest.param(("changelog", "brainstorming", "-n"), "0", id="changelog-n-0"),
    pytest.param(("changelog", "brainstorming", "-n"), "-5", id="changelog-n-neg"),
    pytest.param(("absorb", "--limit"), "0", id="absorb-limit-0"),
    pytest.param(("absorb", "--limit"), "-1", id="absorb-limit-neg"),
    pytest.param(("tap", "--catalog", "--dry-run", "--limit"), "0", id="tap-limit-0"),
    pytest.param(("tap", "--catalog", "--dry-run", "--limit"), "-1", id="tap-limit-neg"),
    pytest.param(("chat", "--limit"), "0", id="chat-limit-0"),
    pytest.param(("chat", "--limit"), "-1", id="chat-limit-neg"),
]


@pytest.mark.parametrize("argv,value", NONPOSITIVE)
def test_count_flag_rejects_nonpositive(boost, tapped, argv, value):
    r = boost(*argv, value, expect=2)
    assert "must be >= 1" in (r.out + r.err)


OUT_OF_RANGE_PORTS = ["-1", "65536", "70000"]


@pytest.mark.parametrize("port", OUT_OF_RANGE_PORTS)
def test_serve_rejects_an_out_of_range_port(boost, port):
    """A typo must not produce a crash report telling the user to file a bug."""
    r = boost("serve", "--port", port, expect=2)
    text = r.out + r.err
    assert "boost hit an unexpected error" not in text
    assert "crash report" not in text
    assert "0-65535" in text


def test_serve_still_accepts_a_valid_port():
    """The guard must not reject the ports a user actually wants.

    Asserted against the ``type=`` callable rather than the command: ``serve``
    binds a socket as its next act, which the test tier cannot do.
    """
    from boost_cli.core import util

    for ok in ("1", "8787", "65535"):
        assert util.port_number(ok) == int(ok)


def test_port_zero_stays_the_any_free_port_idiom():
    """`bind(host, 0)` is how you ask the OS for a free port, and boost's own
    `TestServe` starts the server that way — so 0 is valid input, not a typo.
    Bolting a maximum onto `positive_int` would have broken it."""
    from boost_cli.core import util

    assert util.port_number("0") == 0
