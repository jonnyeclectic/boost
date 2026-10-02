# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the boost test suite.

Every test runs against a throwaway $HOME so nothing can touch the real
environment. Functional tests drive the CLI IN-PROCESS via boost_cli.cli.main
so the command modules count toward coverage.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The directory pytest was started from, captured before any fixture can chdir.
# Under the mutation gate that is `mutants/`, not the checkout — see
# :func:`watched_roots`.
_START_DIR = Path.cwd()

# The real home directory, captured now: `checkout_root` stops there the way
# `scopes.project_root` does, and by the time the guard first runs the `sandbox`
# fixture has already pointed `$HOME` at a tempdir.
_REAL_HOME = Path(os.environ.get("HOME") or Path.home())

# A name joined into probe paths that are never read, only stat-ed. It has to
# satisfy `util.is_safe_component` and the skill-name rule, so it cannot be a
# marker like "<probe>".
_PROBE_NAME = "boost-repo-guard-probe"

# What `scopes.PROJECT_MARKERS` looks for, duplicated rather than imported so
# the guard keeps working if a mutant deletes that constant. `.git` is a *file*
# in a worktree and a directory in a plain clone, so this is `exists`, not
# `is_dir`.
_VCS_MARKERS = (".git", ".hg", ".svn")


def checkout_root(start, home=None):
    """The working tree ``start`` sits in — the same answer `scopes` computes.

    `scopes.resolve_base` walks *up* from the cwd for a VCS marker, so this has
    to as well or the guard watches a directory nothing writes to. It matters
    because `ROOT` cannot be trusted for this: mutmut copies `tests/` into
    `mutants/` and runs the suite from there, so under the mutation gate
    ``Path(__file__).parent.parent`` is ``<checkout>/mutants`` — the one run
    where a stray project install is most likely, and the one where deriving
    the checkout from `__file__` silently stops naming the checkout.

    **The walk stops at ``$HOME``**, exactly where `scopes.project_root` stops
    and for the same reason: dotfile setups make ``~/.git`` common, and no
    scope-resolved writer can put a project install at ``$HOME`` — that is what
    that stop guarantees. Without it, running `pytest` from a directory under a
    dotfiles repo makes the guard fingerprint the live ``~/.claude``,
    ``~/.codex`` and ``~/.boost`` trees, so a `boost install` in another
    terminal, or Claude Code rewriting its own ``settings.json``, fails
    whichever test happened to be running — an accusation against an innocent
    test, in exchange for watching a tree nothing under test can write to.

    Falls back to ``start`` when there is no marker above it, which is what a
    `pytest` run from an unpacked sdist looks like.
    """
    start = Path(start)
    home = Path(home) if home is not None else _REAL_HOME
    for d in (start, *start.parents):
        if d == home:
            break
        if any((d / m).exists() for m in _VCS_MARKERS):
            return d
    return start


def watched_roots(*candidates) -> list[Path]:
    """The working trees a stray project-scope write could land in.

    More than one, because the writers disagree about what "the project" is.
    `scopes.resolve_base` walks *up* for a VCS marker, so under the mutation
    gate — which runs the suite from `mutants/` inside the checkout — a project
    install lands at the **repo** root. A cwd-relative writer such as
    `claude_settings.settings_path("project")` — whose ``project_dir`` defaults
    to ``Path.cwd()`` (`boost_cli/core/claude_settings.py`) — lands in
    `mutants/` itself. Both are therefore reachable from one run, and watching
    only the one `__file__` names would miss whichever the escape used.

    Deduplicated in the order given, so the caller decides which is reported
    first and a `mutants/`-shaped run costs one extra root rather than two
    copies of the same one.
    """
    seen, out = set(), []
    for c in candidates:
        p = Path(c)
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def agent_specs() -> dict:
    """The agent table the guard probes: ``DEFAULTS`` plus whatever is live.

    ``DEFAULTS`` is the floor, so the guard means the same thing on every
    machine and an agent someone disabled locally is still one the suite can
    write to. The developer's own ``config.json`` is merged **over** it,
    because `store.install` iterates the live table: an agent added by hand is
    one boost writes to under project scope and would otherwise be the one
    place the guard is blind.

    Best-effort and never raises. `config.load` reads a user-editable file and
    `paths.expand` raises `BoostError` for an unresolvable ``${VAR}`` — a state
    CLAUDE.md says boost deliberately tolerates. Letting either propagate out
    of an autouse fixture would turn one developer's config into a setup error
    on every test in the suite. Raw rows are used rather than
    `agents.known_agents`, so nothing is expanded and no environment is read.
    """
    from boost_cli.core import config
    specs = dict(config.DEFAULTS["agents"])
    try:
        live = config.load().get("agents")
        if isinstance(live, dict):
            specs.update({n: s for n, s in live.items()
                          if isinstance(s, dict) and s.get("dir")})
    except Exception:
        # Bare, and deliberately: this runs in an autouse fixture, so any
        # exception here is a setup error on every test in the suite.
        pass
    return specs


