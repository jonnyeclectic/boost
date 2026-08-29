# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit test: .github/dependabot.yml — what actually gets bump PRs.

Dependabot only scans manifests under an entry's declared ``directory``, so
"we have a pip entry" says nothing about which manifests are covered. This
pins the two that matter (``/requirements`` for the hash-pinned toolchain, ``/``
for ``pyproject.toml``'s extras) and ties the root entry's ignore list to the
version ceilings pyproject actually sets — so lifting a ceiling and leaving a
stale ignore behind fails here rather than silently costing us the bump PRs.

Read by hand rather than with a YAML parser: PyYAML is not a dependency of this
repo, and ``scripts/check_required_checks.py`` sets the same precedent for
workflow YAML.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"
PYPROJECT = ROOT / "pyproject.toml"

pytestmark = pytest.mark.skipif(
    not CONFIG.exists(),
    reason="repo-root .github/dependabot.yml not reachable (e.g. mutation sandbox)")

_ENTRY = re.compile(r"^  - package-ecosystem:\s*(\S+)\s*$")
_FIELD = re.compile(r"^    (\w[\w-]*):\s*(\S*)\s*$")
_IGNORE = re.compile(r"^      - dependency-name:\s*(\S+)\s*$")


def entries():
    """[(ecosystem, directory, [ignored dependency names])] in file order."""
    out = []
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        m = _ENTRY.match(line)
        if m:
            out.append((m.group(1), None, []))
            continue
        if not out:
            continue
        eco, _directory, ignored = out[-1]
        m = _FIELD.match(line)
        if m and m.group(1) == "directory":
            out[-1] = (eco, m.group(2), ignored)
            continue
        m = _IGNORE.match(line)
        if m:
            ignored.append(m.group(1))
    return out


def pip_entry(directory: str):
    matches = [e for e in entries() if e[0] == "pip" and e[1] == directory]
    assert len(matches) == 1, "expected exactly one pip entry for %r" % directory
    return matches[0]


def test_every_entry_declares_a_directory():
    # An entry with no directory silently defaults to /, which would make one
    # of these a duplicate of another rather than the coverage it looks like.
    assert entries(), "no update entries parsed — has the file's shape changed?"
    for eco, directory, _ignored in entries():
        assert directory, "%s entry has no directory" % eco


def test_the_pinned_toolchain_is_covered():
    # requirements/*.txt are hash-pinned; a pin with no update path is only
    # half the job, so this entry is what stops the lock silently rotting.
    assert pip_entry("/requirements")[1] == "/requirements"


def test_pyprojects_extras_are_covered():
    # The bug this file was added for: only /requirements was declared, so
    # pyproject.toml at the repo root was never scanned and [rag]/[bdd]/[perf]
    # got no proactive bumps at all — only reactive pip-audit CVE flags.
    assert pip_entry("/")[1] == "/"


def test_the_actions_workflows_are_covered():
    assert [e for e in entries() if e[0] == "github-actions"], \
        "workflow action versions are a supply-chain surface too"


@pytest.mark.skipif(sys.version_info < (3, 11),
                    reason="tomllib is stdlib only on Python 3.11+")
def test_the_root_ignore_list_matches_the_ceilings_pyproject_sets():
    """Ignore exactly the packages pyproject deliberately holds back.

    ragas 0.2.x hard-imports a ChatVertexAI path that langchain>=1.0 removed,
    so the [eval] stack carries upper bounds and a bump PR there cannot be
    merged. Ignoring them is why declaring ``directory: /`` is safe at all.
    Anything held back but *not* ignored raises unmergeable PRs; anything
    ignored but no longer held back silently costs us a bump we could take.
    """
    import tomllib

    with open(PYPROJECT, "rb") as f:
        extras = tomllib.load(f)["project"]["optional-dependencies"]
    held_back = {re.split(r"[<>=!~\[]", req, maxsplit=1)[0].strip()
                 for reqs in extras.values() for req in reqs if "<" in req}
    assert held_back, "no upper bounds left in pyproject — drop the ignores"
    assert set(pip_entry("/")[2]) == held_back


def limit_for(directory: str):
    """The `open-pull-requests-limit` of the pip entry for `directory`, or None.

    Parsed separately rather than by widening `entries()`, which several tests
    unpack positionally.
    """
    seen = None
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        m = _ENTRY.match(line)
        if m:
            seen = {"eco": m.group(1)}
            continue
        if seen is None:
            continue
        m = _FIELD.match(line)
        if not m:
            continue
        seen[m.group(1)] = m.group(2)
        if seen.get("directory") == directory and seen["eco"] == "pip" \
                and "open-pull-requests-limit" in seen:
            return int(seen["open-pull-requests-limit"])
    return None


class TestNeitherPipEntryRegeneratesTheLock:
    """Dependabot must not raise *version* updates for either pip entry.

    Not a preference — it cannot regenerate the hash-pinned locks correctly. It
    re-resolves on Linux and commits that resolution, dropping every pin whose
    environment marker excludes it there, and the locks install with
    --require-hashes on Windows and macOS too. `scripts/lock_toolchain.py`
    resolves --universal for every supported platform, which is why it is the
    source of truth (see its `-P` flag, and requirements/platform-pins.lock).

    `open-pull-requests-limit: 0` disables version updates while leaving
    **security** updates firing, which is what these entries are actually worth.
    """

    def test_the_requirements_entry_raises_no_version_prs(self):
        assert limit_for("/requirements") == 0

    def test_the_root_entry_raises_no_version_prs(self):
        # The root entry cannot deliver what it was added for: every constraint
        # under [project.optional-dependencies] is either an open lower bound or
        # in its own ignore list, so the set of pyproject version updates it can
        # ever produce is EMPTY — none of the eight PRs in the first scheduled
        # run touched pyproject.toml. What it did produce was byte-identical
        # duplicates of the /requirements entry's lock regenerations, which is
        # the one thing that must never be merged.
        assert limit_for("/") == 0

    def test_both_pip_entries_still_exist(self):
        # Deleting them would give up security updates too, which ignore the
        # limit and are the coverage these entries genuinely provide.
        assert pip_entry("/requirements")
        assert pip_entry("/")
