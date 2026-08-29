# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The browser demo's index must stay a faithful projection of the real one.

`docs/demo.html` claims to run "the same BM25 ranking `boost search` runs". That
claim is the whole point of the demo, so it needs a test: a scorer that drifts
from `rag._bm25` turns the demo into a misrepresentation of the product rather
than a preview of it.

Parity of the *ranking* is checked by running both implementations over the same
queries (see the PR); what these tests pin is the contract that makes parity
possible — the index carries the exact scoring parameters, and the shape the JS
expects.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO = ROOT / "docs" / "demo-index.json"
PAGE = ROOT / "docs" / "demo.html"


@pytest.fixture(scope="module")
def index():
    if not DEMO.exists():
        pytest.skip("demo index not built (scripts/build_demo_index.py)")
    return json.loads(DEMO.read_text(encoding="utf-8"))


class TestScoringParameters:
    """The demo must score with the CLI's constants, not its own."""

    def test_k1_and_b_match_the_engine(self, index):
        from boost_cli.core import rag
        assert index["k1"] == rag.K1
        assert index["b"] == rag.B

    def test_avg_len_is_present_and_positive(self, index):
        # BM25 divides by it; a missing or zero value silently flattens length
        # normalisation and every ranking with it.
        assert index["avg_len"] > 0


class TestShape:
    """The JS reads these fields by name; renaming one breaks the demo silently."""

    def test_docs_carry_what_a_result_row_shows(self, index):
        d = index["docs"][0]
        assert set(d) == {"n", "t", "k", "l", "s"}

    def test_postings_are_parallel_arrays(self, index):
        term, (ids, tfs) = next(iter(index["postings"].items()))
        assert isinstance(term, str)
        assert len(ids) == len(tfs), "doc ids and term freqs must pair up"
        assert all(isinstance(i, int) for i in ids)

    def test_every_posting_points_at_a_real_doc(self, index):
        n = len(index["docs"])
        for term, (ids, _tfs) in index["postings"].items():
            assert all(0 <= i < n for i in ids), "dangling doc id under %r" % term

    def test_document_lengths_are_usable(self, index):
        # `dl or 1` in both implementations, so 0 is tolerated — negatives are not.
        assert all(d["l"] >= 0 for d in index["docs"])


class TestHonesty:
    """The page must not imply it demos the semantic engine."""

    def test_the_page_says_it_is_the_keyword_engine(self):
        html = PAGE.read_text(encoding="utf-8")
        assert "not</b> the semantic engine" in html or "not the semantic engine" in html

    def test_the_page_names_the_measured_gap(self):
        # Concrete numbers from the published eval, so the limitation is
        # quantified rather than hand-waved.
        html = PAGE.read_text(encoding="utf-8")
        assert "0.340" in html and "0.440" in html

    def test_the_page_ships_no_external_dependency(self):
        # Every docs page is self-contained; the demo must not be the first to
        # reach for a CDN, which is also why it cannot embed queries.
        html = PAGE.read_text(encoding="utf-8")
        for marker in ("https://cdn", "http://cdn", "unpkg.com", "jsdelivr"):
            assert marker not in html


class TestGeneratorIsReproducible:
    def test_the_builder_refuses_without_an_index(self, tmp_path):
        # Emitting an empty demo index would ship a search box that finds
        # nothing, which is worse than failing the build.
        #
        # The environment is INHERITED and then overridden, not built from
        # scratch: a hand-made {PATH, HOME} dict kills Python on Windows before
        # it runs a line ("_Py_HashRandomization_Init: failed to get random
        # numbers"), because it drops SystemRoot. The test then "passes" its
        # returncode check for entirely the wrong reason.
        env = dict(os.environ, BOOST_HOME=str(tmp_path))
        proc = subprocess.run([sys.executable, "scripts/build_demo_index.py"],
                              cwd=str(ROOT), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        assert proc.returncode == 1
        assert "no BM25 index" in proc.stderr or "no postings" in proc.stderr
