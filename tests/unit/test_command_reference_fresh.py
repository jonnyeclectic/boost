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


@_skip
def test_every_command_builds_a_parser():
    # missing_help() walks the parsers each command builds; a command whose
    # parser the spy never saw would make the check below pass vacuously.
    builder = _load_builder()
    from boost_cli import cli

    for name, _group, module, _summary in cli.COMMANDS:
        assert builder._capture_parsers(name, module), name


@_skip
def test_every_argument_has_help_text():
    """No positional, option or sub-command of any command ships with an
    empty help string. `test --help` used to end at a bare `NAME`, and
    `conflict --help` at a bare `--json`; 38 arguments across 33 commands
    rendered as `<code>name</code><span></span>` in docs/commands.html."""
    builder = _load_builder()
    bare = builder.missing_help()
    assert bare == [], "arguments with no help text:\n  " + "\n  ".join(bare)


@_skip
def test_missing_help_walks_every_command(monkeypatch):
    # The sweep above passes just as green if missing_help() stops early
    # (`cli.COMMANDS[:40]`), so pin the walk itself: every command is visited,
    # in order, and a bare argument on the last one is still reported.
    builder = _load_builder()
    from boost_cli import cli

    names = [name for name, _group, _module, _summary in cli.COMMANDS]
    walked: list[str] = []

    def spy(name, _module):
        walked.append(name)
        if name != names[-1]:
            return []
        p = argparse.ArgumentParser(prog="boost %s" % name)
        p.add_argument("--bare", action="store_true")
        return [p]

    monkeypatch.setattr(builder, "_capture_parsers", spy)
    assert builder.missing_help() == ["boost %s: --bare" % names[-1]]
    assert walked == names


@_skip
def test_epilog_is_rendered_after_the_options():
    # `boost cohort --help` ends with a note that membership is a deterministic
    # hash; the page used to drop parser.epilog, so the note was not on it.
    builder = _load_builder()
    rec = builder._extract("cohort", "team", "team",
                           "Controlled skill rollouts & team A/B testing")
    assert rec["epilog"].startswith("Membership is a deterministic hash")
    page = builder.render()
    section = page.split('id="cmd-cohort"', 1)[1].split("</section>", 1)[0]
    assert section.rstrip().endswith(
        '<p class="epilog">%s</p>' % builder.html.escape(rec["epilog"]))


@_skip
def test_no_epilog_renders_no_paragraph():
    builder = _load_builder()
    rec = builder._extract("install", "pkg", "pkg", "Install a skill from a tap registry")
    assert rec["epilog"] == ""
    assert '<p class="epilog"></p>' not in builder.render()


@_skip
def test_epilog_is_escaped(monkeypatch):
    builder = _load_builder()
    p = argparse.ArgumentParser(prog="boost cohort", epilog="  a < b & c  ")
    monkeypatch.setattr(builder, "_capture_parser",
                        lambda name, module: p if name == "cohort" else None)
    assert '<p class="epilog">a &lt; b &amp; c</p>' in builder.render()


@_skip
def test_check_fails_when_an_argument_has_no_help(monkeypatch, capsys):
    builder = _load_builder()
    monkeypatch.setattr(builder, "missing_help", lambda: ["boost x: NAME"])
    assert builder.main(["--check"]) == 1
    err = capsys.readouterr().err
    assert "1 argument(s) have no help text" in err
    assert "boost x: NAME" in err


class TestUndocumented:
    """The walker behind the help-text check, against synthetic parsers."""

    def test_documented_parser_is_clean(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        p.add_argument("name", help="skill name")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        assert builder.undocumented(p) == []

    def test_bare_positional_and_option_are_named(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        p.add_argument("names", nargs="*", metavar="NAME")
        p.add_argument("-j", "--json", action="store_true")
        p.add_argument("--ok", action="store_true", help="fine")
        assert builder.undocumented(p) == ["boost x: NAME", "boost x: -j, --json"]

    def test_choices_positional_is_named_by_its_choices(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        p.add_argument("action", choices=("list", "show"))
        assert builder.undocumented(p) == ["boost x: {list,show}"]

    def test_whitespace_only_help_counts_as_empty(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        p.add_argument("name", help="   ")
        assert builder.undocumented(p) == ["boost x: name"]

    def test_help_flag_and_suppressed_arguments_are_skipped(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        p.add_argument("--secret", help=argparse.SUPPRESS)
        assert builder.undocumented(p) == []

    def test_sub_parser_arguments_are_reached(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        sub = p.add_subparsers(dest="action", metavar="ACTION", help="what to do")
        sp = sub.add_parser("status", help="show state")
        sp.add_argument("--json", action="store_true")
        assert builder.undocumented(p) == ["boost x status: --json"]

    def test_sub_command_and_subparsers_without_help_are_named(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        sub = p.add_subparsers(dest="action", metavar="ACTION")
        sub.add_parser("status", help="show state")
        sub.add_parser("apply")
        assert builder.undocumented(p) == ["boost x: ACTION", "boost x: apply"]

    def test_alias_is_not_reported_as_its_own_sub_command(self):
        builder = _load_builder()
        p = argparse.ArgumentParser(prog="boost x")
        sub = p.add_subparsers(dest="action", metavar="ACTION", help="what to do")
        sp = sub.add_parser("status", aliases=["st"], help="show state")
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        assert builder.undocumented(p) == []
