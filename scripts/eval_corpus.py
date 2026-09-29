#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Materialise the Tier 1 eval corpus at the exact commits it was measured on.

WHY THIS EXISTS. `tests/eval/taps.txt` used to pin repository NAMES. Tapping is
a shallow clone of whatever the default branch points at, so the corpus the
required `eval` gate scores against was a moving target: the list was written
recording **743** entries and the same 20 repos later resolved to **3,843**, a
5.2x growth nobody caused by editing a file. `affaan-m/ECC` alone was 1,616 of
them, so one third-party repository can move the gate's number by itself.

That is not academic. Measured on a clean 20-tap install, BM25 scored recall@10
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

    at the #410 pins        entries  recall@10 / hit@1 / MRR / nDCG@10
    all 20 repos             10,152  0.852 / 0.473 / 0.605 / 0.657
    minus sickn33 (62%)       3,843  0.885 / 0.593 / 0.711 / 0.746
    minus that and ECC        2,227  0.967 / 0.659 / 0.769 / 0.814
    minus LessUp (targets)    9,682  0.676 / 0.374 / 0.483 / 0.523
    floors                           0.780 / 0.400 / 0.520 / 0.580

Losing a *scale* repo makes the gate EASIER — all four metrics rise and the
check goes green having measured a third of the intended corpus. Losing a repo
that holds golden targets fails all four floors in a way indistinguishable from
"this pull request broke retrieval". So "skip whichever repos are missing today"
is unsafe in both directions, and the count is what makes the first case
detectable at all: a corpus that does not match its pins stops the run before
anything is scored.

WHY A ROW ALSO CARRIES A DISTINCT COUNT. The entry count is
`len(catalog.scan_dir())` — files on disk — and it is the right number for both
jobs above, because the index BM25 scores is built from exactly those rows:
`rag.build` indexes `catalog.all_entries()` with no de-duplication at all, so
ten vendored copies of one skill really are ten competing documents in the
ranking. What it is NOT is a measure of how much distinct material the corpus
holds, and the gap is not small:

    repo                                       entries  distinct  copies
    sickn33/antigravity-awesome-skills           6,634     2,117    68.1%
    NeoLabHQ/context-engineering-kit               268        90    66.4%
    affaan-m/ECC                                 1,621     1,588     2.0%
    the whole corpus                            10,731     5,938    44.7%

`MAX_ROW_SHARE` is the only shipped guard against the gate's corpus becoming
one publisher's house style, and it ratcheted on the first column alone. That
is a quantity a third party can inflate threefold without publishing one new
skill — rendering the same skill into `.claude/`, `.cursor/` and `.gemini/` is
a normal thing for a registry to do now — and one it can dodge entirely by
dominating the content without vendoring. So a row records both counts and
`--audit` ratchets on both: the first says how many documents the ranker
sorts, the second how many distinct things it had to sort.

The identity is `catalog._content_digest` — name, description and the
frontmatter-stripped body — which is what `rag.dedupe_by_content` collapses a
ranked list on, so the second column is measured with the rule the gate's own
de-duplication already uses. It is deliberately NOT
`scripts/measure_registry.py`'s digest, which normalises agent dotdir tokens so
one skill rendered into `.claude/` and `.cursor/` counts once: that is the
right question for `est_items` and the wrong one here, because the gate scores
those renders as separate competing rows and a measure that merges them cannot
describe the corpus it ranks.

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
  python3 scripts/eval_corpus.py --list      # print "repo sha count distinct"
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAPS = ROOT / "tests" / "eval" / "taps.txt"
#: The Tier 1b scale corpus — the required rows plus distractors. Scheduled,
#: never required; see .github/workflows/eval-scale.yml.
SCALE_TAPS = ROOT / "tests" / "eval" / "taps-scale.txt"

_SHA = re.compile(r"[0-9a-f]{40}")

#: ``(owner/repo, pinned commit or None, pinned entry count or None)``. A row
#: in the file carries a fourth field too; :func:`parse_taps` drops it and
#: :func:`parse_distinct` is how a caller asks for it. Keeping this tuple three
#: wide is deliberate: the shards matrix job's whole defence against splitting
#: one row into three registries is that it unpacks this shape by name
#: (``tests/unit/test_shards_matrix.py``), and widening a tuple every caller
#: destructures is a change with no local reader.
Row = tuple[str, str | None, int | None]

