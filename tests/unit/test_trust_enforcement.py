# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: provenance and install policy hold on every path back in.

`boost tap` checked a tap's signature once, and `install` the policy; `update`
moved a tap onto any later commit unchecked, and `snapshot restore` /
`quarantine --release` brought back skills the policy had since blocked.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from boost_cli.core import (
    catalog,
    gitutil,
    lockfile,
    paths,
    policy,
    provenance,
    registry,
    store,
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

    def test_require_signed_clone_checks_the_working_tree(self, signed):
        _src, tap, _head = signed
        registry.require_signed_clone("stap", tap.path)     # signed: passes
        (tap.path / provenance.SIGNATURE_FILE).unlink()
        with pytest.raises(BoostError) as exc:
            registry.require_signed_clone("stap", tap.path)
        assert exc.value.message == _UNSIGNED
        assert "boost trust add" in exc.value.hint

    def test_unreadable_policy_hint_names_the_repair(self, signed):
        src, _tap, _head = signed
        _unsign(src)
        paths.policy_path().write_text('{"require_signed_taps": "maybe"}',
                                       encoding="utf-8")
        with pytest.raises(BoostError) as exc:
            registry.update("stap")
        assert exc.value.hint.startswith("repair policy.json first")


# ── recorded items coming back: release and snapshot restore ────────────

@pytest.fixture()
def two(sandbox, fixture_tap_src):
    registry.add(str(fixture_tap_src))
    for n in ("brainstorming", "tdd-workflow"):
        store.install(catalog.find(n)[0])


def _block(**changes):
    pol = policy.load()
    pol.update(changes)
    policy.save(pol)


class TestRecordedPolicyViolations:
    def test_blocklisted_skill(self, two):
        _block(blocked_skills=["brainstorming"])
        entry = lockfile.get_skill("brainstorming")
        assert store.recorded_policy_violations(
            "skill", "brainstorming", entry) == [
            "skill 'brainstorming' is on the blocklist"]

    def test_counts_the_item_itself_as_installed(self, two):
        _block(max_skills=2)
        entry = lockfile.get_skill("brainstorming")
        assert store.recorded_policy_violations(
            "skill", "brainstorming", entry) == []
        assert store.recorded_policy_violations(
            "rule", "house", {"tap": "t", "version": "1.0.0"}) == []
        assert store.recorded_policy_violations(
            "skill", "other", {"tap": "t", "version": "1.0.0"}) == [
            "max_skills limit (2) reached"]

    def test_description_comes_from_the_skill_copy(self, two):
        _block(require_description=True)
        assert store.recorded_policy_violations(
            "skill", "brainstorming",
            lockfile.get_skill("brainstorming")) == []
        skill_md = paths.store_dir() / "brainstorming" / "SKILL.md"
        skill_md.write_text("---\nname: brainstorming\nversion: 1.0.0\n---\n"
                            "body\n", encoding="utf-8")
        assert store.recorded_policy_violations(
            "skill", "brainstorming", lockfile.get_skill("brainstorming")) == [
            "skill has no description (required by policy)"]

    def test_an_unread_description_is_not_a_violation(self, two):
        _block(require_description=True)
        assert store.recorded_policy_violations(
            "workflow", "ship", {"tap": "t", "version": "1.0.0"}) == []

    def test_version_is_read_from_the_record(self, two):
        _block(require_version=True)
        assert store.recorded_policy_violations(
            "rule", "house", {"tap": "t"}) == [
            "skill has no version (required by policy)"]
        assert store.recorded_policy_violations(
            "rule", "house", {"tap": "t", "version": "2.0.0"}) == []

    def test_blocked_tap_is_read_from_the_record(self, two):
        _block(blocked_taps=["t"])
        assert store.recorded_policy_violations(
            "rule", "house", {"tap": "t", "version": "1.0.0"}) == [
            "tap 't' is blocked"]


class TestRefuseRelease:
    def test_refusal_names_the_rule_and_the_way_out(self, two):
        _block(blocked_skills=["tdd-workflow"])
        with pytest.raises(BoostError) as exc:
            store.refuse_release_by_policy(
                "skill", "tdd-workflow", lockfile.get_skill("tdd-workflow"))
        assert exc.value.message == (
            "policy blocks releasing tdd-workflow: skill 'tdd-workflow' is on "
            "the blocklist — it stays quarantined")
        assert exc.value.hint == ("inspect with `boost policy list`; `boost "
                                  "uninstall tdd-workflow` removes it")

    def test_allowed_release_passes(self, two):
        store.refuse_release_by_policy(
            "skill", "tdd-workflow", lockfile.get_skill("tdd-workflow"))


class TestDeclineRestored:
    def test_declines_only_what_the_restore_brought_back(self, two):
        _block(blocked_skills=["brainstorming", "tdd-workflow"])
        lines = store.decline_restored_by_policy({"brainstorming"})
        assert lines == [
            "not restored tdd-workflow: policy blocks installing "
            "tdd-workflow: skill 'tdd-workflow' is on the blocklist"]
        assert sorted(lockfile.installed()) == ["brainstorming"]
        assert not (paths.store_dir() / "tdd-workflow").exists()
        assert (paths.store_dir() / "brainstorming").is_dir()

    def test_max_skills_counts_the_accepted_ones(self, two):
        _block(max_skills=1)
        lines = store.decline_restored_by_policy(set())
        assert lines == [
            "not restored tdd-workflow: policy blocks installing "
            "tdd-workflow: max_skills limit (1) reached"]
        assert sorted(lockfile.installed()) == ["brainstorming"]

    def test_nothing_declined_leaves_everything(self, two):
        assert store.decline_restored_by_policy(set()) == []
        assert sorted(lockfile.installed()) == ["brainstorming",
                                                "tdd-workflow"]

    def test_a_quarantined_row_is_left_alone(self, two):
        store.quarantine_skill("tdd-workflow", lockfile.get_skill("tdd-workflow"))
        held = store.held_copy_dir("tdd-workflow")
        assert held.is_dir()
        _block(blocked_skills=["tdd-workflow"])
        assert store.decline_restored_by_policy(set()) == []
        assert sorted(lockfile.installed()) == ["brainstorming",
                                                "tdd-workflow"]
        assert held.is_dir()
