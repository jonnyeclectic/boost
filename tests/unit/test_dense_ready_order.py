"""dense.ready() must stat before it imports.

On a machine with no vector store — the common BM25-only install — ready()
used to import sqlite_vec (which drags in numpy, ~120 ms measured) just to
answer False. The cheap ``db_path().exists()`` check has to come first; the
backend and provider probes only run once there is a store worth opening.
"""
from __future__ import annotations

import pytest

from boost_cli.core import dense, embed, paths


class TestReadyShortCircuit:
    def test_missing_store_answers_false_without_importing(self, sandbox,
                                                           monkeypatch):
        monkeypatch.setattr(
            dense, "_load",
            lambda: pytest.fail("no store on disk — backend must not import"))
        monkeypatch.setattr(
            embed, "available",
            lambda: pytest.fail("no store on disk — provider must not probe"))
        assert not dense.db_path().exists()
        assert dense.ready() is False

    def test_present_store_still_requires_the_backend(self, sandbox,
                                                      monkeypatch):
        paths.ensure_dirs()
        dense.db_path().write_bytes(b"")
        monkeypatch.setattr(dense, "_load", lambda: None)
        assert dense.ready() is False

    def test_present_store_still_requires_a_provider(self, sandbox,
                                                     monkeypatch):
        paths.ensure_dirs()
        dense.db_path().write_bytes(b"")
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "available", lambda: False)
        assert dense.ready() is False
