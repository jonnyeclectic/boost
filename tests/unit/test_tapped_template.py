# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`tapped` restores a session-built template instead of running `boost tap`.

A test that asked for `tapped` used to pay for a real `git clone`, a catalog
scan and a config write on every run. The fixture now builds one tapped HOME
per session (``tapped_template``) and copies it into the test's sandbox. A copy
is only a faithful substitute if three things hold, and each is pinned here:

* it is what a real `boost tap` leaves, not a hand-picked subset of it;
* nothing a test does to its copy can reach the template, or the test after it
  would start from a HOME the previous one had edited;
* the things that key off file times and git's index still read "just tapped".

Under mutmut the copy is bypassed -- ``tapped`` runs the real command per test,
as it did before the template existed -- and that is pinned here too.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import _tapped_support
import pytest

from boost_cli.core import catalog, logs, registry

REPO_ROOT = Path(__file__).resolve().parents[2]

# These pin conftest plumbing, which mutmut never mutates, but each one taps (or
# builds the template), so under mutmut they would join the test set of every
# tap-path mutant for nothing -- and the template ones assume the copy path that
# mutmut turns off, so in its stats run they would fail and abort the run. The
# clean-test pass sets the variable to "" and does run them.
pytestmark = pytest.mark.skipif(
    _tapped_support.under_mutmut(),
    reason="mutmut run: `tapped` taps per test, so the template is not in play")


def _fingerprint(root: Path) -> dict[str, tuple]:
    """Every entry under ``root``: relative path -> kind and content digest.

    ``os.walk`` without ``followlinks`` and ``lstat`` throughout, so a symlink
    is recorded as the link rather than as whatever it points at -- the shape
    ``copytree(symlinks=True)`` has to preserve.
    """
    out: dict[str, tuple] = {}
    for top, dirs, files in os.walk(root):
        for name in (*dirs, *files):
            p = Path(top) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                out[rel] = ("link", os.readlink(p))
            elif p.is_dir():
                out[rel] = ("dir",)
            else:
                out[rel] = ("file", hashlib.sha256(p.read_bytes()).hexdigest())
    return out


def _inodes(root: Path) -> set[tuple[int, int]]:
    """``(device, inode)`` of every non-directory under ``root``."""
    found = set()
    for top, _dirs, files in os.walk(root):
        for name in files:
            st = (Path(top) / name).lstat()
            found.add((st.st_dev, st.st_ino))
    return found


def _git(repo: Path, *args: str) -> str:
    # Identity passed with -c: the sandbox HOME carries no ~/.gitconfig.
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@boost.test",
         "-C", str(repo), *args],
        check=True, capture_output=True, text=True)
    return proc.stdout


