# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: the clock canary -- its shim, its runner, and the workflow around them.

The canary (``scripts/clock_canary.py``, ``.github/workflows/clock-canary.yml``)
runs the suite with Python's calendar moved forward, so a test that compares a
fixed date against ``now`` fails before the real calendar gets there. The one
that cost eleven red nightlies (2026-11-13..23) is the model for the planted
bomb below.

Every check of the shim runs in a child interpreter with an environment built
here, never by importing the shim into this process: the suite runs inside
mutmut's single-process stats pass, and a patched ``datetime`` leaking out of
one test would be the outage this exists to prevent. The children read the
real clock from ``_datetime``, the C module the shim cannot reach, so these
tests pass whether or not the process running them is itself on a moved clock
-- which it is, when the canary runs this file.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "clock_canary.py"
SHIM_DIR = ROOT / "tests" / "clock_canary"
WORKFLOWS = ROOT / ".github" / "workflows"
CANARY_YML = WORKFLOWS / "clock-canary.yml"
ALERT_YML = WORKFLOWS / "ci-failure-issue.yml"
REQUIRED = ROOT / ".github" / "required-checks.txt"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cc = _load("clock_canary_under_test", SCRIPT)


def _clean_env(**extra: str) -> dict[str, str]:
    """This process's environment minus anything the canary sets, plus ``extra``."""
    drop = {cc.DAYS_ENV, cc.REPORT_ENV, cc.SENTINEL_ENV, "PYTHONPATH"}
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(extra)
    return env


def _child(code: str, days: int | None) -> dict:
    """Run ``code`` with the shim on the path (moved ``days``, or not at all).

    ``code`` must print one JSON object as its last line.
    """
    extra = {"PYTHONPATH": str(SHIM_DIR)}
    if days is not None:
        extra[cc.DAYS_ENV] = str(days)
    proc = subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                          env=_clean_env(**extra), capture_output=True, text=True,
                          timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


DAY = 86400.0


class TestTheShimMovesTheCalendar:
    def test_every_reading_of_now_moves_by_the_days_asked(self):
        # Local readings are compared with the local time AT the moved instant,
        # not with today's local time plus 14 days: across a DST change those
        # differ by an hour, and this test must not be a date bomb itself.
        seen = _child("""
            import _datetime as real, datetime as d, json
            utc = real.timezone.utc
            r = real.datetime.now(utc)
            local = (r + real.timedelta(days=14)).astimezone().replace(tzinfo=None)
            print(json.dumps({
                "now_utc": (d.datetime.now(d.timezone.utc) - r).total_seconds() - 14 * 86400,
                "now_local": (d.datetime.now() - local).total_seconds(),
                "today": (d.datetime.today() - local).total_seconds(),
                "utcnow": (d.datetime.utcnow() - r.replace(tzinfo=None)).total_seconds()
                          - 14 * 86400,
                "date_today": (d.date.today() - local.date()).days,
            }))""", days=14)
        for key in ("now_utc", "now_local", "today", "utcnow"):
            assert abs(seen[key]) < 60, (key, seen)
        assert seen["date_today"] == 0, seen

    def test_without_the_variable_it_changes_nothing(self):
        # A plain run never puts the shim on the path at all; this is the
        # second line of defence, for a run that does but sets no offset.
        seen = _child("""
            import _datetime as real, datetime as d, json, sitecustomize
            print(json.dumps({"shim": sitecustomize.__file__,
                              "datetime": d.datetime is real.datetime,
                              "date": d.date is real.date}))""", days=None)
        assert Path(seen["shim"]).resolve() == (SHIM_DIR / "sitecustomize.py").resolve()
        assert seen["datetime"] and seen["date"], seen

    def test_wall_clock_time_and_file_times_are_left_alone(self):
        # Measured, not assumed: moving time.time() as well put a fresh file
        # 14 days in the past for every `time.time() - st_mtime` in boost (see
        # the shim's docstring), so only the calendar moves.
        seen = _child("""
            import json, time
            print(json.dumps({"skew": time.time() - time.clock_gettime(time.CLOCK_REALTIME)
                              if hasattr(time, "clock_gettime") else 0.0,
                              "gm": time.gmtime().tm_yday,
                              "real_gm": time.gmtime(time.time()).tm_yday}))""", days=14)
        assert abs(seen["skew"]) < 5, seen
        assert seen["gm"] == seen["real_gm"], seen

    def test_an_aware_now_lands_in_the_zone_at_the_moved_instant(self):
        # 14 days from any date crosses some zone's DST change; the offset
        # must be the one in force at the moved instant, not today's.
        seen = _child("""
            import _datetime as real, datetime as d, json
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                tz = ZoneInfo("America/Chicago")
            except ZoneInfoNotFoundError:
                print(json.dumps({"skip": True})); raise SystemExit
            moved = d.datetime.now(tz)
            want = (real.datetime.now(real.timezone.utc)
                    + real.timedelta(days=40)).astimezone(tz)
            print(json.dumps({"skip": False, "off": moved.utcoffset().total_seconds(),
                              "want": want.utcoffset().total_seconds(),
                              "tz": moved.tzinfo is tz}))""", days=40)
        if seen["skip"]:
            pytest.skip("no tz database on this machine")
        assert seen["tz"] and seen["off"] == seen["want"], seen


