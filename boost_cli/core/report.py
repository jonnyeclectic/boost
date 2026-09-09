# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One command, two audiences: the prose a person reads and the JSON a machine
parses.

Eleven read-only reporting commands rejected the ``--json`` their group
siblings all accept, and the sharp ones are the ones a machine reads: ``doctor``
is the check CI would poll and the MCP server already exposes a ``boost_doctor``
tool, yet the CLI offered only prose.

The naive fix is an ``if args.json`` beside every ``out.ok`` call, and it is
wrong twice. It duplicates the message in two spellings that drift apart, and
it invites a stray ``print`` to land on stdout beside the payload, which makes
the document unparseable for a consumer that is by definition not reading it
with their eyes. So a command reports through a collector instead: the call
sites say *what was checked and how it went*, and the mode decides whether that
becomes a glyph or a row.

**Prose mode delegates to the same ``out.*`` functions with the same
arguments**, so routing an existing command through this changes nothing a
reader sees. That is what lets a command adopt it without rewriting its tests,
and it is the property to protect — a collector that reformats is a rewrite of
every command that adopts it.

**``note`` does not raise the issue count, and that is load-bearing rather than
an oversight.** ``doctor`` deliberately reports foreign symlinks, foreign hooks
and crash reports with ``out.info``: boost did not create them, ``heal`` will
not remove them, and counting them would leave the command permanently red on
something no boost command can clear — which is how a health check stops being
read. The three statuses keep that distinction addressable from the payload.
"""
from __future__ import annotations

import json

from . import output as out

#: A check went the way it should.
OK = "ok"
#: A real fault, counted toward the exit code.
ISSUE = "issue"
#: A warning line that summarizes faults already counted elsewhere. Wears the
#: `!` glyph, never moves the exit code — counting it would report the same
#: fault twice.
WARN = "warn"
#: Worth saying, never counted — see the module docstring.
INFO = "info"


class Report:
    """Collect a command's check lines, then render them as prose or JSON.

    ``as_json`` is decided once by the caller from its parsed arguments and
    never re-read, so a single run cannot emit half of each.
    """

    def __init__(self, as_json: bool = False) -> None:
        self.as_json = as_json
        self.issues = 0
        self._checks: list[dict] = []
        self._verdict: str | None = None

    # ---------------------------------------------------------- recording

    def _record(self, name: str, status: str, message: str,
                hint: str | None) -> None:
        self._checks.append({"name": name, "status": status,
                             "message": message, "hint": hint})

    def ok(self, name: str, message: str, *, hint: str | None = None) -> None:
        """Record a passing check."""
        self._record(name, OK, message, hint)
        if not self.as_json:
            # `out.ok` takes no `wrap` — it is a short confirmation, and the
            # commands never asked it to fold.
            out.ok(message)

    def issue(self, name: str, message: str, *, hint: str | None = None,
              wrap: bool = False) -> None:
        """Record a fault. This is the only status that moves the exit code."""
        self.issues += 1
        self._record(name, ISSUE, message, hint)
        if not self.as_json:
            out.warn(message, wrap=wrap)

    def warn(self, name: str, message: str, *, hint: str | None = None,
             wrap: bool = False) -> None:
        """Record a warning that restates faults already counted.

        `doctor` closes with two such lines — a one-line dashboard and a
        lock-file/rotation summary — which wear the `!` glyph when anything
        upstream failed. They are renderings of checks already recorded, so
        counting them would report the same fault twice and put the issue
        total permanently one or two above the number of things actually
        wrong.
        """
        self._record(name, WARN, message, hint)
        if not self.as_json:
            out.warn(message, wrap=wrap)

    def note(self, name: str, message: str, *, hint: str | None = None,
             wrap: bool = False) -> None:
        """Record something worth saying that is not a fault.

        Never counted — see the module docstring for why that is a decision
        rather than a default.
        """
        self._record(name, INFO, message, hint)
        if not self.as_json:
            out.info(message, wrap=wrap)

    def verdict(self, ok: bool, message: str) -> None:
        """Record the closing dashboard line."""
        self._verdict = message
        if not self.as_json:
            out.verdict(ok, message)

    # ----------------------------------------------------------- rendering

    def exit_code(self) -> int:
        """``1`` when anything was recorded as an issue, else ``0``.

        The commands' existing contract, kept in one place so a payload
        claiming ``ok`` cannot disagree with the status the same run returned.
        """
        return 1 if self.issues else 0

    def payload(self) -> dict:
        """The machine-readable document, as a snapshot.

        A snapshot rather than a live view: callers hold this and keep
        reporting, and a shared list would keep growing under an already
        emitted document.
        """
        return {
            "checks": [c.copy() for c in self._checks],
            "issues": self.issues,
            "ok": self.issues == 0,
            # `None`, never `""` or `False`: a command that returned early
            # never rendered a verdict, and both of those spell a verdict that
            # was reached and said something.
            "verdict": self._verdict,
        }

    def emit(self) -> None:
        """Print the payload when in JSON mode; do nothing in prose mode.

        Prose has already been printed line by line as the checks ran, so this
        is the whole of the JSON path's output — one document, one call, one
        spelling of the format.
        """
        if self.as_json:
            print(json.dumps(self.payload(), indent=2))