def _probe_dotdir(spec) -> str:
    """`agents.project_dotdir`, off a raw spec row and without reading config.

    Pinned against the real one by `test_repo_root_guard.py`. Inlined because
    the real one calls `known_agents()`, which calls `paths.expand` on every
    agent's dir — see :func:`agent_specs` for why that cannot happen here.
    """
    declared = spec.get("project_dir") or ""
    if declared in ("", ".", "..") or "/" in declared or "\\" in declared:
        return Path(str(spec["dir"])).parent.name
    return declared


def project_scope_probes(root, specs=None) -> list[Path]:
    """Paths under ``root`` that a project-scope write materializes.

    Every entry is produced by *calling the writer's own path function* with
    ``base=root`` rather than by spelling the layout out here. A hardcoded list
    would be wrong the first time an agent, a hook host or a workflow slot is
    added — and wrong silently, since what it guards is an absence.

    The agent set is :func:`agent_specs` — ``DEFAULTS`` merged under the live
    config — and ``specs`` overrides it so a test can pin the derivation
    against a table that does not vary by machine.

    What this covers is project *scope*, not every cwd-relative write. A few
    commands join straight onto ``Path.cwd()`` (`boost distill` writes
    ``<cwd>/<name>.SKILL.md`, `boost bmad` takes the cwd as its project base),
    and those land outside every probe here. The `sandbox` fixture's chdir is
    what contains them; this is the backstop for the scope-resolved writers,
    which are the ones that reach a checkout the cwd is not even inside.
    """
    from boost_cli.core import (
        claude_settings,
        hookhost,
        projectlock,
        rules,
        scopes,
        store,
        workflows,
    )
    root = Path(root)
    if specs is None:
        specs = agent_specs()
    # The lock file, and the directory holding it: a test that writes the lock
    # and removes the file in its own cleanup leaves `<root>/.boost/` behind,
    # gitignored, with before == after == absent. The directory also covers
    # `projectlock`'s corrupt-file quarantine sibling.
    probes: list[Path] = [projectlock.lock_path(root),
                          projectlock.lock_path(root).parent]

    for name, spec in specs.items():
        if not spec.get("project_scope", True):
            continue          # antigravity: no repo-local path to watch
        skills_dir = Path(str(spec["dir"]))
        dotdir = _probe_dotdir(spec)
        probes.append(scopes.agent_root(skills_dir, root, dotdir)
                      / skills_dir.name)
        mode, target = rules.rule_target(name, skills_dir, _PROBE_NAME,
                                         base=root, dotdir=dotdir)
        # A context-file rule edits a file that already exists and that every
        # agent working this repo loads as instructions, so that one is watched
        # by content; a rules-dir rule creates a file, so watch the directory.
        probes.append(target if mode == rules.MODE_CLAUDE else target.parent)
        probes.extend(
            workflows.workflow_target(skills_dir, slot, _PROBE_NAME,
                                      base=root, agent=name,
                                      dotdir=dotdir).parent
            for slot in (workflows.SLOT_COMMANDS, workflows.SLOT_AGENTS))

    probes.extend(
        claude_settings.settings_path("project", project_dir=root, host=host)
        for host in hookhost.hosts())
    # `<root>/.mcp.json`, named rather than derived, and the standing exception
    # to "a new target is covered by adding it to a table": `store.
    # project_mcp_sidecar` is joined straight onto the base by
    # `register_project_mcp`/`unregister_project_mcp`, so no table mentions it.
    # A stray project install is still *detected* without it — both writers sit
    # beside a `projectlock` write, which is probed — but this is the artifact
    # that is committable and shows up in `git status`, so leaving it out of
    # the report means the developer cleans up everything the guard names and
    # still commits one file.
    probes.append(store.project_mcp_sidecar(root))

    seen, unique = set(), []
    for p in probes:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _dir_entries(d):
    """``name|kind[|target|size|mtime_ns]`` for each immediate entry of ``d``.

    A symlink carries its *target*, not just its name, for the same reason a
    file carries its size: `store.install` under project scope links
    ``<root>/.claude/skills/<name>`` into the canonical store, so a reinstall
    that re-points an existing link changes nothing a name-only listing can
    see. It is read with `os.readlink` rather than `resolve()` — one syscall,
    no walk, and a broken link answers instead of vanishing.
    """
    out = []
    with os.scandir(d) as it:
        for e in it:
            if e.is_symlink():
                out.append("%s|l|%s" % (e.name, os.readlink(e.path)))
            elif e.is_dir():
                out.append("%s|d" % e.name)
            else:
                st = e.stat()
                out.append("%s|f|%d|%d" % (e.name, st.st_size, st.st_mtime_ns))
    return out


