# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""The one tap boost ships itself, and the rule inside it.

boost's whole product is asking a user to accept standing text written by
strangers, under ``boost install`` and reversible with ``boost uninstall``. Its
OWN standing text has to be the same kind of thing, subject to the same
commands — a privileged block that ``boost list`` cannot see and
``boost uninstall`` cannot remove is exactly the asymmetry a user is entitled
to resent. So ``boost-first`` is not a special case bolted onto the register
path: it is an ordinary rule, in an ordinary tap, that happens to arrive with
the wheel instead of over the network.

**The tap directory is under ``~/.boost/repos/`` and never inside the wheel.**
That is not an implementation detail, it is the whole safety argument. A
``Tap`` whose ``path`` pointed at package data would sit one ``boost untap``
away from :func:`registry.remove`, which ends in ``util.rmtree(tap.path)`` —
deleting part of the user's installed package. Here the worst case is that a
recreatable directory goes away and :func:`ensure_tap` rebuilds it.

The shipped files are therefore *copied out* of the wheel on first use, and the
copy is what everything else — catalog scan, install, lock file, uninstall —
sees. Nothing in ``core/`` needs to know this tap is different.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import config, paths, registry

#: The tap name. Contains a ``/`` like any other, so ``Tap.safe_name`` maps it
#: to ``boost__builtin`` under ``~/.boost/repos/``.
BUILTIN_TAP = "boost/builtin"

#: A sentinel URL rather than a real one. ``boost update`` must not try to
#: fetch this tap: its source of truth is the installed wheel, so it refreshes
#: when boost itself does. The scheme is deliberately not ``https`` so any code
#: that hands it to git fails loudly instead of reaching the network.
BUILTIN_URL = "builtin:boost"

#: The rule boost authors. One entry today; the list is what makes adding a
#: second a data change rather than a code change.
BUILTIN_RULES = ("boost-first",)

#: MCP host id -> boost agent id. The two vocabularies genuinely differ
#: (``mcphost.CLAUDE`` is ``"claude"``; the agent is ``"claude-code"``), and
#: the offer is scoped through this so standing text naming ``boost_search``
#: only reaches an agent boost actually registered a server with. Cursor and
#: Windsurf are absent on purpose: boost registers no MCP server for them, so
#: the rule would advertise tools they do not have.
AGENT_FOR_HOST = {"claude": "claude-code", "gemini": "gemini"}


def source_dir() -> Path:
    """The shipped rules inside the installed package. **Read-only.**

    Never returned as a ``Tap.path`` and never written to — a wheel is not
    guaranteed writable, and on a system install it is not guaranteed to be
    the user's to modify.
    """
    return Path(__file__).resolve().parent.parent / "data" / "rules"


def is_builtin(tap_name: str) -> bool:
    """Whether ``tap_name`` is boost's own tap rather than a user's."""
    return tap_name == BUILTIN_TAP


def configured_tap_count() -> int:
    """Taps the USER configured — the builtin does not count.

    ``mcp.no_results`` and ``boost_doctor`` both ask "has this user configured
    anything yet" by counting taps, and print the one-command setup path when
    the answer is zero. boost's own tap must not answer that question for
    them: a machine holding nothing but ``boost-first`` has an effectively
    empty catalog, and suppressing the setup message there would strand a new
    user with a search that can never match.
    """
    return sum(1 for tap in registry.list_taps() if not is_builtin(tap.name))


def ensure_tap() -> registry.Tap:
    """Materialize the shipped rules on disk and register the tap. Idempotent.

    Copies each shipped ``.mdc`` into ``~/.boost/repos/boost__builtin/`` and
    appends the config row if it is not already there. Safe to call on every
    install: an existing file is overwritten from the wheel, which is what
    makes the rule track boost's own version rather than drifting once written.
    """
    tap = registry.Tap(name=BUILTIN_TAP, url=BUILTIN_URL, curated=True)
    paths.ensure_dirs()
    tap.path.mkdir(parents=True, exist_ok=True)
    src = source_dir()
    for rule in BUILTIN_RULES:
        origin = src / (rule + ".mdc")
        if origin.is_file():
            shutil.copyfile(origin, tap.path / (rule + ".mdc"))
    cfg = config.load()
    rows = cfg.setdefault("taps", [])
    if not any(str(row.get("name")) == BUILTIN_TAP for row in rows):
        rows.append({"name": BUILTIN_TAP, "url": BUILTIN_URL, "curated": True})
        config.save(cfg)
    return tap


def rule_is_available() -> bool:
    """Whether the wheel actually carries the rule.

    Package data is a packaging decision that can regress silently — a missing
    ``package-data`` entry makes this a dev-checkout-only feature that is
    simply absent for every pip and pipx user. The offer checks this rather
    than assuming, so a packaging mistake degrades to "no offer" instead of a
    traceback on the one command new users are told to run.
    """
    return (source_dir() / (BUILTIN_RULES[0] + ".mdc")).is_file()
