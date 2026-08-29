# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The keyless local embedding backend: ONNX Runtime over a pinned BGE model.

``core.embed`` owns the provider chain; this owns the one thing that chain was
missing — a way to turn text into vectors with no API key. It is reached only
through ``embed.provider() == "local"`` and, like every other optional path in
this codebase, returns ``None`` rather than raising so the caller floors to
BM25.

Why the model is fetched rather than vendored
---------------------------------------------
The weights are 133 MB — far too large to ship in a wheel for a CLI whose whole
runtime is stdlib. So they are downloaded once, on first use, and cached under
``~/.boost/cache/models``. That download is the one part of boost that reaches
for something big at runtime, so it is pinned the same way the toolchain lock
is: a fixed repository *revision*, an expected byte length, and a **sha256 that
is verified before the file is used**. A mismatch deletes the download and
degrades rather than loading whatever arrived.

(For the record, because the number circulates: the "~30 MB" figure often
quoted for bge-small is the *quantized* rebuild third parties publish, not
BAAI's own export. This uses the authoritative one — a signed-supply-chain
repo has no business pulling model weights from a re-uploader to save a
one-time download. Quantization is a later optimisation, and it changes the
vectors, so it would need its own eval.)

Pooling
-------
BGE is a CLS-pooled model: the sentence embedding is the first token's hidden
state, L2-normalised — *not* a mean over tokens. Using mean pooling here would
still produce 384 plausible-looking floats and quietly worse retrieval, which
is the kind of bug an eval catches and a unit test does not, so the choice is
stated here and asserted against a known-good pair in the tests.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from . import paths

# Pinned to a revision, not a branch: `main` moving would silently change every
# vector in every user's index, and the index only rebuilds when the *model
# name* changes — which it would not.
MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REV = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
_BASE = "https://huggingface.co/%s/resolve/%s/" % (MODEL_REPO, MODEL_REV)

# path -> (bytes, sha256). Verified after download and again on every load, so
# a truncated or tampered cache cannot be used.
FILES = {
    "onnx/model.onnx": (
        133093490,
        "828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35"),
    "tokenizer.json": (
        711396,
        "d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"),
}

# BGE caps at 512 tokens; longer input is truncated rather than rejected, which
# matches how the chunker already feeds this.
MAX_TOKENS = 512

_session = None
_tokenizer = None


def _deps():
    """(onnxruntime, tokenizers) or (None, None) when the extra is absent.

    Imported inside the function: ``scripts/import_budget.py`` gates CLI
    startup, and an ONNX runtime at module import would charge `boost --help`
    for a feature it never uses.
    """
    try:
        import onnxruntime
        import tokenizers
    except Exception:      # any import failure means "no backend"
        return None, None
    return onnxruntime, tokenizers


def available() -> bool:
    """True when the runtime and tokenizer libraries are importable."""
    return _deps()[0] is not None


def model_dir() -> Path:
    """Where the pinned weights are cached, keyed by revision."""
    return paths.cache_dir() / "models" / MODEL_REV


def _verified(path: Path, size: int, digest: str) -> bool:
    """True when `path` matches the pinned length and hash.

    Length first because it is free and rules out the common case (a truncated
    download) without reading 133 MB.
    """
    try:
        if path.stat().st_size != size:
            return False
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest() == digest
    except OSError:
        return False


def _fetch(rel: str, dest: Path, size: int, digest: str) -> bool:
    """Download one pinned file. False on any failure, leaving nothing behind.

    Downloads to a temporary name and only renames after the hash matches, so
    an interrupted fetch can never be mistaken for a complete one on the next
    run.
    """
    from . import nethttp
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with nethttp.urlopen(_BASE + rel, timeout=600) as resp, \
                tmp.open("wb") as out:
            shutil.copyfileobj(resp, out, 1 << 20)
    except Exception:      # network/disk failure degrades to BM25
        tmp.unlink(missing_ok=True)
        return False
    if not _verified(tmp, size, digest):
        tmp.unlink(missing_ok=True)
        return False
    try:
        tmp.replace(dest)
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    return True


def ensure_model() -> Path | None:
    """The verified model directory, downloading it once if needed, or None."""
    root = model_dir()
    for rel, (size, digest) in FILES.items():
        dest = root / rel
        if _verified(dest, size, digest):
            continue
        if not _fetch(rel, dest, size, digest):
            return None
    return root


def _load():
    """Build and cache the session and tokenizer. False when unavailable."""
    global _session, _tokenizer
    if _session is not None and _tokenizer is not None:
        return True
    onnxruntime, tokenizers = _deps()
    # Both, not just the first: they are returned as a pair and a partial
    # install (onnxruntime present, tokenizers missing) would otherwise reach
    # `tokenizers.Tokenizer` on a None.
    if onnxruntime is None or tokenizers is None:
        return False
    root = ensure_model()
    if root is None:
        return False
    try:
        opts = onnxruntime.SessionOptions()
        # A CLI embedding a handful of chunks gains nothing from spawning a
        # thread per core, and an unbounded pool inside a `boost search` is a
        # surprise on a shared machine.
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        session = onnxruntime.InferenceSession(
            str(root / "onnx/model.onnx"), opts,
            providers=["CPUExecutionProvider"])
        tok = tokenizers.Tokenizer.from_file(str(root / "tokenizer.json"))
        tok.enable_truncation(max_length=MAX_TOKENS)
        tok.enable_padding()
    except Exception:      # a broken model degrades, never raises
        return False
    _session, _tokenizer = session, tok
    return True


def reset() -> None:
    """Drop the cached session and tokenizer. For tests."""
    global _session, _tokenizer
    _session = None
    _tokenizer = None


def encode(texts: list[str]) -> list[list[float]] | None:
    """Embed `texts`, or None on any failure.

    CLS pooling plus L2 normalisation, which is what BGE was trained for.
    """
    if not texts:
        return []
    if not _load():
        return None
    session, tok = _session, _tokenizer
    if session is None or tok is None:      # unreachable after _load(); for type narrowing
        return None
    try:
        encoded = tok.encode_batch(texts.copy())
        feed = {}
        wanted = {i.name for i in session.get_inputs()}
        cols = {
            "input_ids": [e.ids for e in encoded],
            "attention_mask": [e.attention_mask for e in encoded],
            "token_type_ids": [e.type_ids for e in encoded],
        }
        for name, col in cols.items():
            if name in wanted:
                feed[name] = _as_i64(col)
        return cls_pool(session.run(None, feed)[0])
    except Exception:      # inference failure degrades to BM25
        return None


def cls_pool(out) -> list[list[float]]:
    """Last hidden state -> one L2-normalised CLS vector per row.

    Kept pure and separate from :func:`encode` so the part that decides *what a
    sentence embedding is* can be tested without an ONNX runtime — it is the
    step most likely to be silently wrong, since taking the mean instead of the
    first token still yields plausible-looking vectors of the right width.

    ``out`` is (batch, tokens, hidden); ``row[0]`` is the [CLS] token.
    """
    return [_normalise([float(x) for x in row[0]]) for row in out]


def _as_i64(rows):
    """Token id matrix as the int64 array onnxruntime expects."""
    import numpy
    return numpy.array(rows, dtype=numpy.int64)


def _normalise(vec: list[float]) -> list[float]:
    """L2-normalise, leaving an all-zero vector alone rather than dividing by 0."""
    norm = sum(x * x for x in vec) ** 0.5
    if not norm:
        return vec
    return [x / norm for x in vec]