class TestTheShadowedSitecustomizeStillRuns:
    """``site`` imports one sitecustomize; the shim must run the one it hides.

    Homebrew's Python ships one that rewrites ``sys.base_prefix``, and while
    the shim shadowed it test_selfupdate_python.py failed on both clocks.
    """

    @pytest.mark.parametrize("days", [None, 14])
    def test_the_next_one_on_the_path_runs_once(self, tmp_path, days):
        (tmp_path / "sitecustomize.py").write_text(
            "import builtins\nbuiltins.CHAINED = getattr(builtins, 'CHAINED', 0) + 1\n",
            encoding="utf-8", newline="\n")
        extra = {"PYTHONPATH": os.pathsep.join([str(SHIM_DIR), str(tmp_path)])}
        if days is not None:
            extra[cc.DAYS_ENV] = str(days)
        proc = subprocess.run(
            [sys.executable, "-c", "import builtins, sitecustomize, json; print(json.dumps("
             "[getattr(builtins, 'CHAINED', 0), sitecustomize.__file__]))"],
            env=_clean_env(**extra), capture_output=True, text=True, timeout=60, check=False)
        assert proc.returncode == 0, proc.stderr
        chained, first = json.loads(proc.stdout)
        assert chained == 1, "the hidden sitecustomize ran %d times" % chained
        assert Path(first).resolve() == (SHIM_DIR / "sitecustomize.py").resolve()


