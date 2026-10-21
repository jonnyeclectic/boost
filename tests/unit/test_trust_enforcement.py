# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: provenance and install policy hold on every path back in.

`boost tap` checked a tap's signature once; `update` moved a tap onto any
later commit unchecked.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import (
    gitutil,
    paths,
    policy,
    provenance,
    registry,
    util,
)
from boost_cli.errors import BoostError


def _git(*args, cwd):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True)


def _require_signed():
    pol = policy.load()
    pol["require_signed_taps"] = True
    policy.save(pol)


@pytest.fixture()
def signed(sandbox, fixture_tap_src, tmp_path, signer):
    """A signed tap, its key trusted, signing required. -> (src, tap, head)."""
    src = tmp_path / "stap"
    shutil.copytree(fixture_tap_src, src)
    signer.write_signed(src)
    _git("add", "-A", cwd=src)
    _git("commit", "-qm", "sign", cwd=src)
    provenance.add_trusted_key("acme", signer.public_key_text())
    _require_signed()
    tap = registry.add(str(src))
    return src, tap, gitutil.head_commit(tap.path)


def _unsign(src):
    _git("rm", "-q", provenance.SIGNATURE_FILE, cwd=src)
    _git("commit", "-qm", "unsign", cwd=src)
    return gitutil.head_commit(src)


_UNSIGNED = ("tap stap failed provenance policy: tap is unsigned (no "
             ".boost/tap.manifest.minisig), and policy requires a trusted "
             "signature")


class TestCheckTapSigningAtACommit:
    def test_reads_the_commit_not_the_working_tree(self, signed):
        src, tap, head = signed
        new = _unsign(src)
        gitutil.run(["-C", str(tap.path), "fetch", "--quiet", "origin"])
        assert policy.check_tap_signing(tap.path, commit=head) == []
        assert policy.check_tap_signing(tap.path, commit=new) == [
            "tap is unsigned (no .boost/tap.manifest.minisig), and policy "
            "requires a trusted signature"]
        assert policy.check_tap_signing(tap.path) == []   # tree still signed

    def test_verify_commit_names_the_key(self, signed):
        _src, tap, head = signed
        res = provenance.verify_commit(tap.path, head)
        assert (res.status, res.key_name) == (provenance.VERIFIED, "acme")

    def test_off_when_signing_is_not_required(self, signed):
        src, tap, _head = signed
        new = _unsign(src)
        pol = policy.load()
        pol["require_signed_taps"] = False
        policy.save(pol)
        assert policy.check_tap_signing(tap.path, commit=new) == []


class TestUpdateRefusesAnUnsignedCommit:
    def test_named_update_raises_and_keeps_head(self, signed):
        src, tap, head = signed
        _unsign(src)
        with pytest.raises(BoostError) as exc:
            registry.update("stap")
        assert exc.value.message == _UNSIGNED + " — kept at %s" % head[:7]
        assert exc.value.hint == (
            "add its key with `boost trust add <name> <key>`, or relax "
            "`boost policy set require_signed_taps false`")
        assert gitutil.head_commit(tap.path) == head

    def test_sweep_reports_it_as_a_policy_failure(self, signed):
        src, tap, head = signed
        _unsign(src)
        results, failures = registry.update()
        assert results == {}
        assert failures == {"stap": _UNSIGNED + " — kept at %s" % head[:7]}
        assert registry.POLICY_REFUSAL in failures["stap"]
        assert gitutil.head_commit(tap.path) == head

    def test_a_resigned_commit_moves(self, signed, signer):
        src, _tap, head = signed
        signer.write_signed(src, manifest=b"boost-tap v2\n")
        _git("add", "-A", cwd=src)
        _git("commit", "-qm", "v2", cwd=src)
        results, failures = registry.update()
        assert failures == {}
        new = gitutil.head_commit(src)
        assert results == {"stap": "%s → %s" % (head[:7], new[:7])}

    def test_reclone_is_gated_and_leaves_nothing(self, signed):
        src, tap, _head = signed
        _unsign(src)
        util.rmtree(tap.path)
        with pytest.raises(BoostError) as exc:
            registry.ensure_cloned(registry.get("stap"))
        assert exc.value.message == _UNSIGNED
        assert not tap.path.exists()
        assert not tap.path.with_name("stap.boost-reclone").exists()

    def test_retarget_is_gated(self, signed):
        src, tap, head = signed
        new = _unsign(src)
        with pytest.raises(BoostError, match="kept at %s" % head[:7]):
            registry.retarget("stap", new)
        assert gitutil.head_commit(tap.path) == head
        assert registry.get("stap").pin == ""

    def test_unreadable_policy_hint_names_the_repair(self, signed):
        src, _tap, _head = signed
        _unsign(src)
        paths.policy_path().write_text('{"require_signed_taps": "maybe"}',
                                       encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            registry.update("stap")
        assert exc.value.hint.startswith("repair policy.json first")
