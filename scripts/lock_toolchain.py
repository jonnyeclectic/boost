#!/usr/bin/env python3
"""Compile the dev/CI toolchain into hash-pinned requirements files.

    python3 scripts/lock_toolchain.py            # regenerate requirements/*.txt
    python3 scripts/lock_toolchain.py --check     # fail (exit 1) on drift
    python3 scripts/lock_toolchain.py --audit     # fail on a LOST platform pin
    python3 scripts/lock_toolchain.py --upgrade   # re-resolve to newest allowed
    python3 scripts/lock_toolchain.py -P twine    # re-resolve ONE package

``-P/--upgrade-package`` exists to answer a Dependabot pull request. Dependabot
regenerates these files itself, on Linux, and writes that resolution back — which
drops every pin whose environment marker excludes it there (``colorama ;
sys_platform == 'win32'`` is pytest's Windows dependency, and it vanished from
three locks in a single run). These files install with ``--require-hashes`` on
Windows and macOS too, so a dropped pin becomes an install failure on the very
platform that needed it — reported against the install step, never naming the
package.

So a bump here is not merged, it is *reproduced*: take the version Dependabot
proposes, run ``-P <name>``, and the resolution stays universal — markers intact,
every other pin untouched. ``--upgrade`` would also pick up the new version, but
it re-resolves all five groups, burying a one-package bump in unrelated churn.

Each ``requirements/<name>.in`` is the human-edited declaration; the generated
``requirements/<name>.txt`` beside it carries an exact version *and every
artifact's sha256* for the full transitive closure. pip enforces those hashes
automatically (any hash in a requirements file implies ``--require-hashes``), so
a yanked, re-uploaded or compromised transitive dependency fails the install
instead of silently changing a build.

The ``--check`` form runs in CI's lint job and in ``make lint``, exactly like
``build_registries.py --check`` / ``build_roadmap.py --check``: the generated
file is committed, and a stale one is a red gate rather than a surprise later.

``--audit`` is the guard for the failure above, and it runs *first* inside
``--check``. ``requirements/platform-pins.lock`` records every marker-gated pin
by **name and marker but not version**, so a routine bump leaves it untouched
and only a change in the *shape* of the resolution moves it. Losing a pin then
fails here, naming the package and the marker, instead of surfacing three jobs
later as an install-step error that never mentions it. Unlike ``--check`` the
audit reads only committed files — no uv, no network — so it also runs in the
unit suite (``tests/unit/test_platform_pins.py``) and on any runner.

Why hash-pinned requirements rather than ``uv.lock``:

* ``[project].dependencies`` is empty and must stay that way — boost's runtime
  is stdlib-only. A ``uv.lock`` wants the dev tools declared *in* pyproject.toml,
  which would put dev tooling in the shipped metadata.
* A universal ``uv.lock`` would also materialize the ``[eval]`` extra's
  deliberately-old langchain 0.3 stack (pinned because ragas 0.2.x needs it) into
  a committed, scannable file. ``.github/workflows/osv-scanner.yml`` is
  PR-diff-scoped specifically to avoid tripping on that pin; a lockfile would
  re-expose it. The ``[eval]`` extra is intentionally absent here.
* ``pip install -r`` needs no extra tool at install time, which matters on the
  3 OS x 3 Python test matrix. uv is needed only to *regenerate*.

Groups are per-consumer and self-contained on purpose. pip enforces hashes
across the whole resolution, so two independently-compiled files that pin the
same transitive dependency to different versions cannot be installed together —
``mutation-tools.in`` redeclares the test tools via ``-r`` instead of layering.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQS = ROOT / "requirements"

# The committed memory of which pins are conditional. Deliberately NOT a .txt:
# tests/unit/test_toolchain_lock.py requires every requirements/*.txt to have a
# matching .in declaration, and the suffix also keeps pip and OSV-Scanner from
# mistaking a hashless manifest for something installable.
PLATFORM_PINS = REQS / "platform-pins.lock"

# (stem, python-version) for each group. Every group resolves --universal.
#
# Universal is not optional for a *committed* lock. Without it uv resolves for
# the machine it runs on, so a file generated on macOS omits the Linux-only
# artifacts CI needs — the drift check then fails on the runner while passing
# locally, which is exactly what happened first time round (release-tools came
# back STALE on CI). Universal emits environment markers instead, so one file is
# correct everywhere and byte-identical no matter who regenerates it.
#
# `python_version` is the interpreter the group's CI job pins, and it matters:
# refurb needs >=3.10 and mutmut >=3.11, so neither can resolve at the 3.9
# floor. Only `test-tools` resolves from 3.9 — it is the one set that installs on
# every leg of the 3 OS x 3 Python matrix, and the markers let one file give 3.9
# the last release that supported it while 3.12/3.14 still get the current one.
GROUPS = (
    ("lint-tools", "3.12"),
    ("test-tools", "3.9"),
    ("mutation-tools", "3.11"),
    ("coverage-tools", "3.12"),
    ("release-tools", "3.12"),
)

# uv stamps the invoking command (including absolute paths and the -o target)
# into a header comment, which would differ between a developer's machine and
# the CI runner and break a byte-exact drift check. Replace it with a stable
# header naming this script instead.
_UV_HEADER = re.compile(r"\A# This file was autogenerated by uv[^\n]*\n"
                        r"(?:#[^\n]*\n)*")


def _header(stem: str, python_version: str) -> str:
    """The stable, machine-independent banner for a generated file."""
    return (
        "# GENERATED by scripts/lock_toolchain.py — DO NOT EDIT.\n"
        "#\n"
        "# Edit requirements/%s.in, then run:\n"
        "#     python3 scripts/lock_toolchain.py\n"
        "#\n"
        "# Resolved universally from Python %s — environment markers cover every\n"
        "# OS and interpreter, so this file is byte-identical wherever it is\n"
        "# regenerated. Every artifact is sha256-pinned, and pip enforces those\n"
        "# hashes on install (any hash implies --require-hashes), so a yanked or\n"
        "# tampered transitive dependency fails the install instead of silently\n"
        "# changing the build.\n"
        % (stem, python_version)
    )


def _uv() -> str:
    """Path to a usable uv, preferring the repo venv's."""
    local = ROOT / ".venv" / "bin" / "uv"
    return str(local) if local.exists() else (shutil.which("uv") or "uv")