class TestEveryInstanceIsARealOne:
    """Only the classes are stand-ins: every object they make is a real date.

    A first version subclassed and returned its own instances, which changed
    ``repr`` and failed test_required_checks.py's ``datetime.date(2026, 11, 3)``
    case on the moved clock for no reason to do with the calendar.
    """

    def test_constructors_parsers_and_repr(self):
        seen = _child("""
            import _datetime as real, datetime as d, json
            made = [d.datetime(2026, 1, 2), d.date(2026, 11, 3),
                    d.datetime.fromisoformat("2026-01-01T00:00:00"),
                    d.date.fromisoformat("2026-11-03"),
                    d.datetime.strptime("2026-01-02", "%Y-%m-%d"),
                    d.datetime.now(), d.date.today()]
            print(json.dumps({
                "real": [type(x) in (real.datetime, real.date) for x in made],
                "repr": repr(d.date(2026, 11, 3)),
                "isinstance": [isinstance(real.datetime(2026, 1, 1), d.datetime),
                               isinstance(real.date(2026, 1, 1), d.date),
                               isinstance(real.datetime(2026, 1, 1), d.date),
                               not isinstance(real.date(2026, 1, 1), d.datetime)],
                "issubclass": issubclass(real.datetime, d.date)}))""", days=14)
        assert all(seen["real"]), seen
        assert seen["repr"] == "datetime.date(2026, 11, 3)"
        assert all(seen["isinstance"]) and seen["issubclass"], seen

    def test_pickle_and_deepcopy_round_trip(self):
        seen = _child("""
            import copy, datetime as d, json, pickle
            vals = [d.datetime.now(), d.datetime.now(d.timezone.utc), d.date.today()]
            print(json.dumps([pickle.loads(pickle.dumps(v)) == v == copy.deepcopy(v)
                              and type(pickle.loads(pickle.dumps(v))) is type(v)
                              for v in vals]))""", days=14)
        assert all(seen), seen

    def test_a_subclass_in_a_test_keeps_its_own_type_and_now(self):
        # tests/unit/test_util.py and test_mutation_hardening.py freeze the
        # clock by subclassing datetime; under the shim they subclass the
        # stand-in, and must still behave as they do without it.
        seen = _child("""
            import _datetime as real, datetime as d, json
            PIN = real.datetime(2026, 3, 4, 5, 6, 7)
            class Frozen(d.datetime):
                @classmethod
                def now(cls, tz=None):
                    return PIN
            x = Frozen(2026, 1, 1)
            print(json.dumps({"type": type(x) is Frozen,
                              "now": Frozen.now() == PIN,
                              "plain_is_not": not isinstance(real.datetime(2026, 1, 1), Frozen),
                              "parse": type(Frozen.strptime("2026", "%Y")) is Frozen}))""",
                      days=14)
        assert all(seen.values()), seen


def test_the_suite_runs_on_the_moved_clock():
    """The canary's check that its shift reached the process running the tests.

    scripts/clock_canary.py names this test as its sentinel: under ``-n auto``
    this body runs in an xdist worker, so it is what proves the workers
    inherited the shift, which the canary's preflight (one probe interpreter)
    cannot. Skipped on any run that is not the canary's.
    """
    days = os.environ.get(cc.DAYS_ENV)
    if not days:
        pytest.skip("only meaningful under scripts/clock_canary.py")
    import _datetime
    import datetime as d
    moved = (d.datetime.now(d.UTC)
             - _datetime.datetime.now(_datetime.timezone.utc)).total_seconds()
    assert abs(moved - int(days) * DAY) < 60, (
        "%s=%s is set but this process reads the clock %.0f s ahead: the shim did "
        "not load here, so the canary's green would mean nothing" % (cc.DAYS_ENV, days, moved))


def test_the_sentinel_the_script_names_exists():
    # The script knows its sentinel by node id alone. Renamed, moved or put in
    # a class, the moved run never collects it, the canary only warns, and
    # nothing proves the xdist workers saw the moved clock any more.
    path, _, name = cc.SELF_TEST.partition("::")
    assert re.fullmatch(r"test_\w+", name), cc.SELF_TEST
    assert re.search(r"^def %s\(" % name, (ROOT / path).read_text(encoding="utf-8"),
                     re.MULTILINE), "%s names no module-level test" % cc.SELF_TEST


def test_a_plain_run_never_loads_the_shim():
    if os.environ.get(cc.DAYS_ENV):
        pytest.skip("this is the canary's run")
    mod = sys.modules.get("sitecustomize")
    where = Path(getattr(mod, "__file__", None) or "/nonexistent").resolve()
    assert where.parent != SHIM_DIR.resolve(), (
        "the clock-canary shim loaded in an ordinary test run: something put "
        "tests/clock_canary on sys.path")


class TestEnvironments:
    def test_the_moved_env_puts_the_shim_first_and_keeps_the_rest(self):
        env = cc.moved_env({"PYTHONPATH": "a%sb" % os.pathsep, "KEEP": "1",
                            cc.REPORT_ENV: "stale"}, 14)
        assert env["PYTHONPATH"].split(os.pathsep) == [str(SHIM_DIR), "a", "b"]
        assert env[cc.DAYS_ENV] == "14" and env["KEEP"] == "1"
        assert cc.REPORT_ENV not in env

    def test_todays_env_keeps_the_plugin_reachable_and_drops_the_offset(self):
        env = cc.today_env({cc.DAYS_ENV: "14", cc.SENTINEL_ENV: "x"})
        assert env["PYTHONPATH"] == str(SHIM_DIR)
        assert cc.DAYS_ENV not in env and cc.SENTINEL_ENV not in env


