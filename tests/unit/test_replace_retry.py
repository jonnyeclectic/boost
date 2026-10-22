# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""util.replace: Windows refuses to replace a file a reader holds open."""
from __future__ import annotations

import pytest

from boost_cli.core import util


def _flaky(fails, calls):
    def fake(src, dst):
        calls.append((src, dst))
        if len(calls) <= fails:
            raise PermissionError(5, "Access is denied")
    return fake


@pytest.fixture()
def no_sleep(monkeypatch):
    pauses = []
    monkeypatch.setattr(util.time, "sleep", pauses.append)
    return pauses


def test_windows_waits_out_a_reader(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(util.sys, "platform", "win32")
    monkeypatch.setattr(util.os, "replace", _flaky(2, calls))
    util.replace("a", "b")
    assert calls == [("a", "b")] * 3
    assert no_sleep == [util.REPLACE_PAUSE] * 2


def test_windows_gives_up_after_the_last_attempt(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(util.sys, "platform", "win32")
    monkeypatch.setattr(util.os, "replace", _flaky(99, calls))
    with pytest.raises(PermissionError):
        util.replace("a", "b")
    assert len(calls) == util.REPLACE_ATTEMPTS == 20
    assert len(no_sleep) == util.REPLACE_ATTEMPTS - 1


def test_elsewhere_the_error_is_real(monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(util.sys, "platform", "linux")
    monkeypatch.setattr(util.os, "replace", _flaky(1, calls))
    with pytest.raises(PermissionError):
        util.replace("a", "b")
    assert len(calls) == 1
    assert no_sleep == []


def test_atomic_write_goes_through_it(tmp_path, monkeypatch):
    seen = []
    real = util.replace
    monkeypatch.setattr(util, "replace",
                        lambda s, d: (seen.append(d), real(s, d)))
    util.atomic_write_text(tmp_path / "x.json", "{}\n")
    assert seen == [str(tmp_path / "x.json")]
    assert (tmp_path / "x.json").read_text(encoding="utf-8") == "{}\n"
