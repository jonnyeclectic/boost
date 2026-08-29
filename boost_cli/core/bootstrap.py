# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Seed an empty machine's catalog, so one command is the whole setup.

`boost mcp` is the only command a new user is told to run after installing.
It registered the server and stopped there — against a catalog with nothing in
it — so the first question any agent asked came back as a miss, which is the
fastest possible way to teach an agent that boost is not worth asking again.

Seeding belongs here rather than in the command layer for the usual reason:
it is behavior with rules worth pinning (idempotent, never fatal, reports what
it did), and `boost_cli/core` is what the mutation gate targets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..errors import BoostError
from . import catalog, config, journal, registry

#: Escape hatch, same shape as ``BOOST_NO_MCP_OFFER``: suppress the implicit
#: seed for anyone who wants `boost mcp` to stay a local, offline operation —
#: CI images, air-gapped machines, and the test suite, which must never clone
#: seven repositories to check that registration prints the right line. An
#: explicit ``--seed`` still wins over it: a flag the user typed outranks an
#: environment default they may not know is set.
NO_SEED_ENV = "BOOST_NO_SEED"


@dataclass
class SeedResult:
    """What a seed attempt did, in terms a caller can print."""

    #: (tap name, item count) for each registry that landed.
    tapped: list[tuple[str, int]] = field(default_factory=list)
    #: One human-readable line per registry that could not be fetched.
    failed: list[str] = field(default_factory=list)
    #: Defaults that were already configured, so nothing was done for them.
    already: list[str] = field(default_factory=list)
    #: True when nothing was attempted at all (opted out, or already complete).
    skipped: bool = False

    @property
    def item_count(self) -> int:
        """Total catalog items across every registry this call added."""
        return sum(count for _name, count in self.tapped)

    def summary(self) -> str:
        """One line for the user: what is now searchable, or why nothing is."""
        if self.skipped:
            return "catalog already tapped — leaving it alone"
        if not self.tapped:
            # Only claim the network is the problem when the network was
            # actually the problem. A run where every default was already
            # configured reaches here too, and telling that user to retry
            # "once you have a network" is advice about a machine they do
            # not have — see the `--seed` repair path, which hits it head-on.
            if self.failed:
                return ("could not reach any default registry — run "
                        "`boost tap --defaults` once you have a network")
            return "catalog already tapped — leaving it alone"
        line = ("tapped %d registries (%d items searchable)"
                % (len(self.tapped), self.item_count))
        if self.already:
            line += " — %d already tapped" % len(self.already)
        if self.failed:
            line += " — %d could not be fetched" % len(self.failed)
        return line


def will_seed(*, force: bool = False) -> bool:
    """True when :func:`seed_catalog` would actually clone something.

    Exists so a caller can announce the wait BEFORE it starts. The seed is
    14-45s of network with nothing to print until it returns, and on the one
    command a first-time user was told to run, silence that long reads as a
    hang. Deliberately mirrors seed_catalog's own gates rather than guessing.
    """
    if not force and os.environ.get(NO_SEED_ENV):
        return False
    existing = {t.name for t in registry.list_taps()}
    if not force and existing:
        return False
    return any(str(d["name"]) not in existing for d in config.DEFAULT_TAPS)


def seed_catalog(*, force: bool = False) -> SeedResult:
    """Tap whichever recommended registries this machine is missing.

    The decision is per registry, not per machine, and that distinction is
    load-bearing twice over. A seed interrupted after two clones used to leave
    a machine that read as "configured" forever, because the check was "does
    ANY tap exist" — so the remaining five never arrived and nothing ever said
    so. And `--seed`, documented as the repair path, called ``registry.add``
    on registries that were already there; ``add`` rejects those before it
    touches the network, so the repair reported seven failures and blamed the
    connection on a machine whose connection was fine.

    Skips silently when the user opted out (``BOOST_NO_SEED``) or when every
    default is already present. Never raises: this runs on the registration
    path, where the user's actual request was "register the MCP server" — a
    dead network or one bad remote must cost them a reported line, not the
    server they asked for.
    """
    if not force and os.environ.get(NO_SEED_ENV):
        return SeedResult(skipped=True)
    existing = {t.name for t in registry.list_taps()}
    # `force` re-checks the DEFAULTS rather than re-adding them: a machine
    # missing two of seven is topped up, and one missing none is left alone.
    missing = [d for d in config.DEFAULT_TAPS if str(d["name"]) not in existing]
    if not missing:
        return SeedResult(skipped=True)
    # Without --seed the implicit path stays conservative: a machine with taps
    # of its own is somebody's configured setup, and quietly adding seven
    # registries to it because they re-ran `boost mcp` is boost editing state
    # it was not asked to touch.
    if not force and existing:
        return SeedResult(skipped=True)
    res = SeedResult(already=[str(d["name"]) for d in config.DEFAULT_TAPS
                              if str(d["name"]) in existing])
    for default in missing:
        name = str(default["name"])
        try:
            tap = registry.add(str(default["url"]), curated=True)
            entries = catalog.rebuild_tap(tap)
        except BoostError as e:
            res.failed.append("%s: %s" % (name, e.message))
            continue
        except OSError as e:
            # A clone can fail below BoostError (disk full, permissions).
            # Same contract: report it, keep going, never take the caller down.
            res.failed.append("%s: %s" % (name, e))
            continue
        journal.log("tap", tap.name)
        res.tapped.append((tap.name, len(entries)))
    return res