_CONTEXT_FILES: dict[str, object] = {}


def context_file_facts() -> tuple[frozenset[str], str]:
    """``(filenames, marker prefix)`` for the agents' shared context files.

    Both derived from `rules`, never spelled out, so a new context-file agent
    is covered the moment its row lands in `rules.CONTEXT_FILES` — and cached,
    because this is on the teardown path of every test.
    """
    if not _CONTEXT_FILES:
        from boost_cli.core import rules
        _CONTEXT_FILES["names"] = frozenset(
            n for pair in rules.CONTEXT_FILES.values() for n in pair)
        _CONTEXT_FILES["marker"] = rules.BLOCK_START.split("%s")[0]
    return _CONTEXT_FILES["names"], _CONTEXT_FILES["marker"]


def managed_blocks(path, marker) -> str:
    """The ``marker`` lines of ``path``, in order — boost's footprint in it.

    A context file (``CLAUDE.local.md``, ``GEMINI.md``, ``AGENTS.md``) is the
    one probe that is *prose a human edits*, and hashing the whole file makes
    every concurrent edit to it a test failure: `make check` runs for tens of
    minutes, so appending a line to `AGENTS.md` meanwhile fails one arbitrary
    test with "wrote project-scope state into a real working tree" and passes
    on the re-run, which is a flake in a required gate.

    `rules` brackets every block it writes in ``<!-- boost:rule:<name> ... -->``
    comments and strips exactly those on uninstall, so the marker lines are a
    complete record of what an install or uninstall did to the file, and
    nothing else in it can move them.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "\n".join(ln for ln in text.splitlines() if marker in ln)


def fingerprint_paths(paths) -> dict[str, str]:
    """``{path: fingerprint}`` for the ones that exist — absent means absent.

    A missing path is left out rather than mapped to ``""``, so it can never
    compare equal to a present-but-empty directory: a test that removed the
    last entry from a real ``.claude/skills`` has to read as a change.

    A probed **file** is fingerprinted by content — rather than mtime, because
    an idempotent rewrite is not a change and a guard that fires on one gets
    switched off. The exception is an agent **context file**, which is prose a
    human also edits: those are fingerprinted by their boost markers alone, see
    :func:`managed_blocks`.

    A probed **directory** is fingerprinted by its immediate entries, each as
    ``name|kind`` plus, for a regular file, its size and ``mtime_ns``, and for
    a symlink, its target. Not by name alone: `boost install <workflow>
    --local` writes
    ``<root>/.claude/commands/<name>.md``, and the probe is the ``commands``
    directory, so a *replacement* of a slash command the developer wrote by
    hand left the listing identical and the guard silent — the destructive
    case, which is the worse one. Size and mtime rather than content because
    this runs twice per test: it costs one `scandir` and no reads.

    Immediate entries rather than a walk, for the same reason — and because
    ``.claude/`` in a real checkout holds ``worktrees/``. The residual gap is a
    write *below* an entry that already exists (a ``--force`` reinstall over
    ``.claude/skills/<name>/``); catching that means hashing subtrees on every
    teardown, which is the cost this design exists to avoid.

    Never raises. It runs in teardown for every test, so one unreadable
    directory must not turn into three thousand errors.
    """
    import hashlib
    out: dict[str, str] = {}
    for p in paths:
        p = Path(p)
        try:
            if p.is_dir():
                out[str(p)] = "d:" + ",".join(sorted(_dir_entries(p)))
            elif p.exists():
                names, marker = context_file_facts()
                if p.name in names:
                    out[str(p)] = "m:" + managed_blocks(p, marker)
                else:
                    out[str(p)] = "f:" + hashlib.sha256(
                        p.read_bytes()).hexdigest()[:16]
            elif p.is_symlink():
                # Present, but neither `is_dir` nor `exists` says so: both
                # follow the link. A broken symlink planted at a probe path
                # would otherwise read as absent, which is the state the guard
                # compares against.
                out[str(p)] = "l:" + os.readlink(p)
        except OSError as exc:
            # Unreadable is still *present*, and the reason is stable across
            # the two calls, so it cancels out of the diff rather than
            # masquerading as a change.
            out[str(p)] = "e:%s" % exc.errno
    return out


_GUARD_PROBES: list[Path] = []


def guard_roots() -> list[Path]:
    """Every working tree the guard watches, checkout-first.

    Four candidates collapse to one or two in practice. `ROOT` is where this
    file sits; `checkout_root` of it is the tree that `scopes.resolve_base`
    would pick from there. Both again for `_START_DIR`, which is `ROOT` in an
    ordinary run and ``<checkout>/mutants`` under the mutation gate — where
    `ROOT` is *also* ``mutants``, because mutmut copies `tests/` in, so
    deriving the checkout from `__file__` alone watches neither the tree the
    install lands in nor, by coincidence, anything else that matters.
    """
    return watched_roots(checkout_root(ROOT), ROOT,
                         checkout_root(_START_DIR), _START_DIR)


def _guard_probes() -> list[Path]:
    """:func:`project_scope_probes` over :func:`guard_roots`, computed once."""
    if not _GUARD_PROBES:
        _GUARD_PROBES.extend(p for root in guard_roots()
                             for p in project_scope_probes(root))
    return _GUARD_PROBES


def repo_root_intruders(before: dict, after: dict) -> list[str]:
    """Paths whose fingerprint differs between two snapshots, sorted.

    Symmetric: a test that *deletes* the developer's ``.claude/settings.json``
    is the same class of bug and strictly worse than one that adds a file.
    """
    return sorted({k for k in set(before) | set(after)
                   if before.get(k) != after.get(k)})


def absolutize_source_paths(config) -> list:
    """Rewrite ``config.source_paths`` in place to absolute paths.

    Takes the config object rather than fetching it so the behaviour can be
    tested without mutmut installed. Returns the new list.
    """
    config.source_paths = [Path(p).resolve() for p in config.source_paths]
    return config.source_paths


def pytest_configure(config):
    """Make mutmut's ``source_paths`` absolute before any test can chdir.

    mutmut's ``record_trampoline_hit`` runs on every call into mutated code
    during stats collection, and opens with::

        source_paths = [p.resolve(strict=True) for p in Config.get().source_paths]

    Those paths come from ``setup.cfg`` and are *relative*, so ``resolve()``
    consults the current working directory — and this suite's functional tests
    chdir into throwaway project dirs, where ``boost_cli/`` does not exist. The
    result is ``FileNotFoundError: <tmpdir>/boost_cli`` raised from inside the
    trampoline. It surfaces as a failed test and takes the whole stats phase
    with it ("failed to collect stats"), so no mutation run that selects
    ``tests/functional/`` can start at all.

    That is what pins the mutation gate to ``tests/unit/``, and unit tests
    alone leave ``boost_cli/commands/`` at ~18% line coverage (91.5% with
    functional included). Since "no tests" mutants count against the score, the
    gate cannot be extended past ``core/`` while this stands.

    Resolving once here, while the cwd is still the tree root, is enough:
    ``resolve()`` on an already-absolute path never consults the cwd. No mutmut
    behaviour changes — the list is only ever compared against stack-frame
    filenames, which are absolute already.

    Upstream the offending line is dead code in the default configuration: its
    only consumer sits behind ``if max_stack_depth != -1``, and -1 is the
    default, so it computes a value nothing reads and raises while doing it.

    mutmut 3.8.0 both moved the accessor and fixed the line, which is why the
    config is fetched through :func:`_mutmut_config` rather than named here —
    see its docstring.
    """
    del config
    if not os.environ.get("MUTANT_UNDER_TEST"):
        return          # not a mutmut run — nothing to normalize
    cfg = _mutmut_config()
    if cfg is None:
        return
    absolutize_source_paths(cfg)


def _mutmut_config():
    """mutmut's live config object, or ``None`` — across the 3.8 rename.

    mutmut 3.7.0 exposes it as the staticmethod ``Config.get()``; 3.8.0 moved
    it to a module-level ``config()`` and left the ``Config`` dataclass in
    place without a ``get``. The old call therefore did not fail to *import* —
    the class is still there — it failed at the call, outside the ``try`` that
    was written for exactly this ("mutmut absent, or its internals moved").
    An ``AttributeError`` out of ``pytest_configure`` is an ``INTERNALERROR``
    rather than a test failure, so it takes the whole session: on the branch
    that bumped 3.7.0 → 3.8.0, ``mutation-shard (0)`` reported "failed to
    collect stats" and exited 1 in 88 seconds, before a single mutant ran.

    Both names are tried, newest first, and neither being present returns
    ``None`` instead of raising. The cost of a no-op is one upstream bug
    coming back as a visible ``FileNotFoundError``; the cost of raising is a
    green suite reporting nothing at all.

    **On 3.8.0 the normalization has nothing to fix, and is kept anyway.**
    ``record_trampoline_hit`` now reads ``resolved_mutated_source_paths``,
    which ``_load_config`` builds from ``Path.cwd()`` once, so the hot path no
    longer resolves a relative path per call. Making ``source_paths``
    absolute is then idempotent and free, and it is still the field
    ``__main__`` iterates — a version test here would encode which upstream
    lines are buggy today, which is a worse thing to be wrong about.
    """
    try:
        from mutmut import configuration
    except Exception:   # mutmut absent
        return None
    getter = getattr(configuration, "config", None)             # 3.8.0+
    if getter is None:
        getter = getattr(getattr(configuration, "Config", None), "get", None)
    if getter is None:  # renamed again — a no-op beats an INTERNALERROR
        return None
    return getter()


@pytest.fixture(autouse=True)
def _repo_root_guard(request):
    """Fail the test that writes project-scope state into a real working tree.

    The `sandbox` fixture chdirs, so nothing *should* reach here. This is the
    backstop for what does anyway: a test that forgets `sandbox`, a `base=`
    built from the wrong root, or — the case this was written for — a mutant
    that weakens a scope guard while the mutation stage runs the suite against
    `boost_cli/core`.

    What it adds is attribution, not detection. The damage was always visible;
    it just never named its cause. A killed run left a project-scope
    `brainstorming` at the repo root, and the next full suite failed twelve
    tests across four files that assert an empty install state — none of them
    the test that wrote it, and `git status` shows nothing because `.boost/`
    is gitignored.

    Autouse and unconditional, including under mutmut. Parallel mutant
    processes share `mutants/`, so in principle one process's escape can be
    attributed to another's test and kill a mutant that should have survived.
    That is accepted deliberately: the alternative is a silently poisoned
    checkout, one mutant out of ~26,500 is noise against an 80% floor, and it
    can only happen when something genuinely escaped. The same caveat applies
    to `pytest-xdist`, for the same reason and with the same answer.

    The probe list is cached per process: it is a pure function of the roots,
    computing it reads the developer's `config.json`, and this fixture runs
    thousands of times.
    """
    probes = _guard_probes()
    before = fingerprint_paths(probes)
    yield
    hits = repo_root_intruders(before, fingerprint_paths(probes))
    if hits:
        pytest.fail(
            "%s wrote project-scope state into a real working tree.\n"
            "Changed:\n  %s\n"
            "A project install resolves against os.getcwd(); pass an explicit"
            " `base=` or use the `sandbox` fixture, which chdirs into tmp_path."
            % (request.node.nodeid, "\n  ".join(hits)), pytrace=False)


@pytest.fixture(autouse=True)
def _reset_logging():
    """Rebind the diagnostic logger to each test's sandbox HOME."""
    from boost_cli.core import logs
    logs.reset()
    yield
    logs.reset()