def _manifest_header() -> str:
    """The stable banner for requirements/platform-pins.lock."""
    return (
        "# GENERATED by scripts/lock_toolchain.py — DO NOT EDIT.\n"
        "#\n"
        "# NOT a requirements file — there are no versions and no hashes here,\n"
        "# and nothing installs it. It records which pins in requirements/*.txt\n"
        "# carry an environment marker, so that LOSING one is a red gate.\n"
        "#\n"
        "# Why: a lock re-resolved on a single platform (which is what\n"
        "# Dependabot commits) silently drops every pin whose marker excludes it\n"
        "# there. The locks install with --require-hashes on Windows and macOS\n"
        "# too, so a dropped pin is an install failure on the platform that\n"
        "# needed it — reported against the install step, never naming the\n"
        "# package. `lock_toolchain.py --audit` diffs the locks against this\n"
        "# file and names it.\n"
        "#\n"
        "# Versions are deliberately absent: a routine bump must not churn this\n"
        "# file, or regenerating it becomes reflexive and it stops being a\n"
        "# tripwire. Only a change in the SHAPE of the resolution moves a line.\n"
    )


def marker_pins(text: str) -> tuple[tuple[str, str], ...]:
    """The (name, marker) of every marker-gated pin in one compiled lock.

    Sorted and de-duplicated so the result depends on the resolution, not on the
    order uv happened to emit — that keeps ``render``/``parse`` exactly
    reciprocal and stops a cosmetic reshuffle reading as drift.

    Unmarked pins are ignored on purpose: they install everywhere, so losing one
    is ordinary drift that ``--check`` already catches. This guard is only about
    the conditional pins, which are invisible to a single-platform resolve.
    """
    pins = set()
    for raw in text.splitlines():
        # Every uv pin line ends in ` \` before its indented --hash block.
        line = raw.strip().rstrip("\\").strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue                      # comment, --hash, -r, --index-url
        head, sep, marker = line.partition(";")
        if not sep or "==" not in head:
            continue                      # unmarked, or not a pin at all
        name = head.split("==")[0].strip()   # keeps any `[extra]`
        if name:
            # Collapse whitespace so cosmetic spacing is not a change.
            pins.add((name, " ".join(marker.split())))
    return tuple(sorted(pins))


