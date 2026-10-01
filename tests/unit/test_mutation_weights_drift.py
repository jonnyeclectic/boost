# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: deciding whether the committed shard-balance hints are stale.

``scripts/mutation_weights.json`` is the measured input the six mutation shards
are bin-packed on. ci.yml has uploaded a freshly measured one as an artifact on
every run that reaches the gate since #346 (2026-07-30), with a comment saying
it exists "so a maintainer can drop a measured file in". In the nine weeks
since, a maintainer did it exactly once, by hand, in #834 (2026-09-08). The
artifact's retention is seven days, so the remedy expires weekly while the
committed file ages, and it only ever lands when somebody remembers.

``mutation_shards.py drift`` is what lets a workflow make that call without a
human: it packs the same source tree twice, once on the committed hints and
once on the candidate, and scores **both** packs against the candidate.

That asymmetry is the whole design and the thing these tests pin. A weights
file always reports its own pack as near-perfectly balanced, because that is
precisely what the packer optimised against it; comparing each plan to its own
weights compares two self-reports and finds them equal every time. Measured on
the real tree, the committed plan reported 70.4 minutes a shard, flat — and
cost 150.4 against 75.1 when scored on what the work actually took.

Scoring one tree under two weights files also has to be non-destructive. Every
loader resolves the file from ``root``, so the obvious implementation
overwrites the committed hints mid-comparison: fine in a throwaway CI
checkout, data loss in a developer's, and in a test a global side effect that
leaks into whatever runs next. ``using_weights`` is the override that avoids
it, and ``test_the_committed_file_is_never_touched`` is what keeps it honest.
"""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location(
    "mutation_shards_drift", ROOT / "scripts" / "mutation_shards.py")
ms = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ms)

SHARDS = 3


def _fn(name: str) -> str:
    return "def %s():\n    x = 1\n    y = 2\n    return x + y\n" % name


def _repo(tmp_path: Path, names: list[str]) -> Path:
    """A fake checkout holding one single-function module per name."""
    core = tmp_path / "boost_cli" / "core"
    core.mkdir(parents=True)
    for name in names:
        (core / ("%s.py" % name)).write_text(_fn("run_%s" % name), encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    return tmp_path


def _hints(path: Path, millis: dict[str, int]) -> Path:
    path.write_text(json.dumps({
        "mutants_by_file": dict.fromkeys(millis, 10),
        "mutants_by_symbol": {},
        "millis_by_file": millis,
        "millis_by_symbol": {},
    }), encoding="utf-8")
    return path


#: Six equal files, which any packer splits evenly across three shards.
EVEN = {"%s.py" % n: 60_000 for n in "abcdef"}

#: The same six, measured. Equal weights pair them `{a,d} {b,e} {c,f}`, so
#: putting the cost in `a` and `d` is what makes the stale plan wrong: it
#: lands both heavy files on one shard (600s) where a plan built from these
#: splits them (400s). No single file exceeds an even share, so the gap is
#: packing rather than an indivisible floor — which is the drift this
#: subcommand is for.
SKEWED = {"a.py": 300_000, "b.py": 100_000, "c.py": 100_000,
          "d.py": 300_000, "e.py": 100_000, "f.py": 100_000}


class TestUsingWeights:
    """The override that makes a two-file comparison non-destructive."""

    def test_it_redirects_every_loader(self, tmp_path):
        """All four, each with a value only the redirected file carries.

        Asserting one loader and calling it "every" was the gap: three of the
        four could have ignored the override and the test would still pass.
        Each of the four keys below is distinct in the two files, so a loader
        that read the committed file returns the wrong one of a pair.
        """
        repo = _repo(tmp_path, list("abcdef"))
        here = repo / "scripts" / "mutation_weights.json"
        here.write_text(json.dumps({
            "mutants_by_file": {"a.py": 1},
            "mutants_by_symbol": {"a.py": {"run_a": 1}},
            "millis_by_file": {"a.py": 10},
            "millis_by_symbol": {"a.py": {"run_a": 10}},
        }), encoding="utf-8")
        there = tmp_path / "other.json"
        there.write_text(json.dumps({
            "mutants_by_file": {"a.py": 2},
            "mutants_by_symbol": {"a.py": {"run_a": 2}},
            "millis_by_file": {"a.py": 20},
            "millis_by_symbol": {"a.py": {"run_a": 20}},
        }), encoding="utf-8")

        loaders = (ms.load_weights, ms.load_symbol_weights,
                   ms.load_durations, ms.load_symbol_durations)
        committed = [fn(repo) for fn in loaders]
        with ms.using_weights(there):
            redirected = [fn(repo) for fn in loaders]
        after = [fn(repo) for fn in loaders]

        assert committed == [{"a.py": 1}, {"a.py": {"run_a": 1}},
                             {"a.py": 10}, {"a.py": {"run_a": 10}}]
        assert redirected == [{"a.py": 2}, {"a.py": {"run_a": 2}},
                              {"a.py": 20}, {"a.py": {"run_a": 20}}]
        assert after == committed, "the override outlived its block"

    def test_none_means_no_weights_at_all(self, tmp_path):
        # Not "fall back to the committed file" — the fallback tiers have to be
        # reachable without deleting anything.
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        with ms.using_weights(None):
            assert ms.load_durations(repo) == {}

    def test_it_restores_the_previous_value_after_an_exception(self, tmp_path):
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        with pytest.raises(RuntimeError), \
                ms.using_weights(tmp_path / "other.json"):
            raise RuntimeError("boom")
        assert ms.weights_path(repo) == repo / "scripts" / "mutation_weights.json"

    def test_it_nests(self, tmp_path):
        # `drift` enters it twice around a `pack`, so an override that reset to
        # None on exit instead of to its predecessor would silently drop the
        # outer one.
        outer, inner = tmp_path / "o.json", tmp_path / "i.json"
        with ms.using_weights(outer):
            with ms.using_weights(inner):
                assert ms.weights_path(Path("/nowhere")) == inner
            assert ms.weights_path(Path("/nowhere")) == outer


class TestScoringOnePlanAgainstAnothersWeights:
    def test_a_plan_reports_itself_balanced_under_its_own_weights(self, tmp_path):
        # The measurement trap this subcommand exists to avoid.
        repo = _repo(tmp_path, list("abcdef"))
        even = _hints(tmp_path / "even.json", EVEN)
        with ms.using_weights(even):
            bins = ms.pack(repo, SHARDS)
        loads = ms.score(repo, bins, even)
        assert ms._spread(loads)[0] == pytest.approx(1.0, abs=0.01)

    def test_the_same_plan_is_lopsided_under_the_measured_ones(self, tmp_path):
        repo = _repo(tmp_path, list("abcdef"))
        even = _hints(tmp_path / "even.json", EVEN)
        skewed = _hints(tmp_path / "skewed.json", SKEWED)
        with ms.using_weights(even):
            stale_plan = ms.pack(repo, SHARDS)
        with ms.using_weights(skewed):
            fresh_plan = ms.pack(repo, SHARDS)
        stale = max(ms.score(repo, stale_plan, skewed))
        fresh = max(ms.score(repo, fresh_plan, skewed))
        # The claim is a comparison, not "fresh is flat". A perfectly current
        # weights file still reports a makespan above the ideal whenever some
        # indivisible unit outweighs an even share, which is the normal state
        # of the real tree. What always holds is that the plan built from the
        # measurements is not beaten by the plan built from stale ones.
        assert stale > fresh, (stale, fresh)
        assert stale / fresh == pytest.approx(1.5)

    def test_spread_of_a_flat_pack_is_one(self):
        assert ms._spread([10, 10, 10]) == (1.0, 1.0)

    def test_spread_reports_the_slowest_over_the_ideal(self):
        # 60 of 120 on three shards: twice the even share.
        makespan, ratio = ms._spread([60, 30, 30])
        assert makespan == pytest.approx(1.5)
        assert ratio == pytest.approx(2.0)


def capsys_text(path: Path) -> str:
    """The `$GITHUB_OUTPUT` file's text, or "" when it was never written."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _args(repo, candidate, **kw):
    fields = {"root": str(repo), "candidate": str(candidate), "shards": SHARDS,
              "threshold": ms.DRIFT_THRESHOLD, "summary_md": None,
              "github_output": None}
    fields.update(kw)
    return type("A", (), fields)()


