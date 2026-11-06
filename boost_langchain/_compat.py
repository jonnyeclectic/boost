# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Import-time compatibility checks for the package ``__init__``.

The rule itself lives in :mod:`boost_cli.core.langchain_compat`: this module
sits inside ``boost_langchain``, so importing it runs the package ``__init__``
— which raises the install hint without langchain — and it can never be the
base-venv-testable home it once claimed to be.
"""
from __future__ import annotations

from boost_cli.core.langchain_compat import supported_langchain_core

__all__ = ["supported_langchain_core"]
