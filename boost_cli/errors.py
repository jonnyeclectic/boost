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


class NotUTF8Error(BoostError):
    """A file the *user* owns holds bytes that are not UTF-8.

    Raised by `util.read_user_text` in place of the bare
    ``UnicodeDecodeError`` — a ``ValueError`` that no ``except OSError``
    stops — which turned one latin-1 byte in ``~/.claude/CLAUDE.md`` into a
    crash report and exit 70 from install, uninstall and verify alike. Boost
    edits a context file only as text it can write back byte for byte, so
    the remedy is the user's: re-save the file as UTF-8.
    """

    def __init__(self, path, err: UnicodeDecodeError):
        self.path = path
        byte = err.object[err.start:err.start + 1]
        super().__init__(
            "%s is not UTF-8 (byte 0x%s at offset %d), so boost cannot edit "
            "it without changing your bytes" % (path, byte.hex(), err.start),
            hint="save the file as UTF-8, then run the command again",
            wrap=True)