class TestTheCopyIsTheTemplate:
    def test_a_tapped_home_matches_the_template_byte_for_byte(
            self, tapped, sandbox, tapped_template):
        # Everything, not just repos/<tap>, cache/<tap>.json and config.json:
        # `boost tap` also writes the refresh marker, the journal, the
        # completion names and a log, and a test reading any of them must see
        # what it saw when the fixture ran the command itself.
        assert _fingerprint(sandbox) == _fingerprint(tapped_template)

    def test_it_is_what_a_real_tap_leaves(
            self, tapped, sandbox, boost, fixture_tap_src, tmp_path,
            monkeypatch):
        # The template is built by `boost tap` itself, so this is the check
        # that the *copy* loses nothing a second HOME tapped the long way has:
        # dotfiles, empty directories, the `.git` tree.
        real = tmp_path / "tapped-the-long-way"
        real.mkdir()
        monkeypatch.setenv("HOME", str(real))
        logs.reset()    # the logger is still bound to the first HOME's log
        boost("tap", fixture_tap_src)
        got, want = _fingerprint(sandbox), _fingerprint(real)
        clone = ".boost/repos/fixture-tap/.git/"

        def volatile(rel):
            # Written with a clock, or stat data git stamps per checkout --
            # the reflogs carry the second the clone ran, so comparing them
            # passes or fails on whether two taps straddled a tick.
            return rel in {".boost/config.json", ".boost/cache/fixture-tap.json",
                           ".boost/state/pulse.jsonl", ".boost/logs/boost.log",
                           clone + "index"} or rel.startswith(clone + "logs/")

        assert set(got) == set(want)
        assert {k: v for k, v in got.items() if not volatile(k)} == \
               {k: v for k, v in want.items() if not volatile(k)}
        # ...and the files left out of that comparison, compared by meaning.
        for rel, drop in ((".boost/config.json", "added_at"),
                          (".boost/cache/fixture-tap.json", "generated")):
            a = json.loads((sandbox / rel).read_text(encoding="utf-8"))
            b = json.loads((real / rel).read_text(encoding="utf-8"))
            for blob in (a, b):
                for row in blob.get("taps", [blob]):
                    row.pop(drop, None)
            assert a == b, rel

    def test_file_times_survive_the_copy(self, tapped, sandbox, tapped_template):
        # The refresh marker and the catalog cache are read by mtime
        # (`registry.refresh_age_days`, `catalog._ENTRY_CACHE`'s stamp), and
        # `copytree` is only safe because its default `copy2` keeps them.
        for rel in (".boost/state/last-tap-refresh", ".boost/config.json",
                    ".boost/cache/fixture-tap.json"):
            assert ((sandbox / rel).stat().st_mtime_ns
                    == (tapped_template / rel).stat().st_mtime_ns), rel

    def test_the_tap_reads_as_just_added(self, tapped, sandbox):
        tap = registry.get("fixture-tap")
        assert tap.is_cloned and not tap.is_broken_clone
        assert tap.path == sandbox / ".boost" / "repos" / "fixture-tap"
        # Without a rebuild: the commit the cache stamps is the clone's HEAD.
        assert catalog.cache_is_fresh(tap) is True
        assert registry.refresh_age_days() is not None
        # git's index records stat data that a copy cannot keep (inode,
        # ctime); a status that re-reads the content must still call it clean.
        assert _git(tap.path, "status", "--porcelain") == ""


class TestTheTemplateDoesNotNameItself:
    def test_no_file_in_it_contains_its_own_path(self, tapped_template):
        # The reason a copy is valid at all: a path baked into config.json, a
        # cache, a `.git/config` or the index would point every copy back at
        # the template, and the tap would half-work -- listed from the copy,
        # read from the original. Both spellings, because macOS resolves a
        # tmp dir under /var to /private/var.
        # ...and as JSON writes it: on Windows `C:\\Users\\x` is stored with its
        # backslashes doubled, which the plain spelling never matches, so the
        # test would pass there without looking at anything.
        paths = {str(tapped_template), str(tapped_template.resolve())}
        needles = {p.encode() for p in paths} | {
            json.dumps(p)[1:-1].encode() for p in paths}
        hits = [p.relative_to(tapped_template).as_posix()
                for p in tapped_template.rglob("*")
                if p.is_file() and not p.is_symlink()
                and any(n in p.read_bytes() for n in needles)]
        assert hits == []

    def test_the_tap_points_at_the_shared_source_not_the_template(
            self, tapped, fixture_tap_src):
        tap = registry.get("fixture-tap")
        assert Path(tap.url) == fixture_tap_src.resolve()
        assert _git(tap.path, "remote", "get-url", "origin").strip() == \
            str(fixture_tap_src.resolve())


class TestAHomeThatIsNotEmptyKeepsTheOldBehaviour:
    @pytest.fixture()
    def seeded(self, sandbox):
        """A HOME with a tap row already in config.json, before `tapped`."""
        cfg = sandbox / ".boost" / "config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"taps": [
            {"name": "already-here", "url": "/nowhere/already-here",
             "curated": False}]}), encoding="utf-8")
        return cfg

    def test_tapped_adds_a_row_instead_of_replacing_the_config(
            self, seeded, tapped):
        # `boost tap` appends to the config it finds. A copy of the template's
        # config.json would have replaced it and dropped "already-here", so the
        # fixture taps for real when anything is already in the HOME.
        names = [t.name for t in registry.list_taps()]
        assert sorted(names) == ["already-here", "fixture-tap"]
        assert registry.get("fixture-tap").is_cloned