class TestPreflight:
    def test_a_moved_interpreter_passes(self):
        assert cc.preflight(cc.moved_env(_clean_env(), 14), 14) is None

    def test_an_unmoved_one_is_refused_with_the_measured_skew(self):
        why = cc.preflight(cc.today_env(_clean_env()), 14)
        assert why is not None and "not 14 days" in why

    def test_a_probe_that_cannot_run_or_prints_junk_is_refused(self):
        def crashed(*a, **k):
            return subprocess.CompletedProcess(a, 1, "", "boom")

        def junk(*a, **k):
            return subprocess.CompletedProcess(a, 0, "hello\n", "")

        assert "rc 1" in cc.preflight({}, 14, run=crashed)
        assert "unreadable" in cc.preflight({}, 14, run=junk)

    def test_a_foreign_sitecustomize_is_refused(self):
        def foreign(*a, **k):
            return subprocess.CompletedProcess(a, 0, json.dumps(
                {"shim": "/usr/lib/python3/sitecustomize.py", "moved": 14 * DAY,
                 "real": 0.0}) + "\n", "")

        assert "never loaded" in cc.preflight({}, 14, run=foreign)


class TestReportAndVerdict:
    def test_ids_with_spaces_and_dashes_survive(self):
        nodeid = 'tests/unit/t.py::test_pin[util.py:fd, "w" - x]'
        got = cc.read_report(1, "failed\t%s\nfailed\t%s\npassed\t%s\n"
                             % (nodeid, nodeid, cc.SELF_TEST))
        assert got.failed == {nodeid} and got.sentinel == {"passed"}

    def test_each_failure_lands_in_exactly_one_bucket(self):
        v = cc.classify(["bomb", "red", "flaky"], again=["bomb", "red"],
                        today_failed=["red"])
        assert (v.bombs, v.red, v.flaky) == (("bomb",), ("red",), ("flaky",))

    def test_the_annotation_names_the_offset_and_the_date(self):
        from datetime import date
        line = cc.bomb_line("t.py::test_x", 14, date(2026, 12, 8))
        assert line.startswith("::error title=clock canary +14d::t.py::test_x ")
        assert "moved 14 days ahead (to 2026-12-08)" in line
        assert "by 2026-12-08 at the latest" in line
        # The other cause of the same verdict, seen for real: test_logs.py
        # compared datetime's now with logging's time.time() stamp, which
        # this canary does not move, and was no date bomb.
        assert "a clock this canary leaves alone" in line
        assert "tests/clock_canary/sitecustomize.py" in line


class FakePytest:
    """Stands in for every subprocess the runner starts, in order.

    The first call is the preflight probe; each later one is a pytest run,
    answered from ``runs`` as ``(rc, {nodeid: outcome})``, written to the report
    file the runner named exactly as the plugin would.
    """

    def __init__(self, *runs, probe_ok=True):
        self.runs = list(runs)
        self.probe_ok = probe_ok
        self.calls = []

    def __call__(self, cmd, env=None, **kw):
        self.calls.append((cmd, env))
        if "-c" in cmd:
            moved = 14 * DAY if self.probe_ok else 0.0
            out = json.dumps({"shim": str(SHIM_DIR / "sitecustomize.py"),
                              "moved": moved, "real": 0.0})
            return subprocess.CompletedProcess(cmd, 0, out + "\n", "")
        rc, outcomes = self.runs.pop(0)
        with open(env[cc.REPORT_ENV], "a", encoding="utf-8", newline="\n") as out:
            for nodeid, outcome in outcomes.items():
                out.write("%s\t%s\n" % (outcome, nodeid))
        return subprocess.CompletedProcess(cmd, rc)


