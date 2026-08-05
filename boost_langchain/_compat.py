"""Import-time compatibility checks, importable without langchain installed.

Deliberately dependency-free: the package __init__ needs this BEFORE it can
trust the langchain imports, and the unit suite needs to test the rule from
the base venv, where importing boost_langchain itself raises the extra hint.
"""
from __future__ import annotations


def supported_langchain_core(version: str) -> bool:
    """True when ``version`` satisfies the [langchain] extra's pin (>=1,<2).

    The floor is not pedantry: langchain-core 0.3 — exactly what the [eval]
    extra pins — satisfies every import this package makes (BaseRetriever,
    BaseLoader and the message types all exist there) and then fails subtly
    at runtime, because ``BaseMessage.text`` is a method in 0.3 and a
    property from 1.0. The cap matters for the same reason in reverse: the
    BaseRetriever contract moves on majors.
    """
    try:
        major = int(version.partition(".")[0])
    except ValueError:
        return False
    return 1 <= major < 2
