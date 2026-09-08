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


# The one-line diagnosis for `unclosed()` below — shared so a caller can
# recognise and filter the note `util.score_skill` emits for the same fault
# rather than re-typing the string (and risking the two drifting apart).
UNCLOSED_NOTE = "frontmatter is not closed (no terminating ---)"


def unclosed(text: str) -> bool:
    """True if `text` opens a frontmatter fence but never closes it.

    `split()` falls back to "no frontmatter at all" for this case — the block
    comes back "" and every field it would have carried reads as absent. That
    misdiagnoses a real syntax error (a missing closing `---`/`...`) as three
    unrelated missing-field errors, so callers that want to tell the two apart
    check this first: a file that never opens a fence (doesn't start with
    `---`) is legitimately frontmatter-less, but one that opens and never
    closes is broken and should say so once, not by omission three times over.
    """
    if not text.startswith("---"):
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    return not any(line.strip() in ("---", "...") for line in lines[1:])


def _dump_escape(s: str) -> str:
    """Escape `s` for a double-quoted scalar; `_dump_unescape` inverts this."""
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return "".join(out)


def _dump_unescape(s: str) -> str:
    """Inverse of `_dump_escape`, applied to a double-quoted scalar's inside."""
    out = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n and s[i + 1] in ("n", '"', "\\"):
            out.append("\n" if s[i + 1] == "n" else s[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


_BLOCK_SCALAR_TOKENS = frozenset({"|", "|-", "|+", ">", ">-", ">+"})


def _needs_quoting(s: str) -> bool:
    """True if dumping `s` bare would not read back as this same string.

    Mirrors every branch in `_scalar`/`parse_block` that treats an unquoted
    scalar specially: a flow list (``[...]``), a block-scalar opener, the
    true/false/null/``~`` keywords, a numeral `_scalar` would coerce
    losslessly, or a value already wrapped the way `_scalar` unwraps a
    quoted one. Only meant for values that are already Python `str` —
    `dump()` never calls this for a real int/float/bool, which already round
    trip correctly unquoted.
    """
    if s == "":
        return False
    if s != s.strip():
        return True
    if "\n" in s or ":" in s or "#" in s:
        return True
    if s in _BLOCK_SCALAR_TOKENS:
        return True
    if s.startswith("[") and s.endswith("]"):
        return True
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return True
    low = s.lower()
    if low in ("true", "false", "null") or s == "~":
        return True
    with suppress(ValueError):
        int(s)
        return True
    with suppress(ValueError):
        float(s)
        return True
    return False


def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        inner = s[1:-1]
        return _dump_unescape(inner) if s[0] == '"' else inner
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


def _dump_item(v) -> str:
    """Render one scalar the way `dump()` would, quoting only when needed."""
    if isinstance(v, str) and _needs_quoting(v):
        return '"%s"' % _dump_escape(v)
    return str(v)


def dump(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced).

    A string scalar is quoted (and ``\\``/``"``/``\\n`` escaped) whenever
    leaving it bare would change what `parse()` reads back — see
    `_needs_quoting`. A real int/float/bool/None never goes through that
    check: those already round-trip unquoted via `_scalar`'s own coercions.
    """
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            lines.extend("  - %s" % _dump_item(item) for item in v)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            lines.append("%s: %s" % (k, _dump_item(v)))
    lines.append("---")
    return "\n".join(lines)


def set_field(text: str, key: str, value) -> str:
    """Return `text` with top-level frontmatter key `key` set to `value`,
    leaving every other line of the block byte-identical.

    A full parse -> dict -> `dump()` round trip rewrites every field through
    `dump()`'s own quoting rules, not just the one that changed — turning
    ``description: "Use before ..."`` into ``description: Use before ...``
    in a diff the caller never asked for. `evolve`'s heuristic revision only
    ever bumps ``version``, so it edits that one line in place instead.
    Falls back to returning `text` unchanged when it has no frontmatter
    block to splice into.
    """
    block, body = split(text)
    if not block:
        return text
    formatted = _dump_item(value)
    lines = block.splitlines()
    for i, raw in enumerate(lines):
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0 and ":" in line and line.split(":", 1)[0].strip() == key:
            lines[i] = "%s: %s" % (key, formatted)
            break
    else:
        lines.append("%s: %s" % (key, formatted))
    return "---\n%s\n---\n\n%s" % ("\n".join(lines), body)