class TestDrift:
    def test_identical_weights_do_not_move(self, tmp_path, capsys):
        repo = _repo(tmp_path, list("abcdef"))
        committed = _hints(repo / "scripts" / "mutation_weights.json", SKEWED)
        candidate = _hints(tmp_path / "candidate.json", json.loads(
            committed.read_text(encoding="utf-8"))["millis_by_file"])
        out = tmp_path / "gh.txt"
        assert ms.cmd_drift(_args(repo, candidate, github_output=str(out))) == 0
        assert "moved=false" in out.read_text(encoding="utf-8")
        assert "close enough" in capsys.readouterr().out

    def test_a_stale_plan_moves(self, tmp_path, capsys):
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        out = tmp_path / "gh.txt"
        assert ms.cmd_drift(_args(repo, candidate, github_output=str(out))) == 0
        text = out.read_text(encoding="utf-8")
        assert "moved=true" in text
        makespan = float(next(ln for ln in text.splitlines()
                              if ln.startswith("makespan=")).split("=")[1])
        assert makespan > ms.DRIFT_THRESHOLD, makespan
        assert "refresh is worth it" in capsys.readouterr().out

    def test_the_threshold_is_what_decides(self, tmp_path):
        # Same two files, same drift, opposite verdicts — so a future change
        # that hard-coded the answer would fail here rather than read as a
        # tuning decision.
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        lax, strict = tmp_path / "lax.txt", tmp_path / "strict.txt"
        ms.cmd_drift(_args(repo, candidate, threshold=99.0,
                           github_output=str(lax)))
        ms.cmd_drift(_args(repo, candidate, threshold=1.0001,
                           github_output=str(strict)))
        assert "moved=false" in lax.read_text(encoding="utf-8")
        assert "moved=true" in strict.read_text(encoding="utf-8")

    def test_the_committed_file_is_never_written_to(self, tmp_path):
        # The hazard `using_weights` exists for: the natural implementation
        # swaps the candidate in, packs, and swaps back — losing the committed
        # hints to any failure in between.
        #
        # Comparing the bytes afterwards does NOT catch that, which is the
        # whole reason this is a permission test. Swap-and-restore leaves the
        # file byte-identical at the end, so an earlier version of this test
        # passed against the exact implementation its own comment named. A
        # read-only file fails the write instead of forgiving it.
        repo = _repo(tmp_path, list("abcdef"))
        committed = _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        committed.chmod(0o444)
        try:
            assert ms.cmd_drift(_args(repo, candidate)) == 0
        finally:
            committed.chmod(0o644)

    def test_the_read_only_guard_would_catch_a_write(self, tmp_path):
        # Otherwise the test above passes on a platform that ignores the mode.
        target = tmp_path / "locked.json"
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o444)
        try:
            with pytest.raises(PermissionError):
                target.write_text("overwritten", encoding="utf-8")
        finally:
            target.chmod(0o644)

    def test_the_threshold_boundary_is_inclusive(self, tmp_path):
        # `>=`, not `>`. Both spellings pass every other test in this file,
        # so without this the comparison operator is free to drift.
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        out = tmp_path / "exact.txt"
        # The fixture's committed plan costs exactly 1.5x the measured best.
        ms.cmd_drift(_args(repo, candidate, threshold=1.5, github_output=str(out)))
        assert "moved=true" in out.read_text(encoding="utf-8")

    def test_a_missing_candidate_is_not_an_error(self, tmp_path, capsys):
        # ci.yml skips the mutation gate entirely when nothing mutable changed,
        # so "there is no artifact" is the ordinary case on a docs-only merge.
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        assert ms.cmd_drift(_args(repo, tmp_path / "absent.json")) == 0
        assert "nothing to compare" in capsys.readouterr().out

    def test_it_runs_with_no_committed_hints_at_all(self, tmp_path):
        # A checkout before the file existed, or after someone deleted it. The
        # committed "plan" is then the line-count fallback, which is a real
        # plan and a fair comparison — not a crash.
        repo = _repo(tmp_path, list("abcdef"))
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        out = tmp_path / "gh.txt"
        assert ms.cmd_drift(_args(repo, candidate, github_output=str(out))) == 0
        assert "moved=" in out.read_text(encoding="utf-8")

    def test_the_total_line_says_so_when_there_is_nothing_to_compare(
            self, tmp_path, capsys):
        # It used to print "+99999900%", from a divisor clamped to 1 ms.
        repo = _repo(tmp_path, list("abcdef"))
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        ms.cmd_drift(_args(repo, candidate))
        out = capsys.readouterr().out
        assert "no committed total to compare" in out
        assert "%" not in out.split("Recorded total")[1].split("\n")[0]

    def test_an_empty_shard_is_not_an_enormous_ratio(self, tmp_path, capsys):
        # More shards than units: the slowest/fastest column divided by a
        # clamp of 1 ms and reported 300000.00x for a bin that drew no work.
        repo = _repo(tmp_path, ["a", "b"])
        two = {"a.py": 300_000, "b.py": 100_000}
        _hints(repo / "scripts" / "mutation_weights.json", two)
        candidate = _hints(tmp_path / "candidate.json", two)
        ms.cmd_drift(_args(repo, candidate, shards=10))
        assert "n/a" in capsys.readouterr().out
        # 300000 over an even share of 400000/3, and an empty bin for the
        # ratio. (Written out because an earlier draft multiplied its own
        # derivation by zero and added the answer back as a literal.)
        assert ms._spread([300_000, 100_000, 0]) == (
            300_000 / (400_000 / 3), math.inf)

    def test_the_report_names_files_measured_for_the_first_time(self, tmp_path):
        # `compact.py`, `prereq.py` and `report.py` were in exactly this state
        # on the real tree: new modules the planner was sizing by line count
        # because no recorded run had ever seen them.
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json",
               {k: v for k, v in SKEWED.items() if k != "f.py"})
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        md = tmp_path / "drift.md"
        ms.cmd_drift(_args(repo, candidate, summary_md=str(md)))
        assert "`f.py`" in md.read_text(encoding="utf-8")

    def test_the_markdown_report_is_also_what_is_printed(self, tmp_path, capsys):
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        md = tmp_path / "drift.md"
        ms.cmd_drift(_args(repo, candidate, summary_md=str(md)))
        assert md.read_text(encoding="utf-8") in capsys.readouterr().out

    def test_the_file_on_disk_is_the_string_that_was_printed(self, tmp_path,
                                                             capsys):
        """Byte for byte: same characters, same line endings.

        One report written twice — to `$GITHUB_STEP_SUMMARY` and to the log
        beside it — so the two have to agree, and the Windows jobs found two
        separate ways for them not to. First the encoding: the report carries
        an em dash and `write_text(report)` with none named picks the locale
        codec, cp1252 on a GitHub Windows runner. Then, once that was fixed,
        the line endings: text mode translates every "\n" to the platform
        separator on write, so the file held CRLF while `sys.stdout.write`
        emitted LF and this same comparison failed again.

        Reading the bytes and decoding them explicitly is what makes both
        halves testable on *every* platform rather than only on the runner
        that disagrees — though only the second half can actually fail here,
        which is why `test_mutation_shards_names_its_encoding.py` walks the
        source as well.
        """
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        md = tmp_path / "drift.md"
        ms.cmd_drift(_args(repo, candidate, summary_md=str(md)))
        printed = capsys.readouterr().out
        # Vacuous if the report were pure ASCII: every encoding agrees there.
        assert any(ord(c) > 127 for c in printed), printed
        assert md.read_bytes().decode("utf-8") in printed


