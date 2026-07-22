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