#: A row as the file spells it: :data:`Row` plus the distinct-content count.
FullRow = tuple[str, str | None, int | None, int | None]

#: A repository, or the commit a row pins, could not be fetched.
UNAVAILABLE = "unavailable"
#: The repository materialised, but into a different number of entries.
DRIFT = "drift"

# 75 is EX_TEMPFAIL from sysexits.h, and the distinction is the point: an
# unreachable third-party repository is not a defect in the change under test,
# and it must not arrive looking like one.
EXIT_DRIFT = 1
EXIT_UNAVAILABLE = 75

# No single repository may hold more than this share of the corpus, counted two
# ways. Both are measured rather than chosen, and both are ratchets against
# making the concentration worse — not claims that today's figure is healthy.
# Diluting either means adding breadth, never dropping the big repo: the table
# above shows that dropping it raises every metric, so "rebalancing" by
# trimming would flatter the gate.
#
# ROWS is documents-in-the-index: what the ranker sorts, and what every recall
# figure this project publishes is averaged over.
# sickn33/antigravity-awesome-skills held 62.1% of it at the #410 pins and
# 61.8% at the #992 ones.
MAX_ROW_SHARE = 0.65
# CONTENT is distinct material: what the corpus is a sample OF. It is the lower
# number for a publisher who vendors and the HIGHER one for a publisher who does
# not, which is the whole reason both exist. At the #992 pins sickn33 is 61.8%
# of rows and 35.7% of content, while affaan-m/ECC is 15.1% of rows and 26.7%
# of content — so a ceiling on rows alone fires on the first repo for copies
# that add no material, and cannot fire on the second at all.
#
# Set like its sibling: a few points above the measured leader (35.7%), loose
# enough that upstream drift cannot flake the build and tight enough to catch a
# collapse. It is deliberately NOT 0.65: the two numbers measure different
# things and there is no reason the same threshold suits both.
MAX_CONTENT_SHARE = 0.40

# taps.txt states its own size between these two lines, and every rewrite of
# the rows (`relock_text`, so `--relock` and `--refresh`) rewrites it. It used
# to be a sentence someone typed, and the first monthly refresh (cbc0a58b)
# moved the rows and left it stating the old total, fifty lines above the rows
# that said otherwise. A list without the two lines is left without them —
# taps-scale.txt is generated, and its generator owns its header.
SIZE_START = "# --- corpus size: written from the rows below by eval_corpus.py ---"
SIZE_END = "# --- end corpus size ---"
# The rows above this line are the six the name-graded floors were first
# measured on. They are NOT "every golden target" any more: both shipped
# query sets pin exemplars below the divider too, so the label written from
# it says "six-repo set", not "targets". taps.txt says why at length.
SCALE_DIVIDER = "# --- scale"


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


def _count(repo: str, field: str, noun: str) -> int:
    """One count field, or a fatal error naming what it was meant to count."""
    if not field.isdigit():
        raise SystemExit(
            "tap list: %s records %r %s, which is not a "
            "non-negative integer" % (repo, field, noun))
    return int(field)


