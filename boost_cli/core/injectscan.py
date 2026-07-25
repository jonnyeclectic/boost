"""Scan skill Markdown for prompt-injection & risky-content patterns (stdlib).

boost installs Markdown that an agent then *executes* as instructions, so the
highest-signal supply-chain risk is content that tries to hijack the agent
("ignore previous instructions"), exfiltrate data, or smuggle a shell command
(``curl … | sh``). There is no dependency-free rule engine on PyPI we want at
runtime, so this module ships a small curated pattern set instead — enough to
flag the obvious attacks at install/tap time without any external tool.

The scanner is deliberately conservative: it reports *suspicious* lines for a
human to look at, it does not block. Each rule has a stable id so callers (and
tests) can reason about individual signals, and a severity so a caller can show
the worst first.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, NamedTuple

# Severity ordering — higher rank = more alarming, used to sort worst-first.
_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


class Rule(NamedTuple):
    """One curated detection pattern applied per line of scanned text.

    ``id`` is stable for callers/tests to key on; ``severity`` is one
    of "high", "medium", or "low".
    """
    id: str
    severity: str
    pattern: re.Pattern[str]
    description: str


class Finding(NamedTuple):
    """One rule match on one line of scanned text.

    ``line`` is 1-based; ``snippet`` is the offending line, trimmed.
    """
    rule_id: str
    severity: str
    line: int          # 1-based line number the pattern matched on
    snippet: str       # the offending line, trimmed
    description: str


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Curated rules. Kept small and high-precision on purpose: a noisy scanner that
# cries wolf gets ignored. Grouped by the three attack shapes the card names.
RULES: tuple = (
    # ── agent-instruction hijacking ──────────────────────────────────────
    Rule("ignore-previous", "high",
         _rx(r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)"
             r"\s+(?:instructions?|prompts?|messages?|context)\b"),
         "attempts to override earlier instructions"),
    Rule("disregard-above", "high",
         _rx(r"\bdisregard\s+(?:all\s+|everything\s+|the\s+)?"
             r"(?:above|previous|prior|foregoing)\b"),
         "attempts to discard prior context"),
    Rule("forget-everything", "high",
         _rx(r"\bforget\s+(?:everything|all\s+(?:previous|prior)|what\s+you)"),
         "attempts to wipe the agent's context"),
    Rule("new-instructions", "medium",
         _rx(r"\b(?:new|updated|real|actual)\s+(?:instructions?|"
             r"system\s+prompt|directive)s?\s*:"),
         "injects a replacement instruction block"),
    Rule("role-override", "medium",
         _rx(r"\byou\s+are\s+now\s+(?:a|an|the|no\s+longer)\b"),
         "attempts to reassign the agent's role"),
    Rule("system-prompt-ref", "low",
         _rx(r"\b(?:reveal|print|repeat|show|leak)\s+(?:your\s+|the\s+)?"
             r"(?:system\s+prompt|initial\s+instructions|hidden\s+prompt)\b"),
         "attempts to extract the system prompt"),
    # ── data exfiltration ────────────────────────────────────────────────
    Rule("exfiltrate-secret", "high",
         _rx(r"\b(?:send|post|upload|exfiltrate|leak|forward|email)\b.{0,40}"
             r"\b(?:api[_\- ]?key|token|secret|password|credential|"
             r"\.env|private\s+key|ssh\s+key)s?\b"),
         "moves credentials/secrets off the machine"),
    Rule("read-env-and-send", "high",
         _rx(r"\b(?:cat|print(?:env)?|echo)\b.{0,30}"
             r"(?:\$\{?[A-Z_]*(?:KEY|TOKEN|SECRET|PASS)|~?/\.(?:aws|ssh|"
             r"env|netrc|npmrc))"),
         "reads a credential store, likely to exfiltrate"),
    # ── risky shell smuggled into instructions ───────────────────────────
    Rule("curl-pipe-shell", "high",
         _rx(r"\b(?:curl|wget|fetch)\b[^\n|]*\|\s*(?:sudo\s+)?"
             r"(?:sh|bash|zsh|python[23]?|node|ruby|perl)\b"),
         "pipes a downloaded script straight into a shell"),
    Rule("base64-pipe-shell", "high",
         _rx(r"\bbase64\s+(?:-{1,2}\w+\s+)*-?[dD]\b[^\n|]*\|\s*"
             r"(?:sudo\s+)?(?:sh|bash|zsh)\b"),
         "decodes an obfuscated blob and runs it"),
    Rule("eval-subshell", "medium",
         _rx(r"\beval\s+[\"']?\$\("),
         "evaluates the output of a subshell"),
    Rule("rm-rf-root", "medium",
         _rx(r"\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+(?:--no-preserve-root\s+)?"
             r"(?:/|~|\$HOME)\S*"),
         "destructive recursive delete of a broad path"),
)


def scan_text(text: str) -> List[Finding]:
    """Return findings for every rule that matches a line of ``text``.

    Scans line by line so each finding carries a 1-based line number and the
    offending line as a trimmed snippet. At most one finding per (rule, line)
    is reported. Results are ordered worst-first: descending severity, then by
    line number, then rule id — a stable order tests can rely on.
    """
    findings: List[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        findings.extend(
            Finding(rule.id, rule.severity, lineno,
                    raw.strip()[:200], rule.description)
            for rule in RULES
            if rule.pattern.search(raw)
        )
    findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.line,
                                 f.rule_id))
    return findings


def scan_file(path) -> List[Finding]:
    """Scan the Markdown at ``path``; a missing/unreadable file yields ``[]``."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return []
    return scan_text(text)


def worst_severity(findings) -> str:
    """Highest severity among ``findings`` ("high" > "medium" > "low"), or ""."""
    best = ""
    best_rank = 0
    for f in findings:
        rank = _SEVERITY_RANK.get(f.severity, 0)
        if rank > best_rank:
            best_rank = rank
            best = f.severity
    return best
