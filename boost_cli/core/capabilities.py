# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What a skill can do — declared, detected, and gated by policy.

boost already blocks installs by name/tap/quality (:mod:`policy`). This is the
next question a governance-minded team asks: not *which* skill, but *what it is
allowed to make the agent do*. A skill is a bundle of instructions an agent
executes; least-privilege means the user's policy can refuse one that expects a
capability they don't grant — the network, a shell, the filesystem.

Two signals, deliberately kept separate:

* **declared** — a ``capabilities:`` frontmatter field the skill author writes.
  Trustworthy in the honest case and the basis for the default policy check:
  enforcing declared capabilities has no false positives, because the author
  said so.
* **detected** — a heuristic scan of the skill's text for capability *tells*
  (a ``curl`` command, a fenced ``bash`` block, an ``rm``). Useful for audit and
  for catching a skill that under-declares, but fuzzy — an example URL in prose
  reads as "network". So detected capabilities gate an install only under an
  explicit opt-in (``policy enforce_detected_capabilities``), never by default.

The vocabulary is intentionally tiny and coarse. Three buckets a user actually
reasons about ("I don't want anything on this machine touching the network")
beat a sprawling taxonomy nobody configures.
"""
from __future__ import annotations

import re

NETWORK = "network"
SHELL = "shell"
FILESYSTEM = "filesystem"
KNOWN: tuple[str, ...] = (NETWORK, SHELL, FILESYSTEM)

# Aliases an author might write for a bucket, folded to the canonical name.
_ALIASES = {
    "net": NETWORK, "http": NETWORK, "url": NETWORK, "web": NETWORK,
    "internet": NETWORK, "download": NETWORK,
    "sh": SHELL, "bash": SHELL, "command": SHELL, "commands": SHELL,
    "exec": SHELL, "subprocess": SHELL, "process": SHELL,
    "fs": FILESYSTEM, "file": FILESYSTEM, "files": FILESYSTEM,
    "disk": FILESYSTEM, "write": FILESYSTEM,
}

# Detection tells, per bucket. Specific enough that ordinary prose does not trip
# them, coarse enough to catch the obvious cases; case-insensitive.
_TELLS = {
    NETWORK: [
        r"https?://", r"\bcurl\b", r"\bwget\b", r"\bfetch\s*\(", r"\brequests\.",
        r"\burllib\b", r"\bwebhook\b", r"\bwss?://", r"\bhttpx\b",
    ],
    SHELL: [
        r"```(?:ba)?sh\b", r"```shell\b", r"```console\b", r"\bsubprocess\b",
        r"\bos\.system\b", r"\bshell\s*=\s*true\b", r"\|\s*(?:ba)?sh\b",
        r"\bsh\s+-c\b", r"\$\([^)]", r"\bpopen\b",
    ],
    FILESYSTEM: [
        r"\brm\s+-", r"\bmkdir\b", r"\bchmod\b", r"\bunlink\b",
        r"\bos\.remove\b", r"\bshutil\.(?:rmtree|copy|move)\b",
        r"\bwrite_text\b", r"\bopen\([^)]*['\"][wa]", r"\brmdir\b",
    ],
}
_COMPILED = {cap: [re.compile(p, re.IGNORECASE) for p in pats]
             for cap, pats in _TELLS.items()}


def declared(meta: dict) -> set[str]:
    """Canonical capabilities a skill's frontmatter declares.

    Accepts a list or a comma-separated string; folds known aliases; drops
    anything it does not recognize (surfaced separately by :func:`unknown`), so
    a typo can never silently grant or deny.
    """
    return {c for c in _normalize(_raw(meta)) if c in KNOWN}


def unknown(meta: dict) -> set[str]:
    """Declared capability names that are not in the known vocabulary."""
    return {c for c in _normalize(_raw(meta)) if c not in KNOWN}


def _raw(meta: dict):
    val = meta.get("capabilities")
    if val in (None, "", False):
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    return str(val).split(",")


def _normalize(items) -> set[str]:
    out: set[str] = set()
    for it in items:
        s = str(it).strip().lower()
        if s:
            out.add(_ALIASES.get(s, s))
    return out


def detect(text: str) -> set[str]:
    """Capabilities a heuristic scan finds evidence of in ``text``.

    Advisory: a match means "this looks like it uses X", not "it is allowed to".
    Used for audit/info and, only under the opt-in strict flag, for enforcement.
    """
    found: set[str] = set()
    for cap, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            found.add(cap)
    return found


def effective(meta: dict, text: str) -> set[str]:
    """Everything a skill declares *or* shows evidence of — the audit view."""
    return declared(meta) | detect(text)


def violations(declared_caps: set[str], detected_caps: set[str],
               denied: set[str], enforce_detected: bool) -> list[str]:
    """Policy violations for a skill's capabilities against a deny list.

    A declared capability on the deny list always violates. A merely *detected*
    one violates only when ``enforce_detected`` is set — the strict, false-
    positive-accepting mode — and is worded so the message says the tell was
    inferred, not authored.
    """
    out = ["declares the %r capability, denied by policy" % cap
           for cap in sorted(denied & declared_caps)]
    if enforce_detected:
        out += ["looks like it uses %r (detected), denied by policy" % cap
                for cap in sorted((denied & detected_caps) - declared_caps)]
    return out