class TestACandidateThatIsNotAMeasurement:
    """Every loader reads an unusable weights file as "no weights".

    That is the right answer for a fresh checkout and the wrong one here: with
    both sides falling back to line counts, the committed pack looks lopsided
    (it was optimised for milliseconds) and the comparison recommends
    replacing a good file with an empty one. Measured against the real
    66-file tree, `{not json`, `{}` and `[]` each reported "refresh is worth
    it" at 1.438, and a file carrying only `mutants_by_file` at 1.588.
    """

    @staticmethod
    def _run(tmp_path, body, committed=SKEWED, names=tuple("abcdef")):
        repo = _repo(tmp_path, list(names))
        before = None
        if committed is not None:
            before = _hints(repo / "scripts" / "mutation_weights.json",
                            committed).read_bytes()
        candidate = tmp_path / "candidate.json"
        candidate.write_text(body, encoding="utf-8")
        out = tmp_path / "gh.txt"
        rc = ms.cmd_drift(_args(repo, candidate, github_output=str(out)))
        return rc, out.read_text(encoding="utf-8"), before

    def test_unreadable_json_is_refused(self, tmp_path, capsys):
        rc, out, _ = self._run(tmp_path, "{not json")
        assert rc == 0 and "moved=false" in out
        assert "not readable JSON" in capsys.readouterr().out

    def test_a_json_scalar_is_refused(self, tmp_path, capsys):
        rc, out, _ = self._run(tmp_path, "[]")
        assert rc == 0 and "moved=false" in out
        assert "not an object" in capsys.readouterr().out

    def test_a_file_with_no_durations_is_refused(self, tmp_path, capsys):
        rc, out, _ = self._run(
            tmp_path, json.dumps({"mutants_by_file": {"a.py": 5000}}))
        assert rc == 0 and "moved=false" in out
        assert "records no per-file durations" in capsys.readouterr().out

    def test_a_partial_measurement_is_refused(self, tmp_path, capsys):
        # The realistic one. `cmd_weights` records a file's time only when
        # every mutant of it carried a duration, so a run that loses durations
        # for some files produces exactly this: a candidate that times fewer
        # files than the committed hints and still packs to something the
        # comparison scores as an improvement (measured 1.235 at 55 of 63).
        fewer = {k: v for k, v in SKEWED.items() if k not in ("e.py", "f.py")}
        rc, out, _ = self._run(tmp_path, json.dumps({
            "mutants_by_file": dict.fromkeys(SKEWED, 10),
            "millis_by_file": fewer, "mutants_by_symbol": {},
            "millis_by_symbol": {}}))
        assert rc == 0 and "moved=false" in out
        assert "a partial measurement, not a fresher one" in capsys.readouterr().out

    def test_a_rename_keeps_the_count_and_is_not_refused(self, tmp_path,
                                                        capsys):
        """The guard is "fewer", not "different".

        A rename is the case that separates the two: `f.py` becomes `g.py`,
        so the candidate times the same six files and the committed hints
        name one that no longer exists. `present` drops `f.py` from the
        committed side and the counts come out 6 against 5, which is more,
        not fewer — the candidate must be compared.

        Two things here were wrong in the first draft and both made the test
        pass for the wrong reason. The repo was built with `f.py` still on
        disk, so this never modelled a rename at all: `g.py` was filtered
        out of `now` and the candidate was refused as partial. And the only
        assertion was `"moved=" in out`, which `_emit_drift` writes on every
        refusal too, so it held on both branches. The fixture now puts
        `g.py` on disk instead of `f.py`, and the assertions name the
        comparison rather than the exit code.
        """
        renamed = {("g.py" if k == "f.py" else k): v for k, v in SKEWED.items()}
        rc, out, _ = self._run(tmp_path, json.dumps({
            "mutants_by_file": dict.fromkeys(renamed, 10),
            "millis_by_file": renamed, "mutants_by_symbol": {},
            "millis_by_symbol": {}}), names=("a", "b", "c", "d", "e", "g"))
        printed = capsys.readouterr().out
        assert rc == 0, printed
        assert "a partial measurement" not in printed, printed
        assert "plan built from" in printed, printed
        # Identical weights under a new name: the pack cannot improve.
        assert "moved=false" in out and "makespan=1.000" in out, out

    def test_a_deleted_module_does_not_latch_the_guard_shut(self, tmp_path,
                                                            capsys):
        """Fewer files is only "partial" over files that still exist.

        A plain ``len(now) < len(was)`` makes deleting a module from
        ``boost_cli/core`` a one-way door. Every candidate after the deletion
        legitimately times one file fewer than the committed hints, so every
        candidate is refused — and the only thing that could rewrite the
        committed hints to clear the condition is the refresh this guard is
        blocking. Permanently off, with no way back but a hand edit.
        """
        # Six files committed, five on disk: `f.py` was deleted. The candidate
        # is a complete measurement of what remains.
        repo = _repo(tmp_path, list("abcde"))
        _hints(repo / "scripts" / "mutation_weights.json", SKEWED)
        live = {k: v for k, v in SKEWED.items() if k != "f.py"}
        candidate = _hints(tmp_path / "candidate.json", live)
        out = tmp_path / "gh.txt"
        assert ms.cmd_drift(_args(repo, candidate, github_output=str(out))) == 0
        # The refusal goes to stdout, never to `--github-output` — asserting
        # its absence from `gh.txt` was vacuous and passed with the `present`
        # filter replaced by `pass`.
        printed = capsys.readouterr().out
        assert "a partial measurement" not in printed, printed
        # Reached the comparison rather than a guard: the candidate measures
        # exactly the five files that remain, so the two plans agree.
        assert "plan built from" in printed, printed
        assert "moved=false" in capsys_text(out)

    def test_a_genuinely_partial_run_is_still_refused_after_a_deletion(
            self, tmp_path, capsys):
        # The filter must not disarm the guard: with `f.py` deleted, a
        # candidate missing one of the five that remain is still partial.
        repo = _repo(tmp_path, list("abcde"))
        _hints(repo / "scripts" / "mutation_weights.json", SKEWED)
        short = {k: v for k, v in SKEWED.items() if k not in ("e.py", "f.py")}
        candidate = _hints(tmp_path / "candidate.json", short)
        ms.cmd_drift(_args(repo, candidate))
        assert "a partial measurement" in capsys.readouterr().out

    @pytest.mark.parametrize("key", ["mutants_by_file", "mutants_by_symbol",
                                     "millis_by_file", "millis_by_symbol"])
    @pytest.mark.parametrize("value", [[], [1], "x", 3], ids=str)
    def test_a_non_mapping_under_a_known_key_is_survivable(
            self, tmp_path, key, value):
        """The top-level object check does not cover one level down.

        ``{"millis_by_file": []}`` parses, is an object, and then raises
        ``AttributeError: 'list' object has no attribute 'items'`` from inside
        the planner — a crash in a tier whose contract is that a corrupt file
        costs balance and never correctness.
        """
        repo = _repo(tmp_path, list("abcdef"))
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({key: value}), encoding="utf-8")
        with ms.using_weights(bad):
            assert ms.load_weights(repo) == {}
            assert ms.load_symbol_weights(repo) == {}
            assert ms.load_durations(repo) == {}
            assert ms.load_symbol_durations(repo) == {}

    def test_an_unreadable_file_is_survivable(self, tmp_path):
        # The OSError arm, which nothing reached: a directory where a file
        # was expected raises IsADirectoryError, not ValueError.
        repo = _repo(tmp_path, list("abcdef"))
        notafile = tmp_path / "weights.json"
        notafile.mkdir()
        with ms.using_weights(notafile):
            assert ms.load_weights(repo) == {}
            assert ms.load_symbol_weights(repo) == {}
            assert ms.load_durations(repo) == {}
            assert ms.load_symbol_durations(repo) == {}
        assert "not readable JSON" in ms._unusable(notafile, {}, {"a.py": 1})

    def test_a_refusal_leaves_the_committed_file_alone(self, tmp_path):
        _rc, _out, before = self._run(tmp_path, "{not json")
        repo = tmp_path / "boost_cli"
        assert before == (repo.parent / "scripts" / "mutation_weights.json").read_bytes()


