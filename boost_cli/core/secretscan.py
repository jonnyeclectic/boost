"""Scan installed skill content for embedded secrets & credentials (stdlib).

A third-party skill can ship a hard-coded credential — an AWS key, a GitHub
token, a private-key block — that then lands in the user's tree, or leak one the
agent was handed. This module carries a small, high-precision set of secret
*shape* patterns (known token prefixes and key blocks, not entropy guessing) so
boost can flag them at install time without any external scanner.

Findings never echo the raw secret: the matched value is redacted to a short
prefix so a warning can point at the offending line without re-leaking it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, NamedTuple

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


class Rule(NamedTuple):
    """One compiled secret-shape detection rule (regex plus severity).

    ``group`` is the capture group holding the secret value to redact
    (0 = the whole match).
    """
    id: str
    severity: str
    pattern: re.Pattern[str]
    group: int          # capture group holding the secret value to redact
    description: str


class Finding(NamedTuple):
    """One redacted secret hit produced by a scan.

    ``line`` is 1-based; ``snippet`` is the offending line with the
    secret masked, so the raw value is never echoed.
    """
    rule_id: str
    severity: str
    line: int           # 1-based line number
    snippet: str        # offending line, secret redacted, trimmed
    description: str


def _rx(pattern: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# High-precision rules keyed on well-known token shapes — chosen so a benign
# skill almost never trips them. ``group`` marks the span to redact (0 = whole
# match).
RULES: tuple = (
    Rule("private-key-block", "high",
         _rx(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
         0, "embedded private key block"),
    Rule("aws-access-key-id", "high",
         _rx(r"\b(AKIA[0-9A-Z]{16})\b"), 1, "AWS access key id"),
    Rule("github-token", "high",
         _rx(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}"
             r"|github_pat_[A-Za-z0-9_]{22,})\b"), 1, "GitHub token"),
    Rule("slack-token", "high",
         _rx(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b"), 1, "Slack token"),
    Rule("google-api-key", "high",
         _rx(r"\b(AIza[0-9A-Za-z_\-]{35})\b"), 1, "Google API key"),
    Rule("stripe-secret-key", "high",
         _rx(r"\b((?:r|s)k_live_[A-Za-z0-9]{16,})\b"), 1, "Stripe live key"),
    Rule("openai-key", "high",
         _rx(r"\b(sk-(?:proj-)?[A-Za-z0-9]{20,})\b"), 1, "OpenAI-style key"),
    Rule("jwt", "medium",
         _rx(r"\b(eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
             r"\.[A-Za-z0-9_\-]{8,})\b"), 1, "JSON Web Token"),
    Rule("generic-secret-assignment", "medium",
         _rx(r"(?i)\b(?:api[_\-]?key|secret|token|passwd|password|"
             r"access[_\-]?key)\b\s*[=:]\s*[\"']([^\"'\n]{8,})[\"']"),
         1, "hard-coded secret assignment"),
    Rule("us-ssn", "medium",
         _rx(r"\b([0-9]{3}-[0-9]{2}-[0-9]{4})\b"), 1, "US Social Security number"),
)


def redact(value: str) -> str:
    """Mask a secret to a short, non-recoverable hint (keeps ≤4 leading chars)."""
    if len(value) <= 4:
        return "****"
    return value[:4] + "****"


def _redacted_line(line: str, rule: Rule, match) -> str:
    """The offending line with this match's secret span replaced by a hint."""
    start, end = match.span(rule.group)
    if start < 0:                       # optional group didn't participate
        return line.strip()[:200]
    masked = line[:start] + redact(match.group(rule.group)) + line[end:]
    return masked.strip()[:200]


def scan_text(text: str) -> List[Finding]:
    """Findings for every secret-shape rule that matches a line of ``text``.

    One finding per (rule, line), using that line's first match. The raw secret
    is never included — the snippet carries a redacted line. Ordered worst-first
    (severity desc, then line, then rule id).
    """
    findings: List[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            m = rule.pattern.search(raw)
            if m:
                findings.append(Finding(rule.id, rule.severity, lineno,
                                        _redacted_line(raw, rule, m),
                                        rule.description))
    findings.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.line,
                                 f.rule_id))
    return findings


def scan_file(path) -> List[Finding]:
    """Scan the file at ``path``; a missing/unreadable file yields ``[]``."""
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