@pytest.fixture(autouse=True)
def _reset_ai_last_failure():
    """Clear `ai._last_failure` so one test's AI failure can't leak into the
    next. Most tests never touch it (`sandbox` sets BOOST_NO_AI=1, which
    `unavailable_reason()` checks before ever reading it), but any test using
    `ai_on` that exercises a failing `ai.ask()` sets this module global with
    nothing to unset it afterward.
    """
    from boost_cli.core import ai
    ai._last_failure = None
    yield
    ai._last_failure = None


@pytest.fixture(autouse=True)
def _reset_localembed_failure():
    """Clear the local model's in-process failure record between tests.

    Same leak as `ai._last_failure` above: the marker file lives under each
    test's sandbox HOME and goes with it, but the in-process copy is a module
    global, and `dense.status()` reads it first — one test's failed fetch would
    turn the next test's healthy local store into `model-unavailable`.
    """
    from boost_cli.core import localembed
    localembed._failure = None
    localembed._fetch_error = ""
    yield
    localembed._failure = None
    localembed._fetch_error = ""


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A fresh fake $HOME; returns its Path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # The working directory is sandboxed too, and it is the one input project
    # scope resolves against: `scopes.resolve_base` walks up from `os.getcwd()`
    # for a `.git` marker, so a test installing with `scope="project"` and no
    # explicit `base` — or driving `boost install --local` without its own
    # chdir — wrote a full agent fan-out into the developer's own checkout.
    #
    # A sibling of `home`, never `home` itself: `scopes.project_root` refuses
    # to call `$HOME` a project, so a cwd equal to the fake HOME would make
    # `resolve_base` return None and change what every project-scope test
    # means. tmp_path carries no `.git`, so the walk up finds nothing and the
    # fallback is this directory — a test that needs a real project root
    # plants its own marker and chdirs into it.
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    # ...and the "carries no `.git`" half is an assumption about where pytest
    # puts tmp_path, not something this fixture controls. `--basetemp` or a
    # `TMPDIR` inside a checkout inverts the whole fix — every project-scope
    # test would resolve to that checkout and the guard would fail all of them
    # with the wrong story. Cheaper to say so here than to debug there.
    # Every marker `scopes.PROJECT_MARKERS` accepts, not just `.git`: a
    # `TMPDIR` inside a Mercurial or Subversion working copy resolves exactly
    # the same way, and checking one of the three would let the inversion this
    # assertion exists to announce pass silently.
    assert not any((d / m).exists()
                   for d in (cwd, *cwd.parents) for m in _VCS_MARKERS), (
        "pytest's tmp_path is inside a working tree (%s) — set TMPDIR or"
        " --basetemp somewhere else, or every project-scope test writes into"
        " it" % cwd)
    monkeypatch.delenv("BOOST_HOME", raising=False)
    monkeypatch.delenv("BOOST_AGENTS_STORE", raising=False)
    monkeypatch.delenv("BOOST_DEBUG", raising=False)
    monkeypatch.delenv("BOOST_LOG_LEVEL", raising=False)
    monkeypatch.delenv("BOOST_NO_LOG", raising=False)
    # The codex agent dir is `${CODEX_HOME:-~/.codex}/skills`, so a developer
    # (or runner) with CODEX_HOME exported would move it out of the sandbox and
    # fail agent/store assertions for reasons nothing in the test says. It is
    # also codex's *MCP* config home, so it is the CLAUDE_CONFIG_DIR case below
    # as well, in one variable. Tests that mean to exercise either relocation
    # set it themselves.
    monkeypatch.delenv("CODEX_HOME", raising=False)
    # Same shape, and it is the bug `boost mcp`'s sandbox guard exists for: an
    # agent CLI resolves its config home from the ambient environment, so a
    # developer with CLAUDE_CONFIG_DIR exported would have every mcp test
    # judged against their real config dir — refused locally, fine in CI.
    # Tests that mean to exercise the escape set it themselves.
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("BOOST_NO_AI", "1")       # deterministic: no AI calls
    # `boost mcp` seeds the default registries on an empty machine. That is
    # seven network clones, which no test may perform as a side effect of
    # checking what registration prints — same contract as BOOST_NO_AI above:
    # a test that means to exercise the seed unsets this explicitly.
    monkeypatch.setenv("BOOST_NO_SEED", "1")
    # `boost mcp register` offers to install boost's own rule into the
    # agent context files. out.confirm returns True under BOOST_ASSUME_YES,
    # which this fixture also sets, so without this guard every register
    # test would silently write a standing block into its sandbox HOME.
    monkeypatch.setenv("BOOST_NO_RULE", "1")
    # `self-update` asks PyPI which version is newest before it will claim to
    # be up to date. Same contract again: no test reaches the network as a side
    # effect of checking what a command prints.
    monkeypatch.setenv("BOOST_NO_NET", "1")
    # `boost quickstart` reads the shard manifest for its pins whether or not
    # the `[rag]` extra is here, so without this every quickstart test would
    # fetch the real one from GitHub. A file that does not exist fails fast
    # and offline; a test that means to read a manifest serves its own.
    monkeypatch.setenv("BOOST_SHARD_MANIFEST",
                       (tmp_path / "no-manifest.json").as_uri())
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)   # no real embed calls
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")         # plain output for assertions
    monkeypatch.setenv("BOOST_ASSUME_YES", "1")  # never block on confirm()
    # Once-per-process warnings for a cache boost could not save. A flag one
    # test left set would silence the warning in the next, so an assertion
    # that it is absent would pass for the wrong reason.
    from boost_cli.core import catalog, complete
    monkeypatch.setattr(complete, "_WARNED_UNSAVED", False)
    monkeypatch.setattr(catalog, "_UNSAVED", set())
    return home


