# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Minimal YAML-frontmatter parser for SKILL.md files (stdlib only).

Supports the subset actually used by skill files:
  ---
  name: brainstorming
  description: Structured ideation &
    divergent-thinking facilitation      # folded continuation lines
  version: 1.4.0
  tags: [ideation, thinking]             # flow lists
  requires:
    - other-skill                        # block lists
  ---
"""
from __future__ import annotations

from contextlib import suppress


def split(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    # YAML 1.2 core schema only: true/false and null/~. The 1.1 aliases
    # (yes/no/on/off, none) are NOT coerced — they are ordinary English words
    # that legitimately appear as a skill's name or tag ("on", "none"), and
    # silently turning them into bool/None leaks the wrong type into search
    # and ranking meta.
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null" or s == "~":
        return None
    # Numbers are coerced ONLY when the coercion is lossless — that is, when
    # str() of the result gives back exactly what the author wrote. A number
    # whose text carries information the numeric type cannot hold stays a
    # string, because every consumer of frontmatter (`version`, tags, names)
    # reads these values back as text.
    #
    # This is not hypothetical. `version: 1.10` is ten patch releases past 1.1,
    # but float("1.10") is 1.1 and str(1.1) is "1.1" — so boost read a skill
    # published at 1.10 as 1.1, decided 1.1 < 1.9, and never offered the update.
    # `boost outdated` reported "everything up to date" while the tap was nine
    # releases ahead. Leading zeros (`007` -> 7) and exponents (`1e5` -> 100000.0)
    # corrupt the same way. Found by the parser fuzz harness (tests/fuzz/).
    with suppress(ValueError):
        n = int(s)
        if str(n) == s:
            return n
    with suppress(ValueError):
        f = float(s)
        if str(f) == s:
            return f
    return s


def _flow_list(s: str):
    inner = s.strip()[1:-1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def _split_commas(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf += ch
            quote = ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def parse_block(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        # block-scalar content: every deeper-indented line folds in verbatim
        if in_block:
            if indent > block_indent:
                prev = meta.get(key)
                if isinstance(prev, str):
                    meta[key] = (prev + " " + line).strip()
                continue
            in_block = False
        if line.startswith("#"):
            continue
        # block-list item under the current key
        if line.startswith("- ") or line == "-":
            if key is None:
                continue
            if not isinstance(meta.get(key), list):
                meta[key] = [] if meta.get(key) in ("", None) else [meta[key]]
            meta[key].append(_scalar(line[1:].strip()))
            continue
        # folded continuation of the previous plain scalar
        if indent > 0 and ":" not in line and key is not None:
            prev = meta.get(key)
            if isinstance(prev, str):
                meta[key] = (prev + " " + line).strip()
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        key = k.strip()
        v = v.strip()
        # strip trailing comments on unquoted scalars
        if v and not v.startswith(("'", '"', "[")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def parse(text: str) -> tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(text)
    return (parse_block(block) if block else {}), body


def dump(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            lines.extend("  - %s" % item for item in v)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)
