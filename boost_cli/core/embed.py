"""Optional dense-embedding bridge for RAG Phase 2.

Strategy mirrors ``core.ai``: prefer Voyage AI when ``VOYAGE_API_KEY`` is set,
else OpenAI when ``OPENAI_API_KEY`` is set, else a **local** ONNX model when the
``[rag]`` extra is installed, else return ``None`` so every caller degrades to
the always-on BM25 engine. The API embeddings come over ``urllib`` — pure
stdlib, no client library. Anthropic exposes no embeddings endpoint, hence
Voyage (its recommended partner) and OpenAI.

Why a local provider exists
---------------------------
Without one, dense search needed an account and a key, so in practice every
keyless user got BM25 — and BM25 answers "my app is slow" with bioinformatics
packages, because nothing in that query shares vocabulary with the docs. The
vector *store* was never the gated part: vectors already live on the user's own
machine in sqlite-vec, keyed on each tap's commit. The only API-bound step is
turning text into vectors.

That also rules out the obvious shortcut of shipping a prebuilt index instead:
answering a query means embedding *the query*, so a downloaded index is useless
without something local to embed with. A local model is the prerequisite, not
an alternative.

The chain order is load-bearing. Local is tried **last**, so a user who has
configured Voyage keeps voyage-4 rather than being silently downgraded to a
384-dim local model. And because ``dense.py`` rebuilds whenever ``model`` or
``dim`` changes, switching providers can never mix two embedding spaces in one
index.

``BOOST_NO_EMBED=1`` is a hard kill-switch for all three, matching
``BOOST_NO_AI``.
"""
from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from typing import Any

from . import nethttp

# The environment variable that selects each API provider. A mapping rather
# than literals inlined at each use, because `dense.fix_hint` has to name the
# exact variable that would revive a store built with a given provider — and a
# second copy of that string is precisely how a surface ends up naming the
# wrong one at the only moment the name matters.
KEY_ENV = {"voyage": "VOYAGE_API_KEY", "openai": "OPENAI_API_KEY"}

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
OPENAI_URL = "https://api.openai.com/v1/embeddings"

# model -> output dimension. Stored in the vector index so a provider/model
# switch is detected and forces a clean rebuild instead of mixing spaces.
# voyage-4 over voyage-3: same 1024-d default and same $/token, but the
# voyage-4 generation carries a 200M-token complimentary allowance where
# voyage-3 has none — so a full index build of a large corpus is free.
VOYAGE_MODEL = "voyage-4"
OPENAI_MODEL = "text-embedding-3-small"

# The keyless path. Small on purpose: skill docs are short and keyword-dense, so
# a 384-dim model closes most of the gap to a paid API and runs on CPU. Named
# with its full hub id because that is what ends up recorded in the index
# metadata — a bare "bge-small-en-v1.5" would collide with any other vendor's
# rebuild of it, and a rebuild produces different vectors. See core.localembed
# for the pinned revision and the (133 MB, not 30 MB) download it implies.
LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
LOCAL_DIM = 384

_DIMS = {VOYAGE_MODEL: 1024, OPENAI_MODEL: 1536, LOCAL_MODEL: LOCAL_DIM}

# Cached backend class and model instance. Loading an ONNX model is expensive
# enough that doing it per query would make the local path unusable, and the
# import itself is retried-on-miss rather than repeated: `provider()` runs on
# effectively every retrieval call.
_BACKEND_MISSING = object()
# Deliberately untyped: the backend is core.localembed, imported lazily, so
# naming its type here would defeat the point of the lazy import.
_backend_cache: Any = None
_model_instance: Any = None


def enabled() -> bool:
    """True unless the ``BOOST_NO_EMBED`` kill-switch is set."""
    return not os.environ.get("BOOST_NO_EMBED")


def _load_backend():
    """The local embedding class, or None when the ``[rag]`` extra is absent.

    ``localembed`` keeps its own imports lazy for the import budget; this is the
    seam the tests stub, so the unit suite passes with the extra uninstalled.
    """
    from . import localembed
    return localembed if localembed.available() else None


def _backend() -> Any:
    """``_load_backend`` memoised, including the negative result."""
    global _backend_cache
    if _backend_cache is None:
        _backend_cache = _load_backend() or _BACKEND_MISSING
    return None if _backend_cache is _BACKEND_MISSING else _backend_cache


def reset_local_cache() -> None:
    """Drop the cached backend and model. For tests, and for a provider switch."""
    global _backend_cache, _model_instance
    _backend_cache = None
    _model_instance = None
    # Nothing to reset when the extra is absent.
    with contextlib.suppress(Exception):
        from . import localembed
        localembed.reset()


