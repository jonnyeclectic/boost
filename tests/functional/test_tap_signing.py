"""Functional tests: tap signing & provenance, end to end.

The contract: a tap can carry a minisign signature over ``.boost/tap.manifest``;
``boost trust`` manages the keys and reports provenance; and with
``require_signed_taps`` on, only a tap signed by a trusted key may be added.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from boost_cli.core import policy


def _git(*args, cwd):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _signed_tap(fixture_tap_src, tmp_path, signer, name="signedtap",
                prehash=False, manifest=b"boost-tap v1\n"):
    """A clone of the fixture tap with a committed minisign signature."""
    dst = tmp_path / name
    shutil.copytree(fixture_tap_src, dst)
    signer.write_signed(dst, manifest=manifest, prehash=prehash)
    _git("add", "-A", cwd=dst)
    _git("commit", "-qm", "sign tap", cwd=dst)
    return dst


# ── trust key management ─────────────────────────────────────────────────

def test_trust_list_is_empty_by_default(boost):
    r = boost("trust")
    assert "none" in r.out.lower() or "trusted keys" in r.out.lower()


def test_trust_add_list_remove(boost, tmp_path, signer):
    pub = tmp_path / "acme.pub"
    pub.write_text(signer.public_key_text(), encoding="utf-8")
    boost("trust", "add", "acme", pub)
    assert "acme" in boost("trust").out
    data = json.loads(boost("trust", "--json").out)
    assert [k["name"] for k in data["trusted_keys"]] == ["acme"]
    assert data["trusted_keys"][0]["fingerprint"] == "1122334455667788"
    boost("trust", "remove", "acme")
    assert "acme" not in boost("trust", "--json").out


def test_trust_add_accepts_inline_key(boost, signer):
    boost("trust", "add", "acme", signer.public_key_text())
    assert "acme" in boost("trust").out


def test_trust_add_rejects_garbage(boost):
    boost("trust", "add", "bad", "not-a-key", expect=1)


def test_trust_remove_unknown_errors(boost):
    boost("trust", "remove", "ghost", expect=1)


# ── provenance verification ──────────────────────────────────────────────

def test_verify_reports_verified_for_trusted_signed_tap(boost, fixture_tap_src,
                                                        tmp_path, signer):
    tap = _signed_tap(fixture_tap_src, tmp_path, signer)
    boost("tap", tap)
    boost("trust", "add", "acme", signer.public_key_text())
    r = boost("trust", "verify")
    assert "verified" in r.out
    data = json.loads(boost("trust", "verify", "--json").out)
    assert any(t["status"] == "verified" for t in data)


def test_verify_specific_untrusted_tap_exits_nonzero(boost, fixture_tap_src,
                                                     tmp_path, signer):
    tap = _signed_tap(fixture_tap_src, tmp_path, signer, name="untrusted")
    boost("tap", tap)                       # signed, but key not trusted
    r = boost("trust", "verify", "untrusted", expect=1)
    assert "untrusted" in r.out


def test_unsigned_tap_shows_unsigned(boost, tapped):
    # the plain fixture tap ships no signature
    assert "unsigned" in boost("trust", "verify").out


# ── enforcement: require_signed_taps ─────────────────────────────────────

@pytest.fixture()
def require_signed(boost):
    pol = policy.load()
    pol["require_signed_taps"] = True
    policy.save(pol)


def test_unsigned_tap_refused_when_signing_required(boost, fixture_tap_src,
                                                    tmp_path, require_signed):
    dst = tmp_path / "plain"
    shutil.copytree(fixture_tap_src, dst)
    r = boost("tap", dst, expect=1)
    assert "provenance policy" in (r.out + r.err)
    assert "unsigned" in (r.out + r.err)
    assert boost("taps").out.count("plain") == 0     # nothing recorded


def test_signed_trusted_tap_accepted_when_required(boost, fixture_tap_src,
                                                   tmp_path, signer, require_signed):
    boost("trust", "add", "acme", signer.public_key_text())
    tap = _signed_tap(fixture_tap_src, tmp_path, signer, name="ok")
    boost("tap", tap)                        # verified -> allowed
    assert "ok" in boost("taps").out


def test_signed_untrusted_tap_refused_when_required(boost, fixture_tap_src,
                                                    tmp_path, signer, require_signed):
    # signed, but its key is not in the trust store
    tap = _signed_tap(fixture_tap_src, tmp_path, signer, name="stranger")
    r = boost("tap", tap, expect=1)
    assert "no trusted key" in (r.out + r.err)


def test_master_switch_bypasses_signing_requirement(boost, fixture_tap_src,
                                                    tmp_path, require_signed):
    boost("config", "set", "policy_enforce", "false")
    dst = tmp_path / "plain2"
    shutil.copytree(fixture_tap_src, dst)
    boost("tap", dst)                        # gate disabled with everything else
    assert "plain2" in boost("taps").out
