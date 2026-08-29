# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: a workflow that pushes has credentials to push with.

``actions/checkout`` with ``persist-credentials: false`` leaves no auth in the
remote — which is the right default, and what zizmor's ``artipacked`` rule asks
for. A later bare ``git push origin`` in the same job therefore cannot work.

``eval-stats.yml`` had exactly that pair. It regenerates
``docs/eval-latest.json`` — the payload the docs site reads — commits it, and
pushes. The proof that it never landed is in the file's own history: **one
commit, ever**, the one that created it. Every scheduled refresh since has
either found nothing to commit or died on the push.

It is the same silence as ``shards`` and ``fuzz``: a workflow that looks like a
control and produces nothing, on a cron nobody watches. The run even reports
*success* when there is nothing to commit, so the conclusion column cannot
distinguish "no drift" from "cannot publish".

``ci.yml`` already had the fix in the repo — it pushes its badges branch with an
explicit ``x-access-token`` URL, keeping the safe checkout default *and* being
able to push. This test pins the pairing so the two halves cannot drift apart
again in either direction.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

pytestmark = pytest.mark.skipif(
    not WORKFLOWS.exists(),
    reason=".github/workflows not reachable (e.g. mutation sandbox)")

#: A push that carries its own credentials, rather than relying on the ones the
#: checkout deliberately did not persist.
_AUTHED_PUSH = re.compile(r"git push[^\n]*(x-access-token|\$\{\{\s*secrets\.|"
                          r"\$\{\{\s*github\.token|GITHUB_TOKEN|GH_TOKEN)")
_ANY_PUSH = re.compile(r"^\s*git push\b", re.M)


def join_continuations(text: str) -> str:
    """Fold shell line-continuations, so one command is one line.

    A push long enough to need credentials in its URL is a push long enough to
    be wrapped, and matching per physical line would read the token on the next
    line as absent — failing a workflow that is correct. Folding first is what
    the shell itself does.
    """
    return re.sub(r"\\\n\s*", " ", text)


def pushing_workflows() -> dict[str, str]:
    """``{file name: folded text}`` for every workflow containing a git push."""
    out = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = join_continuations(path.read_text(encoding="utf-8"))
        if _ANY_PUSH.search(text):
            out[path.name] = text
    return out


class TestTheGuardCanActuallySee:
    def test_at_least_one_workflow_pushes(self):
        # Otherwise every assertion below is vacuous.
        assert pushing_workflows(), "no workflow matched a git push"

    def test_an_authed_push_is_recognised(self):
        line = ('git push -qf "https://x-access-token:${{ github.token }}'
                '@github.com/${{ github.repository }}" badges:badges')
        assert _AUTHED_PUSH.search(line)

    def test_a_bare_push_is_not_recognised_as_authed(self):
        assert not _AUTHED_PUSH.search("          git push origin HEAD:main")

    def test_a_wrapped_authed_push_is_recognised(self):
        # The shape the fix actually takes: a token URL is too long for one
        # line, so without folding the continuation this guard would fail a
        # workflow that is correct.
        wrapped = ('          git push -q \\\n'
                   '            "https://x-access-token:${{ github.token }}'
                   '@github.com/${{ github.repository }}" \\\n'
                   '            HEAD:main\n')
        assert _AUTHED_PUSH.search(join_continuations(wrapped))


#: `HEAD:main`, `HEAD:refs/heads/main`, or a bare push whose refspec is main.
_PUSHES_TO_MAIN = re.compile(r"git push[^\n]*\b(HEAD|[\w./-]+):(refs/heads/)?main\b")


class TestNothingPushesToMain:
    """Credentials were only the first layer; the branch is the second.

    Fixing the missing token got `eval-stats` as far as a *different* permanent
    failure — `GH013: Repository rule violations found for refs/heads/main`.
    main carries a ruleset with a `pull_request` rule and an **empty bypass
    list**, so no token can push to it: not `github.token`, not a PAT, not any
    bot. A workflow that pushes there is not misconfigured, it is impossible.

    The remedy is never to add a bypass actor. That would open the protection
    guarding every change to main so a docs payload can skip review. `ci.yml`
    pushes `badges:badges` and `eval-stats.yml` now pushes `eval-metrics`;
    merging either into main stays a pull request, like everything else.
    """

    def test_the_guard_recognises_a_push_to_main(self):
        for line in ("git push -q origin HEAD:main",
                     'git push -q "https://x@github.com/o/r" HEAD:refs/heads/main',
                     "git push origin main:main"):
            assert _PUSHES_TO_MAIN.search(line), line

    def test_the_guard_does_not_flag_a_side_branch(self):
        for line in ("git push -qf origin badges:badges",
                     'git push -qf "https://x@github.com/o/r" HEAD:eval-metrics'):
            assert not _PUSHES_TO_MAIN.search(line), line

    @pytest.mark.parametrize("name", sorted(pushing_workflows()))
    def test_no_workflow_pushes_to_main(self, name):
        hits = [line.strip() for line in pushing_workflows()[name].splitlines()
                if _PUSHES_TO_MAIN.search(line)]
        assert not hits, (
            "%s pushes to main, which main's ruleset forbids for every token "
            "(GH013). Push to a side branch and open a pull request; do NOT "
            "add a bypass actor to the ruleset: %s" % (name, hits))


@pytest.mark.parametrize("name", sorted(pushing_workflows()))
def test_a_push_after_an_unpersisted_checkout_carries_a_token(name):
    text = pushing_workflows()[name]
    if "persist-credentials: false" not in text:
        pytest.skip("%s keeps the checkout credentials" % name)
    bare = [line.strip() for line in text.splitlines()
            if _ANY_PUSH.match(line) and not _AUTHED_PUSH.search(line)]
    assert not bare, (
        "%s checks out with persist-credentials: false — so the remote has no "
        "auth — and then pushes without supplying any: %s. eval-stats.yml did "
        "exactly this and never once refreshed docs/eval-latest.json; the "
        "file has one commit in its whole history. ci.yml shows the fix: push "
        "to an explicit x-access-token URL." % (name, bare))