def _main(fake, tmp_path, *argv):
    summary = tmp_path / "summary.md"
    env = {"GITHUB_STEP_SUMMARY": str(summary)}
    from datetime import UTC, datetime
    rc = cc.main(list(argv), env=env, run=fake, now=datetime(2026, 11, 24, tzinfo=UTC))
    return rc, (summary.read_text(encoding="utf-8") if summary.exists() else "")


OK = {cc.SELF_TEST: "passed"}


class TestMain:
    def test_a_green_run_exits_zero_and_says_where_the_clock_was(self, tmp_path, capsys):
        fake = FakePytest((0, OK))
        rc, summary = _main(fake, tmp_path)
        assert rc == 0
        assert "no date bomb within 14 days (clock moved to 2026-12-08)" in summary
        cmd, env = fake.calls[1]
        assert cmd[1:8] == ["-m", "pytest", "-p", cc.PLUGIN, "--continue-on-collection-errors",
                            "tests/unit", "tests/functional"]
        assert env[cc.DAYS_ENV] == "14" and env[cc.SENTINEL_ENV] == cc.SELF_TEST

    def test_a_bomb_exits_one_and_flakes_and_old_reds_only_warn(self, tmp_path, capsys):
        fake = FakePytest((1, {**OK, "b": "failed", "r": "failed", "f": "failed"}),
                          (1, {"b": "failed", "r": "failed"}),     # re-run, moved
                          (1, {"r": "failed"}))                    # re-run, today
        rc, summary = _main(fake, tmp_path, "--days", "14", "--", "tests/unit", "-n", "auto")
        out = capsys.readouterr().out
        assert rc == 1
        assert "::error title=clock canary +14d::b fails" in out
        assert "::warning title=clock canary +14d::r fails on today's clock" in out
        assert "::warning title=clock canary +14d::f failed on the moved clock" in out
        assert "1 test(s) go red by 2026-12-08 (+14 days)" in summary
        (moved_rerun, moved_env), (today_rerun, today_env) = fake.calls[2], fake.calls[3]
        assert moved_rerun[-3:] == ["b", "f", "r"] and today_rerun[-3:] == ["b", "f", "r"]
        assert moved_env[cc.DAYS_ENV] == "14" and cc.DAYS_ENV not in today_env

    def test_only_old_reds_and_flakes_exit_zero(self, tmp_path):
        fake = FakePytest((1, {**OK, "r": "failed"}), (1, {"r": "failed"}), (1, {"r": "failed"}))
        assert _main(fake, tmp_path)[0] == 0

    # Every "cannot answer" says why in the job summary as well as in its
    # annotation: the run page is where a red advisory run is read.
    @staticmethod
    def _cannot_answer(result, capsys, why):
        rc, summary = result
        assert rc == 2
        assert summary.startswith("### clock canary: could not answer\n\n"), summary
        assert why in summary, summary
        assert "::error title=clock canary::" in capsys.readouterr().out

    def test_an_unmoved_clock_is_an_error_not_a_green(self, tmp_path, capsys):
        self._cannot_answer(_main(FakePytest(probe_ok=False), tmp_path), capsys,
                            "a green suite would prove nothing")

    @pytest.mark.parametrize("sentinel", ["skipped", "failed"])
    def test_a_sentinel_that_did_not_pass_is_an_error(self, tmp_path, capsys, sentinel):
        fake = FakePytest((1 if sentinel == "failed" else 0,
                           {cc.SELF_TEST: sentinel}))
        self._cannot_answer(_main(fake, tmp_path), capsys, "did not pass (%s)" % sentinel)

    @pytest.mark.parametrize("rc", [4, 1])
    def test_a_run_with_no_named_failure_is_an_error(self, tmp_path, capsys, rc):
        self._cannot_answer(_main(FakePytest((rc, OK)), tmp_path), capsys,
                            "pytest exited %d on the moved clock" % rc)

    def test_an_interrupted_moved_run_is_an_error_even_with_failures_named(self, tmp_path,
                                                                           capsys):
        # The runs continue past collection errors, so rc 2 can only mean the
        # suite stopped part way: sorting what did fail could call the rest
        # clean without having run it.
        fake = FakePytest((2, {**OK, "r": "failed"}), (1, {"r": "failed"}), (1, {"r": "failed"}))
        self._cannot_answer(_main(fake, tmp_path), capsys, "pytest exited 2 on the moved clock")
        assert len(fake.calls) == 2, "no re-run of a partial suite's failures"

    def test_a_rerun_that_could_not_run_is_an_error(self, tmp_path, capsys):
        fake = FakePytest((1, {**OK, "b": "failed"}), (4, {}), (0, {}))
        self._cannot_answer(_main(fake, tmp_path), capsys,
                            "the re-run on the moved clock exited 4")

    def test_artifacts_are_deselected_from_the_moved_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cc, "ARTIFACTS", {"t.py::test_x": "why"})
        fake = FakePytest((0, OK))
        _main(fake, tmp_path)
        assert fake.calls[1][0][-2:] == ["--deselect", "t.py::test_x"]

    @pytest.mark.parametrize("argv", [["--days", "0"], ["--days", "x"]])
    def test_a_bad_offset_is_a_usage_error(self, argv):
        with pytest.raises(SystemExit):
            cc.parse_args(argv)