def render_platform_pins(locks: "dict[str, str]") -> str:
    """The manifest text recording the marker-gated pins of `locks`.

    A group with no conditional pins still gets its section header, so the
    manifest states "none here" rather than staying silent about it.
    """
    out = [_manifest_header()]
    for stem, _python_version in GROUPS:
        if stem not in locks:
            continue
        out.append("\n[%s]\n" % stem)
        for name, marker in marker_pins(locks[stem]):
            out.append("%s ; %s\n" % (name, marker))
    return "".join(out)


def parse_platform_pins(text: str) -> "dict[str, tuple[tuple[str, str], ...]]":
    """`{group: ((name, marker), ...)}` as recorded by a manifest."""
    out: "dict[str, list[tuple[str, str]]]" = {}
    stem = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            stem = line[1:-1]
            out.setdefault(stem, [])
            continue
        if stem is None:
            continue
        name, _sep, marker = line.partition(";")
        out[stem].append((name.strip(), " ".join(marker.split())))
    return {k: tuple(v) for k, v in out.items()}


def read_locks() -> "dict[str, str]":
    """The committed text of every group's generated lock."""
    return {stem: (REQS / ("%s.txt" % stem)).read_text(encoding="utf-8")
            for stem, _python_version in GROUPS}


def audit_platform_pins(locks: "dict[str, str]",
                        manifest_text: str) -> "list[str]":
    """Problems found comparing `locks` against the recorded manifest.

    A LOST pin and a NEW pin are reported differently on purpose. They are the
    same textual drift but opposite in meaning: one is a broken install on a
    platform CI never resolves on, the other is a routine addition that only
    needs the manifest regenerating. Collapsing them into one "stale" message is
    how the original failure stayed invisible.
    """
    recorded = parse_platform_pins(manifest_text)
    problems = []
    for stem, _python_version in GROUPS:
        if stem not in locks:
            continue
        want = set(recorded.get(stem, ()))
        have = set(marker_pins(locks[stem]))
        for name, marker in sorted(want - have):
            problems.append(
                "%s: LOST %s ; %s\n"
                "    The lock no longer carries this marker-gated pin, so a\n"
                "    --require-hashes install fails on the platform the marker\n"
                "    selects. This is what a lock re-resolved on one platform\n"
                "    looks like — do not merge it. Reproduce the bump instead:\n"
                "        python3 scripts/lock_toolchain.py -P %s"
                % (stem, name, marker, name))
        for name, marker in sorted(have - want):
            problems.append(
                "%s: NEW %s ; %s\n"
                "    A marker-gated pin that requirements/platform-pins.lock\n"
                "    does not record. If this addition is intended, run\n"
                "        python3 scripts/lock_toolchain.py\n"
                "    and commit the regenerated manifest."
                % (stem, name, marker))
    return problems


