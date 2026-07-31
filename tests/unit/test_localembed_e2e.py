"""End-to-end: the real ONNX runtime against the real pinned BGE weights.

Scope, stated precisely, because the obvious justification for this file is
wrong. ``test_localembed.py`` runs against a stub that "mimics onnxruntime", and
the tempting claim is that a stub cannot catch a pooling mistake. It can:
``TestClsPooling::test_it_takes_the_first_token_not_the_mean`` feeds
``cls_pool`` a hand-built tensor and pins CLS against the mean directly, in
microseconds and with no download. That test is *better* at that job than
anything here. This was checked rather than assumed — swapping ``cls_pool`` to
mean pooling reddens the stubbed suite immediately.

What no stub can do is run the actual graph. A fake session returns whatever
shape the test declared, so everything downstream of "does onnxruntime accept
these 133 MB and give back what we expect" is asserted against our own
assumptions. Three things only real weights prove:

* **Integration.** The pinned export loads under the installed onnxruntime, the
  input names we feed match the ones it declares, and the result is 384 finite
  unit-norm floats. Every ORT upgrade re-tests this for free.
* **Absolute similarity.** Ordering alone is a weak signal — measured here, mean
  pooling *preserves* the near/far ordering while changing every vector. Pinning
  the values catches a model or revision swap that ordering sails through.
* **Padding.** Batching a short text beside a long one exercises a real
  attention mask; a fake session has none to get wrong.

Reference values come from the measurement published on the roadmap card when
the ONNX path shipped (#354), against these exact pinned weights.

Opt-in by design — ``BOOST_ONNX_E2E=1``. Without it this skips, so neither a
normal ``make test`` nor the mutation gate's in-``mutants/`` run is charged a
133 MB download. CI sets it in the one job that caches the weights.
"""
from __future__ import annotations

import math
import os

import pytest

from boost_cli.core import localembed

pytestmark = [
    pytest.mark.onnx,
    pytest.mark.skipif(os.environ.get("BOOST_ONNX_E2E") != "1",
                       reason="real-weights E2E; set BOOST_ONNX_E2E=1"),
]

# Sentences from the published measurement. The first two are near-paraphrases
# in different vocabulary — no content word in common — which is the case BM25
# cannot serve and the dense tier exists for. The third is the distractor that
# BM25 actually returned for this query before the dense tier existed.
Q_SLOW = "making my application faster"
NEAR = "application performance tuning"
FAR = "quantum computing circuit simulation"

# Published against these weights: near 0.7691, far 0.5338. The tolerance is
# wide enough to absorb onnxruntime/platform float differences and narrow enough
# that a pooling change cannot hide inside it — CLS and mean pooling separate by
# far more than this on BGE.
NEAR_SIM, FAR_SIM, TOL = 0.7691, 0.5338, 0.03


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


@pytest.fixture(scope="module")
def vectors():
    """Encode the three probe sentences once, with real weights.

    ``importorskip`` rather than a plain import so a machine that opted in but
    lacks the extra skips cleanly instead of erroring. ``ensure_model`` is what
    downloads and verifies; a None return means the fetch failed, which is a
    skip and not a failure — this test is about the model contract, not about
    HuggingFace's uptime.
    """
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    if localembed.ensure_model() is None:
        pytest.skip("pinned weights unavailable (download failed)")
    out = localembed.encode([Q_SLOW, NEAR, FAR])
    assert out is not None, "encode returned None with the backend present"
    return dict(zip((Q_SLOW, NEAR, FAR), out))


class TestModelContract:
    def test_dimension_matches_what_embed_advertises(self, vectors):
        # Asserted against `embed.LOCAL_DIM` rather than a literal 384: that
        # constant is what dense.py stores and rebuilds on, so the bug worth
        # catching is the two disagreeing, not either one's value.
        from boost_cli.core import embed
        assert embed.LOCAL_DIM == 384          # the pinned export's hidden size
        for text, vec in vectors.items():
            assert len(vec) == embed.LOCAL_DIM, text

    def test_vectors_are_l2_normalised(self, vectors):
        # Cosine similarity downstream is a plain dot product, which is only
        # correct on unit vectors.
        for text, vec in vectors.items():
            assert math.isclose(math.sqrt(_dot(vec, vec)), 1.0, abs_tol=1e-5), text

    def test_every_component_is_finite(self, vectors):
        # A NaN would poison the whole index and compare False against
        # everything, so KNN would return an arbitrary neighbour set.
        for text, vec in vectors.items():
            assert all(math.isfinite(x) for x in vec), text


class TestSemanticContract:
    """The part a stub cannot fake, and the reason the tier exists."""

    def test_paraphrase_outranks_the_distractor(self, vectors):
        # A floor, not a precision instrument: measured against a mean-pooled
        # build, this ordering SURVIVES — so it does not catch pooling and is
        # not claimed to. What it does catch is a model that loaded but is not
        # discriminating at all, which is the failure that makes the whole
        # keyless tier pointless while every shape assertion still passes.
        near = _dot(vectors[Q_SLOW], vectors[NEAR])
        far = _dot(vectors[Q_SLOW], vectors[FAR])
        assert near > far, (
            "'%s' must rank nearer to '%s' than to '%s' (got %.4f vs %.4f)"
            % (Q_SLOW, NEAR, FAR, near, far))
        assert near - far > 0.10, (
            "margin collapsed to %.4f — the model is loading but not "
            "discriminating; suspect pooling or a wrong input name"
            % (near - far))

    def test_similarities_match_the_published_measurement(self, vectors):
        # This is the one that earns the download. Verified against a mean-pooled
        # build: ordering held, these values moved, and this test was what
        # noticed. Same for a deliberate MODEL_REV repin, where sha256 passes by
        # construction and only the numbers reveal that vectors changed.
        near = _dot(vectors[Q_SLOW], vectors[NEAR])
        far = _dot(vectors[Q_SLOW], vectors[FAR])
        assert math.isclose(near, NEAR_SIM, abs_tol=TOL), (
            "near-pair similarity %.4f drifted from the published %.4f"
            % (near, NEAR_SIM))
        assert math.isclose(far, FAR_SIM, abs_tol=TOL), (
            "far-pair similarity %.4f drifted from the published %.4f"
            % (far, FAR_SIM))

    def test_a_sentence_is_maximally_similar_to_itself(self, vectors):
        # Sanity floor: a degenerate model that maps everything to one point
        # would pass the ordering test by accident but fails here against the
        # off-diagonal.
        self_sim = _dot(vectors[NEAR], vectors[NEAR])
        cross = _dot(vectors[NEAR], vectors[FAR])
        assert math.isclose(self_sim, 1.0, abs_tol=1e-5)
        assert self_sim > cross + 0.10


class TestDeterminism:
    def test_encoding_twice_gives_identical_vectors(self, vectors):
        # The store is a cache keyed on content, so a non-deterministic encoder
        # would make every reindex produce a different index for the same input.
        again = localembed.encode([NEAR])
        assert again is not None
        for a, b in zip(again[0], vectors[NEAR]):
            assert math.isclose(a, b, abs_tol=1e-6)

    def test_batching_does_not_change_a_vector(self, vectors):
        # Padding to the longest row in a batch must not leak into the CLS
        # token. Encoding alone vs. alongside a much longer sentence is the
        # cheapest way to catch an attention-mask mistake.
        alone = localembed.encode([NEAR])
        batched = localembed.encode([NEAR, FAR * 20])
        assert alone is not None and batched is not None
        for a, b in zip(alone[0], batched[0]):
            assert math.isclose(a, b, abs_tol=1e-4), (
                "padding changed the vector — suspect the attention mask")
