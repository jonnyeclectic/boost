# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Parse and verify minisign public keys and signatures (pure stdlib).

`minisign <https://jedisct1.github.io/minisign/>`_ is the small, widely-adopted
signing tool boost standardises on for tap provenance: a publisher signs their
content with ``minisign -Sm``, ships the ``.minisig``, and boost checks it here
against a trusted public key. Only the wire *formats* and *verification* live in
boost — signing stays with the publisher's real key material.

Two signature flavours are supported, matching minisign itself:

* legacy ``Ed`` — the Ed25519 signature is over the raw file bytes.
* prehashed ``ED`` — over ``BLAKE2b-512`` of the file (``hashlib`` ships it), the
  mode minisign uses for large inputs.

The *global* signature over ``signature || trusted_comment`` is always checked
too, so the human-readable trusted comment can't be swapped without detection.
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from . import ed25519

_ALG_LEGACY = b"Ed"       # Ed25519 over the raw file
_ALG_PREHASH = b"ED"      # Ed25519 over BLAKE2b-512(file)
_TRUSTED_PREFIX = "trusted comment: "


class MinisignError(ValueError):
    """A minisign public key or signature that cannot be parsed."""


@dataclass(frozen=True)
class PublicKey:
    """A minisign public key: an 8-byte id and its 32-byte Ed25519 key."""
    key_id: bytes    # 8-byte key identifier
    key: bytes       # 32-byte Ed25519 public key


@dataclass(frozen=True)
class Signature:
    """A parsed ``.minisig``: the content signature plus its bound trusted comment."""
    algorithm: bytes         # b"Ed" (raw) or b"ED" (prehashed)
    key_id: bytes            # 8-byte key identifier (must match the public key)
    signature: bytes         # 64-byte Ed25519 signature over the content
    trusted_comment: str     # human-readable, bound by the global signature
    global_signature: bytes  # 64-byte Ed25519 signature over sig+trusted_comment


def _decode_b64(line: str) -> bytes:
    try:
        return base64.b64decode(line.strip(), validate=True)
    except ValueError as exc:  # binascii.Error is a ValueError subclass
        raise MinisignError("invalid base64 in minisign data") from exc


def parse_public_key(text: str) -> PublicKey:
    """Parse a minisign public key (the ``.pub`` file *or* its bare base64 line).

    A ``.pub`` file is an ``untrusted comment:`` line then one base64 line; we
    take the last non-blank line so either form works.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise MinisignError("empty public key")
    raw = _decode_b64(lines[-1])
    if len(raw) != 42:
        raise MinisignError("public key must be 42 bytes, got %d" % len(raw))
    algorithm, key_id, key = raw[:2], raw[2:10], raw[10:]
    if algorithm != _ALG_LEGACY:
        raise MinisignError("unsupported public key algorithm %r" % algorithm)
    return PublicKey(key_id=key_id, key=key)


def parse_signature(text: str) -> Signature:
    """Parse a ``.minisig`` file into its structured parts.

    Located by the ``trusted comment:`` line rather than by fixed offsets, so a
    stray leading blank line does not throw the parse off: the base64 above it is
    the signature blob, the base64 below it the global signature.
    """
    rows = text.splitlines()
    idx = next((i for i, ln in enumerate(rows)
                if ln.startswith(_TRUSTED_PREFIX)), -1)
    if idx < 1 or idx + 1 >= len(rows):
        raise MinisignError("missing or misplaced 'trusted comment:' line")
    blob = _decode_b64(rows[idx - 1])
    if len(blob) != 74:  # 2 + 8 + 64
        raise MinisignError("signature blob must be 74 bytes, got %d" % len(blob))
    algorithm, key_id, signature = blob[:2], blob[2:10], blob[10:]
    if algorithm not in (_ALG_LEGACY, _ALG_PREHASH):
        raise MinisignError("unsupported signature algorithm %r" % algorithm)
    global_signature = _decode_b64(rows[idx + 1])
    if len(global_signature) != 64:
        raise MinisignError("global signature must be 64 bytes, got %d"
                            % len(global_signature))
    return Signature(algorithm=algorithm, key_id=key_id, signature=signature,
                     trusted_comment=rows[idx][len(_TRUSTED_PREFIX):],
                     global_signature=global_signature)


def verify(public_key: PublicKey, message: bytes, signature: Signature) -> bool:
    """True iff ``signature`` over ``message`` checks out under ``public_key``.

    Enforces all three of: the key id matches, the content signature is valid
    (raw or BLAKE2b-prehashed per the algorithm byte), and the global signature
    over the trusted comment is valid. Any failure returns False, never raises.
    """
    if signature.key_id != public_key.key_id:
        return False
    if signature.algorithm == _ALG_PREHASH:
        signed = hashlib.blake2b(message, digest_size=64).digest()
    else:
        signed = message
    if not ed25519.verify(public_key.key, signed, signature.signature):
        return False
    bound = signature.signature + signature.trusted_comment.encode("utf-8")
    return ed25519.verify(public_key.key, bound, signature.global_signature)


def key_id_hex(key_id: bytes) -> str:
    """Uppercase hex of an 8-byte key id, minisign's display form."""
    return key_id.hex().upper()