@pytest.fixture()
def vector_store(sandbox, monkeypatch):
    """Write a dense store into the sandbox, as `dense.status` reads it.

    Plain sqlite, `meta` plus one `chunks` row and no vec0: `status` reads
    `meta` without the extra, so to every question short of a query this is
    the real store — no stubbed status dict whose keys could drift from the
    ones the code under test reads. `have_backend` is stubbed present so the
    ladder reaches the store at all; without it a runner with no `[rag]`
    extra stops at `no-backend` and one with it does not, and the test means
    different things on each. Returns a writer taking the space to stamp,
    voyage-4 by default: the store a user with VOYAGE_API_KEY has paid for.
    ``provider=None`` stamps a store with no recorded space.
    """
    import json
    import sqlite3

    from boost_cli.core import dense
    monkeypatch.setattr(dense, "have_backend", lambda: True)

    def write(provider="voyage", model="voyage-4", dim=1024,
              version=dense.INDEX_VERSION):
        meta = {"version": version, "provider": provider, "model": model,
                "dim": dim, "chunks": 1}
        dense.db_path().parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(dense.db_path()))
        try:
            con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
            con.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY,"
                        " name TEXT)")
            con.execute("INSERT INTO chunks (name) VALUES ('x')")
            con.executemany("INSERT INTO meta (k, v) VALUES (?, ?)",
                            [(k, json.dumps(v)) for k, v in meta.items()
                             if v is not None])
            con.commit()
        finally:
            con.close()
        return dense.status()

    return write


