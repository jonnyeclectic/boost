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

BOM = "\ufeff"


def split(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be "".

    A leading UTF-8 byte-order mark is dropped first. Windows editors
    (Notepad among them) write one, and left in place it hides the opening
    ``---`` from the check below, so a file with a valid fence read as having
    no frontmatter at all: its description became ``\\ufeff---`` and its
    version 0.0.0. Stripping it here, rather than in each reader, keeps
    ``catalog`` and ``rag`` assembling the same body, so the content digest
    stays in parity (tests/unit/test_content_identity.py).
    """
    text = text.removeprefix(BOM)
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
    text = text.removeprefix(BOM)
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


def _value(v: str):
    """A `key: value` line's value: flow list, block-scalar opener or scalar.

    Returns ``_BLOCK`` for a ``|``/``>`` opener, whose content the caller
    collects (or skips) from the indented lines that follow.
    """
    v = v.strip()
    # strip trailing comments on unquoted scalars
    if v and not v.startswith(("'", '"', "[")) and " #" in v:
        v = v.split(" #", 1)[0].strip()
    if v.startswith("[") and v.endswith("]"):
        return _flow_list(v)
    if v in _BLOCK_SCALAR_TOKENS:
        return _BLOCK
    return _scalar(v)


_BLOCK = object()


def _is_item(line: str) -> bool:
    return line.startswith("- ") or line == "-"


def parse_block(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises.

    Top-level keys sit at the indent of the first key line (column 0 in any
    real file). A `k: v` line deeper than that is never a top-level field:
    reading it as one let `author: {name: Jane Doe}` rename the skill to
    jane-doe and `metadata: {version: "2.0"}` set its version. Under a key with
    no value of its own it is one entry of a nested map, kept as a dict under
    that key (`meta["author"] == {"name": "Jane Doe"}`): a scalar, a flow list
    or a block list per entry. Anything deeper than that one level, and an
    indented `k: v` under a key that already has a value, is skipped.
    """
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    top_indent: int | None = None
    nest: dict | None = None   # the nested map being filled, under `key`
    nest_indent = 0            # column of that map's own keys
    nest_key: str | None = None
    skipping = False       # inside an indented subtree that is not modelled
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
        if top_indent is not None and indent > top_indent:
            if skipping:
                continue
            if nest is None and not _is_item(line) and ":" in line:
                if meta.get(key) not in ("", None):
                    skipping = True
                    continue
                nest = meta[key] = {}
                nest_indent, nest_key = indent, None
            if nest is not None:
                if indent == nest_indent and not _is_item(line) and ":" in line:
                    nk, _, nv = line.partition(":")
                    nest_key = nk.strip()
                    val = _value(nv)
                    if val is _BLOCK:   # nested block scalar: not modelled
                        nest[nest_key], nest_key = "", None
                    else:
                        nest[nest_key] = val
                elif (_is_item(line) and indent >= nest_indent
                      and nest_key is not None):
                    prev = nest.get(nest_key)
                    if not isinstance(prev, list):
                        prev = nest[nest_key] = [] if prev in ("", None) else [prev]
                    prev.append(_scalar(line[1:].strip()))
                continue
        else:
            nest, skipping = None, False
        # block-list item under the current key
        if _is_item(line):
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
        if top_indent is None:
            top_indent = indent
        k, _, v = line.partition(":")
        key = k.strip()
        val = _value(v)
        if val is _BLOCK:
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = val
    return meta


def parse(text: str) -> tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(text)
    return (parse_block(block) if block else {}), body


def tags_of(meta) -> list[str]:
    """``tags:`` off third-party frontmatter as a list of strings.

    A list and a comma string (``tags: a, b`` or a lone ``tags: testing``) are
    both common in real repos; anything else reads as "no tags". Iterating the
    raw value instead split a scalar string into single characters, and a
    ``tags: {a: 1}`` must not raise. Case is kept; callers that facet fold it.
    """
    if not isinstance(meta, dict):
        return []
    raw = meta.get("tags")
    if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
        raw = str(raw).split(",")
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(t).strip() for t in raw
            if isinstance(t, (str, int, float)) and not isinstance(t, bool)
            and str(t).strip()]


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
        if isinstance(v, dict):
            # the one level of nested map `parse_block` models
            lines.append("%s:" % k)
            for nk, nv in v.items():
                _dump_field(lines, nk, nv, "  ")
        else:
            _dump_field(lines, k, v, "")
    lines.append("---")
    return "\n".join(lines)


def _dump_field(lines: list[str], k, v, pad: str) -> None:
    if isinstance(v, list):
        lines.append("%s%s:" % (pad, k))
        lines.extend("%s  - %s" % (pad, _dump_item(item)) for item in v)
    elif isinstance(v, bool):
        lines.append("%s%s: %s" % (pad, k, "true" if v else "false"))
    elif v is None:
        lines.append("%s%s:" % (pad, k))
    else:
        lines.append("%s%s: %s" % (pad, k, _dump_item(v)))


def splice_field(text: str, key: str, value) -> str:
    """Return `text` with top-level frontmatter key `key` set to `value`,
    changing that one line and no other byte.

    :func:`set_field` rebuilds the file around the block it edits: it drops a
    BOM, turns CRLF into LF, and puts a blank line after the closing fence.
    That is fine for `evolve`, which writes a revision anyway, and wrong for a
    copy whose only difference from its source is meant to be one field. Here
    each line keeps its own ending, and a key the block lacks goes in just
    before the closing fence with the ending the fence line uses. Returns
    `text` unchanged when it has no closed frontmatter block.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].removeprefix(BOM).strip() != "---":
        return text
    close = next((i for i in range(1, len(lines))
                  if lines[i].strip() in ("---", "...")), None)
    if close is None:       # unclosed: there is no block to edit
        return text
    formatted = "%s: %s" % (key, _dump_item(value))
    for i in range(1, close):
        body = lines[i].rstrip("\r\n")
        if (body[:1] not in (" ", "\t") and ":" in body
                and body.split(":", 1)[0].strip() == key):
            lines[i] = formatted + lines[i][len(body):]
            return "".join(lines)
    fence = lines[close]
    lines.insert(close, formatted + (fence[len(fence.rstrip("\r\n")):] or "\n"))
    return "".join(lines)


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
