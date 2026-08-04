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

from typing import TYPE_CHECKING, NamedTuple

from . import injectscan, secretscan

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids a runtime cycle
    from .store import InstallResult

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
    details: list[str]  # up to MAX_DETAIL "L12 [high] description" lines


def content_label(res: InstallResult) -> str:
    """What was scanned, for the headline: skills ship a SKILL.md; rules and
    workflows ship a single file, so name the kind instead."""
    return "SKILL.md" if res.kind == "skill" else "%s content" % res.kind


def findings_for(res: InstallResult, scanner) -> list:
    """`scanner`'s findings for the content boost just installed.

    Skills scan their SKILL.md; rules and workflows scan the raw source
    (``res.scan_text``) — the exact Markdown that landed, not a non-existent
    SKILL.md under the dest file.
    """
    if res.scan_text is not None:
        return scanner.scan_text(res.scan_text)
    return scanner.scan_file(res.dest / "SKILL.md")


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
                                 content_label(res), worst),
            details=["L%d [%s] %s" % (f.line, f.severity, f.description)
                     for f in found[:MAX_DETAIL]],
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
