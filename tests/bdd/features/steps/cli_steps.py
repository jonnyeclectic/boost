"""Shared Given/When/Then step library — drives boost_cli.cli.main in-process.

Mirrors tests/conftest.py's `boost()` fixture, but there's no capsys in
behave, so stdout/stderr are captured via contextlib.redirect_*.
"""
from __future__ import annotations

import contextlib
import io
import re
import shlex
import sys

from behave import given, then, when

from boost_cli.cli import main as boost_main


def _run(context, argv):
    argv = [str(a) for a in argv]
    out_buf, err_buf = io.StringIO(), io.StringIO()
    rc = 0
    # Swap stdin too (not just stdout/stderr) so isatty() checks (e.g. `boost
    # browse`'s TTY probe) deterministically see a non-interactive terminal,
    # regardless of how behave itself was invoked.
    old_stdin = sys.stdin
    sys.stdin = io.StringIO()
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            try:
                rc = boost_main(argv)
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 0
    finally:
        sys.stdin = old_stdin
    context.rc = int(rc or 0)
    context.out = out_buf.getvalue()
    context.err = err_buf.getvalue()
    context.combined = context.out + context.err
    return context.rc


def _parse_command(command: str):
    tokens = shlex.split(command)
    if tokens and tokens[0] == "boost":
        tokens = tokens[1:]
    return tokens


@given("a fresh boost environment")
def step_fresh_environment(context):
    # environment.py's before_scenario already points HOME at a fresh
    # sandbox and sets the deterministic env vars for every scenario.
    assert context._home.is_dir()


@given("the fixture tap is added")
def step_fixture_tap_added(context):
    if getattr(context, "_tapped", False):
        return
    rc = _run(context, ["tap", str(context.fixture_tap_src)])
    assert rc == 0, "boost tap failed:\n%s" % context.combined
    context._tapped = True


@given('the "{name}" skill is installed')
def step_skill_installed(context, name):
    step_fixture_tap_added(context)
    rc = _run(context, ["install", name])
    assert rc == 0, "boost install %s failed:\n%s" % (name, context.combined)


@when('I run "{command}"')
def step_run_command(context, command):
    _run(context, _parse_command(command))


@then("the exit code should be {code:d}")
def step_exit_code(context, code):
    assert context.rc == code, (
        "rc=%d (want %d)\n--- stdout ---\n%s--- stderr ---\n%s"
        % (context.rc, code, context.out, context.err))


@then('the output should contain "{text}"')
def step_output_contains(context, text):
    assert text in context.combined, (
        "expected %r in output:\n%s" % (text, context.combined))


@then('the output should contain wrapped "{text}"')
def step_output_contains_wrapped(context, text):
    """Match a hint that is wrapped to the pane, ignoring where it broke.

    Deliberately a separate step rather than whitespace-collapsing inside
    `the output should contain` — that one is used ~87 times across eleven
    feature files, and collapsing there would quietly weaken every one of them,
    including assertions about lines and columns.
    """
    flat = " ".join(context.combined.split())
    assert text in flat, (
        "expected %r in wrapped output:\n%s" % (text, context.combined))


@then('the output should not contain "{text}"')
def step_output_not_contains(context, text):
    assert text not in context.combined, (
        "did not expect %r in output:\n%s" % (text, context.combined))


@then('the output should match "{pattern}"')
def step_output_matches(context, pattern):
    # behave's parser doesn't unescape \" inside a quoted {param} — a literal
    # backslash-quote survives into `pattern`. Used as a regex that's harmless
    # (\" == a literal ") so this doubles as the escape hatch for asserting
    # text that itself contains double quotes, e.g. `name=\"x\"`.
    assert re.search(pattern, context.combined), (
        "expected /%s/ to match output:\n%s" % (pattern, context.combined))
