#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Refuse to publish a commit that PyPI already has.

``publish.yml`` checks out ``ref: main`` on purpose: a release ships the tip of
main, not whatever commit happened to fire the trigger. The cost of that choice
is that the trigger and the build can disagree. When two merges land a few
minutes apart, commit A's ``ci`` run fires the release workflow, which resolves
main to B and ships B — and then B's own ``ci`` run fires it a second time, it
resolves main to B again, and B is released twice under two version numbers.
That is how 1.0.282 and 1.0.283 nearly collided; it was avoided by spacing the
two merges by hand, which is not a fix.

"HEAD is already tagged" does NOT identify that case, and gating on it would
break the documented recovery from a failed PyPI upload. That recovery is to
re-run the failed release run: the tag from the first attempt still points at
HEAD, release-drafter resolves the next patch version, and the upload is
retried. A tag-only guard would skip the retry and leave the release stuck.

PyPI is the signal that separates them, because it records what was actually
published rather than what was merely attempted::

    tagged, and that version is on PyPI       -> already shipped, skip
    tagged, and that version is NOT on PyPI   -> a failed upload, retry it
    not tagged                                -> an ordinary release, go

Fails closed. If HEAD is tagged and PyPI cannot be read, this skips: a missed
release is one ``workflow_dispatch`` click away, while a duplicate burns a
version number and publishes identical code twice.

Usage::

    python3 scripts/release_guard.py --project boost-skill-cli

Writes ``proceed=true|false`` to ``$GITHUB_OUTPUT`` and exits 0 whichever way it
decided — "there is nothing to release" is a normal outcome, not a build
failure. The one non-zero exit is 2, for a ``--tag`` argument that is not a
single tag name: there is no verdict to reach on input the caller got wrong,
and exiting 2 fails the guard job, which skips the release job.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence

PYPI = "https://pypi.org/pypi"

# A release tag boost actually cuts: `v1.0.283`. Anything else on the commit
# (`nightly`, a hand-placed marker) says nothing about whether it was published,
# so it is ignored rather than treated as evidence either way.
TAG_RE = re.compile(r"^v?(\d+\.\d+(?:\.\d+)*(?:[.\-+][0-9A-Za-z.\-+]+)?)$")


def version_of(tag: str) -> str | None:
    """The PyPI version a release tag denotes, or None if it is not one."""
    m = TAG_RE.match(tag.strip())
    return m.group(1) if m else None


class TagLookupError(RuntimeError):
    """git could not be asked, or would not say, which tags point at a ref.

    A distinct exception because the one value this must never collapse into
    is the empty list: `decide` reads that as "this commit carries no tag,
    publish it", which is the answer that ships a version twice. Its message
    names the git call that failed, so the reason survives all the way to the
    workflow annotation.
    """