def _rows(text: str) -> list[FullRow]:
    """Every pinned row of ``text``, fully validated; comments and blanks gone.

    One parser, because the two public readers have to agree about what a row
    is: a row :func:`parse_taps` accepts and :func:`parse_distinct` silently
    drops (or the reverse) is a row the corpus half-describes, and nothing
    would say so.

    An absent SHA parses as ``None`` rather than an error so the format stays
    backward compatible, but a SHA that is *present and malformed* is fatal: a
    typo silently degrading to "unpinned" would reintroduce the exact drift this
    file exists to stop, while still looking pinned to a reader. Both counts are
    fatal on the same grounds, and each needs the field before it — a count
    beside an unpinned repo describes a tree free to change underneath it, and
    a distinct count with no entry count has nothing to be a subset of.
    """
    rows: list[FullRow] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        repo = parts[0]
        if len(parts) == 1:
            rows.append((repo, None, None, None))
            continue
        sha = parts[1]
        if not _SHA.fullmatch(sha):
            raise SystemExit(
                "tap list: %s is pinned to %r, which is not a "
                "40-character commit SHA" % (repo, sha))
        if len(parts) == 2:
            rows.append((repo, sha, None, None))
            continue
        if len(parts) > 4:
            raise SystemExit(
                "tap list: %s has %d fields, expected at most 4 "
                "(repo, sha, entry count, distinct count)" % (repo, len(parts)))
        count = _count(repo, parts[2], "entries")
        if len(parts) == 3:
            rows.append((repo, sha, count, None))
            continue
        distinct = _count(repo, parts[3], "distinct items")
        if distinct > count:
            # Not a style rule. Distinct items are the entries that survive
            # de-duplication, so more of them than there are entries means the
            # two fields were measured against different trees, and the row
            # describes neither of them.
            raise SystemExit(
                "tap list: %s records %d distinct items out of %d entries, "
                "which is more distinct than there is"
                % (repo, distinct, count))
        rows.append((repo, sha, count, distinct))
    return rows


def parse_taps(text: str) -> list[Row]:
    """Rows of ``owner/repo [sha [count [distinct]]]`` as ``(repo, sha, count)``.

    Three wide, with the distinct count dropped, because three wide is what
    every caller destructures — see :data:`Row`. :func:`parse_distinct` is how
    the fourth field is read.
    """
    return [(repo, sha, count) for repo, sha, count, _d in _rows(text)]


def parse_distinct(text: str) -> dict[str, int]:
    """The distinct-content count of every row that records one.

    A mapping rather than a column, and a row without the field is absent
    rather than zero: a list relocked before the field existed knows nothing
    about its own content identity, and a zero would let
    :func:`check_concentration` report a concentration it never measured.
    """
    return {repo: d for repo, _s, _c, d in _rows(text) if d is not None}


def shares(rows: Sequence[tuple[Any, ...]], *, column: int = 2
           ) -> list[tuple[str, int, float]]:
    """``(repo, count, share)`` for every counted row, largest first.

    ``column`` picks which count: 2 is the entry count every relocked row
    carries, 3 the distinct-content count :func:`_rows` supplies and
    :func:`parse_taps` drops. It defaults to 2 because that is what the ranker
    actually sorts, and because a caller holding three-wide :data:`Row` tuples
    has nothing else to give.

    Rows with no recorded count are omitted rather than treated as zero: a
    partially counted list should report the concentration of what it knows,
    not a share diluted by rows it cannot see. A row too short to hold
    ``column`` is that same case — it has no count; it does not have zero.
    """
    counted = [(row[0], row[column]) for row in rows
               if len(row) > column and row[column] is not None]
    total = sum(n for _repo, n in counted)
    if not total:
        return []
    return sorted(((repo, n, n / total) for repo, n in counted),
                  key=lambda row: (-row[1], row[0]))


def _paired_entries(rows: Sequence[tuple[Any, ...]]) -> int:
    """Entries on the rows carrying both counts — the only ones a ratio may use.

    A ratio between the two counts has to divide two measurements of the *same*
    rows. Summing entries over every row that has one and distinct items over
    every row that has one gives a numerator and a denominator drawn from
    different populations, which is a ratio of nothing: on ``taps-scale.txt``
    (141 rows with an entry count, 20 with a distinct one) that arithmetic said
    84% of the rows were copies where the rows counted both ways say 44.7%. A
    row missing either number is evidence of neither, so it is in neither half
    of the fraction.

    Shared by the two places that divide the counts, because they had the same
    bug and one of them writes its answer into a tracked file: the console
    report was fixed first and ``size_lines`` kept the cross-population form
    for a while afterwards, which is the argument for one implementation
    rather than two corrected independently.
    """
    return sum(row[2] for row in rows
               if len(row) > 3 and row[2] is not None and row[3] is not None)


