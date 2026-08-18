#!/usr/bin/env python3
"""Materialise the Tier 1 eval corpus at the exact commits it was measured on.

WHY THIS EXISTS. `tests/eval/taps.txt` used to pin repository NAMES. Tapping is
a shallow clone of whatever the default branch points at, so the corpus the
required `eval` gate scores against was a moving target: the list was written
recording **743** entries and the same 20 repos later resolved to **3,843**, a
5.2x growth nobody caused by editing a file. `affaan-m/ECC` alone is 1,616 of
them, so one third-party repository can move the gate's number by itself.

That is not academic. Measured on a clean 20-tap install, BM25 scores recall@10
**0.912** against a floor of **0.85** — a margin of +0.062. Unpinned growth
spends that margin quietly, and the first thing anyone would see is a required
gate failing on a pull request that touched nothing to do with retrieval.

So each row now carries a commit SHA, and this script checks each clone out at
it. `boost tap` still does the cloning (the corpus must be built the way a user
builds one); pinning is a step applied after, because the alternative — teaching
`boost tap` to pin — would add a CLI surface for a test-harness problem.

WHY A ROW ALSO CARRIES AN ENTRY COUNT. A SHA fixes the *tree*; it does not fix
what this project makes of that tree, and it does nothing at all when the tree
cannot be fetched. Both gaps end in the same place — the gate scoring a corpus
that is not the one its floors were set on — and the direction of the error is
the surprise. Measured over the 91-query required set, one repo removed and
everything else identical:

    all 20 repos           10,152 entries   0.852 / 0.473 / 0.605 / 0.657
    minus sickn33 (62%)     3,843 entries   0.885 / 0.593 / 0.711 / 0.746
    minus that and ECC      2,227 entries   0.967 / 0.659 / 0.769 / 0.814
    minus LessUp (targets)  9,682 entries   0.676 / 0.374 / 0.483 / 0.523
    floors                                  0.780 / 0.400 / 0.520 / 0.580

Losing a *scale* repo makes the gate EASIER — all four metrics rise and the
check goes green having measured a third of the intended corpus. Losing a repo
that holds golden targets fails all four floors in a way indistinguishable from
"this pull request broke retrieval". So "skip whichever repos are missing today"
is unsafe in both directions, and the count is what makes the first case
detectable at all: a corpus that does not match its pins stops the run before
anything is scored.

WHY UNAVAILABILITY EXITS 75. `ensure_eval_corpus.sh` runs under `set -euo
pipefail` inside CI's `lint` job, a required context, so one deleted, renamed or
privatised repository reddens every open pull request at once. That is a real
risk for twenty personal repositories, not a hypothetical. Nothing here can keep
a vanished repository available — CI caches the materialised corpus for that —
but the failure can at least say what it is. EX_TEMPFAIL separates "a third
party took their repo down" from "your ranker regressed", which today arrive as
the same red check.

WHY THERE IS A --refresh. Pinning bought reproducibility with
representativeness. The gate asks "does the right skill come back for a real
question", and skills are written by other people continuously — this corpus
grew by thousands of entries in the months before it was pinned — so a frozen
corpus answers that question about a world that no longer exists, and answers it
with total confidence because every number reproduces. Nothing was going to move
the pins on its own. `--refresh` moves every row to current upstream HEAD and
re-measures; .github/workflows/eval-corpus-refresh.yml runs it monthly and opens
a PR, the same shape lock-refresh.yml uses for the toolchain.

It deliberately does not run the eval. A refreshed corpus moves the gate's
numbers and they move DOWN as it grows, so the refresh can propose a corpus that
turns a required gate red through no fault of any change here. Deciding whether
that is acceptable is a separate step from performing the move, and a step that
did both would be deciding it silently.

Usage:
  python3 scripts/eval_corpus.py --ensure    # tap, pin and verify every row
  python3 scripts/eval_corpus.py --audit     # static checks, no network
  python3 scripts/eval_corpus.py --relock    # re-measure the entry counts
  python3 scripts/eval_corpus.py --refresh   # move the pins to upstream HEAD
  python3 scripts/eval_corpus.py --list      # print "repo sha count" rows
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Collection, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAPS = ROOT / "tests" / "eval" / "taps.txt"
#: The Tier 1b scale corpus — the required rows plus distractors. Scheduled,
#: never required; see .github/workflows/eval-scale.yml.
SCALE_TAPS = ROOT / "tests" / "eval" / "taps-scale.txt"

_SHA = re.compile(r"[0-9a-f]{40}")

#: ``(owner/repo, pinned commit or None, pinned entry count or None)``.
Row = tuple[str, str | None, int | None]

#: A repository, or the commit a row pins, could not be fetched.
UNAVAILABLE = "unavailable"
#: The repository materialised, but into a different number of entries.
DRIFT = "drift"

# 75 is EX_TEMPFAIL from sysexits.h, and the distinction is the point: an
# unreachable third-party repository is not a defect in the change under test,
# and it must not arrive looking like one.
EXIT_DRIFT = 1
EXIT_UNAVAILABLE = 75

# No single repository may hold more than this share of the corpus. Measured,
# not chosen: sickn33/antigravity-awesome-skills is 62.1% of the 10,152 entries
# today. So this is a ratchet against making the concentration worse — not a
# claim that 62% is a healthy number, which it is not. Diluting it means adding
# breadth, never dropping the big repo: the table above shows that dropping it
# raises every metric, so "rebalancing" by trimming would flatter the gate.
MAX_SHARE = 0.65


class CorpusError(RuntimeError):
    """A corpus problem that carries which KIND of problem it is.

    The kind is the whole reason this class exists. A corpus can fail to be the
    one the floors were measured on in two unrelated ways — someone else's
    repository went away, or the tree we did get scans into a different number
    of entries — and only the second says anything about this project. Collapsed
    into one exit status they are indistinguishable, which is how a third
    party's force-push comes to look like a retrieval regression.
    """

    def __init__(self, kind: str, repo: str, detail: str) -> None:
        super().__init__("%s: %s" % (repo, detail))
        self.kind = kind
        self.repo = repo
        self.detail = detail


def parse_taps(text: str) -> list[Row]:
    """Rows of ``owner/repo [sha [count]]``, comments and blanks dropped.

    An absent SHA parses as ``None`` rather than an error so the format stays
    backward compatible, but a SHA that is *present and malformed* is fatal: a
    typo silently degrading to "unpinned" would reintroduce the exact drift this
    file exists to stop, while still looking pinned to a reader. A count is
    fatal on the same grounds, and requires a SHA — a count beside an unpinned
    repo describes a tree that is free to change underneath it.
    """
    rows: list[Row] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        repo = parts[0]
        if len(parts) == 1:
            rows.append((repo, None, None))
            continue
        sha = parts[1]
        if not _SHA.fullmatch(sha):
            raise SystemExit(
                "tap list: %s is pinned to %r, which is not a "
                "40-character commit SHA" % (repo, sha))
        if len(parts) == 2:
            rows.append((repo, sha, None))
            continue
        if len(parts) > 3:
            raise SystemExit(
                "tap list: %s has %d fields, expected at most 3 "
                "(repo, sha, entry count)" % (repo, len(parts)))
        count = parts[2]
        if not count.isdigit():
            raise SystemExit(
                "tap list: %s records %r entries, which is not a "
                "non-negative integer" % (repo, count))
        rows.append((repo, sha, int(count)))
    return rows


def shares(rows: Sequence[Row]) -> list[tuple[str, int, float]]:
    """``(repo, count, share)`` for every counted row, largest first.

    Rows with no recorded count are omitted rather than treated as zero: a
    partially counted list should report the concentration of what it knows,
    not a share diluted by rows it cannot see.
    """
    counted = [(repo, n) for repo, _sha, n in rows if n is not None]
    total = sum(n for _repo, n in counted)
    if not total:
        return []
    return sorted(((repo, n, n / total) for repo, n in counted),
                  key=lambda row: (-row[1], row[0]))


def check_concentration(rows: Sequence[Row]) -> str | None:
    """Return a message when one repository exceeds ``MAX_SHARE``, else ``None``.

    Static — it reads the counts already in the file, so it costs no network and
    runs anywhere. Concentration is a sampling bias in every recall figure this
    project publishes, and the bias is invisible in a list of twenty names that
    look equally weighted.
    """
    ranked = shares(rows)
    if not ranked:
        return None
    repo, count, share = ranked[0]
    if share <= MAX_SHARE:
        return None
    return ("%s is %d of %d entries (%.1f%%), over the %.0f%% ceiling. The "
            "corpus would be mostly one publisher's house style, which biases "
            "every recall figure this project reports. Add breadth rather than "
            "dropping the big repo: a smaller corpus scores HIGHER, so trimming "
            "to rebalance would flatter the gate."
            % (repo, count, sum(n for _r, n, _s in ranked), share * 100,
               MAX_SHARE * 100))


def extra_taps(configured: Sequence[str], pinned: Sequence[str]) -> list[str]:
    """Configured taps that this list does not pin, sorted.

    The third way to score a corpus that is not the pinned one, and the easiest
    to walk into: the index is built from ``catalog.all_entries()``, which is
    every configured tap, not the twenty in this file. Point BOOST_HOME at a
    real install — 445 taps and 71,655 entries on the machine this was written
    on — and `make eval` reports numbers for that catalogue while every comment
    in the tree says it measured twenty repos.
    """
    return sorted(set(configured) - set(pinned))


def _run(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(path), *args],
                          capture_output=True, text=True)


def has_commit(path: Path, sha: str) -> bool:
    """True when ``sha`` names a commit already present in ``path``.

    ``^{commit}`` matters: `cat-file -e` succeeds for any object, so a tree or
    blob SHA would otherwise report as present and then fail at checkout.
    """
    return _run(path, "cat-file", "-e", "%s^{commit}" % sha).returncode == 0


def _fetch(path: Path, sha: str) -> subprocess.CompletedProcess:
    # Shallow: the corpus needs the tree at one commit, not the history to it.
    return _run(path, "fetch", "--quiet", "--depth", "1", "origin", sha)


def pin_clone(path: Path, sha: str) -> None:
    """Check ``path`` out at ``sha``, fetching the commit first if it is absent.

    Raises ``CorpusError(UNAVAILABLE, ...)``, which is the same class of event as
    the whole repository being gone: the tree the floors were measured on is not
    obtainable here and now, and that is not a statement about this project.
    """
    if not has_commit(path, sha):
        _fetch(path, sha)
    if not has_commit(path, sha):
        raise CorpusError(
            UNAVAILABLE, path.name,
            "commit %s is not reachable — the pin in tests/eval/taps.txt is "
            "stale, or the repository rewrote history" % sha)
    res = _run(path, "checkout", "--quiet", "--detach", sha)
    if res.returncode != 0:
        raise CorpusError(UNAVAILABLE, path.name,
                          "could not check out %s: %s" % (sha, res.stderr.strip()))


def _materialise(rows: Sequence[Row], verify: bool = True
                 ) -> tuple[dict[str, int], list[CorpusError]]:
    """Tap, pin and rescan every row. Returns ``(counts, failures)``.

    Every row is attempted even after one fails. Stopping at the first would
    report "one repository is unreachable" when five are, and the difference
    decides whether the answer is "re-run it" or "the list needs work".
    """
    sys.path.insert(0, str(ROOT))
    from boost_cli.core import catalog, registry  # deferred: repo-root import shim

    counts: dict[str, int] = {}
    failures: list[CorpusError] = []
    for repo, sha, want in rows:
        try:
            try:
                tap = registry.get(repo)
            except Exception:  # not yet tapped; add it below
                tap = registry.add(repo)
            if sha:
                pin_clone(tap.path, sha)
        except CorpusError as exc:
            # Re-name it: pin_clone only knows the clone directory, and the
            # report has to say what taps.txt says so the reader can grep for it.
            failures.append(CorpusError(exc.kind, repo, exc.detail))
            print("  %-44s %s" % (repo, exc.detail))
            continue
        except Exception as exc:  # any failure to obtain the tree at all
            failures.append(CorpusError(UNAVAILABLE, repo, str(exc)))
            print("  %-44s could not be tapped: %s" % (repo, exc))
            continue
        # Always after pinning: `boost tap` built the cache from the default
        # branch, so an unrebuilt cache would describe a tree we just replaced.
        entries = catalog.rebuild_tap(tap)
        counts[repo] = len(entries)
        note = ""
        if verify and want is not None and len(entries) != want:
            failures.append(CorpusError(
                DRIFT, repo,
                "taps.txt records %d entries, this tree scans into %d"
                % (want, len(entries))))
            note = "  != %d pinned" % want
        print("  %-44s %s  %5d entries%s"
              % (repo, (sha or "unpinned")[:7], len(entries), note))

    extras = extra_taps([t.name for t in registry.list_taps()],
                        [r for r, _s, _n in rows])
    if verify and extras:
        failures.append(CorpusError(
            DRIFT, "BOOST_HOME",
            "%d tap(s) are configured here but not pinned by taps.txt, and the "
            "index is built from ALL configured taps: %s"
            % (len(extras), ", ".join(extras[:5])
               + (", ..." if len(extras) > 5 else ""))))
    return counts, failures


def _report_failures(failures: Sequence[CorpusError], total_rows: int) -> int:
    """Print the failures grouped by kind and return the exit code to use."""
    unavailable = [f for f in failures if f.kind == UNAVAILABLE]
    drift = [f for f in failures if f.kind == DRIFT]
    if unavailable:
        print("\nCORPUS UNAVAILABLE — this is not a retrieval regression.")
        print("%d of %d pinned repositories could not be materialised:"
              % (len(unavailable), total_rows))
        for f in unavailable:
            print("  %s — %s" % (f.repo, f.detail))
        print("The gate cannot run, and scoring the repos that ARE reachable is\n"
              "not a fallback: measured, dropping the largest repo alone moves\n"
              "BM25 recall@10 0.852 -> 0.885 and hit@1 0.473 -> 0.593, so a\n"
              "partial corpus clears the floors MORE easily than the real one.")
    if drift:
        print("\nCORPUS DRIFT — what materialised is not what taps.txt pins.")
        for f in drift:
            print("  %s — %s" % (f.repo, f.detail))
        print("A count mismatch means the scanner changed or a pin moved: "
              "re-measure with\n`--relock`, then regenerate "
              "tests/eval/baseline.json. An unpinned tap means\nBOOST_HOME is "
              "not a corpus this file describes — point it at a scratch\n"
              "directory (`make eval` uses ./.eval-home).")
    # Drift wins when both happen: it is the one that says something about this
    # repository, and it is not fixed by waiting or re-running.
    return EXIT_DRIFT if drift else EXIT_UNAVAILABLE


def relock_text(text: str, counts: dict[str, int],
                shas: dict[str, str] | None = None,
                frozen: Collection[str] | None = None) -> str:
    """Rewrite each pinned row's entry count — and its SHA when ``shas`` says so.

    A whole-file rewrite would lose the header, which is where the reasoning
    lives; this touches only rows it has a new count for. A count is never
    written without a SHA — beside an unpinned repo it would describe a tree
    free to change underneath it — but the SHA may come from ``shas`` rather
    than from the row, which is how ``--refresh`` closes a row that arrived
    bare. Gating on "the row already has a pin" instead left the scale corpus
    at 165 bare rows to 20 pinned, refreshing only the 20 it did not own.

    ``shas`` is what makes ``--refresh`` a rewrite of the pins rather than of
    the counts alone. It is optional because the two operations are genuinely
    different: ``--relock`` re-measures the *same* trees (the scanner changed),
    ``--refresh`` moves to *new* trees (the world changed).

    ``frozen`` names repos whose rows this file does not own, and they are
    emitted byte for byte — not re-pinned, and *not re-columned*. Both halves
    matter: the width is the longest name being rewritten, so refreshing
    ``taps-scale.txt`` (whose distractor names are longer than anything in
    ``taps.txt``) moved every required row even where its pin had not changed.
    """
    shas = shas or {}
    frozen = frozen or ()
    width = max([len(r) for r in counts if r not in frozen] or [1])
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        parts = line.split()
        if not line or line.startswith("#") or not parts \
                or parts[0] not in counts or parts[0] in frozen:
            out.append(raw)
            continue
        repo = parts[0]
        # The row's own pin is only a fallback, and only when well formed: a
        # malformed one is not a value to carry forward, it is a row nothing
        # may claim to have measured.
        committed = (parts[1] if len(parts) > 1
                     and _SHA.fullmatch(parts[1]) else None)
        sha = shas.get(repo) or committed
        if sha is None:
            out.append(raw)
            continue
        if not _SHA.fullmatch(sha):
            raise SystemExit(
                "refusing to write %s: %r is not a 40-character commit SHA"
                % (repo, sha))
        out.append("%-*s %s %5d" % (width, repo, sha, counts[repo]))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def frozen_rows(taps: Path, required: Path = DEFAULT_TAPS) -> set[str]:
    """Repos in ``taps`` whose pins belong to ``required``, not to ``taps``.

    The scale corpus is the required corpus PLUS distractors, and
    ``build_scale_corpus.render`` copies the required block in verbatim so both
    tiers start from the same trees. The golden floors were calibrated against
    those trees; a scale tier measuring a *different* snapshot of the same
    repos reports a difference that is not scale.

    Membership, not identity, decides. ``--refresh`` on ``taps.txt`` itself is
    exactly the job that MAY move those pins, so it must freeze nothing —
    freezing on "is this a required repo" rather than "does another file own
    this row" would make the required corpus permanently unrefreshable, which
    is the same bug pointed the other way and far quieter.
    """
    if taps.resolve() == required.resolve() or not required.exists():
        return set()
    return {repo for repo, _sha, _n in
            parse_taps(required.read_text(encoding="utf-8"))}


def refresh_summary(rows: Sequence[Row], shas: dict[str, str],
                    counts: dict[str, int]) -> str:
    """A Markdown table of what a refresh moved, for the pull request body.

    The point of the scheduled refresh is not the refresh — it is that the diff
    is a direct measurement of how a changing catalogue moves retrieval, which
    nothing else in this repository reports. A table of twenty SHAs is not that
    measurement; the entry deltas beside them are the closest cheap proxy, so
    they go in the body rather than being left for a reader to derive from
    twenty `git log` lookups.
    """
    lines = ["| repo | pin | entries |", "| --- | --- | --- |"]
    moved = 0
    for repo, sha, count in rows:
        new_sha = shas.get(repo, sha or "")
        new_count = counts.get(repo, count)
        if new_sha == sha and new_count == count:
            lines.append("| `%s` | unchanged | %s |" % (repo, count))
            continue
        moved += 1
        pin = ("`%s` → `%s`" % ((sha or "?")[:7], new_sha[:7])
               if new_sha != sha else "unchanged")
        if new_count == count:
            entries = str(count)
        else:
            delta = (new_count or 0) - (count or 0)
            entries = "%s → %s (%+d)" % (count, new_count, delta)
        lines.append("| `%s` | %s | %s |" % (repo, pin, entries))
    total_old = sum(n for _r, _s, n in rows if n is not None)
    total_new = sum(counts.get(r, n or 0) for r, _s, n in rows)
    lines.append("")
    lines.append("**%d of %d repositories moved.** Corpus %d → %d entries (%+d)."
                 % (moved, len(rows), total_old, total_new, total_new - total_old))
    return "\n".join(lines)


def _print_concentration(rows: Sequence[Row]) -> None:
    ranked = shares(rows)
    if not ranked:
        return
    total = sum(n for _r, n, _s in ranked)
    top = ranked[0]
    print("corpus: %d entries across %d taps" % (total, len(ranked)))
    line = "concentration: %s is %.1f%%" % (top[0], top[2] * 100)
    if len(ranked) > 1:
        line += "; top two are %.1f%%" % ((top[2] + ranked[1][2]) * 100)
    print(line)


def _ensure(taps: Path, relock: bool = False) -> int:
    rows = parse_taps(taps.read_text(encoding="utf-8"))
    counts, failures = _materialise(rows, verify=not relock)
    if failures:
        return _report_failures(failures, len(rows))
    if relock:
        taps.write_text(relock_text(taps.read_text(encoding="utf-8"), counts),
                        encoding="utf-8")
        print("relocked %d rows in tests/eval/taps.txt" % len(counts))
        rows = parse_taps(taps.read_text(encoding="utf-8"))
    _print_concentration(rows)
    problem = check_concentration(rows)
    if problem:
        print("\nCORPUS CONCENTRATION — %s" % problem)
        return EXIT_DRIFT
    return 0


def _refresh(taps: Path, summary_path: str | None = None) -> int:
    """Move every row to current upstream HEAD, re-measure, rewrite taps.txt.

    Pinning bought reproducibility with representativeness: the gate measures
    one snapshot for as long as nobody moves it, while the catalogue it is
    meant to represent is written by other people continuously. Reproducible
    and representative are different properties, and nothing here was moving
    the pins.

    This deliberately does NOT run the eval. The refresh and the judgement
    about what it did to the numbers are separate steps, because the numbers
    can legitimately go down — a larger corpus scores lower, measured — and a
    step that both moved the corpus and decided whether that was acceptable
    would be deciding it silently.
    """
    sys.path.insert(0, str(ROOT))
    from boost_cli.core import catalog, gitutil, registry  # deferred: path shim

    rows = parse_taps(taps.read_text(encoding="utf-8"))
    # Rows another file owns are neither measured nor written — skipping the
    # measurement is not just an optimisation here, it is what keeps the two
    # tiers pinned to one set of trees. It also saves re-cloning the required
    # corpus, whose largest member is 6,309 entries.
    frozen = frozen_rows(taps)
    failures: list[CorpusError] = []
    shas: dict[str, str] = {}
    counts: dict[str, int] = {}
    if frozen:
        print("  %d rows are owned by %s and are left alone"
              % (len(frozen & {r for r, _s, _n in rows}), DEFAULT_TAPS.name))
    for repo, old_sha, _n in rows:
        if repo in frozen:
            continue
        try:
            try:
                tap = registry.get(repo)
            except Exception:  # not yet tapped; add it below
                tap = registry.add(repo)
            else:
                # An existing clone is pinned to a detached commit, so it has to
                # be moved back onto the default branch before HEAD means
                # "current upstream" again.
                gitutil.pull(tap.path)
            sha = gitutil.head_commit(tap.path)
        except Exception as exc:  # any failure to reach the current tree
            # This is where a deleted, renamed or privatised repository is
            # discovered — the scheduled job is the only thing that asks.
            failures.append(CorpusError(UNAVAILABLE, repo, str(exc)))
            print("  %-44s could not be refreshed: %s" % (repo, exc))
            continue
        if not _SHA.fullmatch(sha):
            failures.append(CorpusError(
                UNAVAILABLE, repo,
                "upstream HEAD did not resolve to a commit (got %r)" % sha))
            continue
        shas[repo] = sha
        entries = catalog.rebuild_tap(tap)
        counts[repo] = len(entries)
        print("  %-44s %s -> %s  %5d entries%s"
              % (repo, (old_sha or "?")[:7], sha[:7], len(entries),
                 "" if sha == old_sha else "   MOVED"))
    if failures:
        return _report_failures(failures, len(rows))
    taps.write_text(
        relock_text(taps.read_text(encoding="utf-8"), counts, shas,
                    frozen=frozen),
        encoding="utf-8")
    summary = refresh_summary(rows, shas, counts)
    print("\n" + summary)
    if summary_path:
        Path(summary_path).write_text(summary + "\n", encoding="utf-8")
    new_rows = parse_taps(taps.read_text(encoding="utf-8"))
    _print_concentration(new_rows)
    problem = check_concentration(new_rows)
    if problem:
        # Upstream growth alone can push one publisher over the ceiling, and it
        # is worth failing the refresh rather than opening a PR that quietly
        # makes the corpus more lopsided than the ratchet allows.
        print("\nCORPUS CONCENTRATION — %s" % problem)
        return EXIT_DRIFT
    return 0


def _audit(taps: Path) -> int:
    """Static checks over the shipped list — no network, no clones."""
    rows = parse_taps(taps.read_text(encoding="utf-8"))
    for repo, count, share in shares(rows):
        print("  %-44s %5d entries  %5.1f%%" % (repo, count, share * 100))
    _print_concentration(rows)
    uncounted = [r for r, _s, n in rows if n is None]
    if uncounted:
        print("\nuncounted rows (run --relock): %s" % ", ".join(uncounted))
        return EXIT_DRIFT
    problem = check_concentration(rows)
    if problem:
        print("\nCORPUS CONCENTRATION — %s" % problem)
        return EXIT_DRIFT
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval_corpus.py", description=__doc__)
    p.add_argument("--ensure", action="store_true",
                   help="tap, pin and verify every row, then rebuild its cache")
    p.add_argument("--relock", action="store_true",
                   help="re-measure entry counts and write them into taps.txt")
    p.add_argument("--refresh", action="store_true",
                   help="move every pin to current upstream HEAD, then re-measure")
    p.add_argument("--summary-md", metavar="PATH",
                   help="with --refresh, also write the Markdown summary here")
    p.add_argument("--audit", action="store_true",
                   help="static concentration/count checks, no network")
    p.add_argument("--list", action="store_true",
                   help="print the parsed rows and exit")
    p.add_argument("--list-repos", action="store_true",
                   help="print one owner/repo per line and exit (a matrix "
                        "source that cannot be field-split by mistake)")
    p.add_argument("--taps", metavar="PATH", default=str(DEFAULT_TAPS),
                   help="corpus list to act on (default the required corpus; "
                        "%s is the scale tier)" % SCALE_TAPS.name)
    args = p.parse_args(argv)
    taps = Path(args.taps)
    if not taps.is_file():
        raise SystemExit("no such corpus list: %s" % taps)
    if args.list_repos:
        # Names only, one per line. `--list` prints the SHA and count too, and
        # a caller that splits THAT on whitespace gets three matrix entries per
        # row — which is exactly how shards.yml ended up dispatching 60 jobs
        # for 20 registries, two thirds of them tapping a bare SHA or integer.
        for repo, _sha, _count in parse_taps(taps.read_text(encoding="utf-8")):
            print(repo)
        return 0
    if args.list:
        for repo, sha, count in parse_taps(taps.read_text(encoding="utf-8")):
            print("%s %s %s" % (repo, sha or "", "" if count is None else count))
        return 0
    if args.audit:
        return _audit(taps)
    if args.refresh:
        return _refresh(taps, args.summary_md)
    if args.relock:
        return _ensure(taps, relock=True)
    if args.ensure:
        return _ensure(taps)
    p.error("provide --ensure, --relock, --refresh, --audit, --list "
            "or --list-repos")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
