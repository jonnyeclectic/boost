# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Embedding says how far along it is, and keeps what it embedded.

`boost reindex --dense` is the longest thing boost does — a full catalogue is
tens of thousands of distinct chunks at roughly a second each — and it ran under
one fixed label, "embedding chunks into the dense store", for hours. That is
indistinguishable from a hang, and it was reported as one.

Worse, every row landed in a single transaction that committed only after the
last one, so interrupting a three-hour build threw away everything it had paid
to embed. Both halves are pinned here: progress is reported with real numbers
from the first batch, and rows are durable long before the end.

Re-running after an interrupt stays correct because `build` deletes each
changed tap's rows before re-inserting them, so a partial store is replaced
rather than doubled — asserted below, since that is what makes periodic commits
safe rather than a duplication bug.
"""
from __future__ import annotations

import hashlib
import sqlite3

import pytest

from boost_cli.core import dense, embed, rag, util


def _vec_loadable() -> bool:
    con = sqlite3.connect(":memory:")
    try:
        import sqlite_vec
        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.enable_load_extension(False)
        con.execute("create virtual table t using vec0(embedding float[4])")
        return True
    except Exception:
        return False
    finally:
        con.close()


# Scoped to the classes that need a vector store, not the module: the label
# and duration tests are pure and must still run where the extra is absent —
# which is every default install.
needs_vec = pytest.mark.skipif(
    not _vec_loadable(), reason="sqlite-vec extension not loadable here")


def _toy_embed(texts, input_type="document"):
    """A distinct vector per distinct text, which is now load-bearing.

    The store keeps one vector row per DISTINCT embedding, so an embedder
    keying on `len(text) % 7` — every fixture name is four characters — would
    make a 200-entry build store a single vector and call `_store_vector`
    once. `TestDurability` counts those calls to interrupt part-way through.
    """
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([float(h[0]), 1.0, float(h[1]), 0.5])
    return out


def _entries(n):
    return [{"name": "s%03d" % i, "tap": "acme/skills", "kind": "skill",
             "skill_md": "skills/s%03d/SKILL.md" % i} for i in range(n)]


@pytest.fixture()
def dense_env(sandbox, monkeypatch):
    monkeypatch.setattr(embed, "embed", _toy_embed)
    monkeypatch.setattr(embed, "provider", lambda: "openai")
    monkeypatch.setattr(embed, "model", lambda: "toy-4")
    monkeypatch.setattr(embed, "dimension", lambda: 4)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"acme/skills": "/x"})
    monkeypatch.setattr(rag, "_tap_commits", lambda: {"acme__skills": "c1"})
    # One distinct body per entry, so the distinct-text count is the entry
    # count and the progress totals are predictable.
    monkeypatch.setattr(dense, "read_body", lambda e, tp=None: e["name"])
    return monkeypatch


@needs_vec
class TestProgressReporting:
    def test_it_reports_the_total_before_the_first_request(self, dense_env):
        seen = []
        dense.build(_entries(5), on_progress=lambda d, t: seen.append((d, t)))
        # The size of the job has to be knowable up front; inferring it from
        # how long it has already taken is what users were left doing.
        assert seen[0] == (0, 5)

    def test_it_reaches_the_total(self, dense_env):
        seen = []
        dense.build(_entries(5), on_progress=lambda d, t: seen.append((d, t)))
        assert seen[-1] == (5, 5)

    def test_progress_never_goes_backwards(self, dense_env):
        seen = []
        dense.build(_entries(300), on_progress=lambda d, t: seen.append(d))
        assert seen == sorted(seen)

    def test_it_advances_even_when_a_batch_is_rejected(self, dense_env):
        # A provider that rejects a batch used to leave the count frozen for
        # that stretch, which reads as the stall it is not.
        dense_env.setattr(embed, "embed", lambda texts, input_type="document": [])
        seen = []
        dense.build(_entries(300), on_progress=lambda d, t: seen.append((d, t)))
        assert seen[0] == (0, 300)
        assert seen[-1] == (300, 300)

    def test_no_callback_is_fine(self, dense_env):
        # The MCP server and every non-interactive caller pass nothing.
        assert dense.build(_entries(3)) is not None

    def test_the_total_counts_distinct_texts_not_rows(self, dense_env):
        # Registries mirror each other, so identical text is embedded once —
        # a progress total that counted rows would over-report the work.
        dense_env.setattr(dense, "read_body", lambda e, tp=None: "same body")
        seen = []
        dense.build(_entries(10), on_progress=lambda d, t: seen.append((d, t)))
        assert seen[0] == (0, 1)


@needs_vec
class TestDurability:
    def _rows(self):
        con = sqlite3.connect(str(dense.db_path()))
        try:
            return con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        finally:
            con.close()

    def test_rows_survive_an_interrupt_mid_build(self, dense_env):
        # The failure this prevents: hours of embedding discarded because the
        # single transaction never reached its commit.
        boom = {"n": 0}
        real = dense._store_vector

        def flaky(con, rowid, blob):
            boom["n"] += 1
            if boom["n"] > dense._COMMIT_EVERY + 10:
                raise KeyboardInterrupt("user pressed ctrl-c")
            return real(con, rowid, blob)

        dense_env.setattr(dense, "_store_vector", flaky)
        dense_env.setattr(dense, "_COMMIT_EVERY", 20)
        with pytest.raises(KeyboardInterrupt):
            dense.build(_entries(200))
        assert self._rows() > 0

    def test_a_rerun_replaces_a_partial_store_rather_than_doubling_it(
            self, dense_env):
        dense.build(_entries(20))
        first = self._rows()
        dense.build(_entries(20), force=True)
        # `build` deletes each changed tap's rows before re-inserting, which is
        # what makes committing part-way through safe.
        assert self._rows() == first


class TestProgressLabel:
    """What the user actually reads while it runs. No dense backend needed."""

    class _Spin:
        label = ""

    def test_it_names_the_count_and_percentage(self):
        from boost_cli.commands import discovery
        sp = self._Spin()
        discovery._embed_progress(sp)(12480, 62331)
        assert "12,480/62,331 chunks" in sp.label
        assert "20%" in sp.label

    def test_it_draws_a_determinate_bar(self):
        # The bar answers "is this moving?" before any digit is read, which is
        # the question a fixed spinner left unanswerable for hours.
        from boost_cli.commands import discovery
        sp = self._Spin()
        report = discovery._embed_progress(sp)
        report(0, 100)
        assert "░" in sp.label and "▓" not in sp.label
        report(50, 100)
        assert sp.label.count("▓") == 8      # half of a 16-wide bar
        report(100, 100)
        assert "░" not in sp.label

    def test_no_estimate_before_there_is_anything_to_estimate_from(self):
        # Until a batch has finished there is no rate; inventing one would be
        # a guess dressed as a measurement.
        from boost_cli.commands import discovery
        sp = self._Spin()
        discovery._embed_progress(sp)(0, 62331)
        assert "left" not in sp.label

    def test_a_missing_spinner_is_a_no_op(self):
        from boost_cli.commands import discovery
        discovery._embed_progress(None)(5, 10)      # must not raise

    def test_zero_total_is_a_no_op(self):
        from boost_cli.commands import discovery
        sp = self._Spin()
        discovery._embed_progress(sp)(0, 0)
        assert sp.label == ""


class TestHumanDuration:
    """The estimate's wording: coarse, because the number is extrapolated."""

    @pytest.mark.parametrize("seconds,want", [
        (0, "0s"), (45, "45s"), (60, "1m"), (600, "10m"),
        (3600, "1h"), (7500, "2h 5m"),
    ])
    def test_it_reads_as_a_person_would_say_it(self, seconds, want):
        assert util.human_duration(seconds) == want

    def test_negative_input_does_not_produce_nonsense(self):
        # The estimate is (total - done) * rate; a clock that jumps backwards
        # must not print "-3s left".
        assert util.human_duration(-5) == "0s"