def size_lines(text: str) -> list[str]:
    """The corpus-size block's body, from the rows of ``text`` alone.

    The scores are not stated: `--refresh` writes this before the eval runs,
    so the only true thing it can say about them is where they are.
    """
    rows = _rows(text)
    ranked = shares(rows)
    total = sum(n for _r, n, _s in ranked)
    lines = ["# total:   %s entries in %d repos" % (f"{total:,}", len(ranked))]
    head, divider, _tail = text.partition("\n" + SCALE_DIVIDER)
    if divider:
        targets = [n for _r, _s, n in parse_taps(head) if n is not None]
        lines.append("# sixrepo: %s entries in the %d repos above the scale"
                     % (f"{sum(targets):,}", len(targets)))
        lines.append("#          divider -- a historical baseline, not a "
                     "subset that scores")
    # strict=False: a list of one repo has a largest and no runner-up.
    labels = ("largest:", "next:   ")
    for label, (repo, count, share) in zip(labels, ranked, strict=False):
        lines.append("# %s %s, %s entries (%.1f%%)"
                     % (label, repo, f"{count:,}", share * 100))
    # The noun is "distinct items", never "entries": tests/unit/test_corpus_prose
    # reads every "<number> entries" in this file as a claim about the corpus
    # size, and this is a claim about something else.
    content = shares(rows, column=3)
    if content:
        c_total = sum(n for _r, n, _s in content)
        paired = _paired_entries(rows)
        # Two lines, because the neighbours are ~60 columns and a 120-column
        # one in the middle of them reads as a different kind of thing.
        lines.append("# content: %s distinct items; %s holds %.1f%%"
                     % (f"{c_total:,}", content[0][0], content[0][2] * 100))
        lines.append("#          of them, and the rows overstate the corpus "
                     "%.2fx" % (paired / c_total))
        # A third line only when the two counts do not cover the same rows,
        # so the shipped block — every row of taps.txt carries both — is
        # byte-identical. Saying which rows the ratio came from is the whole
        # point of measuring it over them: a reader who takes `1.12x` for the
        # whole corpus has been told something the file cannot support.
        if paired != total:
            lines.append("#          measured over the %d of %d rows counted "
                         "both ways" % (len(content), len(ranked)))
    lines.append("# scores:  tests/eval/baseline.json, re-baselined with every "
                 "move")
    return lines


def with_size(text: str) -> str:
    """``text`` with its corpus-size block rewritten from its rows.

    A list without the block is returned unchanged rather than given one.
    """
    lines = text.splitlines()
    try:
        start = lines.index(SIZE_START)
        end = lines.index(SIZE_END, start)
    except ValueError:
        return text
    lines[start + 1:end] = size_lines(text)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


#: Per counted column: its ceiling, what it counts, and the sentence that
#: explains why THAT column is the one complaining. A dict rather than two
#: keyword arguments so an unrecognised column is a ``KeyError`` at the call
#: site: a concentration check that silently ran ungated would read exactly
#: like one that passed.
_CEILINGS: dict[int, tuple[float, str, str]] = {
    2: (MAX_ROW_SHARE, "entries", ""),
    3: (MAX_CONTENT_SHARE, "distinct items",
        " This is the content ceiling, not the row one: the repo dominates "
        "the distinct material, which no amount of de-duplication dilutes."),
}


def check_concentration(rows: Sequence[tuple[Any, ...]], *,
                        column: int = 2) -> str | None:
    """A message when one repository exceeds its ceiling, else ``None``.

    Static — it reads counts already in the file, so it costs no network and
    runs anywhere. Concentration is a sampling bias in every recall figure this
    project publishes, and the bias is invisible in a list of twenty names that
    look equally weighted.

    ``column`` is 2 for entries and 3 for distinct content, and both are
    checked because they fail differently: a vendoring publisher is over the
    row ceiling while holding a third of the material, and a publisher who does
    not vendor can dominate the material while staying well under it.

    A corpus of fewer than ``1 / ceiling`` repositories is not judged, because
    at that size no arrangement of counts could pass: the smallest possible top
    share is ``1 / len(rows)``, so two repos cannot get below 50% and a 45%
    ceiling would fail every two-repo corpus however it was balanced. That is
    not a strict gate, it is an unsatisfiable one — it would refuse the list
    rather than describe it, and the remedy it prints ("add breadth") is the
    only thing that could ever clear it. The shipped list has twenty repos
    against a floor of three, so this never softens the real check; it is what
    lets a fixture corpus exercise the same code path.
    """
    ceiling, noun, tail = _CEILINGS[column]
    ranked = shares(rows, column=column)
    if len(ranked) * ceiling < 1:      # also covers the empty list
        return None
    repo, count, share = ranked[0]
    if share <= ceiling:
        return None
    return ("%s is %d of %d %s (%.1f%%), over the %.0f%% ceiling. The "
            "corpus would be mostly one publisher's house style, which biases "
            "every recall figure this project reports. Add breadth rather than "
            "dropping the big repo: a smaller corpus scores HIGHER, so trimming "
            "to rebalance would flatter the gate.%s"
            % (repo, count, sum(n for _r, n, _s in ranked), noun, share * 100,
               ceiling * 100, tail))


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


