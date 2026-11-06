# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The [langchain] extra's version rule, importable without langchain.

It lives here, not in ``boost_langchain``, because nothing inside that package
can be imported without langchain: ``import boost_langchain._compat`` runs the
package ``__init__`` first, and that raises the install hint on a base venv.
``boost_langchain/_compat.py`` used to hold this and say it was importable
there; its test passed only when an earlier test had left the module in
``sys.modules``. Here the rule is reachable from the base venv by an ordinary
import, and ``boost_langchain`` re-exports it.
"""
from __future__ import annotations


def supported_langchain_core(version: str) -> bool:
    """True when ``version`` satisfies the [langchain] extra's pin (>=1,<2).

    The floor is not pedantry: langchain-core 0.3 — exactly what the [eval]
    extra pins — satisfies every import boost_langchain makes (BaseRetriever,
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
