"""Small shared utilities: time, hashing, versions, skill quality scoring."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

IGNORED = {".git", "__pycache__", ".DS_Store"}


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_now_iso__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_now_iso__mutmut)
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def x_now_iso__mutmut_orig() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def x_now_iso__mutmut_1() -> str:
    return datetime.now(timezone.utc).strftime(None)


def x_now_iso__mutmut_2() -> str:
    return datetime.now(None).strftime("%Y-%m-%dT%H:%M:%SZ")


def x_now_iso__mutmut_3() -> str:
    return datetime.now(timezone.utc).strftime("XX%Y-%m-%dT%H:%M:%SZXX")


def x_now_iso__mutmut_4() -> str:
    return datetime.now(timezone.utc).strftime("%y-%m-%dt%h:%m:%sz")


def x_now_iso__mutmut_5() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%M-%DT%H:%M:%SZ")

mutants_x_now_iso__mutmut['_mutmut_orig'] = x_now_iso__mutmut_orig # type: ignore # mutmut generated
mutants_x_now_iso__mutmut['x_now_iso__mutmut_1'] = x_now_iso__mutmut_1 # type: ignore # mutmut generated
mutants_x_now_iso__mutmut['x_now_iso__mutmut_2'] = x_now_iso__mutmut_2 # type: ignore # mutmut generated
mutants_x_now_iso__mutmut['x_now_iso__mutmut_3'] = x_now_iso__mutmut_3 # type: ignore # mutmut generated
mutants_x_now_iso__mutmut['x_now_iso__mutmut_4'] = x_now_iso__mutmut_4 # type: ignore # mutmut generated
mutants_x_now_iso__mutmut['x_now_iso__mutmut_5'] = x_now_iso__mutmut_5 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_rel_time__mutmut)
def rel_time(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_orig(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_1(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = None
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_2(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_3(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(None, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_4(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, None).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_5(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime("%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_6(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, ).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_7(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "XX%Y-%m-%dT%H:%M:%SZXX").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_8(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%y-%m-%dt%h:%m:%sz").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_9(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%M-%DT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_10(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso and "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_11(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "XX?XX"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_12(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = None
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_13(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) + then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_14(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(None) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_15(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((61, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_16(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 2, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_17(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "XXsXX"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_18(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "S"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_19(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3601, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_20(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 61, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_21(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "XXmXX"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_22(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "M"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_23(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86401, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_24(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3601, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_25(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "XXhXX"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_26(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "H"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_27(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604801, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_28(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86401, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_29(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "XXdXX")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_30(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "D")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_31(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs <= limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_32(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" / (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_33(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "XX%d%s agoXX" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_34(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%D%S AGO" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_35(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(None, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_36(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, None), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_37(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_38(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, ), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_39(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(2, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_40(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs / size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_41(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs <= 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_42(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 / 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_43(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604801 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_44(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 9:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_45(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" / (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_46(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "XX%dw agoXX" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_47(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%DW AGO" % (secs // 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_48(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs / 604800)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_49(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604801)
    return then.strftime("%Y-%m-%d")


def x_rel_time__mutmut_50(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime(None)


def x_rel_time__mutmut_51(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("XX%Y-%m-%dXX")


def x_rel_time__mutmut_52(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%y-%m-%d")


def x_rel_time__mutmut_53(iso: str) -> str:
    """'2026-07-16T01:00:00Z' -> '3h ago' (best effort)."""
    try:
        then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return iso or "?"
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    for limit, size, unit in ((60, 1, "s"), (3600, 60, "m"),
                              (86400, 3600, "h"), (604800, 86400, "d")):
        if secs < limit:
            return "%d%s ago" % (max(1, secs // size), unit)
    if secs < 604800 * 8:
        return "%dw ago" % (secs // 604800)
    return then.strftime("%Y-%M-%D")

mutants_x_rel_time__mutmut['_mutmut_orig'] = x_rel_time__mutmut_orig # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_1'] = x_rel_time__mutmut_1 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_2'] = x_rel_time__mutmut_2 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_3'] = x_rel_time__mutmut_3 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_4'] = x_rel_time__mutmut_4 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_5'] = x_rel_time__mutmut_5 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_6'] = x_rel_time__mutmut_6 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_7'] = x_rel_time__mutmut_7 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_8'] = x_rel_time__mutmut_8 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_9'] = x_rel_time__mutmut_9 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_10'] = x_rel_time__mutmut_10 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_11'] = x_rel_time__mutmut_11 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_12'] = x_rel_time__mutmut_12 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_13'] = x_rel_time__mutmut_13 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_14'] = x_rel_time__mutmut_14 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_15'] = x_rel_time__mutmut_15 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_16'] = x_rel_time__mutmut_16 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_17'] = x_rel_time__mutmut_17 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_18'] = x_rel_time__mutmut_18 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_19'] = x_rel_time__mutmut_19 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_20'] = x_rel_time__mutmut_20 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_21'] = x_rel_time__mutmut_21 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_22'] = x_rel_time__mutmut_22 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_23'] = x_rel_time__mutmut_23 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_24'] = x_rel_time__mutmut_24 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_25'] = x_rel_time__mutmut_25 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_26'] = x_rel_time__mutmut_26 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_27'] = x_rel_time__mutmut_27 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_28'] = x_rel_time__mutmut_28 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_29'] = x_rel_time__mutmut_29 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_30'] = x_rel_time__mutmut_30 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_31'] = x_rel_time__mutmut_31 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_32'] = x_rel_time__mutmut_32 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_33'] = x_rel_time__mutmut_33 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_34'] = x_rel_time__mutmut_34 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_35'] = x_rel_time__mutmut_35 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_36'] = x_rel_time__mutmut_36 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_37'] = x_rel_time__mutmut_37 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_38'] = x_rel_time__mutmut_38 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_39'] = x_rel_time__mutmut_39 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_40'] = x_rel_time__mutmut_40 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_41'] = x_rel_time__mutmut_41 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_42'] = x_rel_time__mutmut_42 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_43'] = x_rel_time__mutmut_43 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_44'] = x_rel_time__mutmut_44 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_45'] = x_rel_time__mutmut_45 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_46'] = x_rel_time__mutmut_46 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_47'] = x_rel_time__mutmut_47 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_48'] = x_rel_time__mutmut_48 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_49'] = x_rel_time__mutmut_49 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_50'] = x_rel_time__mutmut_50 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_51'] = x_rel_time__mutmut_51 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_52'] = x_rel_time__mutmut_52 # type: ignore # mutmut generated
mutants_x_rel_time__mutmut['x_rel_time__mutmut_53'] = x_rel_time__mutmut_53 # type: ignore # mutmut generated
mutants_x_human_size__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_human_size__mutmut)
def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_orig(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_1(n: int) -> str:
    for unit in ("XXBXX", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_2(n: int) -> str:
    for unit in ("b", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_3(n: int) -> str:
    for unit in ("B", "XXKBXX", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_4(n: int) -> str:
    for unit in ("B", "kb", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_5(n: int) -> str:
    for unit in ("B", "KB", "XXMBXX", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_6(n: int) -> str:
    for unit in ("B", "KB", "mb", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_7(n: int) -> str:
    for unit in ("B", "KB", "MB", "XXGBXX"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_8(n: int) -> str:
    for unit in ("B", "KB", "MB", "gb"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_9(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 and unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_10(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n <= 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_11(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1025 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_12(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit != "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_13(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "XXGBXX":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_14(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "gb":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_15(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") / (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_16(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("XX%d%sXX" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_17(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%D%S" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_18(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit != "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_19(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "XXBXX" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_20(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "b" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_21(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "XX%.1f%sXX") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_22(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1F%S") % (n, unit)
        n /= 1024.0
    return str(n)


def x_human_size__mutmut_23(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n = 1024.0
    return str(n)


def x_human_size__mutmut_24(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n *= 1024.0
    return str(n)


def x_human_size__mutmut_25(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1025.0
    return str(n)


def x_human_size__mutmut_26(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d%s" if unit == "B" else "%.1f%s") % (n, unit)
        n /= 1024.0
    return str(None)

mutants_x_human_size__mutmut['_mutmut_orig'] = x_human_size__mutmut_orig # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_1'] = x_human_size__mutmut_1 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_2'] = x_human_size__mutmut_2 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_3'] = x_human_size__mutmut_3 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_4'] = x_human_size__mutmut_4 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_5'] = x_human_size__mutmut_5 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_6'] = x_human_size__mutmut_6 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_7'] = x_human_size__mutmut_7 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_8'] = x_human_size__mutmut_8 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_9'] = x_human_size__mutmut_9 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_10'] = x_human_size__mutmut_10 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_11'] = x_human_size__mutmut_11 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_12'] = x_human_size__mutmut_12 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_13'] = x_human_size__mutmut_13 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_14'] = x_human_size__mutmut_14 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_15'] = x_human_size__mutmut_15 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_16'] = x_human_size__mutmut_16 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_17'] = x_human_size__mutmut_17 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_18'] = x_human_size__mutmut_18 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_19'] = x_human_size__mutmut_19 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_20'] = x_human_size__mutmut_20 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_21'] = x_human_size__mutmut_21 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_22'] = x_human_size__mutmut_22 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_23'] = x_human_size__mutmut_23 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_24'] = x_human_size__mutmut_24 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_25'] = x_human_size__mutmut_25 # type: ignore # mutmut generated
mutants_x_human_size__mutmut['x_human_size__mutmut_26'] = x_human_size__mutmut_26 # type: ignore # mutmut generated
mutants_x_slugify__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_slugify__mutmut)
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_orig(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_1(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") and "skill"


def x_slugify__mutmut_2(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip(None) or "skill"


def x_slugify__mutmut_3(name: str) -> str:
    return re.sub(None, "-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_4(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", None, name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_5(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", None).strip("-") or "skill"


def x_slugify__mutmut_6(name: str) -> str:
    return re.sub("-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_7(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_8(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", ).strip("-") or "skill"


def x_slugify__mutmut_9(name: str) -> str:
    return re.sub(r"XX[^a-z0-9-]+XX", "-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_10(name: str) -> str:
    return re.sub(r"[^A-Z0-9-]+", "-", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_11(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "XX-XX", name.strip().lower()).strip("-") or "skill"


def x_slugify__mutmut_12(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().upper()).strip("-") or "skill"


def x_slugify__mutmut_13(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("XX-XX") or "skill"


def x_slugify__mutmut_14(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "XXskillXX"


def x_slugify__mutmut_15(name: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-") or "SKILL"

mutants_x_slugify__mutmut['_mutmut_orig'] = x_slugify__mutmut_orig # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_1'] = x_slugify__mutmut_1 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_2'] = x_slugify__mutmut_2 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_3'] = x_slugify__mutmut_3 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_4'] = x_slugify__mutmut_4 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_5'] = x_slugify__mutmut_5 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_6'] = x_slugify__mutmut_6 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_7'] = x_slugify__mutmut_7 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_8'] = x_slugify__mutmut_8 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_9'] = x_slugify__mutmut_9 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_10'] = x_slugify__mutmut_10 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_11'] = x_slugify__mutmut_11 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_12'] = x_slugify__mutmut_12 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_13'] = x_slugify__mutmut_13 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_14'] = x_slugify__mutmut_14 # type: ignore # mutmut generated
mutants_x_slugify__mutmut['x_slugify__mutmut_15'] = x_slugify__mutmut_15 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_sha256_dir__mutmut)
def sha256_dir(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_orig(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_1(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = None
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_2(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = None
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_3(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(None)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_4(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = None
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_5(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        None
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_6(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob(None)
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_7(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("XX*XX")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_8(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() or not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_9(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_10(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(None)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_11(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part not in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_12(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(None)
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_13(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(None).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_14(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(None)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_15(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(None)
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_16(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"XX\0XX")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_17(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(None)
        h.update(b"\0")
    return h.hexdigest()


def x_sha256_dir__mutmut_18(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(None)
    return h.hexdigest()


def x_sha256_dir__mutmut_19(path: Path) -> str:
    """Deterministic content hash of a directory tree (paths + bytes)."""
    h = hashlib.sha256()
    root = Path(path)
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in IGNORED for part in p.parts)
    )
    for f in files:
        h.update(str(f.relative_to(root)).encode())
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"XX\0XX")
    return h.hexdigest()

mutants_x_sha256_dir__mutmut['_mutmut_orig'] = x_sha256_dir__mutmut_orig # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_1'] = x_sha256_dir__mutmut_1 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_2'] = x_sha256_dir__mutmut_2 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_3'] = x_sha256_dir__mutmut_3 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_4'] = x_sha256_dir__mutmut_4 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_5'] = x_sha256_dir__mutmut_5 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_6'] = x_sha256_dir__mutmut_6 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_7'] = x_sha256_dir__mutmut_7 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_8'] = x_sha256_dir__mutmut_8 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_9'] = x_sha256_dir__mutmut_9 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_10'] = x_sha256_dir__mutmut_10 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_11'] = x_sha256_dir__mutmut_11 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_12'] = x_sha256_dir__mutmut_12 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_13'] = x_sha256_dir__mutmut_13 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_14'] = x_sha256_dir__mutmut_14 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_15'] = x_sha256_dir__mutmut_15 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_16'] = x_sha256_dir__mutmut_16 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_17'] = x_sha256_dir__mutmut_17 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_18'] = x_sha256_dir__mutmut_18 # type: ignore # mutmut generated
mutants_x_sha256_dir__mutmut['x_sha256_dir__mutmut_19'] = x_sha256_dir__mutmut_19 # type: ignore # mutmut generated
mutants_x_dir_size__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_dir_size__mutmut)
def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def x_dir_size__mutmut_orig(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file())


def x_dir_size__mutmut_1(path: Path) -> int:
    return sum(None)


def x_dir_size__mutmut_2(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob(None) if p.is_file())


def x_dir_size__mutmut_3(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(None).rglob("*") if p.is_file())


def x_dir_size__mutmut_4(path: Path) -> int:
    return sum(p.stat().st_size for p in Path(path).rglob("XX*XX") if p.is_file())

mutants_x_dir_size__mutmut['_mutmut_orig'] = x_dir_size__mutmut_orig # type: ignore # mutmut generated
mutants_x_dir_size__mutmut['x_dir_size__mutmut_1'] = x_dir_size__mutmut_1 # type: ignore # mutmut generated
mutants_x_dir_size__mutmut['x_dir_size__mutmut_2'] = x_dir_size__mutmut_2 # type: ignore # mutmut generated
mutants_x_dir_size__mutmut['x_dir_size__mutmut_3'] = x_dir_size__mutmut_3 # type: ignore # mutmut generated
mutants_x_dir_size__mutmut['x_dir_size__mutmut_4'] = x_dir_size__mutmut_4 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_semver_tuple__mutmut)
def semver_tuple(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_orig(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_1(v: str):
    parts = None
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_2(v: str):
    parts = re.findall(None, str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_3(v: str):
    parts = re.findall(r"\d+", None)[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_4(v: str):
    parts = re.findall(str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_5(v: str):
    parts = re.findall(r"\d+", )[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_6(v: str):
    parts = re.findall(r"XX\d+XX", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_7(v: str):
    parts = re.findall(r"\d+", str(None))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_8(v: str):
    parts = re.findall(r"\d+", str(v and "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_9(v: str):
    parts = re.findall(r"\d+", str(v or "XX0XX"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_10(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:4]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_11(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) - (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_12(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(None) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_13(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(None) for p in parts) + (0,) * (3 - len(parts))


def x_semver_tuple__mutmut_14(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) / (3 - len(parts))


def x_semver_tuple__mutmut_15(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (1,) * (3 - len(parts))


def x_semver_tuple__mutmut_16(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 + len(parts))


def x_semver_tuple__mutmut_17(v: str):
    parts = re.findall(r"\d+", str(v or "0"))[:3]
    return tuple(int(p) for p in parts) + (0,) * (4 - len(parts))

mutants_x_semver_tuple__mutmut['_mutmut_orig'] = x_semver_tuple__mutmut_orig # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_1'] = x_semver_tuple__mutmut_1 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_2'] = x_semver_tuple__mutmut_2 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_3'] = x_semver_tuple__mutmut_3 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_4'] = x_semver_tuple__mutmut_4 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_5'] = x_semver_tuple__mutmut_5 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_6'] = x_semver_tuple__mutmut_6 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_7'] = x_semver_tuple__mutmut_7 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_8'] = x_semver_tuple__mutmut_8 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_9'] = x_semver_tuple__mutmut_9 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_10'] = x_semver_tuple__mutmut_10 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_11'] = x_semver_tuple__mutmut_11 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_12'] = x_semver_tuple__mutmut_12 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_13'] = x_semver_tuple__mutmut_13 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_14'] = x_semver_tuple__mutmut_14 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_15'] = x_semver_tuple__mutmut_15 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_16'] = x_semver_tuple__mutmut_16 # type: ignore # mutmut generated
mutants_x_semver_tuple__mutmut['x_semver_tuple__mutmut_17'] = x_semver_tuple__mutmut_17 # type: ignore # mutmut generated
mutants_x_semver_gt__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_semver_gt__mutmut)
def semver_gt(a: str, b: str) -> bool:
    return semver_tuple(a) > semver_tuple(b)


def x_semver_gt__mutmut_orig(a: str, b: str) -> bool:
    return semver_tuple(a) > semver_tuple(b)


def x_semver_gt__mutmut_1(a: str, b: str) -> bool:
    return semver_tuple(None) > semver_tuple(b)


def x_semver_gt__mutmut_2(a: str, b: str) -> bool:
    return semver_tuple(a) >= semver_tuple(b)


def x_semver_gt__mutmut_3(a: str, b: str) -> bool:
    return semver_tuple(a) > semver_tuple(None)

mutants_x_semver_gt__mutmut['_mutmut_orig'] = x_semver_gt__mutmut_orig # type: ignore # mutmut generated
mutants_x_semver_gt__mutmut['x_semver_gt__mutmut_1'] = x_semver_gt__mutmut_1 # type: ignore # mutmut generated
mutants_x_semver_gt__mutmut['x_semver_gt__mutmut_2'] = x_semver_gt__mutmut_2 # type: ignore # mutmut generated
mutants_x_semver_gt__mutmut['x_semver_gt__mutmut_3'] = x_semver_gt__mutmut_3 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_score_skill__mutmut)
def score_skill(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_orig(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_1(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = None
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_2(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) * "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_3(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(None) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_4(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "XXSKILL.mdXX"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_5(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "skill.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_6(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.MD"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_7(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = None
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_8(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_9(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 1, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_10(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["XXmissing SKILL.mdXX"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_11(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing skill.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_12(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["MISSING SKILL.MD"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_13(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = None
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_14(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding=None, errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_15(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors=None)
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_16(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_17(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", )
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_18(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="XXutf-8XX", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_19(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="UTF-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_20(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="XXreplaceXX")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_21(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="REPLACE")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_22(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 1, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_23(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" / e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_24(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["XXunreadable SKILL.md: %sXX" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_25(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable skill.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_26(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["UNREADABLE SKILL.MD: %S" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_27(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = None
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_28(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(None)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_29(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = None  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_30(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 21  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_31(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get(None):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_32(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("XXnameXX"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_33(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("NAME"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_34(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score = 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_35(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score -= 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_36(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 11
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_37(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append(None)
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_38(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("XXfrontmatter missing `name`XX")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_39(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("FRONTMATTER MISSING `NAME`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_40(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = None
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_41(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(None)
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_42(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") and "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_43(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get(None) or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_44(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("XXdescriptionXX") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_45(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("DESCRIPTION") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_46(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "XXXX")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_47(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score = 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_48(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score -= 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_49(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 11
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_50(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) > 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_51(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 41:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_52(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score = 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_53(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score -= 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_54(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 6
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_55(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append(None)
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_56(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("XXdescription is thin (<40 chars)XX")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_57(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("DESCRIPTION IS THIN (<40 CHARS)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_58(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append(None)
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_59(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("XXfrontmatter missing `description`XX")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_60(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("FRONTMATTER MISSING `DESCRIPTION`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_61(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get(None):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_62(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("XXversionXX"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_63(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("VERSION"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_64(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score = 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_65(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score -= 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_66(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 11
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_67(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_68(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(None, str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_69(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", None):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_70(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_71(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", ):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_72(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"XX^\d+\.\d+(\.\d+)?XX", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_73(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(None)):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_74(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["XXversionXX"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_75(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["VERSION"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_76(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score = 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_77(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score += 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_78(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 6
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_79(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append(None)
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_80(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("XXversion is not semver-ishXX")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_81(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("VERSION IS NOT SEMVER-ISH")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_82(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append(None)

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_83(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("XXfrontmatter missing `version`XX")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_84(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("FRONTMATTER MISSING `VERSION`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_85(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) > 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_86(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 201:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_87(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score = 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_88(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score -= 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_89(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 16
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_90(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append(None)
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_91(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("XXbody is short (<200 chars)XX")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_92(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("BODY IS SHORT (<200 CHARS)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_93(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(None, body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_94(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", None, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_95(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, None):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_96(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_97(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_98(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, ):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_99(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"XX^#{1,3} XX", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_100(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score = 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_101(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score -= 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_102(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 11
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_103(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append(None)
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_104(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("XXno markdown headings in bodyXX")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_105(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("NO MARKDOWN HEADINGS IN BODY")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_106(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) and re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_107(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body and re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_108(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "XX```XX" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_109(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" not in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_110(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(None, body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_111(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", None, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_112(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, None) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_113(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_114(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_115(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, ) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_116(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"XX^\d+\. XX", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_117(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(None, body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_118(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", None, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_119(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, None):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_120(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_121(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_122(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, ):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_123(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"XX^- XX", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_124(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score = 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_125(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score -= 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_126(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 11  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_127(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append(None)
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_128(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("XXno examples, steps, or code blocksXX")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_129(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("NO EXAMPLES, STEPS, OR CODE BLOCKS")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_130(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_131(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(None, body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_132(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", None):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_133(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_134(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", ):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_135(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"XX\bTODO\b|\bFIXME\bXX", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_136(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\btodo\b|\bfixme\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_137(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score = 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_138(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score -= 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_139(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 6
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_140(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append(None)
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_141(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("XXcontains TODO/FIXMEXX")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_142(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains todo/fixme")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_143(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("CONTAINS TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_144(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") and (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_145(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get(None) or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_146(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("XXlicenseXX") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_147(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("LICENSE") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_148(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) * "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_149(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(None) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_150(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "XXLICENSEXX").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_151(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "license").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_152(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score = 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_153(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score -= 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_154(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 6
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_155(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = None
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_156(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(None).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_157(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED or p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_158(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_159(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name == "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_160(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "XXSKILL.mdXX"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_161(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "skill.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_162(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.MD"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_163(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score = 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_164(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score -= 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_165(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 6  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_166(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) >= 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_167(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48001:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_168(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score = 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_169(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score += 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_170(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 11
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_171(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append(None)
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_172(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("XXvery large SKILL.md (>48KB) — consider splittingXX")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_173(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large skill.md (>48kb) — consider splitting")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_174(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("VERY LARGE SKILL.MD (>48KB) — CONSIDER SPLITTING")
    return max(0, min(100, score)), notes


def x_score_skill__mutmut_175(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(None, min(100, score)), notes


def x_score_skill__mutmut_176(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, None), notes


def x_score_skill__mutmut_177(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(min(100, score)), notes


def x_score_skill__mutmut_178(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, ), notes


def x_score_skill__mutmut_179(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(1, min(100, score)), notes


def x_score_skill__mutmut_180(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(None, score)), notes


def x_score_skill__mutmut_181(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, None)), notes


def x_score_skill__mutmut_182(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(score)), notes


def x_score_skill__mutmut_183(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(100, )), notes


def x_score_skill__mutmut_184(skill_dir: Path) -> Tuple[int, List[str]]:
    """Heuristic quality score 0-100 for a skill directory, with notes.

    Shared by `boost install` (display), `boost lint`, and `boost test`.
    """
    from . import frontmatter

    skill_md = Path(skill_dir) / "SKILL.md"
    notes: List[str] = []
    if not skill_md.exists():
        return 0, ["missing SKILL.md"]
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, ["unreadable SKILL.md: %s" % e]
    meta, body = frontmatter.parse(text)
    score = 20  # exists and parses

    if meta.get("name"):
        score += 10
    else:
        notes.append("frontmatter missing `name`")
    desc = str(meta.get("description") or "")
    if desc:
        score += 10
        if len(desc) >= 40:
            score += 5
        else:
            notes.append("description is thin (<40 chars)")
    else:
        notes.append("frontmatter missing `description`")
    if meta.get("version"):
        score += 10
        if not re.match(r"^\d+\.\d+(\.\d+)?", str(meta["version"])):
            score -= 5
            notes.append("version is not semver-ish")
    else:
        notes.append("frontmatter missing `version`")

    if len(body.strip()) >= 200:
        score += 15
    else:
        notes.append("body is short (<200 chars)")
    if re.search(r"^#{1,3} ", body, re.M):
        score += 10
    else:
        notes.append("no markdown headings in body")
    if "```" in body or re.search(r"^\d+\. ", body, re.M) or re.search(r"^- ", body, re.M):
        score += 10  # concrete steps or examples
    else:
        notes.append("no examples, steps, or code blocks")
    if not re.search(r"\bTODO\b|\bFIXME\b", body):
        score += 5
    else:
        notes.append("contains TODO/FIXME")
    if meta.get("license") or (Path(skill_dir) / "LICENSE").exists():
        score += 5
    extras = [p for p in Path(skill_dir).iterdir()
              if p.name not in IGNORED and p.name != "SKILL.md"]
    if extras:
        score += 5  # ships supporting references/scripts
    if len(text) > 48_000:
        score -= 10
        notes.append("very large SKILL.md (>48KB) — consider splitting")
    return max(0, min(101, score)), notes

mutants_x_score_skill__mutmut['_mutmut_orig'] = x_score_skill__mutmut_orig # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_1'] = x_score_skill__mutmut_1 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_2'] = x_score_skill__mutmut_2 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_3'] = x_score_skill__mutmut_3 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_4'] = x_score_skill__mutmut_4 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_5'] = x_score_skill__mutmut_5 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_6'] = x_score_skill__mutmut_6 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_7'] = x_score_skill__mutmut_7 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_8'] = x_score_skill__mutmut_8 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_9'] = x_score_skill__mutmut_9 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_10'] = x_score_skill__mutmut_10 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_11'] = x_score_skill__mutmut_11 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_12'] = x_score_skill__mutmut_12 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_13'] = x_score_skill__mutmut_13 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_14'] = x_score_skill__mutmut_14 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_15'] = x_score_skill__mutmut_15 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_16'] = x_score_skill__mutmut_16 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_17'] = x_score_skill__mutmut_17 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_18'] = x_score_skill__mutmut_18 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_19'] = x_score_skill__mutmut_19 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_20'] = x_score_skill__mutmut_20 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_21'] = x_score_skill__mutmut_21 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_22'] = x_score_skill__mutmut_22 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_23'] = x_score_skill__mutmut_23 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_24'] = x_score_skill__mutmut_24 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_25'] = x_score_skill__mutmut_25 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_26'] = x_score_skill__mutmut_26 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_27'] = x_score_skill__mutmut_27 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_28'] = x_score_skill__mutmut_28 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_29'] = x_score_skill__mutmut_29 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_30'] = x_score_skill__mutmut_30 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_31'] = x_score_skill__mutmut_31 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_32'] = x_score_skill__mutmut_32 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_33'] = x_score_skill__mutmut_33 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_34'] = x_score_skill__mutmut_34 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_35'] = x_score_skill__mutmut_35 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_36'] = x_score_skill__mutmut_36 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_37'] = x_score_skill__mutmut_37 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_38'] = x_score_skill__mutmut_38 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_39'] = x_score_skill__mutmut_39 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_40'] = x_score_skill__mutmut_40 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_41'] = x_score_skill__mutmut_41 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_42'] = x_score_skill__mutmut_42 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_43'] = x_score_skill__mutmut_43 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_44'] = x_score_skill__mutmut_44 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_45'] = x_score_skill__mutmut_45 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_46'] = x_score_skill__mutmut_46 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_47'] = x_score_skill__mutmut_47 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_48'] = x_score_skill__mutmut_48 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_49'] = x_score_skill__mutmut_49 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_50'] = x_score_skill__mutmut_50 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_51'] = x_score_skill__mutmut_51 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_52'] = x_score_skill__mutmut_52 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_53'] = x_score_skill__mutmut_53 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_54'] = x_score_skill__mutmut_54 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_55'] = x_score_skill__mutmut_55 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_56'] = x_score_skill__mutmut_56 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_57'] = x_score_skill__mutmut_57 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_58'] = x_score_skill__mutmut_58 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_59'] = x_score_skill__mutmut_59 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_60'] = x_score_skill__mutmut_60 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_61'] = x_score_skill__mutmut_61 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_62'] = x_score_skill__mutmut_62 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_63'] = x_score_skill__mutmut_63 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_64'] = x_score_skill__mutmut_64 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_65'] = x_score_skill__mutmut_65 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_66'] = x_score_skill__mutmut_66 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_67'] = x_score_skill__mutmut_67 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_68'] = x_score_skill__mutmut_68 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_69'] = x_score_skill__mutmut_69 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_70'] = x_score_skill__mutmut_70 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_71'] = x_score_skill__mutmut_71 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_72'] = x_score_skill__mutmut_72 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_73'] = x_score_skill__mutmut_73 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_74'] = x_score_skill__mutmut_74 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_75'] = x_score_skill__mutmut_75 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_76'] = x_score_skill__mutmut_76 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_77'] = x_score_skill__mutmut_77 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_78'] = x_score_skill__mutmut_78 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_79'] = x_score_skill__mutmut_79 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_80'] = x_score_skill__mutmut_80 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_81'] = x_score_skill__mutmut_81 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_82'] = x_score_skill__mutmut_82 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_83'] = x_score_skill__mutmut_83 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_84'] = x_score_skill__mutmut_84 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_85'] = x_score_skill__mutmut_85 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_86'] = x_score_skill__mutmut_86 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_87'] = x_score_skill__mutmut_87 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_88'] = x_score_skill__mutmut_88 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_89'] = x_score_skill__mutmut_89 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_90'] = x_score_skill__mutmut_90 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_91'] = x_score_skill__mutmut_91 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_92'] = x_score_skill__mutmut_92 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_93'] = x_score_skill__mutmut_93 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_94'] = x_score_skill__mutmut_94 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_95'] = x_score_skill__mutmut_95 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_96'] = x_score_skill__mutmut_96 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_97'] = x_score_skill__mutmut_97 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_98'] = x_score_skill__mutmut_98 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_99'] = x_score_skill__mutmut_99 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_100'] = x_score_skill__mutmut_100 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_101'] = x_score_skill__mutmut_101 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_102'] = x_score_skill__mutmut_102 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_103'] = x_score_skill__mutmut_103 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_104'] = x_score_skill__mutmut_104 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_105'] = x_score_skill__mutmut_105 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_106'] = x_score_skill__mutmut_106 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_107'] = x_score_skill__mutmut_107 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_108'] = x_score_skill__mutmut_108 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_109'] = x_score_skill__mutmut_109 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_110'] = x_score_skill__mutmut_110 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_111'] = x_score_skill__mutmut_111 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_112'] = x_score_skill__mutmut_112 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_113'] = x_score_skill__mutmut_113 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_114'] = x_score_skill__mutmut_114 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_115'] = x_score_skill__mutmut_115 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_116'] = x_score_skill__mutmut_116 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_117'] = x_score_skill__mutmut_117 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_118'] = x_score_skill__mutmut_118 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_119'] = x_score_skill__mutmut_119 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_120'] = x_score_skill__mutmut_120 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_121'] = x_score_skill__mutmut_121 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_122'] = x_score_skill__mutmut_122 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_123'] = x_score_skill__mutmut_123 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_124'] = x_score_skill__mutmut_124 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_125'] = x_score_skill__mutmut_125 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_126'] = x_score_skill__mutmut_126 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_127'] = x_score_skill__mutmut_127 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_128'] = x_score_skill__mutmut_128 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_129'] = x_score_skill__mutmut_129 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_130'] = x_score_skill__mutmut_130 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_131'] = x_score_skill__mutmut_131 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_132'] = x_score_skill__mutmut_132 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_133'] = x_score_skill__mutmut_133 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_134'] = x_score_skill__mutmut_134 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_135'] = x_score_skill__mutmut_135 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_136'] = x_score_skill__mutmut_136 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_137'] = x_score_skill__mutmut_137 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_138'] = x_score_skill__mutmut_138 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_139'] = x_score_skill__mutmut_139 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_140'] = x_score_skill__mutmut_140 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_141'] = x_score_skill__mutmut_141 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_142'] = x_score_skill__mutmut_142 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_143'] = x_score_skill__mutmut_143 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_144'] = x_score_skill__mutmut_144 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_145'] = x_score_skill__mutmut_145 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_146'] = x_score_skill__mutmut_146 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_147'] = x_score_skill__mutmut_147 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_148'] = x_score_skill__mutmut_148 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_149'] = x_score_skill__mutmut_149 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_150'] = x_score_skill__mutmut_150 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_151'] = x_score_skill__mutmut_151 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_152'] = x_score_skill__mutmut_152 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_153'] = x_score_skill__mutmut_153 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_154'] = x_score_skill__mutmut_154 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_155'] = x_score_skill__mutmut_155 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_156'] = x_score_skill__mutmut_156 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_157'] = x_score_skill__mutmut_157 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_158'] = x_score_skill__mutmut_158 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_159'] = x_score_skill__mutmut_159 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_160'] = x_score_skill__mutmut_160 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_161'] = x_score_skill__mutmut_161 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_162'] = x_score_skill__mutmut_162 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_163'] = x_score_skill__mutmut_163 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_164'] = x_score_skill__mutmut_164 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_165'] = x_score_skill__mutmut_165 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_166'] = x_score_skill__mutmut_166 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_167'] = x_score_skill__mutmut_167 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_168'] = x_score_skill__mutmut_168 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_169'] = x_score_skill__mutmut_169 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_170'] = x_score_skill__mutmut_170 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_171'] = x_score_skill__mutmut_171 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_172'] = x_score_skill__mutmut_172 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_173'] = x_score_skill__mutmut_173 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_174'] = x_score_skill__mutmut_174 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_175'] = x_score_skill__mutmut_175 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_176'] = x_score_skill__mutmut_176 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_177'] = x_score_skill__mutmut_177 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_178'] = x_score_skill__mutmut_178 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_179'] = x_score_skill__mutmut_179 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_180'] = x_score_skill__mutmut_180 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_181'] = x_score_skill__mutmut_181 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_182'] = x_score_skill__mutmut_182 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_183'] = x_score_skill__mutmut_183 # type: ignore # mutmut generated
mutants_x_score_skill__mutmut['x_score_skill__mutmut_184'] = x_score_skill__mutmut_184 # type: ignore # mutmut generated
