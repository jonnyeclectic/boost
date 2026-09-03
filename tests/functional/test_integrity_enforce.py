# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: digest enforcement & commit pinning through the CLI.

The invariant: the recorded digest is advisory until you opt in, and binding
once you do — a tampered skill is reported by `verify` always, and refused by
the content-reading commands only when enforcement is switched on.
"""
from __future__ import annotations

import json

from boost_cli.core import lockfile, paths


def _tamper(name):
    (paths.store_dir() / name / "SKILL.md").write_text("EVIL\n", encoding="utf-8")


# ── verify reports regardless of enforcement ─────────────────────────────

def test_verify_reports_modified(boost, installed):
    _tamper(installed)
    res = boost("verify", installed, expect=1)
    assert "modified" in res.out
    assert "failed verification" in (res.out + res.err)


def test_verify_json_carries_status_and_commit_pin(boost, installed):
    data = json.loads(boost("verify", installed, "--json").out)
    row = data["skills"][0]
    assert row["status"] == "ok" and row["commit_pin"] is None


# ── enforcement gates the read commands ──────────────────────────────────

def test_cat_works_when_enforcement_is_off(boost, installed):
    _tamper(installed)
    boost("cat", installed)          # default: advisory, so this still prints


def test_cat_refuses_a_tampered_skill_when_enforced(boost, installed):
    _tamper(installed)
    boost("config", "set", "security.enforce_digest", "true")
    res = boost("cat", installed, expect=1)
    assert "modified since install" in (res.out + res.err)


def test_preview_also_refuses_under_enforcement(boost, installed):
    _tamper(installed)
    boost("config", "set", "security.enforce_digest", "true")
    boost("preview", installed, expect=1)


def test_a_clean_skill_still_reads_under_enforcement(boost, installed):
    boost("config", "set", "security.enforce_digest", "true")
    boost("cat", installed)          # untouched — enforcement must not block it


def test_reinstall_restores_and_unblocks(boost, installed):
    _tamper(installed)
    boost("config", "set", "security.enforce_digest", "true")
    boost("cat", installed, expect=1)
    boost("reinstall", installed)    # restores the locked copy
    boost("cat", installed)          # now clean again


# ── commit pinning ───────────────────────────────────────────────────────

def test_pin_commit_records_and_verify_shows_it(boost, installed):
    res = boost("pin", installed, "--commit")
    assert "commit-pinned" in res.out
    entry = lockfile.get_skill(installed)
    assert entry["commit_pin"] == entry["commit"]
    assert "commit-pinned" in boost("verify", installed).out


def test_pin_commit_needs_a_source_commit(boost, installed):
    entry = lockfile.get_skill(installed)
    entry["commit"] = ""
    lockfile.set_skill(installed, entry)
    res = boost("pin", installed, "--commit", expect=1)
    assert "no recorded source commit" in (res.out + res.err)


def test_unpin_releases_the_commit_pin(boost, installed):
    boost("pin", installed, "--commit")
    boost("unpin", installed)
    assert "commit_pin" not in lockfile.get_skill(installed)


def test_drifted_commit_pin_fails_verify(boost, installed):
    boost("pin", installed, "--commit")
    entry = lockfile.get_skill(installed)
    entry["commit"] = "f" * 40
    lockfile.set_skill(installed, entry)
    res = boost("verify", installed, expect=1)
    assert "DRIFTED" in res.out


# ── a row counted as failed must not also carry a passing status ────────
# (docs/roadmap/items/audit-verify-findings.md: verify used to color a row
# "ok" — and, in --json, report status "ok" with no per-row signal at all —
# on the exact row it counted among the failures.)

def test_verify_json_marks_an_ok_status_row_with_missing_fields_as_failed(
        boost, installed):
    entry = lockfile.get_skill(installed)
    del entry["version"]
    entry["installed_at"] = ""
    lockfile.set_skill(installed, entry)
    data = json.loads(boost("verify", installed, "--json", expect=1).out)
    row = data["skills"][0]
    assert row["status"] == "ok"
    assert row["passed"] is False
    assert data["failed"] == 1


def test_verify_json_marks_a_clean_row_as_passed(boost, installed):
    data = json.loads(boost("verify", installed, "--json").out)
    assert data["skills"][0]["passed"] is True


def test_verify_text_does_not_report_ok_alone_as_the_final_verdict(boost,
                                                                    installed):
    # Two rows: one clean, one ok-but-missing-fields — the failure count must
    # name exactly the broken one, not "lock file integrity OK".
    entry = lockfile.get_skill(installed)
    del entry["version"]
    lockfile.set_skill(installed, entry)
    res = boost("verify", expect=1)
    assert "1 of 1 item failed verification" in res.out
    assert "lock file integrity OK" not in res.out
