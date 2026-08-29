# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: core/provenance.py — trusted-key store & tap verification."""
from __future__ import annotations

from boost_cli.core import paths, provenance

# ── trusted-key store ────────────────────────────────────────────────────

def test_empty_store_reads_as_no_keys(sandbox):
    assert provenance.trusted_keys() == []


def test_add_and_list_trusted_key(sandbox, signer):
    rec = provenance.add_trusted_key("acme", signer.public_key_text())
    assert rec["name"] == "acme"
    assert rec["fingerprint"] == "1122334455667788"
    names = [k["name"] for k in provenance.trusted_keys()]
    assert names == ["acme"]


def test_adding_same_name_replaces_not_duplicates(sandbox, signer):
    provenance.add_trusted_key("acme", signer.public_key_text())
    provenance.add_trusted_key("acme", signer.public_key_text())
    assert len(provenance.trusted_keys()) == 1


def test_add_rejects_garbage_key(sandbox):
    from boost_cli.errors import BoostError
    try:
        provenance.add_trusted_key("bad", "this is not a key")
    except BoostError:
        pass
    else:  # pragma: no cover - failure path
        raise AssertionError("expected BoostError")


def test_add_rejects_blank_name(sandbox, signer):
    from boost_cli.errors import BoostError
    try:
        provenance.add_trusted_key("   ", signer.public_key_text())
    except BoostError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected BoostError")


def test_remove_trusted_key(sandbox, signer):
    provenance.add_trusted_key("acme", signer.public_key_text())
    assert provenance.remove_trusted_key("acme") is True
    assert provenance.trusted_keys() == []


def test_remove_missing_key_returns_false(sandbox):
    assert provenance.remove_trusted_key("nope") is False


def test_corrupt_store_reads_as_empty(sandbox):
    paths.ensure_dirs()
    paths.trusted_keys_path().write_text("{not json", encoding="utf-8")
    assert provenance.trusted_keys() == []


def test_non_list_store_reads_as_empty(sandbox):
    paths.ensure_dirs()
    paths.trusted_keys_path().write_text('{"name": "x"}', encoding="utf-8")
    assert provenance.trusted_keys() == []


# ── verify_dir ───────────────────────────────────────────────────────────

def test_unsigned_when_no_signature(sandbox, tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    r = provenance.verify_dir(clone)
    assert r.status == provenance.UNSIGNED and not r.ok


def test_verified_with_trusted_key(sandbox, signer, tmp_path):
    provenance.add_trusted_key("acme", signer.public_key_text())
    clone = tmp_path / "clone"
    clone.mkdir()
    signer.write_signed(clone, manifest=b"boost-tap v1\n")
    r = provenance.verify_dir(clone)
    assert r.ok and r.status == provenance.VERIFIED
    assert r.key_name == "acme" and r.fingerprint == "1122334455667788"


def test_verified_prehashed_manifest(sandbox, signer, tmp_path):
    provenance.add_trusted_key("acme", signer.public_key_text())
    clone = tmp_path / "clone"
    clone.mkdir()
    signer.write_signed(clone, manifest=b"big\n", prehash=True)
    assert provenance.verify_dir(clone).ok


def test_untrusted_when_key_not_registered(sandbox, signer, tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    signer.write_signed(clone)                    # signed, but no key added
    r = provenance.verify_dir(clone)
    assert r.status == provenance.UNTRUSTED and not r.ok
    assert r.fingerprint == "1122334455667788"    # still reports whose key


def test_untrusted_when_content_tampered(sandbox, signer, tmp_path):
    provenance.add_trusted_key("acme", signer.public_key_text())
    clone = tmp_path / "clone"
    clone.mkdir()
    signer.write_signed(clone, manifest=b"original\n")
    (clone / provenance.SIGNED_FILE).write_bytes(b"tampered\n")
    assert provenance.verify_dir(clone).status == provenance.UNTRUSTED


def test_invalid_when_signature_present_but_manifest_missing(sandbox, signer, tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    signer.write_signed(clone)
    (clone / provenance.SIGNED_FILE).unlink()
    assert provenance.verify_dir(clone).status == provenance.INVALID


def test_invalid_when_signature_malformed(sandbox, tmp_path):
    clone = tmp_path / "clone"
    (clone / ".boost").mkdir(parents=True)
    (clone / provenance.SIGNED_FILE).write_bytes(b"x\n")
    (clone / provenance.SIGNATURE_FILE).write_text("garbage", encoding="utf-8")
    assert provenance.verify_dir(clone).status == provenance.INVALID
