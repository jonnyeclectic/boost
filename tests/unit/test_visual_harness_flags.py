"""Unit tests: the Chrome flags the two headless sweeps launch with.

`tests/visual/` holds two puppeteer harnesses that drive the same binary on the
same runner — `visual_check.mjs` (render regression) and `a11y_check.mjs`
(axe-core). They must agree about `--single-process`, and for two days they did
not.

`--single-process` exists for one reason: `chrome-headless-shell` is the only
binary that starts under a macOS sandbox denying Mach port rendezvous, and it
needs the flag to get there. On CI the binary is `/usr/bin/google-chrome`, where
the flag is debug-only and unsupported. `a11y_check.mjs` was fixed to scope it to
the shell binary and its comment recorded that `visual_check.mjs` still passed it
unconditionally — that prediction came true when the runner image bumped Chrome:

    TargetCloseError: Protocol error (Target.setAutoAttach): Target closed
        at ChromeLauncher.launch (…/ChromeLauncher.js:39:16)

The browser died during the CDP startup handshake, so `sweep` failed before a
single page loaded — on every branch and on `main`. The tell that it was the
environment and not the repo: #515's own PR run passed on 2026-08-13 and the
byte-identical squash-merge failed on 2026-08-15.

These tests are the ratchet. The flag stays available for the sandbox that needs
it, and neither harness may hand it to a full Chrome again.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HARNESSES = {
    "visual_check.mjs": ROOT / "tests" / "visual" / "visual_check.mjs",
    "a11y_check.mjs": ROOT / "tests" / "visual" / "a11y_check.mjs",
}

#: Flags that only ever belong to the sandboxed `chrome-headless-shell` run.
#: `--in-process-gpu` is here because it is half of the same workaround — it
#: pairs with `--single-process` and is equally pointless against full Chrome.
SANDBOX_ONLY_FLAGS = ("--single-process", "--in-process-gpu")


def _source(name: str) -> str:
    path = HARNESSES[name]
    assert path.is_file(), "%s is missing" % path
    return path.read_text(encoding="utf-8")


def _code_lines(src: str) -> list[str]:
    """Source lines with `//` comments dropped.

    The flag is *named* in prose in both files — that is the documentation, not
    an invocation, and asserting over raw text would fail on the comment that
    explains the rule.
    """
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        out.append(line.split("//", 1)[0])
    return out


@pytest.mark.parametrize("name", sorted(HARNESSES))
class TestSandboxFlagsAreConditional:
    def test_no_sandbox_only_flag_is_passed_unconditionally(self, name):
        """A bare flag in the args array is what broke CI for two days."""
        for line in _code_lines(_source(name)):
            for flag in SANDBOX_ONLY_FLAGS:
                if flag not in line:
                    continue
                assert "?" in line or "&&" in line, (
                    "%s passes %s unconditionally (%r) — on CI the binary is "
                    "full Chrome, where it kills the browser at launch"
                    % (name, flag, line.strip()))

    def test_the_guard_is_keyed_on_the_shell_binary(self, name):
        """Scoped by *binary*, not by platform: what needs the flag is
        `chrome-headless-shell`, and a macOS runner using full Chrome must not
        inherit it."""
        src = _source(name)
        if not any(f in src for f in SANDBOX_ONLY_FLAGS):
            pytest.skip("%s passes no sandbox-only flag" % name)
        assert re.search(r"/chrome\[-_\]headless\[-_\]shell/\.test\(bin\)", src), (
            "%s gates the flag on something other than the shell binary — "
            "`process.platform` is the tempting wrong answer, because a macOS "
            "run pointed at full Chrome would then inherit it" % name)

    def test_ci_binary_path_is_still_a_candidate(self, name):
        """The guard is only meaningful while CI really does use full Chrome."""
        assert "/usr/bin/google-chrome" in _source(name)


class TestTheTwoHarnessesAgree:
    """They drive the same binary on the same runner in the same job."""

    def test_both_use_the_same_predicate(self):
        preds = {}
        for name in HARNESSES:
            src = _source(name)
            m = re.search(r"=\s*(/chrome.*?/)\.test\(bin\)", src)
            preds[name] = m.group(1) if m else None
        assert len(set(preds.values())) == 1, (
            "the harnesses disagree about which binary needs the flag: %r"
            % preds)
        assert all(preds.values()), (
            "a harness has no shell-binary predicate at all: %r" % preds)

    def test_neither_hands_a_sandbox_flag_to_full_chrome(self):
        """The end state, stated once over both files."""
        offenders = [
            (name, line.strip())
            for name in HARNESSES
            for line in _code_lines(_source(name))
            for flag in SANDBOX_ONLY_FLAGS
            if flag in line and "?" not in line and "&&" not in line
        ]
        assert not offenders, offenders
