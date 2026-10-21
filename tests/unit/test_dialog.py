# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the desktop confirmation dialog the boost:// handler asks with."""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.core import dialog

DISPLAY = {"DISPLAY": ":0"}


def _which(*present):
    return lambda c: "/usr/bin/" + c if c in present else None


class TestSanitize:
    def test_drops_markup_brackets_and_control_chars(self):
        assert dialog.sanitize('a<b>c\nd\te\x7ff"g') == 'abc d e f"g'

    def test_drops_bidi_and_zero_width_and_blanks_c1_controls(self):
        assert dialog.sanitize("a\u202eb\u200bc\x85d\u00e9") == "abc d\u00e9"

    def test_caps_length_with_an_ellipsis(self):
        out = dialog.sanitize("x" * 400)
        assert len(out) == dialog.MAX_PROMPT
        assert out == "x" * (dialog.MAX_PROMPT - 1) + "…"

    def test_exact_cap_is_kept_whole(self):
        assert dialog.sanitize("x" * dialog.MAX_PROMPT) == "x" * dialog.MAX_PROMPT


class TestArgv:
    def test_darwin_passes_the_prompt_as_an_argument_not_source(self):
        argv = dialog.argv_for('install "evil" do shell script?', "Install",
                               "Darwin", which=_which("osascript"))
        assert argv == [
            "osascript", "-e", "on run argv", "-e",
            'display dialog (item 1 of argv) with title "boost" '
            'buttons {"Cancel", (item 2 of argv)} default button "Cancel" '
            'cancel button "Cancel" with icon caution giving up after 120',
            "-e", "end run", 'install "evil" do shell script?', "Install"]

    def test_darwin_without_osascript_is_none(self):
        assert dialog.argv_for("q", "OK", "Darwin", which=_which()) is None

    def test_linux_prefers_zenity_without_markup(self):
        argv = dialog.argv_for("tap <b>x</b>?", "Tap", "Linux",
                               which=_which("zenity", "kdialog"), env=DISPLAY)
        assert argv == ["zenity", "--question", "--no-markup", "--title=boost",
                        "--ok-label=Tap", "--cancel-label=Cancel",
                        "--timeout=120", "--text=tap bx/b?"]

    def test_linux_falls_back_to_kdialog(self):
        argv = dialog.argv_for("q", "Tap", "Linux", which=_which("kdialog"),
                               env={"WAYLAND_DISPLAY": "wayland-0"})
        assert argv == ["kdialog", "--title", "boost", "--yes-label", "Tap",
                        "--no-label", "Cancel", "--yesno", "q"]

    def test_linux_with_no_display_is_none(self):
        assert dialog.argv_for("q", "OK", "Linux", which=_which("zenity"),
                               env={}) is None

    def test_linux_with_no_tool_is_none(self):
        assert dialog.argv_for("q", "OK", "Linux", which=_which(),
                               env=DISPLAY) is None

    def test_other_platforms_are_none(self):
        assert dialog.argv_for("q", "OK", "Windows",
                               which=_which("osascript", "zenity"),
                               env=DISPLAY) is None


class TestAnsweredYes:
    OSA = ("osascript",)

    def test_osascript_needs_the_ok_button(self):
        assert dialog.answered_yes(list(self.OSA), "Install", 0,
                                   "button returned:Install, gave up:false\n")
        assert not dialog.answered_yes(list(self.OSA), "Install", 0,
                                       "button returned:Tap\n")

    def test_osascript_timeout_is_no(self):
        assert not dialog.answered_yes(
            list(self.OSA), "Install", 0, "button returned:Install, gave up:true")

    def test_osascript_cancel_is_no(self):
        assert not dialog.answered_yes(list(self.OSA), "Install", 1,
                                       "button returned:Install")

    @pytest.mark.parametrize("rc,want", [(0, True), (1, False), (5, False),
                                         (-1, False)])
    def test_zenity_and_kdialog_go_by_exit_code(self, rc, want):
        assert dialog.answered_yes(["zenity"], "Tap", rc, "") is want
        assert dialog.answered_yes(["kdialog"], "Tap", rc, "") is want


class TestAsk:
    def test_none_when_nothing_can_ask(self):
        def run(*a, **k):
            raise AssertionError("must not run")
        assert dialog.ask("q", "OK", "Linux", which=_which(), run=run,
                          env=DISPLAY) is None

    def test_runs_the_dialog_and_reads_the_answer(self):
        seen = {}

        def run(argv, **kw):
            seen["argv"], seen["kw"] = argv, kw
            return subprocess.CompletedProcess(argv, 0, "", "")
        assert dialog.ask("q", "Tap", "Linux", which=_which("zenity"),
                          run=run, env=DISPLAY) is True
        assert seen["argv"][0] == "zenity"
        assert seen["kw"] == {"capture_output": True, "text": True,
                              "encoding": "utf-8", "errors": "replace",
                              "timeout": dialog.TIMEOUT + 30}

    def test_a_decline_is_false(self):
        def run(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, None, "")
        assert dialog.ask("q", "Tap", "Linux", which=_which("zenity"),
                          run=run, env=DISPLAY) is False

    @pytest.mark.parametrize("exc", [OSError("gone"),
                                     subprocess.TimeoutExpired("zenity", 1)])
    def test_a_dialog_that_fails_to_run_is_a_decline(self, exc):
        def run(argv, **kw):
            raise exc
        assert dialog.ask("q", "Tap", "Linux", which=_which("zenity"),
                          run=run, env=DISPLAY) is False
