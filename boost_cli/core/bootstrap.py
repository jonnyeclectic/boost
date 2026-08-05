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
    #: True when the machine already had taps and nothing was touched.
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
            return ("could not reach any default registry — run "
                    "`boost tap --defaults` once you have a network")
        line = ("tapped %d registries (%d items searchable)"
                % (len(self.tapped), self.item_count))
        if self.failed:
            line += " — %d could not be fetched" % len(self.failed)
        return line


def seed_catalog(*, force: bool = False) -> SeedResult:
    """Tap the recommended registries when the machine has none.

    Idempotent by default: a machine that already has taps is left completely
    alone, because re-tapping someone's configured setup because they re-ran
    `boost mcp` would be boost editing state it was not asked to touch.
    ``force`` is the repair path for a machine that lost its taps.

    Never raises. This runs on the registration path, where the user's actual
    request was "register the MCP server" — a dead network or one bad remote
    must cost them a reported line, not the server they asked for.
    """
    if not force and os.environ.get(NO_SEED_ENV):
        return SeedResult(skipped=True)
    if not force and registry.list_taps():
        return SeedResult(skipped=True)
    res = SeedResult()
    for default in config.DEFAULT_TAPS:
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