def compile_group(stem: str, python_version: str, upgrade: bool,
                  packages: Sequence[str] = ()) -> str:
    """Resolve one group and return the file contents we want on disk.

    Resolution is deliberately NOT "newest that satisfies the .in". uv treats an
    existing ``--output-file`` as the preferred solution and keeps those pins
    unless a declaration forces a change, so the compile is *stable*: it
    reproduces the committed lock byte-for-byte until someone edits the .in or
    passes ``--upgrade``.

    ``packages`` narrows that to a named few: uv re-resolves those and keeps its
    preference for every other committed pin. A group that does not contain the
    named package is therefore recompiled to exactly what it already was, which
    is why this can be applied across all groups without knowing which ones the
    package appears in.

    That distinction is the whole gate. Compiling to stdout instead re-resolves
    against the live index every time, so any upstream release makes the
    committed lock "stale" and reddens `lint` on unrelated PRs with no code
    change — which is precisely the failure mode requirements/lint-tools.in's
    header was written about. (It happened: three groups went STALE overnight.)
    """
    target = REQS / ("%s.txt" % stem)
    # Compile into a scratch copy of the committed lock so uv can read the
    # current pins and prefer them, without touching the real file until the
    # caller decides to write it.
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / target.name
        if target.exists():
            shutil.copyfile(target, scratch)
        cmd = [_uv(), "pip", "compile", str(REQS / ("%s.in" % stem)),
               "--generate-hashes", "--universal",
               "--python-version", python_version, "--no-header",
               "--output-file", str(scratch)]
        if upgrade:
            cmd.append("--upgrade")
        for name in packages:
            cmd += ["--upgrade-package", name]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit("lock_toolchain: `uv pip compile` failed for %s" % stem)
        body = _UV_HEADER.sub("", scratch.read_text(encoding="utf-8")).lstrip("\n")
    return _header(stem, python_version) + body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any generated file is stale")
    ap.add_argument("--audit", action="store_true",
                    help="exit 1 if a lock has lost a marker-gated pin "
                         "(no uv, no network — runs first inside --check)")
    ap.add_argument("--upgrade", action="store_true",
                    help="re-resolve to the newest versions the .in files allow")
    ap.add_argument("-P", "--upgrade-package", action="append", default=[],
                    metavar="NAME", dest="upgrade_package",
                    help="re-resolve only NAME (repeatable), keeping every "
                         "other committed pin — use this to answer a Dependabot "
                         "bump instead of merging its regenerated lock")
    args = ap.parse_args()

    if args.check and (args.upgrade or args.upgrade_package):
        raise SystemExit(
            "lock_toolchain: --check cannot be combined with --upgrade/-P")
    if args.upgrade and args.upgrade_package:
        # --upgrade already re-resolves everything, so naming a package on top
        # of it reads as a narrowing that is not happening.
        raise SystemExit("lock_toolchain: --upgrade and -P are exclusive")
    if args.audit and (args.upgrade or args.upgrade_package):
        # The audit reads what is committed; re-resolving in the same breath
        # would audit a file the caller is in the middle of replacing.
        raise SystemExit(
            "lock_toolchain: --audit cannot be combined with --upgrade/-P")

    # Before anything that needs uv or the network. A lost platform pin is the
    # failure that costs three Windows jobs and never names the package, so it
    # is reported here even on a runner that could not resolve at all.
    if args.audit or args.check:
        problems = audit_platform_pins(
            read_locks(),
            PLATFORM_PINS.read_text(encoding="utf-8")
            if PLATFORM_PINS.exists() else "")
        if problems:
            print("platform-pin audit FAILED:\n")
            for problem in problems:
                print("  %s\n" % problem)
            return 1
        print("platform pins intact.")
        if args.audit and not args.check:
            return 0
        # `--check --audit` asked for both, so fall through to the drift check
        # rather than letting the cheaper flag silently swallow the other.

    stale = []
    for stem, python_version in GROUPS:
        target = REQS / ("%s.txt" % stem)
        want = compile_group(stem, python_version, args.upgrade,
                             args.upgrade_package)
        if args.check:
            have = target.read_text(encoding="utf-8") if target.exists() else ""
            if have != want:
                stale.append(stem)
            continue
        target.write_text(want, encoding="utf-8")
        print("wrote %s" % target.relative_to(ROOT))

    if not args.check:
        # Recorded from what was just written, so the manifest and the locks
        # can only ever disagree when something regenerated the locks WITHOUT
        # going through this script — which is precisely the case to catch.
        PLATFORM_PINS.write_text(render_platform_pins(read_locks()),
                                 encoding="utf-8")
        print("wrote %s" % PLATFORM_PINS.relative_to(ROOT))

    if args.check:
        if stale:
            print("toolchain lock is STALE for: %s" % ", ".join(stale))
            print("run `python3 scripts/lock_toolchain.py` and commit the result")
            return 1
        print("toolchain lock is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
