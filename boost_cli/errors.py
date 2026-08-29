# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""User-facing errors."""
from __future__ import annotations


class BoostError(Exception):
    """An expected, user-facing failure. Printed without a traceback."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
