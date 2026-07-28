"""Unit tests: the hash-pinned dev/CI toolchain (requirements/*.txt).

These assert the lock's *invariants* rather than its contents — a version bump
must not need a test edit, but the properties that make the lock worth having
(every requirement pinned, every pin hashed, every consumer's file present) must
never silently erode.

The freshness check itself (`scripts/lock_toolchain.py --check`) is not run here:
it needs `uv` and the network. `make lint` and CI's lint job own that.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REQS = ROOT / "requirements"
SCRIPT = ROOT / "scripts" / "lock_toolchain.py"


def load_lock_toolchain():
    """Import scripts/lock_toolchain.py by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("lock_toolchain_under_test",
                                                  SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

# Every group scripts/lock_toolchain.py generates, and the consumer that reads
# it. Keep in step with that script's GROUPS tuple.
GROUPS = ("lint-tools", "test-tools", "mutation-tools", "coverage-tools",
          "release-tools")

# The extras group is not optional decoration: without it, `coverage[toml]==7.15.2`
# matches `name=coverage`, then `spec` fails because the next character is `[`,
# and the pin invariant below reports a perfectly pinned line as unpinned.
# uv and pip-tools emit `name[extra]==version` routinely.
_REQ = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
                  r"(?P<extras>\[[^\]]+\])?"
                  r"(?P<spec>==[^\s;\\]+)?(?P<rest>.*)$")


def _clean(raw):
    """A compiled line with its line-continuation backslash removed."""
    return raw.strip().rstrip("\\").strip()


def _requirement_lines(text):
    """The requirement lines of a compiled file (no comments, no hash lines)."""
    lines = []
    for raw in text.splitlines():
        line = _clean(raw)
        if not line or line.startswith("#") or line.startswith("-"):
            continue                           # comment, --hash, -r, --index-url
        lines.append(line)
    return lines


def _blocks(text):
    """(requirement line, [hashes]) for each requirement in a compiled file."""
    out = []
    current = None
    for raw in text.splitlines():
        line = _clean(raw)
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash="):
            if current is not None:
                current[1].append(line)
            continue
        if line.startswith("-"):
            continue
        current = (line, [])
        out.append(current)
    return out


class TestEveryGroupIsLocked:
    def test_declaration_exists_for_every_group(self):
        for stem in GROUPS:
            assert (REQS / ("%s.in" % stem)).is_file(), stem

    def test_generated_lock_exists_for_every_group(self):
        for stem in GROUPS:
            assert (REQS / ("%s.txt" % stem)).is_file(), stem

    def test_no_stray_generated_file_without_a_declaration(self):
        # a .txt with no .in would be hand-maintained — exactly what the
        # generator exists to replace.
        for txt in REQS.glob("*.txt"):
            assert (REQS / (txt.stem + ".in")).is_file(), txt.name

    def test_lock_toolchain_groups_match_this_test(self):
        # the script is the source of truth; this pins them together so adding a
        # group there without locking it here is a failure, not a silent gap.
        src = (ROOT / "scripts" / "lock_toolchain.py").read_text(encoding="utf-8")
        for stem in GROUPS:
            assert '"%s"' % stem in src, stem