def _is_clone(path: Path) -> bool:
    """True when ``path`` holds its own repository, not one git finds above it.

    ``.git`` is a directory in a clone and a file in a worktree; either way it
    is what stops `git -C` from walking up to an enclosing repository.
    """
    return (path / ".git").exists()


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
    if not _is_clone(path):
        # Without its own .git, `git -C` walks UP to the nearest enclosing
        # repository. Under `make eval` that is the boost checkout itself
        # (.eval-home sits inside it), and the forced checkout below would
        # act on the developer's working tree.
        raise CorpusError(UNAVAILABLE, path.name,
                          "%s is not a git clone" % path)
    if not has_commit(path, sha):
        _fetch(path, sha)
    if not has_commit(path, sha):
        raise CorpusError(
            UNAVAILABLE, path.name,
            "commit %s is not reachable — the pin in tests/eval/taps.txt is "
            "stale, or the repository rewrote history" % sha)
    # --force, because the pin names a TREE and not only a commit. Checking
    # out the commit HEAD already sits on is a no-op for the working tree, so a
    # SKILL.md deleted by hand stayed deleted, the rescan came up one entry
    # short, and the run exited DRIFT — from the remedy the eval gate's refusal
    # prints. Forcing restores tracked files inside the sparse cone and leaves
    # everything outside it alone; a tap clone is boost's copy of someone
    # else's tree, not a place work is kept.
    res = _run(path, "checkout", "--quiet", "--force", "--detach", sha)
    if res.returncode != 0:
        raise CorpusError(UNAVAILABLE, path.name,
                          "could not check out %s: %s" % (sha, res.stderr.strip()))


