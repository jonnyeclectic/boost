# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost update` with no git on PATH says so once, and advises no untap.

Each tap used to fail on its own: N copies of "git is required", then a
summary telling the user to `boost untap` every healthy tap, then a green
"everything up to date, except the taps above".
"""
from __future__ import annotations

from boost_cli.core import config, registry


def _no_git(monkeypatch, tmp_path):
    empty = tmp_path / "no-git-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


def test_one_install_git_error(boost, rival_tap, monkeypatch, tmp_path):
    _no_git(monkeypatch, tmp_path)
    r = boost("update", expect=1)
    text = r.out + r.err
    assert text.count("git is required but was not found on PATH") == 1
    assert "install git, e.g. `xcode-select --install` or `brew install git`" in text
    assert "untap" not in text
    assert "up to date" not in text
    r = boost("update", "--taps-only", expect=1)
    assert (r.out + r.err).count("git is required") == 1


def test_a_pinned_clone_needs_no_git(boost, tapped, monkeypatch, tmp_path):
    cfg = config.load()
    for row in cfg["taps"]:
        row["pin"] = "0" * 40
    config.save(cfg)
    _no_git(monkeypatch, tmp_path)
    results, failures = registry.update()
    assert failures == {}
    assert list(results.values()) == ["pinned at 0000000 (skipped)"]


def test_force_moves_a_pinned_clone_so_it_needs_git(boost, tapped,
                                                    monkeypatch, tmp_path):
    cfg = config.load()
    for row in cfg["taps"]:
        row["pin"] = "0" * 40
    config.save(cfg)
    tap = registry.list_taps()[0]
    assert registry._update_needs_git(tap, force=False) is False
    assert registry._update_needs_git(tap, force=True) is True
    _no_git(monkeypatch, tmp_path)
    r = boost("update", "--force", expect=1)
    assert (r.out + r.err).count("git is required") == 1


def test_a_missing_clone_needs_git_even_pinned(boost, tapped):
    from boost_cli.core import util
    cfg = config.load()
    for row in cfg["taps"]:
        row["pin"] = "0" * 40
    config.save(cfg)
    tap = registry.list_taps()[0]
    util.rmtree(tap.path)
    assert registry._update_needs_git(registry.list_taps()[0], False) is True


def test_the_wheel_tap_needs_no_git(sandbox):
    tap = registry.Tap(name="boost", url=registry.WHEEL_SCHEME + "boost")
    assert registry._update_needs_git(tap, force=False) is False
    assert registry._update_needs_git(tap, force=True) is False
    assert registry._update_needs_git(
        registry.Tap(name="x", url="https://example.invalid/x"), False) is True