def _git(args: list[str]) -> str:
    """Run a read-only git command, or raise TagLookupError naming it.

    stderr is captured rather than discarded: "exit 128" alone does not
    distinguish "not a git repository" from "bad revision", and the person
    reading a skipped release needs to know which.
    """
    cmd = ["git", *args]
    shown = " ".join(cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as e:
        raise TagLookupError("`%s` could not be run: %s" % (shown, e)) from e
    if proc.returncode != 0:
        raise TagLookupError(
            "`%s` failed (exit %d): %s"
            % (shown, proc.returncode, proc.stderr.strip() or "no stderr"))
    return proc.stdout


def git_tags_at(ref: str = "HEAD") -> list[str]:
    """Tags pointing at `ref`, or raise TagLookupError.

    Raising is the whole point: an unreadable tag list must not be mistaken
    for "no tags, go ahead". `decide` refuses when it is told the lookup
    failed, and an empty list here means git looked and found nothing — a
    genuinely untagged commit, which releases as usual.

    A shallow checkout is the quiet case, because git does not fail on it:
    `git tag --points-at` succeeds and reports nothing from a tag list that
    was never fetched. publish.yml checks out with `fetch-depth: 0  # all tags
    — the guard reads them`; this is what makes that comment load-bearing
    rather than aspirational.
    """
    if _git(["rev-parse", "--is-shallow-repository"]).strip() == "true":
        raise TagLookupError(
            "`git rev-parse --is-shallow-repository` says this is a shallow "
            "checkout, so `git tag --points-at %s` reports a tag list that "
            "was never fetched — check out with fetch-depth: 0" % ref)
    out = _git(["tag", "--points-at", ref])
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def malformed_tags(tags: Sequence[str]) -> list[str]:
    """The `--tag` values that are not a single tag name.

    `--tag "$(git tag --points-at HEAD)"` puts every tag into ONE argument,
    or — with no tags — an empty one. Neither matches TAG_RE, so `decide`
    used to answer "carries no release tag, go ahead": the guard cleared a
    commit its own caller had just told it was tagged. There is nothing to
    decide on input like that, so `main` refuses it.
    """
    return [t for t in tags if len(t.split()) != 1]


def pypi_has(project: str, version: str, attempts: int = 3) -> bool | None:
    """True if `version` of `project` is on PyPI, False if not, None if unknown.

    None is the important third answer: it means PyPI did not tell us, and the
    caller must not read that as "not published".
    """
    url = "%s/%s/%s/json" % (PYPI, project, version)
    # S310 is suppressed on the request below: the URL is built from the
    # constant https PyPI root plus a version already matched against TAG_RE,
    # so there is no caller-controlled scheme to audit.
    req = urllib.request.Request(  # noqa: S310
        url, headers={"Accept": "application/json",
                      "User-Agent": "boost-release-guard"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                if 200 <= resp.status < 300:
                    return True
                # Not reachable through the stock opener (urlopen raises on
                # >= 400 and follows 3xx), which is exactly why it mattered:
                # `return 200 <= resp.status < 300` spelled "a status I do not
                # understand" as False, and False here means "not published,
                # release it". Unknown is None, like every other unknown.
                print("  ! PyPI %s: unexpected HTTP %s" % (version, resp.status))
                return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if attempt == attempts - 1:
                print("  ! PyPI %s: HTTP %s" % (version, e.code))
                return None
        except (urllib.error.URLError, OSError) as e:
            if attempt == attempts - 1:
                print("  ! PyPI %s: %s" % (version, e))
                return None
        time.sleep(2 ** attempt)
    return None


def decide(tags: Sequence[str] | None, project: str,
           probe: Callable[[str, str], bool | None],
           lookup_error: str | None = None) -> tuple[bool, str]:
    """(proceed, reason) for a commit carrying `tags`.

    `tags` is None when the tag list could not be read at all, which is NOT
    the same as an empty list and is the one input that refuses without
    asking PyPI anything: with no tag list there is no version to ask about,
    and "I could not look" must not read as "there was nothing there".
    `lookup_error` carries which git call failed, so the refusal says so.

    Pure apart from `probe`, which is what makes the decision testable without
    touching the network.
    """
    if tags is None:
        return False, ("the tags on this commit could not be read (%s) — "
                       "skipping rather than risk a duplicate release; fix the "
                       "checkout and re-run this workflow, or dispatch it "
                       "manually" % (lookup_error or "reason not recorded"))

    versions = [v for v in (version_of(t) for t in tags) if v]
    if not versions:
        if tags:
            return True, ("no release tag on this commit (ignoring %s)"
                          % ", ".join(sorted(tags)))
        return True, "this commit carries no tag"

    unknown = []
    for version in sorted(versions):
        published = probe(project, version)
        if published:
            return False, ("%s %s is already on PyPI — this commit was released "
                           "by an earlier run" % (project, version))
        if published is None:
            unknown.append(version)

    if unknown:
        # Fails closed: tagged, but PyPI would not say. Skipping is recoverable.
        return False, ("tagged %s but PyPI could not be read — skipping rather "
                       "than risk a duplicate release; re-run this workflow or "
                       "dispatch it manually once PyPI is reachable"
                       % ", ".join(unknown))

    return True, ("tagged %s but not on PyPI — a previous upload did not "
                  "complete, releasing" % ", ".join(sorted(versions)))


def emit(name: str, value: str, path: str | None = None) -> None:
    """Append a step output for GitHub Actions. A no-op off-CI."""
    path = path if path is not None else os.environ.get("GITHUB_OUTPUT", "")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("%s=%s\n" % (name, value))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="boost-skill-cli",
                    help="PyPI project name (default: %(default)s)")
    ap.add_argument("--ref", default="HEAD",
                    help="git ref to inspect (default: %(default)s)")
    ap.add_argument("--tag", action="append", dest="tags", metavar="TAG",
                    help="tag on the commit; repeatable. Defaults to whatever "
                         "`git tag --points-at <ref>` reports.")
    args = ap.parse_args(argv)

    tags: list[str] | None
    lookup_error: str | None = None
    if args.tags is not None:
        bad = malformed_tags(args.tags)
        if bad:
            print("error: --tag takes one tag name, and %s %s not. Pass a "
                  "separate --tag per tag rather than one argument holding "
                  "several."
                  % (", ".join(repr(b) for b in bad),
                     "is" if len(bad) == 1 else "are"))
            return 2
        tags = list(args.tags)
    else:
        try:
            tags = git_tags_at(args.ref)
        except TagLookupError as exc:
            tags, lookup_error = None, str(exc)

    proceed, reason = decide(tags, args.project, pypi_has, lookup_error)

    print("release guard: %s" % reason)
    print("release guard: %s" % ("RELEASE" if proceed else "SKIP"))
    emit("proceed", "true" if proceed else "false")
    if lookup_error is not None:
        # An annotation, not a notice: the guard could not run, which is a
        # different event from "there was nothing to release" and should not
        # sink into a run log alongside every routine skip.
        print("::error title=release guard could not read tags::%s" % reason)
    elif not proceed:
        print("::notice title=release skipped::%s" % reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
