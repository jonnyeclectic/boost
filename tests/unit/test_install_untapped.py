# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost install owner/repo:skill` taps an untapped repo, after asking.

`npx skills add owner/repo@skill` installs from any repository in one step,
and skills.sh pages print that spelling. boost answered "no tap named" and
made the user run `boost tap` first. The repo is the fixture tap's real git
repo, reached under a GitHub-shaped name through ``parse_spec``.
"""
from __future__ import annotations

import pytest

from boost_cli.commands import pkg
from boost_cli.core import installplan, registry
from boost_cli.errors import BoostError

REPO = "acme/widgets"


class TestNormalizeSpec:
    @pytest.mark.parametrize("raw, want", [
        ("acme/widgets@jira-integration", "acme/widgets:jira-integration"),
        ("vercel-labs/agent-skills@react-best-practices",
         "vercel-labs/agent-skills:react-best-practices"),
        ("a/b.c@x.y_z-1", "a/b.c:x.y_z-1"),
    ])
    def test_the_npx_spelling_becomes_boosts(self, raw, want):
        assert installplan.normalize_spec(raw) == want

    @pytest.mark.parametrize("raw", [
        "jira-integration", "acme/widgets:jira-integration", "acme/widgets",
        "@scope/pkg", "acme@widgets", "a/b@", "a/b@-x", "-a/b@x",
        "a/b/c@x", "a/b@x y", "user@example.com"])
    def test_everything_else_is_left_alone(self, raw):
        assert installplan.normalize_spec(raw) == raw


class TestUntappedRepo:
    @pytest.fixture
    def taps(self, monkeypatch):
        rows = [registry.Tap(name="Owner/Known", url="https://x/y")]
        monkeypatch.setattr(registry, "list_taps", lambda: rows)
        return rows

    def test_an_untapped_qualifier(self, taps):
        assert installplan.untapped_repo("acme/widgets:x") == "acme/widgets"

    @pytest.mark.parametrize("name", [
        "owner/known:x", "Owner/Known:x", "known:x"])
    def test_a_qualifier_a_tap_answers_to(self, taps, name):
        assert installplan.untapped_repo(name) is None

    @pytest.mark.parametrize("name", [
        "x", "acme/widgets", "acme:x", "acme/widgets:", "../etc:x",
        "./x:y", "a b/c:x"])
    def test_not_a_qualified_repo(self, taps, name):
        assert installplan.untapped_repo(name) is None


@pytest.fixture
def github_named(sandbox, fixture_tap_src, monkeypatch):
    """`acme/widgets` resolves to the local fixture repo, not to GitHub."""
    real = registry.parse_spec

    def parse(spec):
        if spec == REPO:
            return REPO, str(fixture_tap_src)
        return real(spec)
    monkeypatch.setattr(registry, "parse_spec", parse)
    monkeypatch.delenv("BOOST_ASSUME_YES", raising=False)
    return fixture_tap_src


def _tapped() -> list[str]:
    return [t.name for t in registry.list_taps()]


class TestInstallTapsFirst:
    def test_yes_taps_then_installs_only_the_named_skill(self, github_named, capsys):
        assert pkg.cmd_install([REPO + ":jira-integration", "-y"]) == 0
        assert _tapped() == [REPO]
        text = capsys.readouterr().out
        assert "tapped acme/widgets (" in text
        from boost_cli.core import lockfile
        # commit-messages is jira-integration's declared `requires:` in the
        # fixture; nothing else the tap ships is installed.
        assert set(lockfile.installed()) == {"jira-integration",
                                             "commit-messages"}

    def test_the_npx_spelling_works_end_to_end(self, github_named):
        assert pkg.cmd_install([REPO + "@jira-integration", "-y"]) == 0
        assert _tapped() == [REPO]

    def test_assume_yes_answers_the_question(self, github_named, monkeypatch):
        monkeypatch.setenv("BOOST_ASSUME_YES", "1")
        assert pkg.cmd_install([REPO + ":jira-integration"]) == 0
        assert _tapped() == [REPO]

    def test_a_decline_taps_nothing_and_says_how(self, github_named,
                                                 monkeypatch):
        monkeypatch.setattr(pkg.out, "confirm",
                            lambda prompt, default=False, **kw: False)
        with pytest.raises(BoostError) as exc:
            pkg.cmd_install([REPO + ":jira-integration"])
        assert "no tap named 'acme/widgets'" in exc.value.message
        assert _tapped() == []

    def test_the_question_names_the_repo_and_defaults_to_yes(
            self, github_named, monkeypatch):
        asked = []
        monkeypatch.setattr(pkg.out, "confirm", lambda prompt, default=False,
                            **kw: asked.append((prompt, default)) or True)
        assert pkg.cmd_install([REPO + ":jira-integration"]) == 0
        assert asked == [("acme/widgets is not tapped here. Tap it now?",
                          True)]

    def test_one_repo_is_asked_about_once(self, github_named, monkeypatch):
        asked = []
        monkeypatch.setattr(pkg.out, "confirm", lambda prompt, default=False,
                            **kw: asked.append(prompt) or True)
        names = [REPO + ":jira-integration", REPO + "@jira-integration"]
        pkg.cmd_install(names)
        assert len(asked) == 1

    def test_dry_run_taps_nothing(self, github_named, capsys):
        with pytest.raises(BoostError):
            pkg.cmd_install([REPO + ":jira-integration", "--dry-run", "-y"])
        assert "would tap acme/widgets first" in capsys.readouterr().out
        assert _tapped() == []

    def test_a_tapped_repo_is_not_asked_about(self, github_named,
                                              monkeypatch):
        registry.add(REPO)
        monkeypatch.setattr(pkg.out, "confirm", lambda *a, **k: pytest.fail(
            "asked to tap a repo that is already tapped"))
        assert pkg.cmd_install([REPO + ":jira-integration"]) == 0

    def test_a_bare_repo_name_is_not_tapped(self, github_named, monkeypatch):
        monkeypatch.setattr(pkg.out, "confirm", lambda *a, **k: pytest.fail(
            "offered a tap for an unqualified name"))
        with pytest.raises(BoostError):
            pkg.cmd_install([REPO])
        assert _tapped() == []


class TestMcpInstall:
    """`boost_install` cannot ask, so `tap: true` is the user's answer."""

    def _call(self, **args):
        from boost_cli.commands import configuration
        return configuration._tool_install(args)

    def test_without_tap_it_says_whose_call_it_is(self, github_named):
        text, err = self._call(name=REPO + ":jira-integration")
        assert err is True
        assert text == (
            "acme/widgets is not tapped here. Tapping it clones that "
            "repository (its Markdown only) onto this machine. Ask the user; "
            "if they agree, call boost_install again with tap: true, or they "
            "can run `boost tap acme/widgets`.")
        assert _tapped() == []

    @pytest.mark.parametrize("value", ["true", 1, "yes"])
    def test_only_a_json_true_counts(self, github_named, value):
        _text, err = self._call(name=REPO + ":jira-integration", tap=value)
        assert err is True and _tapped() == []

    def test_tap_true_taps_and_installs(self, github_named):
        text, err = self._call(name=REPO + "@jira-integration", tap=True)
        assert err is False
        assert text.splitlines()[0].startswith("tapped acme/widgets (")
        assert _tapped() == [REPO]
        from boost_cli.core import lockfile
        assert "jira-integration" in lockfile.installed()

    def test_tap_is_ignored_for_a_tapped_repo(self, github_named):
        registry.add(REPO)
        text, err = self._call(name=REPO + ":jira-integration", tap=True)
        assert err is False and "tapped acme/widgets (" not in text

    def test_the_schema_declares_tap(self):
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_install")
        assert spec["inputSchema"]["properties"]["tap"]["type"] == "boolean"
        assert "tap" not in spec["inputSchema"]["required"]