def _materialise(rows: Sequence[FullRow], verify: bool = True
                 ) -> tuple[dict[str, int], dict[str, int], list[CorpusError]]:
    """Tap, pin and rescan every row. Returns ``(counts, distinct, failures)``.

    Every row is attempted even after one fails. Stopping at the first would
    report "one repository is unreachable" when five are, and the difference
    decides whether the answer is "re-run it" or "the list needs work".
    """
    sys.path.insert(0, str(ROOT))
    from boost_cli.core import catalog, registry  # deferred: repo-root import shim

    counts: dict[str, int] = {}
    distinct: dict[str, int] = {}
    failures: list[CorpusError] = []
    for repo, sha, want, want_distinct in rows:
        try:
            try:
                tap = registry.get(repo)
            except Exception:  # not yet tapped; add it below
                tap = registry.add(repo)
            else:
                if not _is_clone(tap.path):
                    # Configured, with no clone behind it: `repos/` reclaimed
                    # by hand while config.json survived. Skipping the add and
                    # pinning anyway ran git in a directory that did not exist,
                    # and every row read "the pin is stale" — a false red,
                    # blaming the pins, from the one command meant to repair
                    # it. `update` is core's own answer to a missing clone.
                    #
                    # Asked of `.git`, not `is_cloned` (`is_dir()`): an emptied
                    # directory read as a clone. An empty one is cleared so the
                    # update re-clones into it; one holding files is not ours
                    # to delete, and `pin_clone` refuses it by name below.
                    if tap.path.is_dir() and not any(tap.path.iterdir()):
                        tap.path.rmdir()
                    if not tap.path.exists():
                        registry.update(tap.name)
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
        distinct[repo] = catalog.distinct_content(entries)
        note = ""
        if verify and want is not None and len(entries) != want:
            failures.append(CorpusError(
                DRIFT, repo,
                "taps.txt records %d entries, this tree scans into %d"
                % (want, len(entries))))
            note += "  != %d pinned" % want
        # Checked separately, and both are reported: the two counts drift for
        # different reasons — the scanner finding different files, against the
        # content-identity rule collapsing them differently — and a row that
        # matches on one and not the other is the case worth naming.
        if verify and want_distinct is not None \
                and distinct[repo] != want_distinct:
            failures.append(CorpusError(
                DRIFT, repo,
                "taps.txt records %d distinct items, this tree scans into %d"
                % (want_distinct, distinct[repo])))
            note += "  != %d distinct pinned" % want_distinct
        print("  %-44s %s  %5d entries (%5d distinct)%s"
              % (repo, (sha or "unpinned")[:7], len(entries),
                 distinct[repo], note))

    extras = extra_taps([t.name for t in registry.list_taps()],
                        [r for r, _s, _n, _d in rows])
    if verify and extras:
        failures.append(CorpusError(
            DRIFT, "BOOST_HOME",
            "%d tap(s) are configured here but not pinned by taps.txt, and the "
            "index is built from ALL configured taps: %s"
            % (len(extras), ", ".join(extras[:5])
               + (", ..." if len(extras) > 5 else ""))))
    return counts, distinct, failures


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
              "not a fallback: measured at the #410 pins, dropping the largest\n"
              "repo alone moved BM25 recall@10 0.852 -> 0.885 and hit@1\n"
              "0.473 -> 0.593, so a partial corpus clears the floors MORE\n"
              "easily than the real one.")
    if drift:
        print("\nCORPUS DRIFT — what materialised is not what taps.txt pins.")
        for f in drift:
            print("  %s — %s" % (f.repo, f.detail))
        print("A count mismatch means the scanner changed, the "
              "content-identity rule\nchanged, or a pin moved: re-measure with "
              "`--relock`, then regenerate\ntests/eval/baseline.json. An "
              "unpinned tap means\nBOOST_HOME is "
              "not a corpus this file describes — point it at a scratch\n"
              "directory (`make eval` uses ./.eval-home).")
    # Drift wins when both happen: it is the one that says something about this
    # repository, and it is not fixed by waiting or re-running.
    return EXIT_DRIFT if drift else EXIT_UNAVAILABLE