@pytest.mark.parametrize("nodeid", sorted(cc.ARTIFACTS) or ["(none)"])
def test_every_artifact_names_a_test_that_exists_and_says_why(nodeid):
    if nodeid == "(none)":
        return
    path, _, name = nodeid.partition("::")
    func = re.split(r"::|\[", name)[-1]
    assert re.search(r"def %s\(" % re.escape(func),
                     (ROOT / path).read_text(encoding="utf-8")), nodeid
    assert len(cc.ARTIFACTS[nodeid]) > 20, "say why it cannot run on a moved clock"


class TestAPlantedBombIsCaught:
    """End to end, on a copy of the bomb that cost eleven nightlies.

    The original stamped a PR run with a fixed date and aged it against
    ``datetime.now()`` and a 13-day window. Planted with today's date, it passes
    today, passes a week ahead, and the canary's default offset finds it the
    first night it exists -- which is what 14 days was chosen for.
    """

    @pytest.fixture
    def stamped(self):
        # Today on the real clock, read from the C module the shim cannot
        # reach: this file runs under the canary too.
        import _datetime
        return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @pytest.fixture
    def bomb(self, tmp_path, stamped):
        (tmp_path / "test_bomb.py").write_text(textwrap.dedent("""
            from datetime import UTC, datetime, timedelta
            PR_RUN_CREATED = datetime.strptime("%s", "%%Y-%%m-%%dT%%H:%%M:%%SZ").replace(tzinfo=UTC)
            MAX_PR_RUN_AGE = timedelta(days=13)

            def test_the_pr_run_still_proves_the_tree():
                assert datetime.now(UTC) - PR_RUN_CREATED < MAX_PR_RUN_AGE
            """ % stamped), encoding="utf-8", newline="\n")
        return tmp_path

    def _canary(self, where, days, *targets):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--days", str(days), "--",
             *(targets or ("test_bomb.py",)), "-p", "no:cacheprovider"],
            cwd=where, env=_clean_env(), capture_output=True, text=True, timeout=300,
            check=False)

    def test_one_that_goes_off_at_import_is_named_and_hides_no_other(self, bomb, stamped):
        # A module-level bomb fails collection, and a serial pytest that hits
        # a collection error runs no test at all and exits 2. The canary used
        # to stop there with "cannot be told apart", naming no date, while the
        # bomb next to it never ran.
        (bomb / "test_import_bomb.py").write_text(textwrap.dedent("""
            from datetime import UTC, datetime, timedelta
            PR_RUN_CREATED = datetime.strptime("%s", "%%Y-%%m-%%dT%%H:%%M:%%SZ").replace(tzinfo=UTC)
            assert datetime.now(UTC) - PR_RUN_CREATED < timedelta(days=13), "stale at import"

            def test_unreached_when_the_import_fails():
                pass
            """ % stamped), encoding="utf-8", newline="\n")
        # And one that cannot import on any date: red regardless, not a bomb.
        (bomb / "test_broken_import.py").write_text(
            "import a_module_no_one_ships_for_the_clock_canary\n\n"
            "def test_unreached():\n    pass\n", encoding="utf-8", newline="\n")
        proc = self._canary(bomb, cc.DEFAULT_DAYS, "test_bomb.py", "test_import_bomb.py",
                            "test_broken_import.py")
        assert proc.returncode == 1, proc.stdout + proc.stderr
        for nodeid in ("test_import_bomb.py",
                       "test_bomb.py::test_the_pr_run_still_proves_the_tree"):
            assert re.search(r"::error title=clock canary \+14d::%s fails on a clock moved "
                             r"14 days ahead \(to \d{4}-\d\d-\d\d\)" % re.escape(nodeid),
                             proc.stdout), (nodeid, proc.stdout)
        assert ("::warning title=clock canary +14d::test_broken_import.py fails on "
                "today's clock as well") in proc.stdout, proc.stdout
        assert "::error title=clock canary +14d::test_broken_import.py" not in proc.stdout

    def test_the_default_offset_catches_it_and_says_when(self, bomb):
        proc = self._canary(bomb, cc.DEFAULT_DAYS)
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert re.search(r"::error title=clock canary \+14d::test_bomb\.py::"
                         r"test_the_pr_run_still_proves_the_tree fails on a clock moved "
                         r"14 days ahead \(to \d{4}-\d\d-\d\d\)", proc.stdout), proc.stdout

    def test_inside_its_window_it_is_left_alone(self, bomb):
        proc = self._canary(bomb, 7)
        assert proc.returncode == 0, proc.stdout + proc.stderr