class CliResult:
    def __init__(self, rc: int, out: str, err: str):
        self.rc, self.out, self.err = rc, out, err

    def __repr__(self):
        return "CliResult(rc=%r, out=%r, err=%r)" % (self.rc, self.out, self.err)


@pytest.fixture()
def boost(sandbox, capsys):
    """In-process CLI runner: boost('install', 'x') -> CliResult.

    Asserts the exit code (default 0); pass expect=None to skip the assert,
    or expect=<n> for error-path tests.
    """
    from boost_cli.cli import main

    def run(*argv, expect=0):
        argv = [str(a) for a in argv]
        try:
            rc = main(argv)
        except SystemExit as e:  # argparse --help / usage errors
            rc = e.code if isinstance(e.code, int) else 0
        cap = capsys.readouterr()
        res = CliResult(int(rc or 0), cap.out, cap.err)
        if expect is not None:
            assert res.rc == expect, (
                "boost %s -> rc=%d (want %d)\n--- stdout ---\n%s--- stderr ---\n%s"
                % (" ".join(argv), res.rc, expect, cap.out, cap.err))
        return res

    return run


@pytest.fixture(scope="session")
def fixture_tap_src(tmp_path_factory):
    """The sample-skill git repo, built once per session (read-only)."""
    dest = tmp_path_factory.mktemp("fixture") / "fixture-tap"
    subprocess.run(
        [sys.executable, str(ROOT / "tests" / "make_fixture.py"), str(dest)],
        check=True, capture_output=True)
    return dest


