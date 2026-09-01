# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Tap provenance: is this clone signed by a key we trust?

A tap records the ``commit`` it is pinned at, which binds *content* (git is a
Merkle tree) — but says nothing about *who* published it. A hijacked mirror can
serve a different-but-internally-consistent tree. This module closes that gap: a
publisher signs a manifest in their repo with :mod:`minisign`, boost checks the
signature against a locally-held set of trusted public keys, and policy can
*require* a trusted signature before a tap is added.

The convention is deliberately plain — a detached signature over one file:

* ``.boost/tap.manifest``           — bytes the publisher commits and signs
* ``.boost/tap.manifest.minisig``   — the detached minisign signature

boost verifies the signature over the manifest bytes; what the manifest *says* is
the publisher's business (a version line, a digest of their skills). The trust
store lives at ``~/.boost/state/trusted_keys.json`` and, like every other boost
state file, a missing or corrupt one reads as "no trusted keys" rather than
raising.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..errors import BoostError
from . import minisign, paths

# Where a signed tap keeps its manifest and detached signature, relative to the
# clone root.
SIGNED_FILE = ".boost/tap.manifest"
SIGNATURE_FILE = ".boost/tap.manifest.minisig"

# verify_dir statuses.
VERIFIED = "verified"        # a trusted key validated the signature
UNTRUSTED = "untrusted"      # a signature, but no trusted key accepts it
INVALID = "invalid"          # signature present but malformed / fails crypto
UNSIGNED = "unsigned"        # no signature file at all


@dataclass(frozen=True)
class Result:
    """Outcome of verifying one tap clone."""
    status: str
    key_name: str | None = None
    fingerprint: str | None = None   # public 8-byte key id, hex — not secret
    trusted_comment: str | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        """True only when a trusted key validated the signature."""
        return self.status == VERIFIED


# ── trusted-key store ────────────────────────────────────────────────────

def trusted_keys() -> list[dict]:
    """Trusted keys from the store: ``[{name, key_id, key}]``.

    A missing or unparseable store, or a non-list payload, reads as empty.
    """
    p = paths.trusted_keys_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [k for k in data if isinstance(k, dict) and k.get("name") and k.get("key")]


def _save(keys: list[dict]) -> None:
    paths.ensure_dirs()
    paths.trusted_keys_path().write_text(
        json.dumps(keys, indent=2) + "\n", encoding="utf-8")


def add_trusted_key(name: str, public_key_text: str) -> dict:
    """Parse ``public_key_text`` (a ``.pub`` file or its base64 line) and store it.

    Replaces any existing key of the same ``name`` so re-adding is idempotent.
    Raises :class:`BoostError` if the key does not parse.
    """
    name = name.strip()
    if not name:
        raise BoostError("a trusted key needs a name")
    try:
        pk = minisign.parse_public_key(public_key_text)
    except minisign.MinisignError as exc:
        raise BoostError("not a valid minisign public key: %s" % exc,
                         hint="pass the .pub file or its base64 line") from exc
    import base64
    record = {
        "name": name,
        "fingerprint": minisign.key_id_hex(pk.key_id),
        "key": base64.b64encode(pk.key_id + pk.key).decode("ascii"),
    }
    keys = [k for k in trusted_keys() if k.get("name") != name]
    keys.append(record)
    _save(keys)
    return record


def remove_trusted_key(name: str) -> bool:
    """Drop the trusted key named ``name``; return True if one was removed."""
    keys = trusted_keys()
    kept = [k for k in keys if k.get("name") != name]
    if len(kept) == len(keys):
        return False
    _save(kept)
    return True


def _public_keys() -> list[tuple]:
    """Trusted keys as ``(name, minisign.PublicKey)`` pairs, skipping any junk."""
    import base64
    out = []
    for k in trusted_keys():
        try:
            raw = base64.b64decode(k["key"], validate=True)
        except (ValueError, KeyError):
            continue
        if len(raw) == 40:  # key_id(8) + key(32)
            out.append((k["name"], minisign.PublicKey(key_id=raw[:8], key=raw[8:])))
    return out


# ── tap verification ─────────────────────────────────────────────────────

def verify_dir(clone: Path) -> Result:
    """Verify the signature in a tap clone against the trusted-key store.

    Returns a :class:`Result` — ``verified`` only when a trusted key validates
    the detached signature over the manifest; ``untrusted`` for a well-formed
    signature no trusted key accepts; ``invalid`` for a malformed signature or a
    signature whose manifest is missing; ``unsigned`` when there is no signature.
    """
    sig_path = clone / SIGNATURE_FILE
    manifest_path = clone / SIGNED_FILE
    if not sig_path.is_file():
        return Result(UNSIGNED, detail="no %s" % SIGNATURE_FILE)
    if not manifest_path.is_file():
        return Result(INVALID, detail="signature present but %s is missing"
                      % SIGNED_FILE)
    try:
        sig = minisign.parse_signature(sig_path.read_text(encoding="utf-8"))
        message = manifest_path.read_bytes()
    except (OSError, minisign.MinisignError) as exc:
        return Result(INVALID, detail=str(exc))
    for name, pk in _public_keys():
        if minisign.verify(pk, message, sig):
            return Result(VERIFIED, key_name=name,
                          fingerprint=minisign.key_id_hex(pk.key_id),
                          trusted_comment=sig.trusted_comment)
    # A signature carrying a *trusted* key's id that still fails to verify is
    # not a merely-unknown signer — it is the tampering this module exists to
    # catch (the manifest was edited after a trusted key signed it). Report it
    # as INVALID, not UNTRUSTED, so callers that only alarm on INVALID (the
    # `trust verify` sweep) don't wave a modified manifest through.
    for name, pk in _public_keys():
        if sig.key_id == pk.key_id:
            return Result(INVALID, key_name=name,
                          fingerprint=minisign.key_id_hex(pk.key_id),
                          trusted_comment=sig.trusted_comment,
                          detail="signature by trusted key %s does not verify"
                                 " — manifest modified?" % name)
    return Result(UNTRUSTED, fingerprint=minisign.key_id_hex(sig.key_id),
                  trusted_comment=sig.trusted_comment,
                  detail="no trusted key verifies this signature")
