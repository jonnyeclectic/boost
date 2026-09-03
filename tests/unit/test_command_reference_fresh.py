# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Committed command reference stays in lockstep with the CLI.

``docs/commands.html`` is generated from ``boost_cli.cli.COMMANDS`` and each
command's argparse parser by ``scripts/build_command_reference.py``. This test —
the in-suite twin of the ``build_command_reference.py --check`` CI step — fails
if the committed HTML drifts from a fresh render, so a stale reference (a new
command, a renamed flag) can't merge.

Skips when the repo-root files aren't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "build_command_reference.py"
_OUT = _ROOT / "docs" / "commands.html"

_reachable = _SCRIPT.exists() and _OUT.exists()
_skip = pytest.mark.skipif(
    not _reachable, reason="repo-root files not reachable (e.g. mutation sandbox)")


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_command_reference", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@_skip
def test_command_reference_is_regenerated():
    builder = _load_builder()
    committed = _OUT.read_text(encoding="utf-8")
    assert committed == builder.render(), (
        "docs/commands.html is out of date — regenerate with\n"
        "    python3 scripts/build_command_reference.py\n"
        "and commit the result (see CONTRIBUTING.md)."
    )


@_skip
def test_check_flag_passes_on_fresh_tree():
    builder = _load_builder()
    assert builder.main(["--check"]) == 0


@_skip
def test_every_command_is_documented():
    """Every COMMANDS entry renders exactly one section — no command left out."""
    builder = _load_builder()
    from boost_cli import cli

    html = builder.render()
    for name, _group, _module, _summary in cli.COMMANDS:
        assert ('id="cmd-%s"' % name) in html, "command %r missing from reference" % name
    assert html.count('<section class="cmd"') == len(cli.COMMANDS)


@_skip
def test_extract_captures_flags_and_synopsis():
    """A representative command's structured extraction has its real flags."""
    builder = _load_builder()
    rec = builder._extract("install", "pkg", "pkg", "Install a skill from a tap registry")
    assert rec["synopsis"].startswith("boost install")
    flags = [label for label, _help in rec["options"]]
    assert any(f.startswith("--force") for f in flags)
    assert any(f.startswith("--scope") for f in flags)
    assert rec["positionals"], "install should document its NAME positional"


@_skip
def test_required_option_is_unbracketed_in_synopsis():
    # `adapt --help` prints an unbracketed `--to FRAMEWORK` and omitting it
    # exits 2 — the generator used to bracket it as `[--to FRAMEWORK]`
    # regardless, documenting it as optional when it is not.
    builder = _load_builder()
    rec = builder._extract("adapt", "pkg", "pkg",
                           "Render a skill as another framework's agent source")
    assert "--to FRAMEWORK" in rec["synopsis"]
    assert "[--to FRAMEWORK]" not in rec["synopsis"]


@_skip
def test_required_mutex_group_renders_as_parenthesized_alternation():
    # catalog's --export/--import/--show is a required mutually-exclusive
    # group — none individually required, but exactly one must be given.
    builder = _load_builder()
    rec = builder._extract("catalog", "tap", "taps",
                           "Share the tapped catalogue so others skip the clone")
    assert "(--export FILE | --import FILE | --show FILE)" in rec["synopsis"]


@_skip
def test_non_required_option_stays_bracketed():
    builder = _load_builder()
    rec = builder._extract("install", "pkg", "pkg", "Install a skill from a tap registry")
    assert "[--force]" in rec["synopsis"]


class TestOptSynParts:
    """Direct tests of the synopsis-token builder against synthetic parsers —
    the generator has no unit tests of its own beyond the golden-HTML drift
    check above, so a regression here would only ever surface as a diff in
    generated HTML nobody reads closely."""

    def test_required_solo_option_unbracketed(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        act = p.add_argument("--to", metavar="FRAMEWORK", required=True)
        assert builder._opt_syn_parts(p, [act]) == ["--to FRAMEWORK"]

    def test_optional_solo_option_bracketed(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        act = p.add_argument("--model", metavar="M")
        assert builder._opt_syn_parts(p, [act]) == ["[--model M]"]

    def test_flag_option_prefers_first_declared_string(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        act = p.add_argument("-y", "--yes", action="store_true")
        assert builder._opt_syn_parts(p, [act]) == ["[-y]"]

    def test_required_mutex_group_parenthesized(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        g = p.add_mutually_exclusive_group(required=True)
        a = g.add_argument("--export", metavar="FILE")
        b = g.add_argument("--import", metavar="FILE", dest="import_")
        assert builder._opt_syn_parts(p, [a, b]) == ["(--export FILE | --import FILE)"]

    def test_optional_mutex_group_bracketed(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        g = p.add_mutually_exclusive_group(required=False)
        a = g.add_argument("--local", action="store_true")
        b = g.add_argument("--global", action="store_true", dest="global_")
        assert builder._opt_syn_parts(p, [a, b]) == ["[--local | --global]"]

    def test_mutex_group_action_only_emitted_once(self):
        builder = _load_builder()
        p = argparse.ArgumentParser()
        g = p.add_mutually_exclusive_group(required=True)
        a = g.add_argument("--export", metavar="FILE")
        b = g.add_argument("--import", metavar="FILE", dest="import_")
        c = p.add_argument("--json", action="store_true")
        assert builder._opt_syn_parts(p, [a, b, c]) == \
            ["(--export FILE | --import FILE)", "[--json]"]