class TestTheOffsetCoversTheProofWindows:
    def test_the_default_is_longer_than_every_window_in_ci_proven_tree(self):
        pt = _load("ci_proven_tree_for_clock_canary", ROOT / "scripts" / "ci_proven_tree.py")
        windows = {n: getattr(pt, n) for n in dir(pt)
                   if n.startswith("MAX_") and isinstance(getattr(pt, n), timedelta)}
        assert {"MAX_PR_RUN_AGE", "MAX_INHERIT_AGE", "MAX_NIGHTLY_AGE"} <= set(windows)
        longest = max(windows.values())
        assert timedelta(days=cc.DEFAULT_DAYS) > longest, (
            "a fixture dated today and aged against a %s window would not fail the "
            "canary on its first night; raise DEFAULT_DAYS past it" % longest)


@pytest.mark.skipif(not CANARY_YML.exists(), reason=".github not reachable")
class TestTheWorkflow:
    def _text(self):
        return CANARY_YML.read_text(encoding="utf-8")

    def test_it_runs_the_script_with_the_default_offset(self):
        assert "scripts/clock_canary.py" in self._text()

    def test_it_is_advisory_never_required(self):
        names = {ln.strip() for ln in REQUIRED.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")}
        assert not any(n.startswith("clock-canary") for n in names), names

    def test_a_red_run_on_main_opens_a_tracker(self):
        assert re.search(r'"clock-canary"', ALERT_YML.read_text(encoding="utf-8"))

    def test_a_change_to_the_canary_runs_it_before_it_merges(self):
        text = self._text()
        # This file included: it holds the sentinel the script names.
        assert cc.SELF_TEST.startswith("tests/unit/test_clock_canary.py::")
        for path in ("tests/clock_canary/**", "tests/unit/test_clock_canary.py",
                     "scripts/clock_canary.py", ".github/workflows/clock-canary.yml"):
            assert text.count('"%s"' % path) == 2, (path, "pull_request and push")

    def test_it_is_not_on_the_release_path(self):
        # publish.yml releases on `ci` alone; a canary inside ci.yml could
        # block or skip a release on a date that has not happened yet.
        for path in WORKFLOWS.glob("*.yml"):
            if path != CANARY_YML:
                assert cc.DAYS_ENV not in path.read_text(encoding="utf-8"), path.name
                assert "clock_canary" not in path.read_text(encoding="utf-8"), path.name
