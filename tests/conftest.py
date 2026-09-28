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

# A name joined into probe paths that are never read, only stat-ed. It has to
# satisfy `util.is_safe_component` and the skill-name rule, so it cannot be a
# marker like "<probe>".
_PROBE_NAME = "boost-repo-guard-probe"


def watched_roots(root, start) -> list[Path]:
    """The working trees a stray project-scope write could land in.

    Two of them, because the two writers disagree about what "the project" is.
    `scopes.resolve_base` walks *up* for a `.git` marker, so under the mutation
    gate — which runs the suite from `mutants/` inside the checkout — a project
    install lands at the repo root. A cwd-relative writer such as
    `claude_settings.settings_path("project")` lands in `mutants/` itself.
    Measured: a `mutants/.codex/hooks.json` left behind by one mutant execution
    was read back by the next clean-test run and failed it, and the traceback
    pointed at the assertion rather than at the file.

    Deduplicated, and ordered checkout-first so the more surprising of the two
    is reported second.
    """
    root, start = Path(root), Path(start)
    return [root] if start == root else [root, start]


def project_scope_probes(root) -> list[Path]:
    """Paths under ``root`` that a project-scope write materializes.

    Every entry is produced by *calling the writer's own path function* with
    ``base=root`` rather than by spelling the layout out here. A hardcoded list
    would be wrong the first time an agent, a hook host or a workflow slot is
    added — and wrong silently, since what it guards is an absence.

    The agent set comes from :data:`config.DEFAULTS` rather than from the
    developer's ``config.json``: the guard has to mean the same thing on every
    machine, and an agent someone disabled locally is still one the suite can
    write to.
    """
    from boost_cli.core import (
        agents,
        claude_settings,
        config,
        hookhost,
        projectlock,
        rules,
        scopes,
        workflows,
    )
    root = Path(root)
    probes: list[Path] = [projectlock.lock_path(root)]

    for name, spec in config.DEFAULTS["agents"].items():
        if not spec.get("project_scope", True):
            continue          # antigravity: no repo-local path to watch
        skills_dir = Path(str(spec["dir"]))
        dotdir = agents.project_dotdir(name, skills_dir)
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

    seen, unique = set(), []
    for p in probes:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def fingerprint_paths(paths) -> dict[str, str]:
    """``{path: fingerprint}`` for the ones that exist — absent means absent.

    A missing path is left out rather than mapped to ``""``, so it can never
    compare equal to a present-but-empty directory: a test that removed the
    last entry from a real ``.claude/skills`` has to read as a change.

    Files are fingerprinted by content and directories by their *immediate*
    entries. Content rather than mtime because an idempotent rewrite is not a
    change, and a guard that fires on one gets switched off. Immediate entries
    rather than a walk because ``.claude/`` in a real checkout holds
    ``worktrees/``, and this runs twice for every test in the suite.

    Never raises. It runs in teardown for every test, so one unreadable
    directory must not turn into three thousand errors.
    """
    import hashlib
    out: dict[str, str] = {}
    for p in paths:
        p = Path(p)
        try:
            if p.is_dir():
                out[str(p)] = "d:" + ",".join(sorted(os.listdir(p)))
            elif p.exists():
                out[str(p)] = "f:" + hashlib.sha256(
                    p.read_bytes()).hexdigest()[:16]
        except OSError as exc:
            # Unreadable is still *present*, and the reason is stable across
            # the two calls, so it cancels out of the diff rather than
            # masquerading as a change.
            out[str(p)] = "e:%s" % exc.errno
    return out


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
    """
    del config
    if not os.environ.get("MUTANT_UNDER_TEST"):
        return          # not a mutmut run — nothing to normalize
    try:
        from mutmut.configuration import Config
    except Exception:   # mutmut absent, or its internals moved
        return
    absolutize_source_paths(Config.get())


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
    can only happen when something genuinely escaped.
    """
    probes = [p for root in watched_roots(ROOT, _START_DIR)
              for p in project_scope_probes(root)]
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
