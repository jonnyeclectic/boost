# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: core/ed25519.py — verify against the RFC 8032 vectors.

The known-good vectors are the real guard: they are signed by keys we do not
hold, so any error in the field math makes them fail to verify. The targeted
malformed-input cases pin the length and range checks.
"""
from __future__ import annotations

import pytest

from boost_cli.core import ed25519

# RFC 8032 §7.1 — (public_key, message, signature), all hex.
_VECTORS = [
    ("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb882159"
     "0a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e"
     "15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d"
     "16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


@pytest.mark.parametrize("pub,msg,sig", _VECTORS)
def test_rfc8032_vectors_verify(pub, msg, sig):
    assert ed25519.verify(bytes.fromhex(pub), bytes.fromhex(msg),
                          bytes.fromhex(sig)) is True


@pytest.mark.parametrize("pub,msg,sig", _VECTORS)
def test_flipping_any_signature_bit_fails(pub, msg, sig):
    raw = bytearray.fromhex(sig)
    raw[0] ^= 0x01
    assert ed25519.verify(bytes.fromhex(pub), bytes.fromhex(msg), bytes(raw)) is False


def test_wrong_message_fails():
    pub, _msg, sig = _VECTORS[1]
    assert ed25519.verify(bytes.fromhex(pub), b"different",
                          bytes.fromhex(sig)) is False


def test_wrong_public_key_fails():
    _pub, msg, sig = _VECTORS[1]
    other = _VECTORS[0][0]
    assert ed25519.verify(bytes.fromhex(other), bytes.fromhex(msg),
                          bytes.fromhex(sig)) is False


def test_bad_public_key_length_fails():
    _pub, msg, sig = _VECTORS[1]
    assert ed25519.verify(b"\x00" * 31, bytes.fromhex(msg),
                          bytes.fromhex(sig)) is False


def test_bad_signature_length_fails():
    pub, msg, _sig = _VECTORS[1]
    assert ed25519.verify(bytes.fromhex(pub), bytes.fromhex(msg),
                          b"\x00" * 63) is False


def test_scalar_at_or_above_group_order_fails():
    """S must be < L; setting S = L (a canonical-form violation) is rejected."""
    pub, msg, sig = _VECTORS[1]
    raw = bytearray.fromhex(sig)
    raw[32:] = ed25519._L.to_bytes(32, "little")  # S = L
    assert ed25519.verify(bytes.fromhex(pub), bytes.fromhex(msg), bytes(raw)) is False


def test_non_canonical_all_ones_r_is_rejected():
    """An R that is not a valid curve point makes verification fail, not raise."""
    pub, msg, sig = _VECTORS[1]
    raw = bytearray.fromhex(sig)
    raw[:32] = b"\xff" * 32  # y = 2^255-1 with high bit set: off-curve
    assert ed25519.verify(bytes.fromhex(pub), bytes.fromhex(msg), bytes(raw)) is False


def test_base_point_is_on_curve():
    """The precomputed base point B must satisfy the curve — recover_x succeeded."""
    assert ed25519._Bx is not None
    x, y, z, t = ed25519._B
    assert (x * y) % ed25519._P == (t * z) % ed25519._P


def test_signer_round_trip(signer):
    """A signature the fixture signer makes verifies under the public key."""
    msg = b"provenance manifest bytes"
    assert ed25519.verify(signer.public, msg, signer.sign_raw(msg)) is True
    assert ed25519.verify(signer.public, msg + b"!", signer.sign_raw(msg)) is False
