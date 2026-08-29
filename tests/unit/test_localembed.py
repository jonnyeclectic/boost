# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core.localembed's integrity, caching and pooling logic.

``test_embed_local.py`` stubs the backend at the ``core.embed`` seam, which
proves the provider chain but leaves this module's own logic untested — and it
is the part handling untrusted bytes off the network, so it is exactly the part
that should not be taken on faith. Everything here runs without onnxruntime
installed: the download, verification, cache and normalisation paths need no
inference.

The property under test throughout is that **nothing unverified is ever used**.
A truncated download, a hash mismatch, a tampered cache and a failed rename all
have to end with no usable file and a clean degrade, because the alternative is
loading whatever arrived off the wire into an ONNX runtime.
"""
from __future__ import annotations

import hashlib

import pytest

from boost_cli.core import localembed

pytestmark = pytest.mark.usefixtures("sandbox")

BODY = b"the pinned bytes"
DIGEST = hashlib.sha256(BODY).hexdigest()


@pytest.fixture(autouse=True)
def _reset():
    localembed.reset()
    yield
    localembed.reset()


class TestVerification:
    def test_a_matching_file_verifies(self, tmp_path):
        p = tmp_path / "f"
        p.write_bytes(BODY)
        assert localembed._verified(p, len(BODY), DIGEST) is True

    def test_a_missing_file_does_not_verify(self, tmp_path):
        assert localembed._verified(tmp_path / "absent", len(BODY), DIGEST) is False

    def test_a_truncated_file_does_not_verify(self, tmp_path):
        # The common failure: an interrupted download. Caught on length alone,
        # before hashing 133 MB.
        p = tmp_path / "f"
        p.write_bytes(BODY[:-1])
        assert localembed._verified(p, len(BODY), DIGEST) is False

    def test_right_length_wrong_bytes_does_not_verify(self, tmp_path):
        # THE ONE THAT MATTERS: same size, different content. Only the hash
        # catches this, which is why the length check cannot be the whole test.
        p = tmp_path / "f"
        p.write_bytes(b"x" * len(BODY))
        assert localembed._verified(p, len(BODY), DIGEST) is False

    def test_a_wrong_digest_does_not_verify(self, tmp_path):
        p = tmp_path / "f"
        p.write_bytes(BODY)
        assert localembed._verified(p, len(BODY), "0" * 64) is False

    def test_a_directory_in_the_way_does_not_raise(self, tmp_path):
        d = tmp_path / "f"
        d.mkdir()
        assert localembed._verified(d, len(BODY), DIGEST) is False


class TestFetch:
    @staticmethod
    def _serving(monkeypatch, payload):
        """Stub nethttp.urlopen with a context manager yielding `payload`."""
        from boost_cli.core import nethttp

        class Resp:
            def __init__(self):
                self._data = payload
            def read(self, n=-1):
                if not self._data:
                    return b""
                if n is None or n < 0:
                    out, self._data = self._data, b""
                    return out
                out, self._data = self._data[:n], self._data[n:]
                return out
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        monkeypatch.setattr(nethttp, "urlopen", lambda *_a, **_k: Resp())

    def test_a_good_download_lands_at_the_destination(self, tmp_path, monkeypatch):
        self._serving(monkeypatch, BODY)
        dest = tmp_path / "sub" / "f"
        assert localembed._fetch("f", dest, len(BODY), DIGEST) is True
        assert dest.read_bytes() == BODY

    def test_a_corrupt_download_is_not_kept(self, tmp_path, monkeypatch):
        # The whole point of verifying before the rename: a body that does not
        # match the pin must leave nothing usable behind.
        self._serving(monkeypatch, b"tampered payload")
        dest = tmp_path / "f"
        assert localembed._fetch("f", dest, len(BODY), DIGEST) is False
        assert not dest.exists()

    def test_no_part_file_survives_a_failure(self, tmp_path, monkeypatch):
        # A leftover .part would be re-verified and rejected next run, but it
        # would also silently consume disk on every retry.
        self._serving(monkeypatch, b"tampered payload")
        dest = tmp_path / "f"
        localembed._fetch("f", dest, len(BODY), DIGEST)
        assert list(tmp_path.glob("*.part")) == []

    def test_a_network_failure_degrades(self, tmp_path, monkeypatch):
        from boost_cli.core import nethttp

        def boom(*_a, **_k):
            raise OSError("no route to host")

        monkeypatch.setattr(nethttp, "urlopen", boom)
        dest = tmp_path / "f"
        assert localembed._fetch("f", dest, len(BODY), DIGEST) is False
        assert not dest.exists()

    def test_it_requests_the_pinned_revision(self, tmp_path, monkeypatch):
        # A moving `main` would silently change every vector in every index,
        # and nothing would rebuild because the model NAME would not change.
        seen = []
        from boost_cli.core import nethttp

        class Resp:
            def read(self, n=-1):
                return b""
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        def spy(url, *_a, **_k):
            seen.append(url)
            return Resp()

        monkeypatch.setattr(nethttp, "urlopen", spy)
        localembed._fetch("tokenizer.json", tmp_path / "f", 1, DIGEST)
        assert seen and localembed.MODEL_REV in seen[0]
        assert "/resolve/main/" not in seen[0]


class TestEnsureModel:
    def test_already_cached_files_are_not_refetched(self, monkeypatch):
        # First use downloads 133 MB; every use after that must not.
        root = localembed.model_dir()
        for rel in localembed.FILES:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(BODY)
        monkeypatch.setattr(localembed, "_verified", lambda *_a: True)
        monkeypatch.setattr(localembed, "_fetch", lambda *_a: (_ for _ in ()).throw(
            AssertionError("must not refetch a verified file")))
        assert localembed.ensure_model() == root

    def test_a_failed_fetch_returns_none(self, monkeypatch):
        monkeypatch.setattr(localembed, "_verified", lambda *_a: False)
        monkeypatch.setattr(localembed, "_fetch", lambda *_a: False)
        assert localembed.ensure_model() is None

    def test_a_tampered_cache_is_refetched(self, monkeypatch):
        # Verification runs on every load, not just after download, so a file
        # modified in the cache is replaced rather than trusted.
        calls = []
        monkeypatch.setattr(localembed, "_verified", lambda *_a: False)
        monkeypatch.setattr(localembed, "_fetch",
                            lambda *a: (calls.append(a[0]), True)[1])
        assert localembed.ensure_model() is not None
        assert sorted(calls) == sorted(localembed.FILES)

    def test_the_cache_path_is_keyed_by_revision(self):
        # Two revisions must not share a directory, or upgrading the pin would
        # load the old weights from cache.
        assert localembed.MODEL_REV in str(localembed.model_dir())


class TestNormalise:
    def test_it_produces_a_unit_vector(self):
        out = localembed._normalise([3.0, 4.0])
        assert abs(sum(x * x for x in out) ** 0.5 - 1.0) < 1e-9

    def test_it_preserves_direction(self):
        out = localembed._normalise([3.0, 4.0])
        assert out[0] == pytest.approx(0.6)
        assert out[1] == pytest.approx(0.8)

    def test_an_all_zero_vector_is_returned_unchanged(self):
        # Dividing by a zero norm would be a ZeroDivisionError inside the
        # embedding path, which is meant never to raise.
        assert localembed._normalise([0.0, 0.0]) == [0.0, 0.0]

    def test_an_already_normal_vector_is_stable(self):
        assert localembed._normalise([1.0, 0.0]) == pytest.approx([1.0, 0.0])


class TestEncodeWithoutABackend:
    def test_an_empty_batch_short_circuits_before_loading(self, monkeypatch):
        # Cheap and important: `boost search ""` must not trigger a 133 MB
        # download.
        monkeypatch.setattr(localembed, "_load", lambda: (_ for _ in ()).throw(
            AssertionError("must not load a model for an empty batch")))
        assert localembed.encode([]) == []

    def test_encode_degrades_when_the_model_cannot_load(self, monkeypatch):
        monkeypatch.setattr(localembed, "_load", lambda: False)
        assert localembed.encode(["a"]) is None

    def test_available_is_false_without_the_runtime(self, monkeypatch):
        monkeypatch.setattr(localembed, "_deps", lambda: (None, None))
        assert localembed.available() is False

    def test_load_is_false_without_the_runtime(self, monkeypatch):
        monkeypatch.setattr(localembed, "_deps", lambda: (None, None))
        assert localembed._load() is False


class TestClsPooling:
    """The step that decides what a sentence embedding actually is.

    Pure by construction so it needs no ONNX runtime, which matters twice: the
    mutation gate runs without the ``[rag]`` extra, and this is the calculation
    most likely to be silently wrong. Mean pooling instead of CLS would return
    vectors of exactly the right width and quietly worse retrieval.
    """

    def test_it_takes_the_first_token_not_the_mean(self):
        # THE ASSERTION THAT MATTERS. CLS -> [1,0]; a mean over the two tokens
        # would be [0.707, 0.707] after normalising. Only one of those is BGE.
        out = localembed.cls_pool([[[1.0, 0.0], [0.0, 1.0]]])
        assert out[0] == pytest.approx([1.0, 0.0])

    def test_every_row_is_normalised(self):
        out = localembed.cls_pool([[[3.0, 4.0]], [[0.0, 5.0]]])
        for vec in out:
            assert sum(x * x for x in vec) ** 0.5 == pytest.approx(1.0)

    def test_one_vector_per_row(self):
        out = localembed.cls_pool([[[1.0, 0.0]], [[0.0, 1.0]], [[1.0, 1.0]]])
        assert len(out) == 3

    def test_an_empty_batch_yields_nothing(self):
        assert localembed.cls_pool([]) == []

    def test_values_become_plain_floats(self):
        # sqlite-vec and the JSON layer want floats, not numpy scalars.
        out = localembed.cls_pool([[[1, 0]]])
        assert all(isinstance(x, float) for x in out[0])


class _FakeEncoded:
    def __init__(self, ids):
        self.ids = ids
        self.attention_mask = [1] * len(ids)
        self.type_ids = [0] * len(ids)


class _FakeTokenizer:
    def __init__(self):
        self.truncation = None
        self.padded = False

    def encode_batch(self, texts):
        return [_FakeEncoded([101, 7, 102]) for _ in texts]

    def enable_truncation(self, max_length):
        self.truncation = max_length

    def enable_padding(self):
        self.padded = True


class _FakeSession:
    """Mimics onnxruntime: declares input names and returns a hidden state."""

    def __init__(self, names=("input_ids", "attention_mask", "token_type_ids")):
        self._names = names
        self.fed = None

    def get_inputs(self):
        return [type("I", (), {"name": n})() for n in self._names]

    def run(self, _outputs, feed):
        self.fed = feed
        n = len(next(iter(feed.values())))
        # (batch, tokens, hidden): CLS row is distinguishable from the rest.
        return [[[[1.0, 0.0], [0.0, 9.0]] for _ in range(n)]]


class TestEncodeWithAFakeSession:
    """`encode` without an ONNX runtime, so the gate covers it too.

    What is actually under test is the feed: which input names get passed, and
    that the CLS row is what comes back. A model whose graph omits
    ``token_type_ids`` will reject a feed containing it, so the filter against
    ``get_inputs()`` is load-bearing rather than defensive.
    """

    @staticmethod
    def _wire(monkeypatch, session):
        monkeypatch.setattr(localembed, "_load", lambda: True)
        monkeypatch.setattr(localembed, "_session", session, raising=False)
        monkeypatch.setattr(localembed, "_tokenizer", _FakeTokenizer(),
                            raising=False)
        monkeypatch.setattr(localembed, "_as_i64", lambda rows: rows)

    def test_it_returns_one_normalised_cls_vector_per_text(self, monkeypatch):
        self._wire(monkeypatch, _FakeSession())
        out = localembed.encode(["a", "b"])
        assert out is not None and len(out) == 2
        for vec in out:
            assert vec == pytest.approx([1.0, 0.0]), "must be CLS, not the mean"

    def test_it_feeds_every_input_the_graph_declares(self, monkeypatch):
        session = _FakeSession()
        self._wire(monkeypatch, session)
        localembed.encode(["a"])
        assert set(session.fed) == {"input_ids", "attention_mask",
                                    "token_type_ids"}

    def test_it_omits_inputs_the_graph_does_not_declare(self, monkeypatch):
        # Feeding an undeclared name makes onnxruntime raise; some BGE exports
        # take only two inputs.
        session = _FakeSession(names=("input_ids", "attention_mask"))
        self._wire(monkeypatch, session)
        localembed.encode(["a"])
        assert "token_type_ids" not in session.fed

    def test_a_raising_session_degrades(self, monkeypatch):
        class Boom(_FakeSession):
            def run(self, _outputs, feed):
                raise RuntimeError("inference failed")

        self._wire(monkeypatch, Boom())
        assert localembed.encode(["a"]) is None


class TestLoad:
    """`_load` with fake libraries: the wiring, without an ONNX runtime."""

    @staticmethod
    def _fake_modules(tokenizer):
        class Opts:
            def __init__(self):
                self.intra_op_num_threads = None
                self.inter_op_num_threads = None

        made = {}

        class ORT:
            SessionOptions = Opts

            @staticmethod
            def InferenceSession(path, opts, providers):
                made["path"] = path
                made["opts"] = opts
                made["providers"] = providers
                return _FakeSession()

        class Toks:
            class Tokenizer:
                @staticmethod
                def from_file(_p):
                    return tokenizer

        return ORT, Toks, made

    def test_it_builds_a_cpu_session_with_bounded_threads(self, monkeypatch):
        # An unbounded thread pool inside `boost search` is a surprise on a
        # shared machine, and a CLI embedding a few chunks gains nothing.
        tok = _FakeTokenizer()
        ort, toks, made = self._fake_modules(tok)
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, toks))
        monkeypatch.setattr(localembed, "ensure_model",
                            lambda: localembed.model_dir())
        assert localembed._load() is True
        assert made["providers"] == ["CPUExecutionProvider"]
        assert made["opts"].intra_op_num_threads == 1
        assert made["opts"].inter_op_num_threads == 1

    def test_it_truncates_to_the_model_limit(self, monkeypatch):
        # BGE caps at 512; longer input must be truncated, not rejected.
        tok = _FakeTokenizer()
        ort, toks, _made = self._fake_modules(tok)
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, toks))
        monkeypatch.setattr(localembed, "ensure_model",
                            lambda: localembed.model_dir())
        localembed._load()
        assert tok.truncation == 512      # literal: see TestPinnedConstants
        assert tok.padded is True

    def test_a_missing_model_stops_the_load(self, monkeypatch):
        ort, toks, _made = self._fake_modules(_FakeTokenizer())
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, toks))
        monkeypatch.setattr(localembed, "ensure_model", lambda: None)
        assert localembed._load() is False

    def test_a_half_installed_extra_stops_the_load(self, monkeypatch):
        # onnxruntime present, tokenizers missing. Checking only the first
        # would reach `tokenizers.Tokenizer` on a None.
        ort, _toks, _made = self._fake_modules(_FakeTokenizer())
        monkeypatch.setattr(localembed, "_deps", lambda: (ort, None))
        assert localembed._load() is False

    def test_a_raising_session_constructor_degrades(self, monkeypatch):
        class ORT:
            class SessionOptions:
                pass

            @staticmethod
            def InferenceSession(*_a, **_k):
                raise RuntimeError("corrupt model file")

        monkeypatch.setattr(localembed, "_deps", lambda: (ORT, object()))
        monkeypatch.setattr(localembed, "ensure_model",
                            lambda: localembed.model_dir())
        assert localembed._load() is False


class TestFetchRenameFailure:
    def test_a_failed_rename_leaves_nothing_behind(self, tmp_path, monkeypatch):
        from boost_cli.core import nethttp

        class Resp:
            def __init__(self):
                self._d = BODY
            def read(self, n=-1):
                out, self._d = self._d, b""
                return out
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                return False

        monkeypatch.setattr(nethttp, "urlopen", lambda *_a, **_k: Resp())

        def bad_replace(self, _target):
            raise OSError("cross-device link")

        monkeypatch.setattr(localembed.Path, "replace", bad_replace)
        dest = tmp_path / "f"
        assert localembed._fetch("f", dest, len(BODY), DIGEST) is False
        assert list(tmp_path.glob("*.part")) == []


class TestPinnedConstants:
    """The supply-chain pins, asserted against literals.

    Deliberately duplicating the values rather than comparing a constant to
    itself. These identify exactly which bytes get loaded into an ONNX runtime,
    so changing one should require changing this test too — a deliberate act
    with a diff, not a silent edit. (The truncation test above compares against
    a literal for the same reason: `tok.truncation == MAX_TOKENS` would pass
    for any value of MAX_TOKENS.)
    """

    def test_the_model_repo_and_revision_are_pinned(self):
        assert localembed.MODEL_REPO == "BAAI/bge-small-en-v1.5"
        assert localembed.MODEL_REV == "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
        assert len(localembed.MODEL_REV) == 40, "must be a full commit sha"

    def test_the_url_resolves_the_pinned_revision(self):
        assert localembed._BASE == (
            "https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/"
            "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/")

    def test_the_weight_hashes_are_pinned(self):
        # Verified against huggingface.co's own paths-info for this revision.
        assert localembed.FILES["onnx/model.onnx"] == (
            133093490,
            "828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35")
        assert localembed.FILES["tokenizer.json"] == (
            711396,
            "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66")

    def test_every_pin_is_a_full_sha256(self):
        for rel, (size, digest) in localembed.FILES.items():
            assert size > 0, rel
            assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), rel

    def test_the_token_limit_matches_the_model(self):
        # BGE's positional embeddings stop at 512; a larger value would be
        # accepted by the tokenizer and rejected by the graph at runtime.
        assert localembed.MAX_TOKENS == 512