class _MinisignSigner:
    """A deterministic minisign signer for tests, built on boost's own Ed25519.

    boost ships verify-only (:mod:`boost_cli.core.ed25519`); tests need to *make*
    signatures, so this reconstructs the signing half from the same primitives.
    Its correctness is not assumed — the RFC 8032 vectors in ``test_ed25519``
    prove verify, and a signer whose output that proven verifier accepts is by
    definition producing valid signatures. Seeded, so every run is identical.
    """

    def __init__(self, seed: bytes = b"\x07" * 32,
                 key_id: bytes = bytes.fromhex("1122334455667788")):
        from boost_cli.core import ed25519 as e
        self._e = e
        self.seed = seed
        self.key_id = key_id
        a, self._prefix = self._expand(seed)
        self._a = a
        self.public = self._compress(e._point_mul(a, e._B))

    def _expand(self, seed):
        h = self._e._sha512(seed)
        a = int.from_bytes(h[:32], "little")
        a &= (1 << 254) - 8
        a |= (1 << 254)
        return a, h[32:]

    def _compress(self, point):
        e = self._e
        x, y, z, _ = point
        zi = pow(z, e._P - 2, e._P)
        x = (x * zi) % e._P
        y = (y * zi) % e._P
        return (y | ((x & 1) << 255)).to_bytes(32, "little")

    def sign_raw(self, message: bytes) -> bytes:
        """A 64-byte Ed25519 signature of ``message`` under the fixture key."""
        e = self._e
        cap_a = self._compress(e._point_mul(self._a, e._B))
        r = e._sha512_modl(self._prefix + message)
        cap_r = self._compress(e._point_mul(r, e._B))
        h = e._sha512_modl(cap_r + cap_a + message)
        s = (r + h * self._a) % e._L
        return cap_r + s.to_bytes(32, "little")

    def public_key_text(self, comment: str = "test key") -> str:
        import base64
        line = base64.b64encode(b"Ed" + self.key_id + self.public).decode()
        return "untrusted comment: %s\n%s\n" % (comment, line)

    def signature_text(self, content: bytes, prehash: bool = False,
                       trusted_comment: str = "timestamp:1\tfile:tap.manifest") -> str:
        import base64
        import hashlib
        algorithm = b"ED" if prehash else b"Ed"
        signed = (hashlib.blake2b(content, digest_size=64).digest()
                  if prehash else content)
        blob = algorithm + self.key_id + self.sign_raw(signed)
        global_sig = self.sign_raw(self.sign_raw(signed) + trusted_comment.encode())
        return ("untrusted comment: signature\n%s\ntrusted comment: %s\n%s\n"
                % (base64.b64encode(blob).decode(), trusted_comment,
                   base64.b64encode(global_sig).decode()))

    def write_signed(self, clone, manifest: bytes = b"boost-tap v1\n",
                     prehash: bool = False) -> None:
        """Write ``.boost/tap.manifest`` + ``.minisig`` under ``clone``."""
        from boost_cli.core import provenance
        (clone / ".boost").mkdir(parents=True, exist_ok=True)
        (clone / provenance.SIGNED_FILE).write_bytes(manifest)
        (clone / provenance.SIGNATURE_FILE).write_text(
            self.signature_text(manifest, prehash=prehash), encoding="utf-8")


