# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What an install just wrote, scanned once and rendered for any front end.

boost installs Markdown that an agent then executes, so every install is scanned
for prompt-injection patterns (:mod:`.injectscan`) and embedded credentials
(:mod:`.secretscan`). That wiring used to live entirely in the command layer,
which meant it ran only on the path that remembered to call it: ``boost
install`` warned, and the MCP ``boost_install`` tool installed the same content
in silence — the one path with **no human reading a terminal**, driven by an
agent that had just been told to go find and install skills on its own.

Putting the scan here makes it a property of installing rather than a property
of the CLI, so a new front end gets it by calling one function instead of by
remembering a two-step ritual.

Advisory, never blocking: this reports, the caller decides. Nothing here writes
to a terminal — the CLI renders these through ``output.warn`` and the MCP server
folds them into its reply text.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from . import injectscan, secretscan

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a runtime cycle
    from .store import InstallResult

SKILL_MD = "SKILL.md"

#: What gets read under a skill directory besides SKILL.md: everything worth
#: reading for a shell-out, a fetched script, or a prompt-injection string. Not
#: "every UTF-8 file" — a vendored data file or lockfile would just be noise —
#: but wide enough that a NOTES.md, a references/*.md or a hidden .js helper is
#: not invisible. Shared by install and `boost audit`, so the two can never
#: disagree about which bytes were looked at.
SCAN_SUFFIXES = frozenset({".sh", ".py", ".md", ".js", ".ts", ".rb", ".ps1"})

_RANK = {"high": 0, "medium": 1, "low": 2}

# How many individual findings each scanner quotes. The headline always carries
# the true total, so this caps noise without hiding scale.
MAX_DETAIL = 3

INJECTION = "injection"
# S105 is a false positive on the next line: this is the *name of a scanner*,
# used as a dict-style key, not a credential.
SECRET = "secret"  # noqa: S105

# (name, module, headline template). The templates are the exact strings the CLI
# has always printed — tests assert on them, and more importantly users have
# learned to recognise them, so both front ends say the same thing.
_SCANNERS = (
    (INJECTION, injectscan,
     "%s: %d suspicious pattern%s in %s (%s) — review before use"),
    (SECRET, secretscan,
     "%s: %d possible secret%s in %s (%s) — do not commit"),
)


class Report(NamedTuple):
    """One scanner's verdict on one install. Only produced when it found
    something — an empty report is expressed by not returning one."""
    scanner: str        # INJECTION or SECRET
    severity: str       # worst severity present
    # Named `total`, not `count`: a NamedTuple field called `count` would shadow
    # `tuple.count` and change the type of an inherited method.
    total: int          # all findings, not just the ones quoted in `details`
    headline: str
    details: list[str]  # up to MAX_DETAIL "SKILL.md:L12 [high] desc" lines


class Located(NamedTuple):
    """A scanner finding plus the file it was found in.

    The last five fields are the scanners' own ``Finding`` fields in the same
    order, so ``Located(path, *finding)`` builds one and ``worst_severity``
    reads it unchanged. ``path`` is relative to the skill directory (POSIX
    separators), or ``""`` for a rule/workflow, which is one file.
    """
    path: str
    rule_id: str
    severity: str
    line: int
    snippet: str
    description: str


def skill_files(sdir: Path) -> list[tuple[str, Path]]:
    """``(relative posix path, path)`` for every file a scan reads under a
    skill directory: SKILL.md first, then each SCAN_SUFFIXES file in sorted
    order. Empty when ``sdir`` is not a directory."""
    if not sdir.is_dir():
        return []
    files = [sdir / SKILL_MD] if (sdir / SKILL_MD).is_file() else []
    files += [p for p in sorted(sdir.rglob("*"))
              if p.is_file() and p.suffix in SCAN_SUFFIXES
              and p.name != SKILL_MD]
    return [(p.relative_to(sdir).as_posix(), p) for p in files]


def content_label(res: InstallResult, paths=()) -> str:
    """What was scanned, for the headline. Rules and workflows ship a single
    file, so they are named by kind. A skill is named by the one file its
    findings are in (SKILL.md when there are none), or by a count of files."""
    if res.kind != "skill":
        return "%s content" % res.kind
    distinct = sorted(set(paths))
    if len(distinct) > 1:
        return "%d files" % len(distinct)
    return distinct[0] if distinct else SKILL_MD


def findings_for(res: InstallResult, scanner) -> list[Located]:
    """`scanner`'s findings for the content boost just installed, worst-first.

    Skills scan SKILL.md plus every SCAN_SUFFIXES file under the skill dir —
    a ``curl | sh`` in scripts/ or an injection in references/ is installed
    content the agent can be told to run or read. Rules and workflows scan the
    raw source (``res.scan_text``) — the exact Markdown that landed, not a
    non-existent SKILL.md under the dest file.
    """
    if res.scan_text is not None:
        return [Located("", *f) for f in scanner.scan_text(res.scan_text)]
    found: list[tuple[int, Located]] = []
    for order, (rel, path) in enumerate(skill_files(res.dest)):
        found.extend((order, Located(rel, *f)) for f in scanner.scan_file(path))
    # Worst-first ACROSS files, before any caller caps the list: a HIGH in
    # scripts/ must not hide behind three lows in SKILL.md.
    found.sort(key=lambda t: (_RANK.get(t[1].severity, 3), t[0], t[1].line,
                              t[1].rule_id))
    return [loc for _order, loc in found]


def detail_line(f: Located) -> str:
    """``scripts/setup.sh:L2 [high] description`` — or ``L2 [high] …`` for a
    rule/workflow, which has no path within it to name."""
    where = "%s:L%d" % (f.path, f.line) if f.path else "L%d" % f.line
    return "%s [%s] %s" % (where, f.severity, f.description)


def scan(res: InstallResult, *only: str) -> list[Report]:
    """Reports for `res`, worst-first within each scanner, empty when clean.

    `only` restricts to named scanners (``INJECTION`` / ``SECRET``); with no
    argument both run. The filter exists so the CLI can keep warning about
    injection and secrets as two separate steps without scanning twice.
    """
    reports = []
    for name, scanner, template in _SCANNERS:
        if only and name not in only:
            continue
        found = findings_for(res, scanner)
        if not found:
            continue
        worst = scanner.worst_severity(found)
        reports.append(Report(
            scanner=name,
            severity=worst,
            total=len(found),
            headline=template % (res.name, len(found),
                                 "" if len(found) == 1 else "s",
                                 content_label(res, [f.path for f in found]),
                                 worst),
            details=[detail_line(f) for f in found[:MAX_DETAIL]],
        ))
    return reports


def as_lines(reports: list[Report]) -> list[str]:
    """Flatten reports into plain indented text, for a surface with no colour
    and no terminal — the MCP reply, a log line, a file."""
    lines: list[str] = []
    for rep in reports:
        lines.append(rep.headline)
        lines.extend("  " + d for d in rep.details)
    return lines