def relock_text(text: str, counts: dict[str, int],
                shas: dict[str, str] | None = None,
                frozen: Collection[str] | None = None,
                distinct: dict[str, int] | None = None) -> str:
    """Rewrite each pinned row's counts — and its SHA when ``shas`` says so.

    A whole-file rewrite would lose the header, which is where the reasoning
    lives; this touches only rows it has a new count for, and the one part of
    the header written from them — taps.txt's corpus-size block (``with_size``),
    which is how --relock and --refresh keep it true. A count is never
    written without a SHA — beside an unpinned repo it would describe a tree
    free to change underneath it — but the SHA may come from ``shas`` rather
    than from the row, which is how ``--refresh`` closes a row that arrived
    bare. Gating on "the row already has a pin" instead left the scale corpus
    at 165 bare rows to 20 pinned, refreshing only the 20 it did not own.

    ``shas`` is what makes ``--refresh`` a rewrite of the pins rather than of
    the counts alone. It is optional because the two operations are genuinely
    different: ``--relock`` re-measures the *same* trees (the scanner changed),
    ``--refresh`` moves to *new* trees (the world changed).

    ``distinct`` is the fourth field, and it is optional for the same reason
    ``shas`` is: a caller may have re-measured one thing and not the other. A
    row whose distinct count this run did not measure carries its committed one
    forward — the same rule as the SHA below, and for the same reason. Dropping
    the field instead would quietly un-pin half of what the row describes, and
    the next ``--ensure`` would verify only the half that survived.

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
        committed_d = (int(parts[3]) if len(parts) > 3 and parts[3].isdigit()
                       else None)
        n_distinct = (distinct or {}).get(repo, committed_d)
        if n_distinct is not None and n_distinct > counts[repo]:
            # Only a carried-forward count can land here — a measured one is a
            # subset of the entries it was measured from — and one that now
            # exceeds them is stale, not a measurement. Writing it would emit a
            # row `_rows` refuses to parse: a relock whose own parser rejects
            # its output.
            n_distinct = None
        row = "%-*s %s %5d" % (width, repo, sha, counts[repo])
        if n_distinct is not None:
            row += " %5d" % n_distinct
        out.append(row)
    return with_size("\n".join(out) + ("\n" if text.endswith("\n") else ""))


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


def refresh_summary(rows: Sequence[tuple[Any, ...]], shas: dict[str, str],
                    counts: dict[str, int],
                    distinct: dict[str, int] | None = None) -> str:
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
    for row in rows:
        repo, sha, count = row[0], row[1], row[2]
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
    total_old = sum(r[2] for r in rows if r[2] is not None)
    total_new = sum(counts.get(r[0], r[2] or 0) for r in rows)
    lines.append("")
    lines.append("**%d of %d repositories moved.** Corpus %d → %d entries (%+d)."
                 % (moved, len(rows), total_old, total_new, total_new - total_old))
    if distinct is not None:
        # Stated separately rather than as a fourth column, because it answers
        # a different question about the same diff: entries can grow by a
        # thousand while the material behind them does not move at all.
        old_d = sum(r[3] for r in rows if len(r) > 3 and r[3] is not None)
        new_d = sum(distinct.get(r[0], (r[3] if len(r) > 3 else None) or 0)
                    for r in rows)
        lines.append("")
        lines.append("Distinct content %d → %d (%+d); the rest of the corpus "
                     "is copies." % (old_d, new_d, new_d - old_d))
    return "\n".join(lines)


def _concentration_line(ranked: Sequence[tuple[str, int, float]],
                        column: int, noun: str) -> str:
    """One line describing ``ranked``'s top share, or why it is not judged.

    The "not judged" case covers exactly the sizes
    :func:`check_concentration` refuses, and saying so is the point: a share
    printed without it reads as a violation that passed. A two-row content
    ranking at 99/1 printed "is 99.0% of content" and the run exited 0,
    because the gate had already declined to judge a corpus too small for any
    arrangement to clear the ceiling.
    """
    ceiling = _CEILINGS[column][0]
    if len(ranked) * ceiling < 1:
        return ("concentration%s: not judged — %d repos cannot clear a %.0f%% "
                "ceiling however balanced, since the smallest possible top "
                "share is %.0f%%"
                % (noun, len(ranked), ceiling * 100, 100 / len(ranked)))
    line = "concentration%s: %s is %.1f%%" % (noun, ranked[0][0],
                                              ranked[0][2] * 100)
    if len(ranked) > 1:
        line += "; top two are %.1f%%" % ((ranked[0][2]
                                           + ranked[1][2]) * 100)
    return line


def _print_concentration(rows: Sequence[tuple[Any, ...]]) -> None:
    ranked = shares(rows)
    if not ranked:
        return
    total = sum(n for _r, n, _s in ranked)
    print("corpus: %d entries across %d taps" % (total, len(ranked)))
    print(_concentration_line(ranked, 2, ""))
    content = shares(rows, column=3)
    if not content:
        return
    c_total = sum(n for _r, n, _s in content)
    paired = _paired_entries(rows)
    if paired == total:
        print("content: %d distinct items (%.0f%% of the rows are copies)"
              % (c_total, (1 - c_total / paired) * 100))
    else:
        print("content: %d distinct items in the %d rows counted both ways "
              "(%.0f%% of those are copies); %d rows carry an entry count "
              "only" % (c_total, len(content),
                        (1 - c_total / paired) * 100,
                        len(ranked) - len(content)))
    print(_concentration_line(content, 3, " of content"))


def _ensure(taps: Path, relock: bool = False) -> int:
    rows = _rows(taps.read_text(encoding="utf-8"))
    counts, distinct, failures = _materialise(rows, verify=not relock)
    if failures:
        return _report_failures(failures, len(rows))
    if relock:
        # `frozen=` for the same reason --refresh passes it: relocking the
        # scale list must not re-count or re-column the rows taps.txt owns,
        # and leaving it off here was the one path that did.
        frozen = frozen_rows(taps)
        taps.write_text(
            relock_text(taps.read_text(encoding="utf-8"), counts,
                        frozen=frozen, distinct=distinct),
            encoding="utf-8")
        print("relocked %d rows in %s"
              % (len({r for r in counts if r not in frozen}), taps.name))
        rows = _rows(taps.read_text(encoding="utf-8"))
    return _concentration_gate(rows)


def _concentration_gate(rows: Sequence[FullRow]) -> int:
    """Print both concentrations and fail on whichever ceiling is exceeded.

    Both, not the worse of the two: they are different biases with different
    remedies, and a run that reported only the first would let a publisher
    owning half the material pass for as long as it also vendored enough
    copies to stay off the top of the row ranking.
    """
    _print_concentration(rows)
    for column in _CEILINGS:
        problem = check_concentration(rows, column=column)
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

    rows = _rows(taps.read_text(encoding="utf-8"))
    # Rows another file owns are neither measured nor written — skipping the
    # measurement is not just an optimisation here, it is what keeps the two
    # tiers pinned to one set of trees. It also saves re-cloning the required
    # corpus, most of which is one repository.
    frozen = frozen_rows(taps)
    failures: list[CorpusError] = []
    shas: dict[str, str] = {}
    counts: dict[str, int] = {}
    distinct: dict[str, int] = {}
    if frozen:
        print("  %d rows are owned by %s and are left alone"
              % (len(frozen & {r for r, _s, _n, _d in rows}), DEFAULT_TAPS.name))
    for repo, old_sha, _n, _d in rows:
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
        distinct[repo] = catalog.distinct_content(entries)
        print("  %-44s %s -> %s  %5d entries (%5d distinct)%s"
              % (repo, (old_sha or "?")[:7], sha[:7], len(entries),
                 distinct[repo], "" if sha == old_sha else "   MOVED"))
    if failures:
        return _report_failures(failures, len(rows))
    taps.write_text(
        relock_text(taps.read_text(encoding="utf-8"), counts, shas,
                    frozen=frozen, distinct=distinct),
        encoding="utf-8")
    summary = refresh_summary(rows, shas, counts, distinct)
    print("\n" + summary)
    if summary_path:
        Path(summary_path).write_text(summary + "\n", encoding="utf-8")
    # Upstream growth alone can push one publisher over either ceiling, and it
    # is worth failing the refresh rather than opening a PR that quietly makes
    # the corpus more lopsided than the ratchet allows.
    return _concentration_gate(_rows(taps.read_text(encoding="utf-8")))


def _audit(taps: Path) -> int:
    """Static checks over the shipped list — no network, no clones."""
    rows = _rows(taps.read_text(encoding="utf-8"))
    content = {repo: n for repo, n, _s in shares(rows, column=3)}
    for repo, count, share in shares(rows):
        known = content.get(repo)
        print("  %-44s %5d entries  %5.1f%%%s"
              % (repo, count, share * 100,
                 "" if known is None else "  %5d distinct" % known))
    uncounted = [r for r, _s, n, _d in rows if n is None]
    if uncounted:
        print("\nuncounted rows (run --relock): %s" % ", ".join(uncounted))
        return EXIT_DRIFT
    # Reported, not fatal. A list relocked before the fourth field existed is
    # still a corpus this file fully describes in every other respect, and
    # failing it here would red a required job over a field nothing had yet
    # had the chance to write. The shipped list is held to a higher standard
    # by tests/unit/test_eval_corpus.py, which is the right place for it.
    unmeasured = [r for r, _s, _n, d in rows if d is None]
    if unmeasured:
        print("\n%d counted rows record no distinct count, so the content "
              "ceiling is\nunchecked for them (run --relock): %s"
              % (len(unmeasured), ", ".join(unmeasured[:5])
                 + (", ..." if len(unmeasured) > 5 else "")))
    return _concentration_gate(rows)


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
                   help="print the parsed rows (repo, sha, entries, "
                        "distinct items) and exit")
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
        for row in _rows(taps.read_text(encoding="utf-8")):
            print(" ".join("" if f is None else str(f) for f in row).rstrip())
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
