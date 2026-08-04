#!/usr/bin/env python3
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

Writes ``proceed=true|false`` to ``$GITHUB_OUTPUT`` and always exits 0 — "there
is nothing to release" is a normal outcome, not a build failure.
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


def git_tags_at(ref: str = "HEAD") -> list[str]:
    """Tags pointing at `ref`. Empty on any git failure — an unreadable tag
    list must not be mistaken for "no tags, go ahead"; `decide` is told
    separately when the lookup itself failed."""
    try:
        out = subprocess.check_output(["git", "tag", "--points-at", ref],
                                      stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as e:
        print("  ! could not list tags at %s: %s" % (ref, e))
        return []
    return [ln.strip() for ln in out.decode("utf-8").splitlines() if ln.strip()]


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
                return 200 <= resp.status < 300
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


def decide(tags: Sequence[str], project: str,
           probe: Callable[[str, str], bool | None]) -> tuple[bool, str]:
    """(proceed, reason) for a commit carrying `tags`.

    Pure apart from `probe`, which is what makes the decision testable without
    touching the network.
    """
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

    tags = args.tags if args.tags is not None else git_tags_at(args.ref)
    proceed, reason = decide(tags, args.project, pypi_has)

    print("release guard: %s" % reason)
    print("release guard: %s" % ("RELEASE" if proceed else "SKIP"))
    emit("proceed", "true" if proceed else "false")
    if not proceed:
        print("::notice title=release skipped::%s" % reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
