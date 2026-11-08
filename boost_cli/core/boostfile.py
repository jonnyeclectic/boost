# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The Boostfile line grammar: parse and render one ``tap`` or ``skill`` line.

A Boostfile is a reproducibility contract, so every piece of install state it
claims to carry has to survive ``bundle dump`` -> ``bundle install``::

    tap NAME [URL] [--at SHA]
    skill [TAP:]NAME[@VERSION] [--local] [--agent A]... [--pin]
          [--commit-pin SHA] [--tag T]...

``--at`` is ``boost tap --at``'s pin, ``--agent`` is ``boost install
--agent``, ``--pin`` / ``--commit-pin`` are ``boost pin`` / ``boost pin
--commit`` and ``--tag`` is ``boost tag +T``. Every option is optional, so a
Boostfile written before any of them existed parses unchanged.

The tap URL is everything between NAME and a trailing ``--at SHA`` — not a
whitespace token — because a local path may hold a space and the grammar
always read the rest of the line as the URL. A skill line's options are
whitespace tokens, and one this grammar does not know is an error for that
line rather than an ignored extra: ``--locl`` for ``--local`` would otherwise
install at the wrong scope with nothing said.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..errors import BoostError
from . import gitutil, lockfile, registry

GRAMMAR = ("tap NAME [URL] [--at SHA]\n"
           "skill [TAP:]NAME[@VERSION] [--local] [--agent A]... [--pin] "
           "[--commit-pin SHA] [--tag T]...")

_TAP_AT = re.compile(r"(?:(.*?)\s+)?--at(?:\s+(\S+))?")
_VALUED = ("--agent", "--commit-pin", "--tag")
_FLAGS = ("--local", "--pin")


@dataclass
class SkillLine:
    """One parsed ``skill`` line."""

    tap: str
    name: str
    version: str
    local: bool = False
    agents: list[str] = field(default_factory=list)
    pin: bool = False
    commit_pin: str = ""
    tags: list[str] = field(default_factory=list)


def _require_sha(value: str, option: str) -> str:
    if not gitutil._is_sha(value):
        raise BoostError("%s needs a full 40-character commit SHA, got %r"
                         % (option, value))
    return value


def parse_tap(rest: str) -> tuple[str, str]:
    """``(url, at)`` from what follows ``tap NAME``; ``at`` is "" when unpinned."""
    rest = rest.strip()
    m = _TAP_AT.fullmatch(rest)
    if m is None:
        return rest, ""
    if m.group(2) is None:
        raise BoostError("--at needs a commit SHA")
    return (m.group(1) or "").strip(), _require_sha(m.group(2), "--at")


def parse_skill(spec: str, rest: str = "") -> SkillLine:
    """Parse ``[TAP:]NAME[@VERSION]`` and the options after it.

    Raises BoostError naming the offending token for an empty skill name, an
    unknown option or stray word, an option missing its value, and a
    user-lock-only option (``--tag``, ``--commit-pin``) on a ``--local`` line.
    """
    tapq, _, tail = spec.rpartition(":")
    name, _, version = tail.partition("@")
    if not name:
        raise BoostError("no skill name in %r" % spec)
    line = SkillLine(tap=tapq, name=name, version=version)
    tokens = rest.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        opt, eq, inline = tok.partition("=")
        if opt in _FLAGS and not eq:
            if opt == "--local":
                line.local = True
            else:
                line.pin = True
        elif opt in _VALUED:
            if eq:
                value = inline
            elif i + 1 < len(tokens):
                i += 1
                value = tokens[i]
            else:
                value = ""
            if not value:
                raise BoostError("%s needs a value" % opt)
            if opt == "--agent":
                if value not in line.agents:
                    line.agents.append(value)
            elif opt == "--commit-pin":
                line.commit_pin = _require_sha(value, opt)
            else:
                # `boost tag`'s own validation, so a Boostfile cannot carry a
                # tag the command would refuse.
                line.tags = lockfile.apply_tag_mods(line.tags, ["+" + value])[0]
        elif tok.startswith("-"):
            raise BoostError("unknown option %r" % tok)
        else:
            raise BoostError("unexpected %r" % tok)
        i += 1
    if line.local:
        for opt, used in (("--tag", line.tags), ("--commit-pin", line.commit_pin)):
            if used:
                raise BoostError("%s applies to user-scope skills, not a "
                                 "--local one" % opt)
    return line


def render_tap(name: str, url: str, pin: str = "") -> str:
    """A ``tap`` line; ``pin`` adds ``--at`` so the clone lands where it was."""
    text = ("tap %s %s" % (name, url)).rstrip()
    return text + (" --at %s" % pin if pin else "")


def recorded_source(rows: Iterable[Mapping]) -> tuple[str, str]:
    """``(url, at)`` for the ``tap`` line of a tap that is no longer configured.

    The lock rows installed from it remember where it came from: each one
    recorded the tap's ``tap_url`` at install, which ``boost drift`` already
    re-taps from. ``url`` is the first one recorded, skipping boost's own
    wheel tap (``builtin:``), which no Boostfile line can re-tap. ``at`` is
    the commit the rows were installed at when every row records the same
    full SHA, so the ``@version`` on each skill line names the tree the tap
    lands on. Rows installed at different commits name no one tree, and the
    line is left unpinned rather than held where some of them never came
    from. ``("", ...)`` means nothing recorded a URL and the line cannot be
    replayed.
    """
    url = ""
    commits: set[str] = set()
    for row in rows:
        recorded = str(row.get("tap_url") or "")
        if not url and recorded and not recorded.startswith(
                registry.WHEEL_SCHEME):
            url = recorded
        commits.add(str(row.get("commit") or ""))
    at = commits.pop() if len(commits) == 1 else ""
    return url, at if gitutil._is_sha(at) else ""


def render_skill(entry: dict, name: str, *, local: bool = False) -> str:
    """A ``skill`` line for lock ``entry``, carrying every option it records."""
    text = "skill %s:%s@%s" % (entry["tap"], name, entry.get("version", "0.0.0"))
    opts: list[str] = []
    if local:
        opts.append("--local")
    opts += ["--agent %s" % a for a in entry.get("only_agents") or ()]
    if entry.get("pinned"):
        opts.append("--pin")
    if not local:
        if entry.get("commit_pin"):
            opts.append("--commit-pin %s" % entry["commit_pin"])
        opts += ["--tag %s" % t for t in sorted(entry.get("tags") or ())]
    return " ".join([text, *opts])
