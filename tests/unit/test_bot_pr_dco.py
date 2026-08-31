# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a bot-opened PR must pass the DCO gate it will be graded by.

Five workflows open pull requests with `peter-evans/create-pull-request`:
`demo`, `eval-scale`, `eval-corpus-refresh`, `eval-stats` and `lock-refresh`.
That action's `author` input **defaults to `${{ github.actor }}`** — the human
whose push triggered the run — while its `committer` defaults to the bot. So
the commit arrives authored by a person who never wrote it and never signed off
on it, and `scripts/check_dco.py`, which deliberately matches the sign-off
against the commit's *own author*, fails the PR the workflow just opened.

That is what happened to #617, and the shape of the failure is why this test
exists rather than a comment: every one of these workflows is scheduled or
push-triggered, so the break lands on a branch nobody is watching, hours after
the change that caused it, in a PR whose whole purpose was to be routine. And
no human can fix it by signing off — the trailer has to name the author, and
the author did not write the content.

Naming the bot is the honest fix, not a workaround: `check_dco.EXEMPT_NAMES`
exempts `github-actions[bot]` precisely because an account that cannot agree to
a certificate must not be asked for one. This test asserts against
`check_dco`'s own predicate rather than a copied string, so tightening the
exemption list can never leave these workflows passing a rule they no longer
satisfy.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DCO = ROOT / "scripts" / "check_dco.py"

pytestmark = pytest.mark.skipif(
    not WORKFLOWS.is_dir() or not DCO.exists(),
    reason="repo-root .github/scripts not reachable (e.g. mutation sandbox)")

ACTION = "peter-evans/create-pull-request"


def _check_dco():
    spec = importlib.util.spec_from_file_location("check_dco_for_workflows", DCO)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _pr_steps() -> list[tuple[str, dict]]:
    """Every create-pull-request step in the repo, as (workflow file, `with`)."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job in (data.get("jobs") or {}).values():
            found.extend(
                (path.name, step.get("with") or {})
                for step in (job or {}).get("steps") or []
                if ACTION in str((step or {}).get("uses", "")))
    return found


def _split(spec: str) -> tuple[str, str]:
    """`Display Name <email>` -> (name, email), the format the action takes."""
    name, _, rest = spec.partition("<")
    return name.strip(), rest.rstrip(">").strip()


class TestEveryBotPullRequestPassesTheDcoGate:
    def test_the_workflows_that_open_prs_are_still_found(self):
        # If this drops to zero the rest of the file passes vacuously, which is
        # the failure mode a "for each step" test has by construction.
        names = sorted({w for w, _ in _pr_steps()})
        assert len(names) >= 5, names

    @pytest.mark.parametrize("workflow,With", _pr_steps(),
                             ids=[w for w, _ in _pr_steps()])
    def test_the_author_is_named_and_not_left_to_the_triggering_human(
            self, workflow, With):
        assert "author" in With, (
            "%s leaves `author` unset, so it defaults to ${{ github.actor }} "
            "and the bot's commit is authored by whoever pushed — check_dco "
            "then fails the PR this workflow just opened (#617)" % workflow)
        assert "github.actor" not in With["author"], With["author"]

    @pytest.mark.parametrize("workflow,With", _pr_steps(),
                             ids=[w for w, _ in _pr_steps()])
    def test_that_author_is_one_check_dco_actually_exempts(self, workflow, With):
        # Asserted against check_dco's own predicate, not a copy of the string:
        # the two must not be able to drift apart silently.
        name, email = _split(With.get("author", ""))
        assert _check_dco()._exempt(name, email), (
            "%s authors its bot commit as %r <%s>, which check_dco does not "
            "exempt — it would need a Signed-off-by from that identity"
            % (workflow, name, email))

    @pytest.mark.parametrize("workflow,With", _pr_steps(),
                             ids=[w for w, _ in _pr_steps()])
    def test_the_commit_is_signed(self, workflow, With):
        # `sign-commits` has GitHub build and sign the commit through its API,
        # so these land Verified instead of unsigned. Separate property from the
        # DCO fix above — a signed commit authored by the human would still fail
        # the gate, and an unsigned bot commit would still pass it.
        assert With.get("sign-commits") is True, (
            "%s does not set `sign-commits: true`" % workflow)


class TestTheDefaultIsRecordedAsTheBug:
    """Without this the fix above reads as an arbitrary preference."""

    def test_the_actions_own_default_author_is_the_triggering_actor(self):
        # Pinned from the action.yml at the SHA the workflows pin, so a future
        # bump that changes the default is noticed here rather than in a red
        # scheduled run. Kept as the *claim*, checked against the vendored
        # workflows: every step must override it.
        for _workflow, With in _pr_steps():
            assert With.get("author"), "an unset author is the bug, not a style"

    def test_a_human_author_would_be_rejected(self):
        # The exact identity from #617's failure. If check_dco ever started
        # exempting real accounts, the fix above would be pointless and this
        # says so out loud.
        mod = _check_dco()
        assert not mod._exempt(
            "jonnyeclectic", "8794867+jonnyeclectic@users.noreply.github.com")
