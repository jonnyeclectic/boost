# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Packing the catalogue into a matrix GitHub will actually run.

Two facts drive every test here. **GitHub caps a matrix at 256 jobs**, so the
463-registry catalogue cannot be one job per registry — the run fails before a
single job starts. And embedding cost is wildly uneven: the largest catalogued
registry measures 880 items against a median of 30, so slicing the list
into equal chunks puts several giants in one job while others idle, and the run
takes as long as its unluckiest chunk against a hard 6-hour job ceiling.

Longest-processing-time-first fixes the second and the job count fixes the
first. The packing must also be *deterministic*: a rerun that repacked
differently would re-embed registries whose shards were already published.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import shard_plan  # noqa: E402


def _rows(*costs):
    return [{"name": "o/r%d" % i, "cost": c} for i, c in enumerate(costs)]


class TestPack:
    def test_every_registry_lands_in_exactly_one_bin(self):
        rows = _rows(*range(1, 40))
        packed = shard_plan.pack(rows, jobs=7)
        flat = [name for chunk in packed for name in chunk]
        assert sorted(flat) == sorted(r["name"] for r in rows)
        assert len(flat) == len(set(flat))

    def test_it_never_plans_more_bins_than_asked(self):
        # The ceiling is the whole reason this function exists.
        assert len(shard_plan.pack(_rows(*range(500)), jobs=60)) <= 60

    def test_fewer_registries_than_bins_does_not_pad_with_empties(self):
        # An empty matrix entry would be a job that taps nothing and then fails
        # its own "produced no shards" assertion.
        packed = shard_plan.pack(_rows(5, 5, 5), jobs=10)
        assert packed == [["o/r0"], ["o/r1"], ["o/r2"]]

    def test_the_giant_ends_up_effectively_alone(self):
        # It is the run's critical path either way; what matters is that it is
        # not also carrying somebody else's work.
        rows = _rows(1000, 10, 10, 10, 10)
        packed = shard_plan.pack(rows, jobs=3)
        giant = next(c for c in packed if "o/r0" in c)
        assert giant == ["o/r0"]

    def test_load_is_balanced_far_better_than_slicing(self):
        rows = _rows(*([100] * 3 + [1] * 30))
        costs = {r["name"]: r["cost"] for r in rows}
        loads = [sum(costs[n] for n in c)
                 for c in shard_plan.pack(rows, jobs=3)]
        # Sliced by position the three giants land together (300 vs 15); packed
        # they separate.
        assert max(loads) - min(loads) <= 20

    def test_packing_is_deterministic(self):
        rows = _rows(*range(1, 60))
        assert shard_plan.pack(rows, jobs=8) == shard_plan.pack(rows, jobs=8)

    def test_zero_jobs_is_refused_rather_than_silently_empty(self):
        with pytest.raises(SystemExit):
            shard_plan.pack(_rows(1, 2), jobs=0)


class TestCatalogRows:
    def test_it_reads_the_bundled_catalogue_biggest_first(self):
        rows = shard_plan.catalog_rows()
        assert rows, "the bundled catalogue should not be empty"
        assert [r["cost"] for r in rows] == sorted(
            (r["cost"] for r in rows), reverse=True)

    def test_list_only_repos_are_excluded_by_default(self):
        # An awesome-list repo indexes other repos; there is nothing of its own
        # to embed, so a job for it would produce no shard and fail.
        from boost_cli.core import config
        lists = {e["name"] for e in config.load_registry_catalog()
                 if e.get("list_only")}
        names = {r["name"] for r in shard_plan.catalog_rows()}
        assert not (names & lists)
        if lists:
            assert names < {r["name"] for r
                            in shard_plan.catalog_rows(include_lists=True)}


class TestCli:
    def _run(self, *args):
        return subprocess.run([sys.executable,
                               str(ROOT / "scripts" / "shard_plan.py"), *args],
                              capture_output=True, text=True)

    def test_it_emits_a_json_list_of_space_separated_chunks(self):
        out = self._run("--scope", "catalog", "--jobs", "12").stdout
        matrix = json.loads(out)
        assert len(matrix) == 12
        assert all(isinstance(chunk, str) for chunk in matrix)
        assert all("/" in chunk for chunk in matrix)

    def test_over_the_ceiling_is_a_hard_error_not_a_truncation(self):
        # Truncating would silently drop registries from the publish.
        res = self._run("--scope", "catalog", "--jobs", "300")
        assert res.returncode != 0
        assert "256" in res.stderr + res.stdout

    def test_explain_reports_the_shape(self):
        out = self._run("--scope", "catalog", "--jobs", "10", "--explain").stdout
        assert "heaviest" in out and "lightest" in out

    def test_the_whole_catalogue_fits_the_default_plan(self):
        # The number the workflow actually runs with.
        matrix = json.loads(self._run("--scope", "catalog").stdout)
        assert len(matrix) <= shard_plan.MAX_MATRIX_JOBS
        packed = sum(len(chunk.split()) for chunk in matrix)
        assert packed == len(shard_plan.catalog_rows())