class TestLockInvariants:
    def test_every_requirement_is_pinned_exactly(self):
        for stem in GROUPS:
            text = (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8")
            for line in _requirement_lines(text):
                m = _REQ.match(line.strip())
                assert m, "unparseable requirement in %s: %r" % (stem, line)
                assert m.group("spec"), \
                    "%s is not pinned with == in %s: %r" % (
                        m.group("name"), stem, line)

    def test_every_pin_carries_hashes(self):
        # This is the whole point: pip implies --require-hashes when any hash is
        # present, so a single unhashed requirement would break the install
        # rather than weaken it — but a file with NO hashes installs happily and
        # silently gives up the guarantee.
        for stem in GROUPS:
            text = (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8")
            blocks = _blocks(text)
            assert blocks, "%s has no requirements at all" % stem
            for line, hashes in blocks:
                assert hashes, "%s: %r carries no --hash" % (stem, line)
                for h in hashes:
                    assert re.fullmatch(r"--hash=sha256:[0-9a-f]{64}", h), \
                        "%s: malformed hash %r" % (stem, h)

    def test_generated_files_are_marked_generated(self):
        for stem in GROUPS:
            head = (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8")[:200]
            assert "GENERATED by scripts/lock_toolchain.py" in head, stem
            assert "DO NOT EDIT" in head, stem

    def test_header_is_machine_independent(self):
        # uv stamps its own invocation (absolute paths, the -o target) into a
        # header; lock_toolchain.py strips it. If it leaked back in, the drift
        # check would fail on CI for everything generated on a laptop.
        for stem in GROUPS:
            text = (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8")
            assert "autogenerated by uv" not in text, stem
            assert str(ROOT) not in text, stem


class TestRequirementPattern:
    """The pattern itself, against literal lines.

    Everything else in this file runs `_REQ` over whatever `requirements/*.txt`
    happens to contain today, so a form the lock does not currently use is a
    form the pattern is never tested against. That is exactly how the extras
    case got here: nothing in the lock carries an extra, so `coverage[toml]==…`
    reading as *unpinned* stayed invisible until a Dependabot PR regenerated
    the lock and the gate rejected a valid pin with a message naming the wrong
    problem.
    """

    @staticmethod
    def _parsed(line):
        m = _REQ.match(line)
        assert m, "unparseable: %r" % line
        return m

    def test_a_plain_pin(self):
        m = self._parsed("hypothesis==6.140.3")
        assert m.group("name") == "hypothesis"
        assert m.group("extras") is None
        assert m.group("spec") == "==6.140.3"

    def test_a_pin_carrying_an_extra(self):
        # THE BUG: this used to come back with spec=None.
        m = self._parsed("coverage[toml]==7.15.2")
        assert m.group("name") == "coverage"
        assert m.group("extras") == "[toml]"
        assert m.group("spec") == "==7.15.2"

    def test_a_pin_carrying_several_extras(self):
        m = self._parsed("ruff[all,dev]==0.16.0")
        assert m.group("extras") == "[all,dev]"
        assert m.group("spec") == "==0.16.0"

    def test_a_pin_with_an_environment_marker(self):
        m = self._parsed("coverage[toml]==7.10.7 ; python_full_version < '3.10'")
        assert m.group("name") == "coverage"
        assert m.group("spec") == "==7.10.7", "the marker must not eat the pin"

    def test_names_with_dots_dashes_and_digits(self):
        for line, name in (("zope.interface==7.0", "zope.interface"),
                           ("ruff-lsp==0.1", "ruff-lsp"),
                           ("s3transfer==0.10", "s3transfer")):
            assert self._parsed(line).group("name") == name

    def test_an_unpinned_requirement_still_reports_unpinned(self):
        # The fix must not make everything look pinned.
        for line in ("hypothesis", "hypothesis>=6", "coverage[toml]>=7.15",
                     "coverage[toml]~=7.15"):
            assert self._parsed(line).group("spec") is None, line


class TestEvalExtraStaysOut:
    def test_langchain_stack_is_not_locked(self):
        # The [eval] extra deliberately pins the old langchain 0.3 stack (ragas
        # 0.2.x needs it). osv-scanner.yml is PR-diff-scoped specifically to
        # avoid tripping on that pin, so materializing it into a committed,
        # scannable lock would re-expose it. See lock_toolchain.py's docstring.
        for stem in GROUPS:
            text = (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8").lower()
            for forbidden in ("langchain", "ragas", "ranx"):
                assert forbidden not in text, \
                    "%s locks the opt-in [eval] stack (%s)" % (stem, forbidden)


class TestCompileIsStable:
    """The compile must reproduce the committed lock, not chase the newest release.

    uv treats an existing `--output-file` as the preferred solution and keeps
    those pins unless a declaration forces a change. Compiling to stdout instead
    re-resolves against the live index, so any upstream release makes the
    committed lock "stale" and reddens `lint` on unrelated PRs with no code
    change — the exact failure mode requirements/lint-tools.in's header warns
    about, and one this gate hit within a day of landing.

    This asserts the mechanism rather than running uv (which needs the network):
    a resolver invoked without an output file to read cannot be stable.
    """

    def test_compile_passes_output_file_so_uv_reads_current_pins(self):
        src = (ROOT / "scripts" / "lock_toolchain.py").read_text(encoding="utf-8")
        assert "--output-file" in src, \
            "compile_group must give uv the committed lock to prefer"

    def test_compile_seeds_the_scratch_file_from_the_committed_lock(self):
        # Copying the committed .txt into the scratch path is what makes uv
        # prefer the existing pins; without the copy the flag achieves nothing.
        src = (ROOT / "scripts" / "lock_toolchain.py").read_text(encoding="utf-8")
        assert "shutil.copyfile(target, scratch)" in src

    def test_re_resolving_is_always_explicit(self):
        src = SCRIPT.read_text(encoding="utf-8")
        assert '"--upgrade"' in src
        # --check must never imply a re-resolve, or the gate stops being
        # deterministic: it would call the lock stale on any upstream release.
        assert "--check cannot be combined with --upgrade/-P" in src


class TestUpgradePackage:
    """`-P/--upgrade-package`: bump one package, keep every other pin.

    This is how a Dependabot bump gets answered. Dependabot regenerates these
    files on Linux and commits that resolution, which drops the pins whose
    environment markers exclude them there — `colorama ; sys_platform ==
    'win32'` disappeared from three locks in one run, and since the files
    install with --require-hashes on Windows too, the Windows jobs then died in
    their install step without ever naming colorama. Re-resolving one package
    through this script keeps the resolution universal.
    """

    @staticmethod
    def _captured_cmd(monkeypatch, mod, **kwargs):
        """Run compile_group with uv stubbed out; return the argv it built."""
        seen = []

        class FakeProc:
            returncode = 0
            stderr = ""

        def fake_run(cmd, **_):
            seen.append(list(cmd))
            return FakeProc()

        monkeypatch.setattr(mod.subprocess, "run", fake_run)
        mod.compile_group("test-tools", "3.9", **kwargs)
        assert len(seen) == 1
        return seen[0]

    def test_named_package_is_passed_through_to_uv(self, monkeypatch):
        mod = load_lock_toolchain()
        cmd = self._captured_cmd(monkeypatch, mod, upgrade=False,
                                 packages=["hypothesis", "twine"])
        pairs = [(cmd[i], cmd[i + 1]) for i in range(len(cmd) - 1)]
        assert ("--upgrade-package", "hypothesis") in pairs
        assert ("--upgrade-package", "twine") in pairs

    def test_naming_a_package_does_not_upgrade_everything_else(self, monkeypatch):
        # The whole point of -P over --upgrade: a bare --upgrade here would
        # re-resolve all five groups and bury the bump in unrelated churn.
        mod = load_lock_toolchain()
        cmd = self._captured_cmd(monkeypatch, mod, upgrade=False,
                                 packages=["hypothesis"])
        assert "--upgrade" not in cmd

    def test_a_plain_regenerate_names_no_package(self, monkeypatch):
        mod = load_lock_toolchain()
        cmd = self._captured_cmd(monkeypatch, mod, upgrade=False)
        assert "--upgrade" not in cmd
        assert "--upgrade-package" not in cmd

    def test_resolution_stays_universal(self, monkeypatch):
        # --universal is what emits the environment markers instead of resolving
        # for the running machine, so it must survive a targeted upgrade too.
        mod = load_lock_toolchain()
        cmd = self._captured_cmd(monkeypatch, mod, upgrade=False,
                                 packages=["hypothesis"])
        assert "--universal" in cmd
        assert "--generate-hashes" in cmd


class TestMutuallyExclusiveFlags:
    """The flag combinations that would quietly make the gate meaningless."""

    @staticmethod
    def _main_with(monkeypatch, argv):
        mod = load_lock_toolchain()
        monkeypatch.setattr(mod.sys, "argv", ["lock_toolchain.py", *argv])
        # Any of these must be rejected during argument handling, i.e. before
        # uv is ever invoked — so no stub is needed and no network is touched.
        try:
            mod.main()
        except SystemExit as exc:
            return str(exc.code)
        return ""

    def test_check_rejects_upgrade(self, monkeypatch):
        assert "cannot be combined" in self._main_with(
            monkeypatch, ["--check", "--upgrade"])

    def test_check_rejects_upgrade_package(self, monkeypatch):
        # A --check that re-resolves would report the committed lock stale on
        # every upstream release, reddening lint on unrelated PRs.
        assert "cannot be combined" in self._main_with(
            monkeypatch, ["--check", "-P", "hypothesis"])

    def test_upgrade_rejects_upgrade_package(self, monkeypatch):
        assert "exclusive" in self._main_with(
            monkeypatch, ["--upgrade", "-P", "hypothesis"])