class TestEveryExitWritesTheSummary:
    """``--summary-md`` is written on every path, including the refusals.

    The workflow step is two commands: the ``drift`` invocation, then
    ``cat "$RUNNER_TEMP/drift.md" >> "$GITHUB_STEP_SUMMARY"``. ``cat`` is the
    last command, so its exit status is the step's — and the three guard
    paths returned 0 having written nothing. "Keeping the committed hints" is
    a *designed* outcome, and it turned the job red on `main`; the same
    change had added this workflow to ci-failure-issue.yml's watch list, so it
    would also have filed an issue against a workflow whose header says "A
    FAILURE HERE BLOCKS NOTHING".
    """

    @staticmethod
    def _drift(tmp_path, candidate_body, committed=SKEWED, make_candidate=True):
        repo = _repo(tmp_path, list("abcdef"))
        if committed is not None:
            _hints(repo / "scripts" / "mutation_weights.json", committed)
        candidate = tmp_path / "candidate.json"
        if make_candidate:
            candidate.write_text(candidate_body, encoding="utf-8")
        md = tmp_path / "drift.md"
        out = tmp_path / "gh.txt"
        rc = ms.cmd_drift(_args(repo, candidate, summary_md=str(md),
                                github_output=str(out)))
        return rc, md, out

    @pytest.mark.parametrize("label,body,exists", [
        ("a missing candidate", "", False),
        ("unreadable JSON", "{not json", True),
        ("a JSON scalar", "[]", True),
        ("no durations", json.dumps({"mutants_by_file": {"a.py": 5}}), True),
        ("a partial measurement", json.dumps({
            "mutants_by_file": dict.fromkeys(SKEWED, 10),
            "millis_by_file": {k: v for k, v in SKEWED.items()
                               if k not in ("e.py", "f.py")},
            "mutants_by_symbol": {}, "millis_by_symbol": {}}), True),
        ("a real comparison", json.dumps({
            "mutants_by_file": dict.fromkeys(SKEWED, 10),
            "millis_by_file": SKEWED,
            "mutants_by_symbol": {}, "millis_by_symbol": {}}), True),
    ])
    def test_the_file_exists_and_says_something(self, tmp_path, label, body,
                                                exists):
        rc, md, out = self._drift(tmp_path, body, make_candidate=exists)
        assert rc == 0, label
        assert md.exists(), "%s left --summary-md unwritten" % label
        text = md.read_text(encoding="utf-8")
        assert text.strip(), "%s wrote an empty --summary-md" % label
        assert "moved=" in out.read_text(encoding="utf-8"), label

    def test_the_workflow_step_would_not_fail(self, tmp_path):
        """Replays the step's own shape: `drift && cat <summary>`.

        Reproduced as the workflow runs it rather than asserted about —
        ``cat`` of a missing file exits 1, and nothing else in the step would
        have noticed.
        """
        rc, md, _out = self._drift(tmp_path, "{not json")
        assert rc == 0
        completed = subprocess.run(
            ["cat", str(md)], capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        assert "keeping the committed hints" in completed.stdout

    def test_a_refusal_reaches_the_step_summary_not_just_stdout(self, tmp_path):
        # Stdout is inside a collapsed log group; the step summary is what a
        # maintainer reads to find out why no PR appeared.
        _rc, md, _out = self._drift(tmp_path, "[]")
        assert "not an object" in md.read_text(encoding="utf-8")


class TestTheReportNamesItsUnit:
    def test_minutes_when_the_candidate_times_everything(self, tmp_path,
                                                         capsys):
        repo = _repo(tmp_path, list("abcdef"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)
        ms.cmd_drift(_args(repo, candidate))
        assert " min |" in capsys.readouterr().out

    def test_not_minutes_when_the_weights_fall_back_to_counting(self, tmp_path,
                                                                capsys):
        """A candidate with durations but no counts weights by LINES.

        `weight_fn` imputes a missing duration at the measured
        milliseconds-per-mutant rate, and that rate needs `mutants_by_file`.
        Without it the rate is 0, every imputed weight is 0, `use_millis`
        goes false, and the planner is counting lines — which the table
        printed as "0 min", directly above a paragraph reporting the real
        total in minutes. Seven files on disk and six timed is what reaches
        the imputation at all; with every file timed there is nothing to
        impute and the missing counts never matter.
        """
        repo = _repo(tmp_path, list("abcdefg"))
        _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = tmp_path / "candidate.json"
        candidate.write_text(json.dumps({"millis_by_file": SKEWED}),
                             encoding="utf-8")
        ms.cmd_drift(_args(repo, candidate))
        out = capsys.readouterr().out
        assert " units |" in out, out
        assert " min |" not in out, out


class TestTheCandidateIsWhatBothPlansAreScoredAgainst:
    """The second ``score()`` call, which nothing pinned.

    The module docstring calls the asymmetry "the whole design", and the
    suite checked only half of it: every test stayed green with
    ``score(root, new_bins, committed)`` substituted for
    ``score(root, new_bins, candidate)``.
    """

    def test_the_printed_ratio_is_the_candidate_scored_one(self, tmp_path,
                                                           capsys):
        repo = _repo(tmp_path, list("abcdef"))
        committed = _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        candidate = _hints(tmp_path / "candidate.json", SKEWED)

        with ms.using_weights(committed):
            old_bins = ms.pack(repo, SHARDS)
        with ms.using_weights(candidate):
            new_bins = ms.pack(repo, SHARDS)
        old = ms.score(repo, old_bins, candidate)
        right = max(old) / max(max(ms.score(repo, new_bins, candidate)), 1)
        wrong = max(old) / max(max(ms.score(repo, new_bins, committed)), 1)
        # Vacuous unless the two wirings actually disagree on this fixture.
        assert round(right, 3) != round(wrong, 3), (right, wrong)

        ms.cmd_drift(_args(repo, candidate))
        printed = capsys.readouterr().out
        assert "**%.3fx**" % right in printed, printed
        assert "**%.3fx**" % wrong not in printed


class TestWeightsOut:
    """`weights --out`, because the obvious redirection is a trap."""

    @staticmethod
    def _mutants(tmp_path):
        src = tmp_path / "mutants" / "boost_cli" / "core"
        src.mkdir(parents=True)
        (src / "a.py.meta").write_text(json.dumps({
            "exit_code_by_key": {"boost_cli.core.a.x_run_a__mutmut_1": 0},
            "durations_by_key": {"boost_cli.core.a.x_run_a__mutmut_1": 1.5},
        }), encoding="utf-8")
        return tmp_path / "mutants"

    def test_out_writes_there_and_leaves_the_committed_file_alone(self, tmp_path):
        repo = _repo(tmp_path, ["a"])
        committed = _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        before = committed.read_bytes()
        dest = tmp_path / "fresh.json"
        args = type("A", (), {"root": str(repo), "out": str(dest),
                              "source": str(self._mutants(tmp_path))})()
        assert ms.cmd_weights(args) == 0
        written = json.loads(dest.read_text(encoding="utf-8"))
        assert written["millis_by_file"] == {"a.py": 1500}
        assert committed.read_bytes() == before

    def test_an_empty_out_is_refused_rather_than_ignored(self, tmp_path,
                                                         capsys):
        """`--out ""` must not fall through to the committed file.

        That is what `--out "$OUT"` expands to when `$OUT` is unset, and
        `Path(args.out) if args.out else ...` treated it as absent — so the
        flag added to stop `weights` overwriting the committed hints
        overwrote them, while the user believed they had redirected it.
        """
        repo = _repo(tmp_path, ["a"])
        committed = _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        before = committed.read_bytes()
        args = type("A", (), {"root": str(repo), "out": "",
                              "source": str(self._mutants(tmp_path))})()
        assert ms.cmd_weights(args) == 1
        assert "refusing to fall back" in capsys.readouterr().out
        assert committed.read_bytes() == before

    def test_without_out_it_still_writes_in_place(self, tmp_path):
        repo = _repo(tmp_path, ["a"])
        committed = _hints(repo / "scripts" / "mutation_weights.json", EVEN)
        args = type("A", (), {"root": str(repo), "out": None,
                              "source": str(self._mutants(tmp_path))})()
        assert ms.cmd_weights(args) == 0
        written = json.loads(committed.read_text(encoding="utf-8"))
        assert written["millis_by_file"] == {"a.py": 1500}
