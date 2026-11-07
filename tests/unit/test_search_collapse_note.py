# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`search --collapse-near-duplicates` says when it had no dense index to read.

`rag.retrieve_any` collapses only when `dense.ready()`, so without a store the
flag was dropped and the output matched a run without it. The note names the
flag and `dense.fix_hint`'s remedy, and stays silent when the flag was not
given or the collapse could run.
"""
from __future__ import annotations

import types

from boost_cli.commands import discovery
from boost_cli.core import dense


def _args(flag):
    return types.SimpleNamespace(collapse_dupes=flag)


def test_no_flag_no_note_and_no_dense_probe(monkeypatch):
    def boom():
        raise AssertionError("dense.ready() asked without the flag")
    monkeypatch.setattr(dense, "ready", boom)
    assert discovery._collapse_ignored(_args(False)) is None


def test_a_ready_store_runs_the_collapse_so_no_note(monkeypatch):
    monkeypatch.setattr(dense, "ready", lambda: True)
    assert discovery._collapse_ignored(_args(True)) is None


def test_no_store_names_the_flag_and_the_doctor_remedy(monkeypatch):
    st = {"ready": False, "reason": "no-store"}
    monkeypatch.setattr(dense, "ready", lambda: False)
    monkeypatch.setattr(dense, "status", lambda **_kw: st)
    note = discovery._collapse_ignored(_args(True))
    assert note == ("--collapse-near-duplicates needs the dense index, so "
                    "this search ignored it — %s"
                    % dense.fix_hint("no-store", st))


def test_the_note_replaces_the_semantic_hint(monkeypatch, capsys):
    monkeypatch.setattr(discovery, "_semantic_hint",
                        lambda engine: "semantic search is off — x")
    discovery._hint_semantic_search("BM25 full-content", "the note")
    out = capsys.readouterr().out
    assert "the note" in out
    assert "semantic search is off" not in out
    discovery._hint_semantic_search("BM25 full-content")
    assert "semantic search is off — x" in capsys.readouterr().out
