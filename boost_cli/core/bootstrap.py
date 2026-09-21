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


#: Past this many registries, a line about them reports the count, not the
#: list. `--catalog` is 463 registries, so naming every one is a wall of text
#: rather than a report. Both of quickstart's lists obey it: the dry run's
#: "would tap" preview and the closing note on the registries that failed.
MAX_NAMED_REGISTRIES = 12


@dataclass
class SetupOutcome:
    """What one `boost quickstart` run left behind, and whether it worked.

    WHY THIS IS A JUDGEMENT AND NOT A COUNTER. `quickstart` used to end in an
    unconditional ``out.ok("ready …")`` and ``return 0``, so a machine that
    could reach no registry at all printed "✓ indexed 0 items for keyword
    search" and "✓ ready" and exited 0 — while `boost search`, the very next
    line of README's install snippet, exited 1 with "no taps configured".
    Every Dockerfile, CI job and setup script recorded a successful install of
    a boost that cannot answer anything.

    THE CONDITION IS NOT "SOMETHING FAILED". `quickstart` is the first command
    a new user runs; exiting non-zero because one registry of seven 404'd
    would be worse than the bug, and it is not even a reliable signal — a
    rerun on a configured machine carries *zero* ``ok`` results, because
    ``registry.add_many`` answers ``skipped`` for a registry already tapped.
    So "no clone succeeded" would fail every successful rerun.

    Two things make a run a failure, and they are different failures:

    * **Every registry it attempted failed.** Nothing was cloned and nothing
      was already there, so the command did not do its job — even on a machine
      whose index is full from an earlier run, where the items reported belong
      to that run and not to this one.
    * **Nothing is searchable.** The keyword index holds zero items, so
      `boost search` has nothing to answer with whatever the clones did. This
      is also what keeps the closing lines from contradicting each other: "✓
      ready" and "indexed 0 items" can no longer appear together, because the
      second one is the definition of the first being false.

    Anything else is ready: partial failure is named, loudly, and exits 0.
    """

    #: Registries cloned and indexed by this run.
    tapped: list[str] = field(default_factory=list)
    #: Registries that were already configured, so this run did nothing.
    already: list[str] = field(default_factory=list)
    #: Registries that could not be cloned. Nothing of them reached the
    #: machine, so rerunning quickstart retries them.
    failed: list[str] = field(default_factory=list)
    #: Registries whose clone succeeded but which could not be indexed
    #: (``rebuild_tap`` raised). Kept apart from ``failed`` because the
    #: remedy is not the same one: ``add_many`` has already written them to
    #: the config, so the network is not the problem and a rerun skips them
    #: as "already tapped". Folding them into ``failed`` told a user whose
    #: every clone had succeeded to "check the network".
    unindexed: list[str] = field(default_factory=list)
    #: Items in the keyword index after this run.
    entries: int = 0
    #: Why the published vectors cannot serve this machine, and the one thing
    #: that would change that (``shards.remedy``); both empty when they can,
    #: or when none were asked for. Set by :meth:`judge_vectors`, which both
    #: the dry run and the live run call on the same manifest, so the preview
    #: cannot promise shards the real run then refuses — it did, "import 5
    #: shard(s)" on a machine whose every shard came back ``incompatible``.
    #: Never part of :attr:`ok`: keyword search is the documented default, and
    #: vectors that do not apply are a missed upgrade, not a broken setup.
    vectors_refused: str = ""
    vectors_remedy: str = ""

    @property
    def selected(self) -> int:
        """How many registries this run set out to handle."""
        return (len(self.tapped) + len(self.already) + len(self.failed)
                + len(self.unindexed))

    @property
    def searchable(self) -> bool:
        """True when the keyword index can answer a query at all."""
        return self.entries > 0

    @property
    def every_attempt_failed(self) -> bool:
        """True when something failed and nothing arrived or was already here.

        ``already`` counts: six registries in place and the seventh 404'ing is
        a top-up that mostly worked, not a run that achieved nothing. And a
        run that attempted nothing has not failed at anything. A registry
        that cloned but could not be indexed is not searchable either, so it
        fails here the same way — only the advice about it differs.
        """
        return (bool(self.failed or self.unindexed)
                and not self.tapped and not self.already)

    @property
    def ok(self) -> bool:
        """Whether this run may claim the machine is ready."""
        return self.searchable and not self.every_attempt_failed

    def judge_vectors(self, manifest: dict) -> bool:
        """Record whether `manifest`'s shards can serve this machine at all.

        Asked once, from the manifest alone, before any tap is looked up or
        any byte is downloaded — the question does not depend on the tap, so
        answering it per tap is what used to produce seven identical lines,
        or (in quickstart) none. Returns True when the shards are usable.

        ``shards`` is imported here, not at the top: `boost mcp` imports this
        module to seed a catalog, and has no use for urllib or the manifest.
        """
        from . import shards
        why = shards.incompatible(manifest)
        if not why:
            return True
        self.vectors_refused = why
        self.vectors_remedy = shards.remedy(manifest)
        return False

    def vectors_note(self, dry_run: bool = False) -> tuple[str, str]:
        """(line, remedy) saying why no published vectors load, or ("", "").

        The dry run explains the zero in its "import 0 shard(s)" line; the
        live run says nothing arrived. Same reason, same remedy, one line each.
        """
        if not self.vectors_refused:
            return "", ""
        line = ("(0 because %s)" if dry_run
                else "no vectors imported — %s") % self.vectors_refused
        return line, self.vectors_remedy

    def _count(self, names: list[str], what: str) -> str:
        """"K of N registries <what>", naming them while they are a handful."""
        line = "%d of %d registries %s" % (len(names), self.selected, what)
        if len(names) <= MAX_NAMED_REGISTRIES:
            line += ": %s" % ", ".join(names)
        return line

    def failure_note(self) -> str:
        """One closing line for the registries that did not make it.

        Each failure was already warned about as it happened, and on a first
        run those scroll past above the closing line — a green tick is the
        shape that reads as success. This is the same information where the
        eye lands. When every attempt failed the verdict itself says so, so
        the note would only repeat it. Clone and index failures are separate
        clauses because they are separate problems.
        """
        if self.every_attempt_failed:
            return ""
        parts = []
        if self.failed:
            parts.append(self._count(self.failed, "could not be tapped"))
        if self.unindexed:
            parts.append(self._count(self.unindexed, "could not be indexed"))
        return "; ".join(parts)

    def verdict(self) -> tuple[str, str]:
        """(message, hint) for the closing line: the ready line, or the cause.

        The hint differs per cause because the remedies do. A dead network is
        retried by rerunning the command that hit it — not by `boost tap
        --defaults`, which is a strict subset of what just failed. A registry
        whose clone succeeded and would not index is not a network problem:
        it is configured, so a rerun skips it, and what it needs depends on
        why ``rebuild_tap`` refused (today, a clone gone by the time it was
        read, which `boost update` restores). `boost doctor` names that per
        tap with the command that fixes it, so the hint defers to it rather
        than guessing a second answer that could disagree. An empty index
        behind registries that did arrive is a tap with no clone, no catalog,
        or nothing boost indexes in it — `boost doctor` again.
        """
        if self.ok:
            return "ready — try `boost search brainstorming`", ""
        if not self.every_attempt_failed:
            return ("not ready — the keyword index is empty, so `boost search` "
                    "has nothing to answer with",
                    "`boost doctor` checks every tap's clone and catalog")
        retry = "check the network, then run `boost quickstart` again"
        n = self.selected
        # One registry is "the registry", not "none of the 1 registries". A
        # mix of both failures needs two registries, so only these two can.
        if not self.unindexed:
            cause = ("the registry could not be tapped" if n == 1
                     else "none of the %d registries could be tapped" % n)
            hint = retry
        elif not self.failed:
            cause = ("the registry could not be indexed" if n == 1
                     else "none of the %d registries could be indexed" % n)
            hint = ("its clone succeeded and it is configured, so a rerun "
                    "skips it — `boost doctor` names what it is missing and "
                    "the command that fixes it" if n == 1 else
                    "their clones succeeded and they are configured, so a "
                    "rerun skips them — `boost doctor` names what each one "
                    "is missing and the command that fixes it")
        else:
            cause = ("none of the %d registries could be set up: %d could not "
                     "be tapped and %d could not be indexed"
                     % (n, len(self.failed), len(self.unindexed)))
            hint = ("%s; `boost doctor` names what each registry that could "
                    "not be indexed is missing" % retry)
        if self.searchable:
            # Don't call a full index empty: these items are real, they are
            # just not this run's doing.
            return ("not ready — %s; the %s items already indexed are "
                    "unaffected" % (cause, format(self.entries, ",")), hint)
        return "not ready — %s, so nothing is searchable" % cause, hint