@pytest.fixture()
def signer():
    """A deterministic minisign signer (see :class:`_MinisignSigner`)."""
    return _MinisignSigner()


@pytest.fixture()
def tapped(boost, fixture_tap_src):
    """Sandbox with the fixture tap added. Returns the tap's source path."""
    boost("tap", fixture_tap_src)
    return fixture_tap_src


@pytest.fixture()
def installed(boost, tapped):
    """Sandbox with brainstorming installed. Returns the skill name."""
    boost("install", "brainstorming")
    return "brainstorming"


@pytest.fixture()
def rival_tap(boost, tapped, tmp_path):
    """A second real tap that also ships `brainstorming`, at a louder version.

    Two taps carrying one name is the only way to reach the ambiguity error —
    and its hint — so the qualified-name path needs a genuine second clone
    rather than a hand-written cache. Shared across command test files (info,
    adapt, run, discovery, pkg) that each exercise the `tap:name` qualifier.
    """
    root = tmp_path / "rival-tap"
    (root / "skills" / "brainstorming").mkdir(parents=True)
    (root / "skills" / "brainstorming" / "SKILL.md").write_text(
        "---\nname: brainstorming\ndescription: A rival ideation skill\n"
        "version: 9.9.9\n---\n\n# Brainstorming\n\nThe other tap's copy.\n",
        encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "rival@boost.test")
    run("git", "config", "user.name", "Rival Tap")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "rival skills")
    boost("tap", root)
    return "rival-tap"


@pytest.fixture()
def sibling_rules_tap(boost, tmp_path):
    """A real tap whose rules share a directory and whose workflow name repeats.

    Two commits: the first adds ``rules/ci-cd/dotnet-build.mdc`` and three
    differently-worded ``csharp-reviewer`` workflows. The second adds only
    the sibling ``rules/ci-cd/dotnet-test.mdc``. The second commit is not
    part of ``dotnet-build``'s history, so a log over the shared directory
    shows the mistake. The three reviewers make the catalog refuse the bare
    name, so only the lock can tell which one was installed.
    Returns the source repo path.
    """
    root = tmp_path / "sibling-tap"
    files = {
        "rules/ci-cd/dotnet-build.mdc":
            "---\nname: dotnet-build\ndescription: Build dotnet projects\n---\n"
            "Use dotnet build.\n",
        "agents/csharp-reviewer.md":
            "---\nname: csharp-reviewer\ndescription: Reviews C# (top)\n---\n"
            "Review it.\n",
        "plugins/a/agents/csharp-reviewer.md":
            "---\nname: csharp-reviewer\ndescription: Reviews C# (plugin a)\n"
            "---\nReview it, A.\n",
        "plugins/b/agents/csharp-reviewer.md":
            "---\nname: csharp-reviewer\ndescription: Reviews C# (plugin b)\n"
            "---\nReview it, B.\n",
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    run = lambda *a: subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "sib@boost.test")
    run("git", "config", "user.name", "Sibling Tap")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "add dotnet-build and reviewers")
    (root / "rules" / "ci-cd" / "dotnet-test.mdc").write_text(
        "---\nname: dotnet-test\ndescription: Test dotnet projects\n---\n"
        "Use dotnet test.\n", encoding="utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "add sibling rule dotnet-test")
    boost("tap", root)
    return root
