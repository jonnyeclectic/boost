#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Refuse to release a commit whose sibling release gates are not green.

``publish.yml`` triggers on ``workflow_run: [ci]``, so the only verdict it can
see is ci's own. ``pip-audit.yml`` (live-CVE audit of the dependency closure)
and ``package-metadata.yml`` (``twine check --strict`` + wheel contents) are
independent workflows fired by the same push to main — a merge that failed
either one still auto-published to PyPI as long as ci itself was green.

This waits for every required workflow to finish for the exact commit being
released and exits non-zero unless all of them succeeded::

  python3 scripts/release_preflight.py --repo owner/name --sha "$(git rev-parse HEAD)" \\
      --require pip-audit.yml --require package-metadata.yml

Stdlib only, and deliberately fails closed. A workflow that never ran for this
sha, one still running when the deadline passes, an unreadable API reply, and a
run that concluded anything other than ``success`` are all failures: a release
gate that answers "green" when it does not know is worse than no gate at all.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"

PASS, FAIL, PENDING = "pass", "fail", "pending"


def api_get(path: str, token: str, attempts: int = 3):
    """GET a JSON path from the GitHub API, retrying transient failures.

    Returns the decoded body, or None if every attempt failed — the caller
    treats that as "not known yet", never as "green".
    """
    # S310 is suppressed below because the URL is built from a constant https
    # API root, never from caller-supplied input — there is no scheme to audit.
    req = urllib.request.Request(  # noqa: S310
        API + path,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + token,
                 "User-Agent": "boost-release-preflight"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError, OSError) as err:
            if attempt == attempts - 1:
                print("  ! %s: %s" % (path, err))
                return None
            time.sleep(2 ** attempt)
    return None


def evaluate(payload):
    """Classify the newest run in an Actions ``/runs`` payload.

    Returns ``(PASS|FAIL|PENDING, detail)``. Anything the API did not clearly
    say was a success is PENDING (keep waiting) or FAIL (stop now) — there is
    no branch here that turns "no data" into "go ahead".
    """
    if not isinstance(payload, dict):
        return PENDING, "no readable reply from the API yet"
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list) or not runs:
        return PENDING, "no run recorded for this commit yet"
    run = runs[0]
    if not isinstance(run, dict):
        return PENDING, "malformed run entry"
    status = run.get("status")
    url = run.get("html_url") or ""
    if status != "completed":
        return PENDING, "%s (%s)" % (status or "unknown status", url)
    conclusion = run.get("conclusion")
    if conclusion == "success":
        return PASS, url
    if conclusion == "skipped":
        # Fail closed, but say why: a gate that does not run cannot vouch for
        # the commit, and silently treating that as consent is exactly the hole
        # this script exists to close.
        return FAIL, ("concluded 'skipped' — a required release gate that does "
                      "not run cannot vouch for this commit; remove its path "
                      "filter or drop it from --require (%s)" % url)
    return FAIL, "concluded %r (%s)" % (conclusion, url)


def wait_for_gates(repo, sha, workflows, fetch, sleep=time.sleep,
                   clock=time.monotonic, timeout=1800.0, interval=15.0,
                   log=print) -> int:
    """Poll each required workflow until all pass, one fails, or time runs out.

    ``fetch(path)`` is injected so the polling logic is testable without a
    network. Returns a process exit code.
    """
    pending = list(workflows)
    passed, failed = {}, {}
    deadline = clock() + timeout
    while pending:
        for name in list(pending):
            path = ("/repos/%s/actions/workflows/%s/runs?head_sha=%s&per_page=20"
                    % (repo, urllib.parse.quote(name), urllib.parse.quote(sha)))
            verdict, detail = evaluate(fetch(path))
            if verdict is PASS:
                pending.remove(name)
                passed[name] = detail
                log("  ok   %s" % name)
            elif verdict is FAIL:
                pending.remove(name)
                failed[name] = detail
                log("  FAIL %s — %s" % (name, detail))
            else:
                log("  ...  %s — %s" % (name, detail))
        if failed:
            break
        if not pending:
            break
        if clock() >= deadline:
            for name in pending:
                failed[name] = ("still not conclusive after %ds — a release "
                                "gate that never reported cannot be assumed "
                                "green" % int(timeout))
                log("  FAIL %s — %s" % (name, failed[name]))
            break
        sleep(interval)

    if failed:
        log("")
        log("refusing to release %s: %d of %d release gates did not pass"
            % (sha[:10], len(failed), len(workflows)))
        for name in sorted(failed):
            log("  - %s: %s" % (name, failed[name]))
        return 1
    log("")
    log("all %d release gates green for %s" % (len(workflows), sha[:10]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Block a release unless the sibling gate workflows passed "
                    "for this commit.")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"),
                    help="owner/name (defaults to $GITHUB_REPOSITORY)")
    ap.add_argument("--sha", required=True, help="commit being released")
    ap.add_argument("--require", action="append", default=[], metavar="WORKFLOW",
                    help="workflow file name, e.g. pip-audit.yml (repeatable)")
    ap.add_argument("--timeout-seconds", type=float, default=1800.0)
    ap.add_argument("--poll-seconds", type=float, default=15.0)
    args = ap.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repo:
        print("error: --repo or $GITHUB_REPOSITORY is required")
        return 2
    if not args.require:
        # No list means nothing was checked. Say so loudly rather than exit 0
        # and read as a green gate in the release log.
        print("error: --require was not given, so no release gate was checked")
        return 2
    if not token:
        print("error: $GITHUB_TOKEN is required to read workflow runs")
        return 2

    print("release preflight for %s @ %s" % (args.repo, args.sha[:10]))
    return wait_for_gates(
        args.repo, args.sha, args.require,
        fetch=lambda path: api_get(path, token),
        timeout=args.timeout_seconds, interval=args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
