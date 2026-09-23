# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""User-facing errors."""
from __future__ import annotations


class BoostError(Exception):
    """An expected, user-facing failure. Printed without a traceback.

    ``wrap`` says the message is prose and may be folded to the pane. It is
    opt-in for the reason `output.warn` and friends take ``wrap`` per call
    site: most messages are a label and its data (`no such directory:
    /very/long/...`), and folding those moves the path off the label that
    names it. A message that is a sentence — a refusal a user reads before
    deciding what to do — passes ``wrap=True``. The hint always folds.
    """

    def __init__(self, message: str, hint: str | None = None,
                 wrap: bool = False):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.wrap = wrap
