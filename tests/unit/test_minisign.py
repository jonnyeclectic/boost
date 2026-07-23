"""Unit tests: core/minisign.py — parse & verify minisign keys/signatures.

Two layers of oracle: FROZEN blobs (minted once, embedded as literals) that a
mutation to the verifier can't also "fix", plus the deterministic ``signer``
fixture for tampering and both signature flavours.
"""
from __future__ import annotations

import pytest

from boost_cli.core import minisign

# ── frozen fixtures: a fixed key + signatures over MANIFEST (see conftest
# _MinisignSigner, seed=0x07*32, key_id=1122334455667788). Real minisign wire
# format — the public-key line carries minisign's own RWQ prefix. ────────────
MANIFEST = b"boost-tap-manifest\nversion: 1\nskills: 3\n"
PUB_TEXT = ("untrusted comment: boost fixture public key\n"
            "RWQRIjNEVWZ3iOpKbGPinFIKvvVQexMuxfmVR3auvr57kkIe6mkURtIs\n")
SIG_ED = (
    "untrusted comment: signature from boost fixture key\n"
    "RWQRIjNEVWZ3iOCi5DPc72A2KHnZ2Wj8WokC+SLx3/b31PZJIzA1UhzC/0e9+UNd/96K75TVds6"
    "wrpD7kRO1Fg1rkQ243z8vawU=\n"
    "trusted comment: timestamp:1700000000\tfile:tap.manifest\n"
    "6/CcnobM8heQPaurTEVlMHdKjsnWy09JBmUHail70m79l2vKOXOQUr8Mcn+09pZKu9zocduitbxd"
    "+gCXaOICDA==\n")
SIG_PREHASH = (
    "untrusted comment: signature from boost fixture key\n"
    "RUQRIjNEVWZ3iMJYUKjRlb3EfVrd3jPLq8IhGGFTAvP6nfqkkY0xLg8LLCvDKEkkYmQiuMteTRx"
    "49oauZEVpcwlF+GLgpTxVmgk=\n"
    "trusted comment: timestamp:1700000000\tfile:tap.manifest\n"
    "tmHBuHoMJnzn3x5XAecvtIGqQizo9PM1GwpGCNDENjE5dPMWdKUgWMDg6jZJFHj0toh6Bs+SAaz"
    "NfHsfjM0hDg==\n")


# ── public-key parsing ───────────────────────────────────────────────────

def test_parse_public_key_full_file():
    pk = minisign.parse_public_key(PUB_TEXT)
    assert len(pk.key) == 32 and len(pk.key_id) == 8
    assert minisign.key_id_hex(pk.key_id) == "1122334455667788"


def test_parse_public_key_bare_base64_line():
    bare = PUB_TEXT.strip().splitlines()[-1]
    assert minisign.parse_public_key(bare).key_id == bytes.fromhex("1122334455667788")


def test_parse_public_key_rejects_empty():
    with pytest.raises(minisign.MinisignError):
        minisign.parse_public_key("\n\n")


def test_parse_public_key_rejects_wrong_length():
    import base64
    short = base64.b64encode(b"Ed" + b"\x00" * 8).decode()  # missing 32-byte key
    with pytest.raises(minisign.MinisignError):
        minisign.parse_public_key(short)


def test_parse_public_key_rejects_bad_base64():
    with pytest.raises(minisign.MinisignError):
        minisign.parse_public_key("not base64 @@@")


def test_parse_public_key_rejects_unknown_algorithm():
    import base64
    raw = b"XX" + b"\x00" * 8 + b"\x00" * 32
    with pytest.raises(minisign.MinisignError):
        minisign.parse_public_key(base64.b64encode(raw).decode())


# ── signature parsing ────────────────────────────────────────────────────

def test_parse_signature_fields():
    sig = minisign.parse_signature(SIG_ED)
    assert sig.algorithm == b"Ed"
    assert sig.key_id == bytes.fromhex("1122334455667788")
    assert len(sig.signature) == 64 and len(sig.global_signature) == 64
    assert sig.trusted_comment == "timestamp:1700000000\tfile:tap.manifest"


def test_parse_signature_prehash_algorithm():
    assert minisign.parse_signature(SIG_PREHASH).algorithm == b"ED"


def test_parse_signature_tolerates_leading_blank_line():
    assert minisign.parse_signature("\n" + SIG_ED).algorithm == b"Ed"


def test_parse_signature_requires_trusted_comment():
    two_lines = "\n".join(SIG_ED.splitlines()[:2])
    with pytest.raises(minisign.MinisignError):
        minisign.parse_signature(two_lines)


def test_parse_signature_rejects_short_blob():
    import base64
    bad = ("untrusted comment: x\n%s\ntrusted comment: c\n%s\n"
           % (base64.b64encode(b"Ed" + b"\x00" * 8).decode(),
              base64.b64encode(b"\x00" * 64).decode()))
    with pytest.raises(minisign.MinisignError):
        minisign.parse_signature(bad)


def test_parse_signature_rejects_short_global_sig():
    import base64
    good_blob = SIG_ED.splitlines()[1]
    bad = ("untrusted comment: x\n%s\ntrusted comment: c\n%s\n"
           % (good_blob, base64.b64encode(b"\x00" * 10).decode()))
    with pytest.raises(minisign.MinisignError):
        minisign.parse_signature(bad)


# ── verification ─────────────────────────────────────────────────────────

def test_verify_frozen_legacy_signature():
    pk = minisign.parse_public_key(PUB_TEXT)
    assert minisign.verify(pk, MANIFEST, minisign.parse_signature(SIG_ED)) is True


def test_verify_frozen_prehashed_signature():
    pk = minisign.parse_public_key(PUB_TEXT)
    assert minisign.verify(pk, MANIFEST, minisign.parse_signature(SIG_PREHASH)) is True


def test_verify_rejects_tampered_content():
    pk = minisign.parse_public_key(PUB_TEXT)
    assert minisign.verify(pk, MANIFEST + b"x",
                           minisign.parse_signature(SIG_ED)) is False


def test_verify_rejects_key_id_mismatch():
    pk = minisign.parse_public_key(PUB_TEXT)
    wrong = minisign.PublicKey(key_id=b"\x00" * 8, key=pk.key)
    assert minisign.verify(wrong, MANIFEST, minisign.parse_signature(SIG_ED)) is False


def test_verify_rejects_swapped_trusted_comment(signer):
    """The global signature binds the trusted comment; swapping it fails."""
    sig_text = signer.signature_text(MANIFEST, trusted_comment="original")
    tampered = sig_text.replace("trusted comment: original",
                                "trusted comment: forged")
    pk = minisign.parse_public_key(signer.public_key_text())
    assert minisign.verify(pk, MANIFEST, minisign.parse_signature(tampered)) is False


def test_verify_both_modes_via_signer(signer):
    pk = minisign.parse_public_key(signer.public_key_text())
    for prehash in (False, True):
        sig = minisign.parse_signature(signer.signature_text(MANIFEST, prehash=prehash))
        assert minisign.verify(pk, MANIFEST, sig) is True


def test_key_id_hex_is_uppercase():
    assert minisign.key_id_hex(bytes.fromhex("abcd00")) == "ABCD00"
