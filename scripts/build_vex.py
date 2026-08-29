#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Render ``docs/vex/openvex.json`` — boost's OpenVEX 0.2.0 feed — from a
human-edited source of truth.

OSPS Baseline ``OSPS-VM-04.02`` asks for exactly this: "While active, any
vulnerabilities in the software components not affecting the project MUST be
accounted for in a VEX document, augmenting the vulnerability report with
non-exploitability details." boost's scanners (CodeQL, gitleaks, zizmor) each
already carry that reasoning inline — a ``# codeql[rule-id]`` suppression
comment, a gitleaks allowlist entry, a ``.github/zizmor.yml`` ignore — but none
of that is a document a consumer can *ingest*. This script is the bridge.

Source of truth is ``docs/vex/statements/*.md``, one Markdown-with-frontmatter
file per VEX statement — the same convention ``scripts/build_roadmap.py`` uses
for ``docs/roadmap/items/*.md``, for the same reason: two loops adding two
different findings touch two different files and merge cleanly. Document-level
identity (author, version, timestamp) lives in the single shared
``docs/vex/meta.md``, edited by hand when a statement is added, changed, or
removed — bump ``version`` and ``timestamp`` together, the same way a package
changelog does. Nothing here reads the wall clock: the output is a pure
function of the committed files, so ``--check`` (and the test suite's
freshness test) can compare it byte-for-byte.

Statement frontmatter:

    ---
    id: quality-trust-fingerprint-not-sensitive   # must equal the filename
    vulnerability: "codeql:py/clear-text-logging-sensitive-data"
    status: not_affected                          # not_affected|affected|fixed|under_investigation
    justification: vulnerable_code_not_present     # required when status is not_affected
    products:                                      # optional; defaults to [DEFAULT_PRODUCT]
      - pkg:pypi/boost-skill-cli
    ---
    Free-text impact statement — why this finding does not affect boost. This
    becomes the OpenVEX statement's `impact_statement` field.

Run:    python3 scripts/build_vex.py            # regenerate docs/vex/openvex.json
Verify: python3 scripts/build_vex.py --check    # fail if it has drifted
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Reuse the repo's stdlib-only frontmatter parser (no new dependency), the same
# way scripts/build_roadmap.py does. Importable without an editable install.
sys.path.insert(0, str(ROOT))
from boost_cli.core import frontmatter  # noqa: E402

VEX_DIR = ROOT / "docs" / "vex"
STATEMENTS_DIR = VEX_DIR / "statements"
META_FILE = VEX_DIR / "meta.md"
OUTPUT_FILE = VEX_DIR / "openvex.json"

CONTEXT = "https://openvex.dev/ns/v0.2.0"
# Same canonical Pages URL as Makefile's BOOST_SITE and
# scripts/post_deploy_smoke.py's DEFAULT_BASE — keep the three in sync.
SITE_BASE = "https://jonnyeclectic.github.io/boost/"
DOC_ID = SITE_BASE + "vex/openvex.json"
DEFAULT_PRODUCT = "pkg:pypi/boost-skill-cli"

VALID_STATUS = ("not_affected", "affected", "fixed", "under_investigation")
# The five OpenVEX justifications for a `not_affected` statement.
VALID_JUSTIFICATION = (
    "component_not_present",
    "vulnerable_code_not_present",
    "vulnerable_code_not_in_execute_path",
    "vulnerable_code_cannot_be_controlled_by_adversary",
    "inline_mitigations_already_exist",
)


class VexError(Exception):
    """A statement or the document metadata is malformed."""


def load_meta() -> dict:
    meta, _ = frontmatter.parse(META_FILE.read_text(encoding="utf-8"))
    for field in ("author", "version", "timestamp"):
        if not meta.get(field):
            raise VexError("%s: missing %r" % (META_FILE.name, field))
    return meta


def load_statements() -> list[dict]:
    """Load and validate every statement, sorted by id for a stable order."""
    statements = []
    for path in sorted(STATEMENTS_DIR.glob("*.md")):
        meta, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        meta["_file"] = path.name
        meta["_body"] = body.strip()
        if not meta.get("id"):
            raise VexError("%s: missing 'id'" % path.name)
        if meta["id"] != path.stem:
            raise VexError(
                "%s: id %r does not match filename" % (path.name, meta["id"]))
        if not meta.get("vulnerability"):
            raise VexError("%s: missing 'vulnerability'" % path.name)
        status = meta.get("status")
        if status not in VALID_STATUS:
            raise VexError("%s: bad status %r" % (path.name, status))
        justification = meta.get("justification")
        if status == "not_affected" and justification not in VALID_JUSTIFICATION:
            raise VexError(
                "%s: status 'not_affected' requires a valid 'justification' "
                "(one of %s)" % (path.name, ", ".join(VALID_JUSTIFICATION)))
        if not meta["_body"]:
            raise VexError(
                "%s: empty impact statement — the body is what makes this "
                "finding reviewable, not just machine-readable" % path.name)
        statements.append(meta)
    statements.sort(key=lambda m: str(m["id"]))
    return statements


def render_statement(meta: dict) -> dict:
    products = meta.get("products") or [DEFAULT_PRODUCT]
    stmt = {
        "vulnerability": {"name": meta["vulnerability"]},
        "products": [{"@id": p} for p in products],
        "status": meta["status"],
    }
    if meta.get("justification"):
        stmt["justification"] = meta["justification"]
    stmt["impact_statement"] = meta["_body"]
    return stmt


def build() -> str:
    meta = load_meta()
    statements = [render_statement(s) for s in load_statements()]
    doc = {
        "@context": CONTEXT,
        "@id": DOC_ID,
        "author": meta["author"],
        "timestamp": meta["timestamp"],
        "version": int(meta["version"]),
        "statements": statements,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate docs/vex/openvex.json from docs/vex/statements/*.md.")
    parser.add_argument(
        "--check", action="store_true",
        help="verify the committed document matches a fresh render; exit 1 on drift.")
    args = parser.parse_args(argv)

    fresh = build()
    if args.check:
        committed = OUTPUT_FILE.read_text(encoding="utf-8") if OUTPUT_FILE.exists() else None
        if committed != fresh:
            print("ERROR: docs/vex/openvex.json is stale — regenerate with\n"
                  "    python3 scripts/build_vex.py\n"
                  "and commit the result (see CONTRIBUTING.md).", file=sys.stderr)
            print("::error::VEX document is stale — run "
                  "`python3 scripts/build_vex.py` and commit", file=sys.stderr)
            return 1
        print("docs/vex/openvex.json is up to date.")
        return 0

    OUTPUT_FILE.write_text(fresh, encoding="utf-8")
    print("wrote %s" % OUTPUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
