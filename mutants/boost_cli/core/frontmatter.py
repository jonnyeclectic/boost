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

from typing import Tuple


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_split__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_split__mutmut)
def split(text: str) -> Tuple[str, str]:
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


def x_split__mutmut_orig(text: str) -> Tuple[str, str]:
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


def x_split__mutmut_1(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_2(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith(None):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_3(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("XX---XX"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_4(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "XXXX", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_5(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = None
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_6(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines and lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_7(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_8(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[1].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_9(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() == "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_10(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "XX---XX":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_11(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "XXXX", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_12(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(None, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_13(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, None):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_14(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_15(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, ):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_16(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(2, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_17(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() not in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_18(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("XX---XX", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_19(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "XX...XX"):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_20(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(None), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_21(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "XX\nXX".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_22(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[2:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_23(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip(None)
    return "", text


def x_split__mutmut_24(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).rstrip("\n")
    return "", text


def x_split__mutmut_25(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(None).lstrip("\n")
    return "", text


def x_split__mutmut_26(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "XX\nXX".join(lines[i + 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_27(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i - 1:]).lstrip("\n")
    return "", text


def x_split__mutmut_28(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 2:]).lstrip("\n")
    return "", text


def x_split__mutmut_29(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("XX\nXX")
    return "", text


def x_split__mutmut_30(text: str) -> Tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter block may be ""."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]).lstrip("\n")
    return "XXXX", text

mutants_x_split__mutmut['_mutmut_orig'] = x_split__mutmut_orig # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_1'] = x_split__mutmut_1 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_2'] = x_split__mutmut_2 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_3'] = x_split__mutmut_3 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_4'] = x_split__mutmut_4 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_5'] = x_split__mutmut_5 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_6'] = x_split__mutmut_6 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_7'] = x_split__mutmut_7 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_8'] = x_split__mutmut_8 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_9'] = x_split__mutmut_9 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_10'] = x_split__mutmut_10 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_11'] = x_split__mutmut_11 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_12'] = x_split__mutmut_12 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_13'] = x_split__mutmut_13 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_14'] = x_split__mutmut_14 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_15'] = x_split__mutmut_15 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_16'] = x_split__mutmut_16 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_17'] = x_split__mutmut_17 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_18'] = x_split__mutmut_18 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_19'] = x_split__mutmut_19 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_20'] = x_split__mutmut_20 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_21'] = x_split__mutmut_21 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_22'] = x_split__mutmut_22 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_23'] = x_split__mutmut_23 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_24'] = x_split__mutmut_24 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_25'] = x_split__mutmut_25 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_26'] = x_split__mutmut_26 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_27'] = x_split__mutmut_27 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_28'] = x_split__mutmut_28 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_29'] = x_split__mutmut_29 # type: ignore # mutmut generated
mutants_x_split__mutmut['x_split__mutmut_30'] = x_split__mutmut_30 # type: ignore # mutmut generated
mutants_x__scalar__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__scalar__mutmut)
def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_orig(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_1(raw: str):
    s = None
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_2(raw: str):
    s = raw.strip()
    if s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_3(raw: str):
    s = raw.strip()
    if not s:
        return "XXXX"
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_4(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] or s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_5(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 or s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_6(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) > 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_7(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 3 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_8(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[1] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_9(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] != s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_10(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[+1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_11(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-2] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_12(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[1] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_13(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] not in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_14(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "XX'\"XX":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_15(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[2:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_16(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:+1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_17(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-2]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_18(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_19(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.upper()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_20(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low not in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_21(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("XXtrueXX", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_22(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("TRUE", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_23(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "XXyesXX", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_24(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "YES", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_25(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "XXonXX"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_26(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "ON"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_27(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return False
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_28(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low not in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_29(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("XXfalseXX", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_30(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("FALSE", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_31(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "XXnoXX", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_32(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "NO", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_33(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "XXoffXX"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_34(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "OFF"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_35(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return True
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_36(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low not in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_37(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("XXnullXX", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_38(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("NULL", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_39(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "XX~XX", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_40(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "XXnoneXX"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_41(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "NONE"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_42(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(None)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def x__scalar__mutmut_43(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(None)
    except ValueError:
        pass
    return s

mutants_x__scalar__mutmut['_mutmut_orig'] = x__scalar__mutmut_orig # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_1'] = x__scalar__mutmut_1 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_2'] = x__scalar__mutmut_2 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_3'] = x__scalar__mutmut_3 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_4'] = x__scalar__mutmut_4 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_5'] = x__scalar__mutmut_5 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_6'] = x__scalar__mutmut_6 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_7'] = x__scalar__mutmut_7 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_8'] = x__scalar__mutmut_8 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_9'] = x__scalar__mutmut_9 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_10'] = x__scalar__mutmut_10 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_11'] = x__scalar__mutmut_11 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_12'] = x__scalar__mutmut_12 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_13'] = x__scalar__mutmut_13 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_14'] = x__scalar__mutmut_14 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_15'] = x__scalar__mutmut_15 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_16'] = x__scalar__mutmut_16 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_17'] = x__scalar__mutmut_17 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_18'] = x__scalar__mutmut_18 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_19'] = x__scalar__mutmut_19 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_20'] = x__scalar__mutmut_20 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_21'] = x__scalar__mutmut_21 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_22'] = x__scalar__mutmut_22 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_23'] = x__scalar__mutmut_23 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_24'] = x__scalar__mutmut_24 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_25'] = x__scalar__mutmut_25 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_26'] = x__scalar__mutmut_26 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_27'] = x__scalar__mutmut_27 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_28'] = x__scalar__mutmut_28 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_29'] = x__scalar__mutmut_29 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_30'] = x__scalar__mutmut_30 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_31'] = x__scalar__mutmut_31 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_32'] = x__scalar__mutmut_32 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_33'] = x__scalar__mutmut_33 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_34'] = x__scalar__mutmut_34 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_35'] = x__scalar__mutmut_35 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_36'] = x__scalar__mutmut_36 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_37'] = x__scalar__mutmut_37 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_38'] = x__scalar__mutmut_38 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_39'] = x__scalar__mutmut_39 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_40'] = x__scalar__mutmut_40 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_41'] = x__scalar__mutmut_41 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_42'] = x__scalar__mutmut_42 # type: ignore # mutmut generated
mutants_x__scalar__mutmut['x__scalar__mutmut_43'] = x__scalar__mutmut_43 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__flow_list__mutmut)
def _flow_list(s: str):
    inner = s.strip()[1:-1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_orig(s: str):
    inner = s.strip()[1:-1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_1(s: str):
    inner = None
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_2(s: str):
    inner = s.strip()[2:-1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_3(s: str):
    inner = s.strip()[1:+1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_4(s: str):
    inner = s.strip()[1:-2]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_5(s: str):
    inner = s.strip()[1:-1]
    if inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(inner)]


def x__flow_list__mutmut_6(s: str):
    inner = s.strip()[1:-1]
    if not inner.strip():
        return []
    return [_scalar(None) for part in _split_commas(inner)]


def x__flow_list__mutmut_7(s: str):
    inner = s.strip()[1:-1]
    if not inner.strip():
        return []
    return [_scalar(part) for part in _split_commas(None)]

mutants_x__flow_list__mutmut['_mutmut_orig'] = x__flow_list__mutmut_orig # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_1'] = x__flow_list__mutmut_1 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_2'] = x__flow_list__mutmut_2 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_3'] = x__flow_list__mutmut_3 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_4'] = x__flow_list__mutmut_4 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_5'] = x__flow_list__mutmut_5 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_6'] = x__flow_list__mutmut_6 # type: ignore # mutmut generated
mutants_x__flow_list__mutmut['x__flow_list__mutmut_7'] = x__flow_list__mutmut_7 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x__split_commas__mutmut)
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


def x__split_commas__mutmut_orig(s: str):
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


def x__split_commas__mutmut_1(s: str):
    parts, buf, quote = None
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


def x__split_commas__mutmut_2(s: str):
    parts, buf, quote = [], "XXXX", None
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


def x__split_commas__mutmut_3(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf = ch
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


def x__split_commas__mutmut_4(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf -= ch
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


def x__split_commas__mutmut_5(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch != quote:
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


def x__split_commas__mutmut_6(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
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


def x__split_commas__mutmut_7(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch not in "'\"":
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


def x__split_commas__mutmut_8(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "XX'\"XX":
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


def x__split_commas__mutmut_9(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf = ch
            quote = ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_10(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf -= ch
            quote = ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_11(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf += ch
            quote = None
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_12(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf += ch
            quote = ch
        elif ch != ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_13(s: str):
    parts, buf, quote = [], "", None
    for ch in s:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in "'\"":
            buf += ch
            quote = ch
        elif ch == "XX,XX":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_14(s: str):
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
            parts.append(None)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_15(s: str):
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
            buf = None
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_16(s: str):
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
            buf = "XXXX"
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_17(s: str):
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
            buf = ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_18(s: str):
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
            buf -= ch
    if buf.strip():
        parts.append(buf)
    return parts


def x__split_commas__mutmut_19(s: str):
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
        parts.append(None)
    return parts

mutants_x__split_commas__mutmut['_mutmut_orig'] = x__split_commas__mutmut_orig # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_1'] = x__split_commas__mutmut_1 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_2'] = x__split_commas__mutmut_2 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_3'] = x__split_commas__mutmut_3 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_4'] = x__split_commas__mutmut_4 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_5'] = x__split_commas__mutmut_5 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_6'] = x__split_commas__mutmut_6 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_7'] = x__split_commas__mutmut_7 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_8'] = x__split_commas__mutmut_8 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_9'] = x__split_commas__mutmut_9 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_10'] = x__split_commas__mutmut_10 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_11'] = x__split_commas__mutmut_11 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_12'] = x__split_commas__mutmut_12 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_13'] = x__split_commas__mutmut_13 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_14'] = x__split_commas__mutmut_14 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_15'] = x__split_commas__mutmut_15 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_16'] = x__split_commas__mutmut_16 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_17'] = x__split_commas__mutmut_17 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_18'] = x__split_commas__mutmut_18 # type: ignore # mutmut generated
mutants_x__split_commas__mutmut['x__split_commas__mutmut_19'] = x__split_commas__mutmut_19 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_parse_block__mutmut)
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


def x_parse_block__mutmut_orig(block: str) -> dict:
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


def x_parse_block__mutmut_1(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = None
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


def x_parse_block__mutmut_2(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = ""
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


def x_parse_block__mutmut_3(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = None       # inside a | / > block scalar
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


def x_parse_block__mutmut_4(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = True       # inside a | / > block scalar
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


def x_parse_block__mutmut_5(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = None       # indent of the key line that opened it
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


def x_parse_block__mutmut_6(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 1       # indent of the key line that opened it
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


def x_parse_block__mutmut_7(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if raw.strip():
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


def x_parse_block__mutmut_8(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if not raw.strip():
            break
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


def x_parse_block__mutmut_9(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if not raw.strip():
            continue
        indent = None
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


def x_parse_block__mutmut_10(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) + len(raw.lstrip())
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


def x_parse_block__mutmut_11(block: str) -> dict:
    """Parse a frontmatter block into a dict. Best-effort, never raises."""
    meta: dict = {}
    key = None
    in_block = False       # inside a | / > block scalar
    block_indent = 0       # indent of the key line that opened it
    for raw in block.splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        line = None
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


def x_parse_block__mutmut_12(block: str) -> dict:
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
            if indent >= block_indent:
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


def x_parse_block__mutmut_13(block: str) -> dict:
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
                prev = None
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


def x_parse_block__mutmut_14(block: str) -> dict:
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
                prev = meta.get(None)
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


def x_parse_block__mutmut_15(block: str) -> dict:
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
                    meta[key] = None
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


def x_parse_block__mutmut_16(block: str) -> dict:
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
                    meta[key] = (prev + " " - line).strip()
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


def x_parse_block__mutmut_17(block: str) -> dict:
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
                    meta[key] = (prev - " " + line).strip()
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


def x_parse_block__mutmut_18(block: str) -> dict:
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
                    meta[key] = (prev + "XX XX" + line).strip()
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


def x_parse_block__mutmut_19(block: str) -> dict:
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
                break
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


def x_parse_block__mutmut_20(block: str) -> dict:
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
            in_block = None
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


def x_parse_block__mutmut_21(block: str) -> dict:
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
            in_block = True
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


def x_parse_block__mutmut_22(block: str) -> dict:
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
        if line.startswith(None):
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


def x_parse_block__mutmut_23(block: str) -> dict:
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
        if line.startswith("XX#XX"):
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


def x_parse_block__mutmut_24(block: str) -> dict:
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
            break
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


def x_parse_block__mutmut_25(block: str) -> dict:
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
        if line.startswith("- ") and line == "-":
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


def x_parse_block__mutmut_26(block: str) -> dict:
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
        if line.startswith(None) or line == "-":
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


def x_parse_block__mutmut_27(block: str) -> dict:
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
        if line.startswith("XX- XX") or line == "-":
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


def x_parse_block__mutmut_28(block: str) -> dict:
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
        if line.startswith("- ") or line != "-":
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


def x_parse_block__mutmut_29(block: str) -> dict:
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
        if line.startswith("- ") or line == "XX-XX":
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


def x_parse_block__mutmut_30(block: str) -> dict:
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
            if key is not None:
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


def x_parse_block__mutmut_31(block: str) -> dict:
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
                break
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


def x_parse_block__mutmut_32(block: str) -> dict:
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
            if isinstance(meta.get(key), list):
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


def x_parse_block__mutmut_33(block: str) -> dict:
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
                meta[key] = None
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


def x_parse_block__mutmut_34(block: str) -> dict:
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
                meta[key] = [] if meta.get(None) in ("", None) else [meta[key]]
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


def x_parse_block__mutmut_35(block: str) -> dict:
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
                meta[key] = [] if meta.get(key) not in ("", None) else [meta[key]]
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


def x_parse_block__mutmut_36(block: str) -> dict:
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
                meta[key] = [] if meta.get(key) in ("XXXX", None) else [meta[key]]
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


def x_parse_block__mutmut_37(block: str) -> dict:
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
            meta[key].append(None)
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


def x_parse_block__mutmut_38(block: str) -> dict:
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
            meta[key].append(_scalar(None))
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


def x_parse_block__mutmut_39(block: str) -> dict:
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
            meta[key].append(_scalar(line[2:].strip()))
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


def x_parse_block__mutmut_40(block: str) -> dict:
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
            break
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


def x_parse_block__mutmut_41(block: str) -> dict:
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
        if indent > 0 and ":" not in line or key is not None:
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


def x_parse_block__mutmut_42(block: str) -> dict:
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
        if indent > 0 or ":" not in line and key is not None:
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


def x_parse_block__mutmut_43(block: str) -> dict:
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
        if indent >= 0 and ":" not in line and key is not None:
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


def x_parse_block__mutmut_44(block: str) -> dict:
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
        if indent > 1 and ":" not in line and key is not None:
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


def x_parse_block__mutmut_45(block: str) -> dict:
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
        if indent > 0 and "XX:XX" not in line and key is not None:
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


def x_parse_block__mutmut_46(block: str) -> dict:
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
        if indent > 0 and ":" in line and key is not None:
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


def x_parse_block__mutmut_47(block: str) -> dict:
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
        if indent > 0 and ":" not in line and key is None:
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


def x_parse_block__mutmut_48(block: str) -> dict:
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
            prev = None
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


def x_parse_block__mutmut_49(block: str) -> dict:
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
            prev = meta.get(None)
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


def x_parse_block__mutmut_50(block: str) -> dict:
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
                meta[key] = None
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


def x_parse_block__mutmut_51(block: str) -> dict:
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
                meta[key] = (prev + " " - line).strip()
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


def x_parse_block__mutmut_52(block: str) -> dict:
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
                meta[key] = (prev - " " + line).strip()
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


def x_parse_block__mutmut_53(block: str) -> dict:
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
                meta[key] = (prev + "XX XX" + line).strip()
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


def x_parse_block__mutmut_54(block: str) -> dict:
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
            break
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


def x_parse_block__mutmut_55(block: str) -> dict:
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
        if "XX:XX" not in line:
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


def x_parse_block__mutmut_56(block: str) -> dict:
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
        if ":" in line:
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


def x_parse_block__mutmut_57(block: str) -> dict:
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
            break
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


def x_parse_block__mutmut_58(block: str) -> dict:
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
        k, _, v = None
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


def x_parse_block__mutmut_59(block: str) -> dict:
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
        k, _, v = line.partition(None)
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


def x_parse_block__mutmut_60(block: str) -> dict:
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
        k, _, v = line.rpartition(":")
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


def x_parse_block__mutmut_61(block: str) -> dict:
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
        k, _, v = line.partition("XX:XX")
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


def x_parse_block__mutmut_62(block: str) -> dict:
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
        key = None
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


def x_parse_block__mutmut_63(block: str) -> dict:
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
        v = None
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


def x_parse_block__mutmut_64(block: str) -> dict:
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
        if v and not v.startswith(("'", '"', "[")) or " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_65(block: str) -> dict:
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
        if v or not v.startswith(("'", '"', "[")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_66(block: str) -> dict:
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
        if v and v.startswith(("'", '"', "[")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_67(block: str) -> dict:
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
        if v and not v.startswith(None) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_68(block: str) -> dict:
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
        if v and not v.startswith(("XX'XX", '"', "[")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_69(block: str) -> dict:
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
        if v and not v.startswith(("'", 'XX"XX', "[")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_70(block: str) -> dict:
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
        if v and not v.startswith(("'", '"', "XX[XX")) and " #" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_71(block: str) -> dict:
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
        if v and not v.startswith(("'", '"', "[")) and "XX #XX" in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_72(block: str) -> dict:
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
        if v and not v.startswith(("'", '"', "[")) and " #" not in v:
            v = v.split(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_73(block: str) -> dict:
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
            v = None
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_74(block: str) -> dict:
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
            v = v.split(None, 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_75(block: str) -> dict:
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
            v = v.split(" #", None)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_76(block: str) -> dict:
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
            v = v.split(1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_77(block: str) -> dict:
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
            v = v.split(" #", )[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_78(block: str) -> dict:
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
            v = v.rsplit(" #", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_79(block: str) -> dict:
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
            v = v.split("XX #XX", 1)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_80(block: str) -> dict:
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
            v = v.split(" #", 2)[0].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_81(block: str) -> dict:
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
            v = v.split(" #", 1)[1].strip()
        if v.startswith("[") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_82(block: str) -> dict:
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
        if v.startswith("[") or v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_83(block: str) -> dict:
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
        if v.startswith(None) and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_84(block: str) -> dict:
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
        if v.startswith("XX[XX") and v.endswith("]"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_85(block: str) -> dict:
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
        if v.startswith("[") and v.endswith(None):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_86(block: str) -> dict:
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
        if v.startswith("[") and v.endswith("XX]XX"):
            meta[key] = _flow_list(v)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_87(block: str) -> dict:
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
            meta[key] = None
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_88(block: str) -> dict:
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
            meta[key] = _flow_list(None)
        elif v in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_89(block: str) -> dict:
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
        elif v not in ("|", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_90(block: str) -> dict:
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
        elif v in ("XX|XX", "|-", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_91(block: str) -> dict:
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
        elif v in ("|", "XX|-XX", "|+", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_92(block: str) -> dict:
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
        elif v in ("|", "|-", "XX|+XX", ">", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_93(block: str) -> dict:
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
        elif v in ("|", "|-", "|+", "XX>XX", ">-", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_94(block: str) -> dict:
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
        elif v in ("|", "|-", "|+", ">", "XX>-XX", ">+"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_95(block: str) -> dict:
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
        elif v in ("|", "|-", "|+", ">", ">-", "XX>+XX"):
            meta[key] = ""  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_96(block: str) -> dict:
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
            meta[key] = None  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_97(block: str) -> dict:
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
            meta[key] = "XXXX"  # block scalar: folded from the indented lines below
            in_block, block_indent = True, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_98(block: str) -> dict:
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
            in_block, block_indent = None
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_99(block: str) -> dict:
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
            in_block, block_indent = False, indent
        else:
            meta[key] = _scalar(v)
    return meta


def x_parse_block__mutmut_100(block: str) -> dict:
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
            meta[key] = None
    return meta


def x_parse_block__mutmut_101(block: str) -> dict:
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
            meta[key] = _scalar(None)
    return meta

mutants_x_parse_block__mutmut['_mutmut_orig'] = x_parse_block__mutmut_orig # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_1'] = x_parse_block__mutmut_1 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_2'] = x_parse_block__mutmut_2 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_3'] = x_parse_block__mutmut_3 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_4'] = x_parse_block__mutmut_4 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_5'] = x_parse_block__mutmut_5 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_6'] = x_parse_block__mutmut_6 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_7'] = x_parse_block__mutmut_7 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_8'] = x_parse_block__mutmut_8 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_9'] = x_parse_block__mutmut_9 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_10'] = x_parse_block__mutmut_10 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_11'] = x_parse_block__mutmut_11 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_12'] = x_parse_block__mutmut_12 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_13'] = x_parse_block__mutmut_13 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_14'] = x_parse_block__mutmut_14 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_15'] = x_parse_block__mutmut_15 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_16'] = x_parse_block__mutmut_16 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_17'] = x_parse_block__mutmut_17 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_18'] = x_parse_block__mutmut_18 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_19'] = x_parse_block__mutmut_19 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_20'] = x_parse_block__mutmut_20 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_21'] = x_parse_block__mutmut_21 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_22'] = x_parse_block__mutmut_22 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_23'] = x_parse_block__mutmut_23 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_24'] = x_parse_block__mutmut_24 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_25'] = x_parse_block__mutmut_25 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_26'] = x_parse_block__mutmut_26 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_27'] = x_parse_block__mutmut_27 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_28'] = x_parse_block__mutmut_28 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_29'] = x_parse_block__mutmut_29 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_30'] = x_parse_block__mutmut_30 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_31'] = x_parse_block__mutmut_31 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_32'] = x_parse_block__mutmut_32 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_33'] = x_parse_block__mutmut_33 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_34'] = x_parse_block__mutmut_34 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_35'] = x_parse_block__mutmut_35 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_36'] = x_parse_block__mutmut_36 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_37'] = x_parse_block__mutmut_37 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_38'] = x_parse_block__mutmut_38 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_39'] = x_parse_block__mutmut_39 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_40'] = x_parse_block__mutmut_40 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_41'] = x_parse_block__mutmut_41 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_42'] = x_parse_block__mutmut_42 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_43'] = x_parse_block__mutmut_43 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_44'] = x_parse_block__mutmut_44 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_45'] = x_parse_block__mutmut_45 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_46'] = x_parse_block__mutmut_46 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_47'] = x_parse_block__mutmut_47 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_48'] = x_parse_block__mutmut_48 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_49'] = x_parse_block__mutmut_49 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_50'] = x_parse_block__mutmut_50 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_51'] = x_parse_block__mutmut_51 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_52'] = x_parse_block__mutmut_52 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_53'] = x_parse_block__mutmut_53 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_54'] = x_parse_block__mutmut_54 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_55'] = x_parse_block__mutmut_55 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_56'] = x_parse_block__mutmut_56 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_57'] = x_parse_block__mutmut_57 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_58'] = x_parse_block__mutmut_58 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_59'] = x_parse_block__mutmut_59 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_60'] = x_parse_block__mutmut_60 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_61'] = x_parse_block__mutmut_61 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_62'] = x_parse_block__mutmut_62 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_63'] = x_parse_block__mutmut_63 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_64'] = x_parse_block__mutmut_64 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_65'] = x_parse_block__mutmut_65 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_66'] = x_parse_block__mutmut_66 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_67'] = x_parse_block__mutmut_67 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_68'] = x_parse_block__mutmut_68 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_69'] = x_parse_block__mutmut_69 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_70'] = x_parse_block__mutmut_70 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_71'] = x_parse_block__mutmut_71 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_72'] = x_parse_block__mutmut_72 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_73'] = x_parse_block__mutmut_73 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_74'] = x_parse_block__mutmut_74 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_75'] = x_parse_block__mutmut_75 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_76'] = x_parse_block__mutmut_76 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_77'] = x_parse_block__mutmut_77 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_78'] = x_parse_block__mutmut_78 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_79'] = x_parse_block__mutmut_79 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_80'] = x_parse_block__mutmut_80 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_81'] = x_parse_block__mutmut_81 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_82'] = x_parse_block__mutmut_82 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_83'] = x_parse_block__mutmut_83 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_84'] = x_parse_block__mutmut_84 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_85'] = x_parse_block__mutmut_85 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_86'] = x_parse_block__mutmut_86 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_87'] = x_parse_block__mutmut_87 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_88'] = x_parse_block__mutmut_88 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_89'] = x_parse_block__mutmut_89 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_90'] = x_parse_block__mutmut_90 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_91'] = x_parse_block__mutmut_91 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_92'] = x_parse_block__mutmut_92 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_93'] = x_parse_block__mutmut_93 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_94'] = x_parse_block__mutmut_94 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_95'] = x_parse_block__mutmut_95 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_96'] = x_parse_block__mutmut_96 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_97'] = x_parse_block__mutmut_97 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_98'] = x_parse_block__mutmut_98 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_99'] = x_parse_block__mutmut_99 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_100'] = x_parse_block__mutmut_100 # type: ignore # mutmut generated
mutants_x_parse_block__mutmut['x_parse_block__mutmut_101'] = x_parse_block__mutmut_101 # type: ignore # mutmut generated
mutants_x_parse__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_parse__mutmut)
def parse(text: str) -> Tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(text)
    return (parse_block(block) if block else {}), body


def x_parse__mutmut_orig(text: str) -> Tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(text)
    return (parse_block(block) if block else {}), body


def x_parse__mutmut_1(text: str) -> Tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = None
    return (parse_block(block) if block else {}), body


def x_parse__mutmut_2(text: str) -> Tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(None)
    return (parse_block(block) if block else {}), body


def x_parse__mutmut_3(text: str) -> Tuple[dict, str]:
    """Parse a SKILL.md's text -> (frontmatter dict, markdown body)."""
    block, body = split(text)
    return (parse_block(None) if block else {}), body

mutants_x_parse__mutmut['_mutmut_orig'] = x_parse__mutmut_orig # type: ignore # mutmut generated
mutants_x_parse__mutmut['x_parse__mutmut_1'] = x_parse__mutmut_1 # type: ignore # mutmut generated
mutants_x_parse__mutmut['x_parse__mutmut_2'] = x_parse__mutmut_2 # type: ignore # mutmut generated
mutants_x_parse__mutmut['x_parse__mutmut_3'] = x_parse__mutmut_3 # type: ignore # mutmut generated
mutants_x_dump__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_dump__mutmut)
def dump(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_orig(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_1(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = None
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_2(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["XX---XX"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_3(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(None)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_4(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" / k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_5(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("XX%s:XX" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_6(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%S:" % k)
            for item in v:
                lines.append("  - %s" % item)
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


def x_dump__mutmut_7(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append(None)
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


def x_dump__mutmut_8(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" / item)
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


def x_dump__mutmut_9(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("XX  - %sXX" % item)
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


def x_dump__mutmut_10(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %S" % item)
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


def x_dump__mutmut_11(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append(None)
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_12(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" / (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_13(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("XX%s: %sXX" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_14(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%S: %S" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_15(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "XXtrueXX" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_16(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "TRUE" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_17(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "XXfalseXX"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_18(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "FALSE"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_19(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is not None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_20(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append(None)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_21(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" / k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_22(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("XX%s:XX" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_23(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%S:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_24(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = None
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_25(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(None)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_26(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s and s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_27(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if "XX:XX" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_28(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" not in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_29(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s == s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_30(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = None
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_31(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' / s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_32(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = 'XX"%s"XX' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_33(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%S"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_34(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace(None, '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_35(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', None)
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_36(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_37(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', )
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_38(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('XX"XX', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_39(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', 'XX\\"XX')
            lines.append("%s: %s" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_40(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append(None)
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_41(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" / (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_42(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("XX%s: %sXX" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_43(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%S: %S" % (k, s))
    lines.append("---")
    return "\n".join(lines)


def x_dump__mutmut_44(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append(None)
    return "\n".join(lines)


def x_dump__mutmut_45(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
        elif isinstance(v, bool):
            lines.append("%s: %s" % (k, "true" if v else "false"))
        elif v is None:
            lines.append("%s:" % k)
        else:
            s = str(v)
            if ":" in s or s != s.strip():
                s = '"%s"' % s.replace('"', '\\"')
            lines.append("%s: %s" % (k, s))
    lines.append("XX---XX")
    return "\n".join(lines)


def x_dump__mutmut_46(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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
    return "\n".join(None)


def x_dump__mutmut_47(meta: dict) -> str:
    """Serialize a dict back to a frontmatter block (--- fenced)."""
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append("%s:" % k)
            for item in v:
                lines.append("  - %s" % item)
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
    return "XX\nXX".join(lines)

mutants_x_dump__mutmut['_mutmut_orig'] = x_dump__mutmut_orig # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_1'] = x_dump__mutmut_1 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_2'] = x_dump__mutmut_2 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_3'] = x_dump__mutmut_3 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_4'] = x_dump__mutmut_4 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_5'] = x_dump__mutmut_5 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_6'] = x_dump__mutmut_6 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_7'] = x_dump__mutmut_7 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_8'] = x_dump__mutmut_8 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_9'] = x_dump__mutmut_9 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_10'] = x_dump__mutmut_10 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_11'] = x_dump__mutmut_11 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_12'] = x_dump__mutmut_12 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_13'] = x_dump__mutmut_13 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_14'] = x_dump__mutmut_14 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_15'] = x_dump__mutmut_15 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_16'] = x_dump__mutmut_16 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_17'] = x_dump__mutmut_17 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_18'] = x_dump__mutmut_18 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_19'] = x_dump__mutmut_19 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_20'] = x_dump__mutmut_20 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_21'] = x_dump__mutmut_21 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_22'] = x_dump__mutmut_22 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_23'] = x_dump__mutmut_23 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_24'] = x_dump__mutmut_24 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_25'] = x_dump__mutmut_25 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_26'] = x_dump__mutmut_26 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_27'] = x_dump__mutmut_27 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_28'] = x_dump__mutmut_28 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_29'] = x_dump__mutmut_29 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_30'] = x_dump__mutmut_30 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_31'] = x_dump__mutmut_31 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_32'] = x_dump__mutmut_32 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_33'] = x_dump__mutmut_33 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_34'] = x_dump__mutmut_34 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_35'] = x_dump__mutmut_35 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_36'] = x_dump__mutmut_36 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_37'] = x_dump__mutmut_37 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_38'] = x_dump__mutmut_38 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_39'] = x_dump__mutmut_39 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_40'] = x_dump__mutmut_40 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_41'] = x_dump__mutmut_41 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_42'] = x_dump__mutmut_42 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_43'] = x_dump__mutmut_43 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_44'] = x_dump__mutmut_44 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_45'] = x_dump__mutmut_45 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_46'] = x_dump__mutmut_46 # type: ignore # mutmut generated
mutants_x_dump__mutmut['x_dump__mutmut_47'] = x_dump__mutmut_47 # type: ignore # mutmut generated
