"""Optional dense-embedding bridge for RAG Phase 2.

Strategy mirrors ``core.ai``: prefer Voyage AI when ``VOYAGE_API_KEY`` is set,
else OpenAI when ``OPENAI_API_KEY`` is set, else return ``None`` so every caller
degrades to the always-on BM25 engine. The embeddings themselves come from an
HTTP API over ``urllib`` — pure stdlib, no client library. Anthropic exposes no
embeddings endpoint, hence Voyage (its recommended partner) and OpenAI.

``BOOST_NO_EMBED=1`` is a hard kill-switch, matching ``BOOST_NO_AI``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import List, Optional

from . import nethttp

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
OPENAI_URL = "https://api.openai.com/v1/embeddings"

# model -> output dimension. Stored in the vector index so a provider/model
# switch is detected and forces a clean rebuild instead of mixing spaces.
VOYAGE_MODEL = "voyage-3"
OPENAI_MODEL = "text-embedding-3-small"
_DIMS = {VOYAGE_MODEL: 1024, OPENAI_MODEL: 1536}


def enabled() -> bool:
    return not os.environ.get("BOOST_NO_EMBED")


def provider() -> Optional[str]:
    """The active provider name, preferring Voyage, or None when unconfigured."""
    if not enabled():
        return None
    if os.environ.get("VOYAGE_API_KEY"):
        return "voyage"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def available() -> bool:
    return provider() is not None


def model() -> Optional[str]:
    p = provider()
    if p == "voyage":
        return VOYAGE_MODEL
    if p == "openai":
        return OPENAI_MODEL
    return None


def dimension() -> Optional[int]:
    m = model()
    return _DIMS.get(m) if m is not None else None


def fallback_note() -> str:
    return ("dense search needs the `rag` extra and VOYAGE_API_KEY or "
            "OPENAI_API_KEY — using the BM25 full-content engine")


def embed(texts: List[str], input_type: Optional[str] = None,
          timeout: int = 60) -> Optional[List[List[float]]]:
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
    if p == "voyage":
        body = {"input": list(texts), "model": VOYAGE_MODEL}
        if input_type:
            body["input_type"] = input_type
        return _vectors(_post(VOYAGE_URL, os.environ["VOYAGE_API_KEY"],
                              body, timeout), len(texts))
    body = {"input": list(texts), "model": OPENAI_MODEL}
    return _vectors(_post(OPENAI_URL, os.environ["OPENAI_API_KEY"],
                          body, timeout), len(texts))


def _post(url: str, key: str, payload: dict, timeout: int) -> Optional[dict]:
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


def _vectors(obj: Optional[dict], n: int) -> Optional[List[List[float]]]:
    """Pull ``data[].embedding`` out of an OpenAI-shaped response.

    Both Voyage and OpenAI return ``{"data": [{"embedding": [...]}, ...]}``.
    Returns None unless exactly ``n`` numeric vectors come back.
    """
    if not isinstance(obj, dict):
        return None
    data = obj.get("data")
    if not isinstance(data, list) or len(data) != n:
        return None
    out: List[List[float]] = []
    for item in data:
        vec = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(vec, list) or not vec:
            return None
        out.append([float(x) for x in vec])
    return out