def local_available() -> bool:
    """True when the local embedding backend can be imported."""
    return _backend() is not None


def provider() -> str | None:
    """The active provider, preferring a configured key, or None when nothing works.

    Order matters: local comes **last** so configuring Voyage keeps voyage-4.
    A fallback that preempted a paid key would silently downgrade every existing
    keyed install to a smaller model.
    """
    if not enabled():
        return None
    if os.environ.get(KEY_ENV["voyage"]):
        return "voyage"
    if os.environ.get(KEY_ENV["openai"]):
        return "openai"
    if local_available():
        return "local"
    return None


def available() -> bool:
    """True when embeddings are enabled and a provider key is present."""
    return provider() is not None


def model() -> str | None:
    """The active provider's model name, or None when unconfigured."""
    p = provider()
    if p == "voyage":
        return VOYAGE_MODEL
    if p == "openai":
        return OPENAI_MODEL
    if p == "local":
        return LOCAL_MODEL
    return None


def dimension() -> int | None:
    """Output vector dimension of the active model, or None when

    unconfigured. Stored in the index so a model switch forces a rebuild.
    """
    m = model()
    return _DIMS.get(m) if m is not None else None


def fallback_note() -> str:
    """The one-line hint shown when dense search degrades to BM25.

    No longer asks for a key: with a local model in the ``[rag]`` extra the
    extra alone is enough, and telling a user they need an API account when
    they do not is worse than saying nothing.
    """
    if not enabled():
        return "dense search is off (BOOST_NO_EMBED) — using the BM25 engine"
    return ("dense search needs the `[rag]` extra — `pip install "
            "boost-skill-cli[rag]`; using the BM25 full-content engine")


def embed(texts: list[str], input_type: str | None = None,
          timeout: int = 60) -> list[list[float]] | None:
    """Embed a batch of texts.

    Returns one vector per input, ``[]`` for an empty batch, or ``None`` when no
    provider is configured or the call fails (so callers degrade cleanly).
    ``input_type`` ("query"/"document") is honored by Voyage and ignored by
    OpenAI.
    """
    p = provider()
    if p is None:
        return None
    if not texts:
        return []
    if p == "local":
        return _embed_local(texts)
    if p == "voyage":
        body = {"input": texts.copy(), "model": VOYAGE_MODEL}
        if input_type:
            body["input_type"] = input_type
        return _vectors(_post(VOYAGE_URL, os.environ["VOYAGE_API_KEY"],
                              body, timeout), len(texts))
    body = {"input": texts.copy(), "model": OPENAI_MODEL}
    return _vectors(_post(OPENAI_URL, os.environ["OPENAI_API_KEY"],
                          body, timeout), len(texts))


def _local_model():
    """The loaded local model, or None if it cannot be built.

    First use downloads the pinned weights and caches them under
    ``~/.boost/cache/models``, so this can fail on a machine with no network.
    That is a degrade, not an error: the caller floors to BM25 exactly as it
    does when no key is set.
    """
    return _backend()


def _embed_local(texts: list[str]) -> list[list[float]] | None:
    """Embed locally. None on any failure, so the caller degrades to BM25.

    Validated as strictly as the API path: a short batch would misalign vectors
    against their chunks — every hit past the gap pointing at the wrong skill —
    and a wrong-width row would either error inside sqlite-vec or quietly
    corrupt the space, so both are rejected rather than stored.
    """
    backend = _local_model()
    if backend is None:
        return None
    try:
        rows = backend.encode(texts.copy())
    except Exception:      # inference failure degrades, never raises
        return None
    if rows is None or len(rows) != len(texts):
        return None
    out: list[list[float]] = []
    for row in rows:
        try:
            vec = [float(x) for x in row]
        except (TypeError, ValueError):
            return None
        if len(vec) != LOCAL_DIM:
            return None
        out.append(vec)
    return out


def _post(url: str, key: str, payload: dict, timeout: int) -> dict | None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={  # noqa: S310  url is a hardcoded VOYAGE_URL/OPENAI_URL constant
        "Authorization": "Bearer %s" % key,
        "Content-Type": "application/json",
    })
    try:
        with nethttp.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _vectors(obj: dict | None, n: int) -> list[list[float]] | None:
    """Pull ``data[].embedding`` out of an OpenAI-shaped response.

    Both Voyage and OpenAI return ``{"data": [{"embedding": [...]}, ...]}``.
    Returns None unless exactly ``n`` numeric vectors come back.
    """
    if not isinstance(obj, dict):
        return None
    data = obj.get("data")
    if not isinstance(data, list) or len(data) != n:
        return None
    out: list[list[float]] = []
    for item in data:
        vec = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vec, list) or not vec:
            return None
        out.append([float(x) for x in vec])
    return out
