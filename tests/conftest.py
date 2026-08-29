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
def _reset_logging():
    """Rebind the diagnostic logger to each test's sandbox HOME."""
    from boost_cli.core import logs
    logs.reset()
    yield
    logs.reset()


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A fresh fake $HOME; returns its Path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("BOOST_HOME", raising=False)
    monkeypatch.delenv("BOOST_AGENTS_STORE", raising=False)
    monkeypatch.delenv("BOOST_DEBUG", raising=False)
    monkeypatch.delenv("BOOST_LOG_LEVEL", raising=False)
    monkeypatch.delenv("BOOST_NO_LOG", raising=False)
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
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)   # no real embed calls
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")         # plain output for assertions
    monkeypatch.setenv("BOOST_ASSUME_YES", "1")  # never block on confirm()
    return home


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