class TestNothingReachesTheTemplate:
    def test_no_file_is_shared_with_the_template(
            self, tapped, sandbox, tapped_template):
        # A hard link would let an edit to the copy rewrite the template, and
        # a local `git clone` hard-links objects by default -- so a copy that
        # preserved links instead of bytes would pass every other test here
        # until something finally wrote through one.
        assert _inodes(sandbox).isdisjoint(_inodes(tapped_template))

    def test_a_symlink_in_the_copy_never_leads_into_the_template(
            self, tapped, sandbox, tapped_template):
        root = tapped_template.resolve()
        for top, dirs, files in os.walk(sandbox):
            for name in (*dirs, *files):
                p = Path(top) / name
                if p.is_symlink():
                    assert not p.resolve().is_relative_to(root), p

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="creating a symlink needs a privilege there")
    def test_the_copy_keeps_a_link_a_link(self, tmp_path):
        # The real template holds no symlink today (`.agents/skills` is empty),
        # so the test above walks nothing and `symlinks=True` is pinned by no
        # one. Plant the shapes a template could grow: a relative link, and a
        # dangling one -- which `symlinks=False` turns into a copy error.
        template = tmp_path / "template"
        (template / "d").mkdir(parents=True)
        (template / "d" / "file").write_text("x", encoding="utf-8")
        (template / "rel").symlink_to("d/file")
        (template / "dangling").symlink_to("nowhere")
        copy = _tapped_support.copy_template(template, tmp_path / "copy")
        assert (copy / "rel").is_symlink()
        assert os.readlink(copy / "rel") == "d/file"
        assert (copy / "dangling").is_symlink()
        assert not (copy / "d" / "file").samefile(template / "d" / "file")

    def test_editing_the_copy_leaves_the_template_alone(
            self, tapped, sandbox, boost, tapped_template, restore_tapped_home,
            tmp_path):
        before = _fingerprint(tapped_template)
        tap = registry.get("fixture-tap")

        # An edit to a tracked file, committed -- writes the working tree,
        # `.git/objects`, the refs, the reflog and the index.
        skill = tap.path / "skills" / "brainstorming" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nedited\n",
                         encoding="utf-8")
        _git(tap.path, "commit", "-aqm", "edit in the copy")
        # State a command writes: the lock, the store, the journal.
        boost("install", "brainstorming")
        assert _fingerprint(tapped_template) == before

        # Then everything at once: `untap` deletes the clone, the cache and
        # the config row. Through a shared file this is the call that would
        # take the template's copy with it.
        boost("untap", "fixture-tap")
        assert not tap.path.exists()
        assert _fingerprint(tapped_template) == before

        # A fresh `tapped` -- the same restore, into a new HOME -- sees the
        # original rather than the edited copy.
        fresh = restore_tapped_home(tmp_path / "second-home")
        assert _fingerprint(fresh) == before
        original = (fresh / ".boost" / "repos" / "fixture-tap" / "skills"
                    / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
        assert "edited" not in original

    def test_two_restores_are_independent_homes(
            self, restore_tapped_home, tapped_template, tmp_path):
        a = restore_tapped_home(tmp_path / "a")
        b = restore_tapped_home(tmp_path / "b")
        (a / ".boost" / "config.json").write_text("{}", encoding="utf-8")
        assert _fingerprint(b) == _fingerprint(tapped_template)


class TestTheTemplateBelongsToItsWorker:
    def test_it_lives_under_this_workers_basetemp(
            self, tapped_template, tmp_path_factory):
        # `tmp_path_factory` is per xdist worker (`.../popen-gwN`), so a
        # template under it can never be the one another worker is copying
        # from or, worse, building. A path outside it would be shared.
        base = tmp_path_factory.getbasetemp().resolve()
        assert tapped_template.resolve().is_relative_to(base)
        worker = os.environ.get("PYTEST_XDIST_WORKER")
        if worker:      # basetemp is `<root>/popen-gw3` for worker gw3
            assert "popen-" + worker in tapped_template.parts

    def test_it_is_not_a_test_sandbox_or_the_session_home(
            self, tapped_template, sandbox):
        assert tapped_template.resolve() != sandbox.resolve()
        assert tapped_template.resolve() != Path(os.environ["HOME"]).resolve()


@pytest.fixture()
def copies_into(monkeypatch):
    """The destination of every top-level ``shutil.copytree`` the test makes.

    ``copytree`` recurses through the module attribute, so a spy on it is also
    called once per subdirectory; only the outermost call is recorded.
    """
    real, dests, running = shutil.copytree, [], []

    def spy(src, dst, *args, **kwargs):
        if not running:
            dests.append(Path(dst))
        running.append(None)
        try:
            return real(src, dst, *args, **kwargs)
        finally:
            running.pop()

    monkeypatch.setattr(shutil, "copytree", spy)
    return dests


class TestMutmutTapsForRealAndEverythingElseCopies:
    """``tapped`` copies the template unless mutmut is driving the run.

    mutmut decides which tests run against a mutant from the functions each
    test reached in its stats pass, and credits a pass's hits to one test
    (``mutmut.runners.harness.run_stats``). A copy reaches none of
    ``registry.add``, ``catalog.rebuild_tap`` or ``gitutil.clone_shallow``, so
    behind the template those mutants lose every ``tapped`` test but one.
    mutmut says it is driving through ``MUTANT_UNDER_TEST`` -- ``stats`` while
    it records, ``fail`` for its forced-failure check, the mutant's own name
    for a mutant run (``mutmut/__main__.py``, ``workers/isolation.py``) -- and
    sets it to the empty string for the clean pass that runs no mutant.
    The fixtures below set it *before* ``tapped`` is requested: a fixture reads
    the environment when it is set up, not when the test body runs.
    """

    @pytest.fixture()
    def mutmut_stats(self, monkeypatch):
        monkeypatch.setenv("MUTANT_UNDER_TEST", "stats")

    @pytest.fixture()
    def mutmut_clean_pass(self, monkeypatch):
        monkeypatch.setenv("MUTANT_UNDER_TEST", "")

    @pytest.mark.parametrize("value", [
        "stats", "fail", "list_all_tests",
        "boost_cli.core.registry.x_add__mutmut_3"])
    def test_every_value_mutmut_drives_with_counts(self, monkeypatch, value):
        monkeypatch.setenv("MUTANT_UNDER_TEST", value)
        assert _tapped_support.under_mutmut() is True

    @pytest.mark.parametrize("value", [None, ""])
    def test_unset_and_the_clean_pass_do_not(self, monkeypatch, value):
        if value is None:
            monkeypatch.delenv("MUTANT_UNDER_TEST", raising=False)
        else:
            monkeypatch.setenv("MUTANT_UNDER_TEST", value)
        assert _tapped_support.under_mutmut() is False

    def test_under_mutmut_the_tap_is_real_and_the_template_untouched(
            self, mutmut_stats, copies_into, tapped, sandbox, request):
        # Neither the template nor the function copying it was even built for
        # this test -- a session fixture requested here would be tapped under
        # mutmut and credited to whichever test came next.
        assert "tapped_template" not in request.fixturenames
        assert "restore_tapped_home" not in request.fixturenames
        assert copies_into == []
        # ...and the HOME is nonetheless a tapped one.
        tap = registry.get("fixture-tap")
        assert tap.is_cloned and not tap.is_broken_clone
        assert tap.path == sandbox / ".boost" / "repos" / "fixture-tap"
        assert catalog.cache_is_fresh(tap) is True
        assert _git(tap.path, "status", "--porcelain") == ""

    def test_outside_mutmut_the_template_is_copied(
            self, copies_into, tapped, sandbox, request):
        assert "tapped_template" in request.fixturenames
        assert copies_into == [sandbox]

    def test_the_clean_pass_copies_too(
            self, mutmut_clean_pass, copies_into, tapped, sandbox):
        # "" means mutmut is running the suite with no mutant active, so there
        # is no attribution to protect -- the same as an ordinary pytest run.
        assert copies_into == [sandbox]


class TestTheBuildCannotSeeTheRequestingTest:
    """The template is cached for the worker; a test's patches last one test.

    ``tapped`` asks for the template from inside the first test that reaches
    it, so what that test (or a fixture listed before ``tapped``) has patched is
    live when it is built. Built in-process, a fixture stubbing
    ``catalog.scan_dir`` cached an empty catalog and a later, unrelated test
    failed ``0 > 0``. The build is a child process with a built environment.
    """

    @pytest.fixture()
    def patched(self, monkeypatch, tmp_path):
        """Everything of this process's a build could pick up, patched."""
        monkeypatch.setattr(catalog, "scan_dir", lambda *a, **k: [])
        monkeypatch.setenv("BOOST_HOME", str(tmp_path / "decoy-boost-home"))
        monkeypatch.setenv("PATH", str(tmp_path / "no-such-bin"))
        monkeypatch.setenv("BOOST_LIVE_PATCH", "1")
        return tmp_path / "decoy-boost-home"

    def test_a_build_under_patches_equals_the_template(
            self, patched, tmp_path, pristine_env, fixture_tap_src, request):
        # The builder itself, called while the patches are live, so this does
        # not depend on whether another test already built the template.
        home = _tapped_support.build_tapped_home(
            tmp_path / "built-under-patches", fixture_tap_src, pristine_env,
            REPO_ROOT)
        template = request.getfixturevalue("tapped_template")
        cache = json.loads((home / ".boost/cache/fixture-tap.json").read_text(
            encoding="utf-8"))
        assert cache["skills"], "the stubbed scanner reached the child"
        assert not patched.exists(), "BOOST_HOME reached the child"
        assert cache["skills"] == json.loads(
            (template / ".boost/cache/fixture-tap.json").read_text(
                encoding="utf-8"))["skills"]
        assert set(_fingerprint(home)) == set(_fingerprint(template))

    def test_a_test_that_stubs_the_scanner_before_tapped_cannot_poison_it(
            self, patched, fixture_tap_src, pristine_env, request):
        # The reviewer's reproduction, through the fixtures. Whether this test
        # is the one that builds the template depends on which test the worker
        # ran first, so it can only fail when it is -- the test above is the
        # one that does not depend on order.
        #
        # `fixture_tap_src` and `pristine_env` are named here although the body
        # never uses them: the body asks for `tapped` dynamically, and a
        # session fixture first requested from there is built under `patched`
        # -- `fixture_tap_src` runs `make_fixture.py` with the live environment,
        # so with PATH stubbed it failed, and the failure was cached for every
        # later test on the worker. Named in the signature, pytest builds them
        # before any function-scoped patch (a real `tapped` user gets that
        # through `tapped`'s own signature).
        request.getfixturevalue("tapped")
        template = request.getfixturevalue("tapped_template")
        sandbox = request.getfixturevalue("sandbox")
        for home in (template, sandbox):
            cache = json.loads((home / ".boost/cache/fixture-tap.json").read_text(
                encoding="utf-8"))
            assert cache["skills"], home

    def test_the_child_environment_is_not_the_live_one(
            self, patched, pristine_env, tmp_path):
        env = _tapped_support.child_env(
            pristine_env, tmp_path / "home", "file:///no-manifest", REPO_ROOT)
        assert "BOOST_LIVE_PATCH" not in env
        assert "BOOST_HOME" not in env
        assert env["PATH"] == pristine_env["PATH"] != os.environ["PATH"]
        assert env["HOME"] == str(tmp_path / "home")

    def test_the_child_environment_is_what_the_sandbox_gives_a_test(
            self, sandbox_env_delta, pristine_env, tmp_path):
        # SANDBOX_ENV / SANDBOX_UNSET are a second copy of what `sandbox`
        # sets. Compared against what `sandbox` really changed, so a variable
        # added to one and not the other fails here and not as a template that
        # differs from every test's HOME.
        env = _tapped_support.child_env(
            pristine_env, tmp_path / "home", "file:///no-manifest", REPO_ROOT)
        per_test = {"HOME", "USERPROFILE", "BOOST_SHARD_MANIFEST"}  # tmp paths
        differs = {k: (v, env.get(k)) for k, v in sandbox_env_delta.items()
                   if k not in per_test and env.get(k) != v}
        assert differs == {}
        for name in _tapped_support.SANDBOX_UNSET:
            assert name not in env
        assert {k: env[k] for k in _tapped_support.SANDBOX_ENV} == \
            _tapped_support.SANDBOX_ENV

    def test_the_child_runs_git_with_auto_maintenance_off(self, pristine_env):
        env = _tapped_support.child_env(
            pristine_env, Path("h"), "file:///no-manifest", REPO_ROOT)
        count = int(env["GIT_CONFIG_COUNT"])
        pairs = {env["GIT_CONFIG_KEY_%d" % i]: env["GIT_CONFIG_VALUE_%d" % i]
                 for i in range(count)}
        assert pairs["maintenance.auto"] == "false"


class TestABadTemplateFailsLoudly:
    @pytest.fixture()
    def home(self, restore_tapped_home, tmp_path):
        return restore_tapped_home(tmp_path / "doctored-home")

    @pytest.fixture()
    def problems(self, home, fixture_tap_src, pristine_env, tmp_path):
        env = _tapped_support.child_env(
            pristine_env, home, "file:///no-manifest", REPO_ROOT)
        return lambda: _tapped_support.check_tapped_home(
            home, fixture_tap_src, env)

    def test_a_good_template_has_no_problems(self, problems):
        assert problems() == []

    def test_a_missing_tap_row(self, home, problems):
        (home / ".boost/config.json").write_text('{"taps": []}', encoding="utf-8")
        assert any("no tap row" in p for p in problems())

    def test_a_row_for_some_other_source(self, home, problems):
        cfg = home / ".boost/config.json"
        blob = json.loads(cfg.read_text(encoding="utf-8"))
        blob["taps"][0]["url"] = "/somewhere/else"
        cfg.write_text(json.dumps(blob), encoding="utf-8")
        assert any("points at" in p for p in problems())

    def test_a_catalog_with_nothing_in_it(self, home, problems):
        # `boost tap` exiting 0 having catalogued nothing -- the failure that
        # would otherwise show as dozens of tests finding no skills.
        cache = home / ".boost/cache/fixture-tap.json"
        blob = json.loads(cache.read_text(encoding="utf-8"))
        blob["skills"] = []
        cache.write_text(json.dumps(blob), encoding="utf-8")
        assert any("lists no skills" in p for p in problems())

    def test_a_missing_catalog(self, home, problems):
        (home / ".boost/cache/fixture-tap.json").unlink()
        assert any("unreadable" in p for p in problems())

    def test_a_clone_without_a_head(self, home, problems):
        (home / ".boost/repos/fixture-tap/.git/HEAD").unlink()
        assert any("no HEAD" in p for p in problems())

    def test_a_catalog_that_describes_another_commit(self, home, problems):
        cache = home / ".boost/cache/fixture-tap.json"
        blob = json.loads(cache.read_text(encoding="utf-8"))
        blob["commit"] = "0" * 40
        cache.write_text(json.dumps(blob), encoding="utf-8")
        assert any("describes commit" in p for p in problems())

    def test_a_failed_tap_raises_instead_of_returning_a_home(
            self, tmp_path, pristine_env):
        with pytest.raises(AssertionError, match="template is bad") as err:
            _tapped_support.build_tapped_home(
                tmp_path / "root", tmp_path / "not-a-repo", pristine_env,
                REPO_ROOT)
        assert "boost tap exited" in str(err.value)


class TestTheSupportModuleIsSafeToImport:
    def test_it_runs_nothing_at_import(self):
        # A test module imports it at collection time, so a statement that
        # does work -- or can raise -- would abort the run before one test.
        tree = ast.parse(Path(_tapped_support.__file__).read_text(
            encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Expr):
                assert isinstance(node.value, ast.Constant), "only a docstring"
            elif isinstance(node, ast.Assign):
                ast.literal_eval(node.value)    # constants only
            else:
                assert isinstance(node, (ast.Import, ast.ImportFrom,
                                         ast.FunctionDef, ast.ClassDef)), node

    def test_no_test_here_reaches_for_conftest_by_name(self):
        # `import conftest` is whichever conftest.py was imported last; under
        # a bare `pytest` that is tests/langchain's, not tests/'s.
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                    for a in n.names}
        imported |= {n.module for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom)}
        assert "conftest" not in imported
