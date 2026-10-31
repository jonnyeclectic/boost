# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""What the `tapped` fixture's template needs that is not a fixture.

A module of its own, not names in ``conftest.py``, because a test module has no
safe way to reach a conftest: ``import conftest`` resolves to whichever
``conftest.py`` was imported last, and a bare ``pytest`` imports
``tests/langchain/conftest.py`` after ``tests/conftest.py`` -- so
``conftest._under_mutmut()`` evaluated at import time raised ``AttributeError``
and aborted the whole collection. This name is unique, so it cannot be shadowed.

Definitions only; nothing here runs at import.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def under_mutmut() -> bool:
    """Whether mutmut is driving this run -- any non-empty ``MUTANT_UNDER_TEST``.

    mutmut 3.8.0 sets the variable around every pass that runs tests: ``stats``
    while it records which test reaches which function, ``fail`` for its
    forced-failure check, and the mutant's own name (``<module>.<name>__mutmut_N``)
    in each mutant's worker; it sets ``""`` for the clean pass that runs no
    mutant, and that pass has nothing to attribute, so it counts as an ordinary
    run (``mutmut/__main__.py``, ``mutmut/workers/isolation.py``). Read from
    ``os.environ`` rather than through mutmut's accessor: the suite must not
    import mutmut, which is not in the ordinary test requirements.
    """
    return bool(os.environ.get("MUTANT_UNDER_TEST"))


#: What the ``sandbox`` fixture sets that bears on a tap, spelled out for a child
#: process. ``sandbox`` itself is a run of ``monkeypatch.setenv`` calls with a
#: comment each, and a child cannot inherit those from a fixture it was started
#: beside, so this is the second copy of the list -- which is why
#: ``test_tapped_template.py`` compares it with what ``sandbox`` really changes
#: (``sandbox_env_delta``) rather than trusting it to stay in step.
SANDBOX_ENV = {
    "BOOST_NO_AI": "1",         # deterministic: no AI calls
    "BOOST_NO_SEED": "1",       # no seven-registry clone on an empty machine
    "BOOST_NO_RULE": "1",       # no standing block written into a context file
    "BOOST_NO_NET": "1",        # nothing reaches PyPI as a side effect
    "NO_COLOR": "1",            # plain output
    "BOOST_ASSUME_YES": "1",    # never block on a confirm
}

#: ...and what it removes: variables that relocate boost's or an agent's state
#: out of ``$HOME``, and keys that would make a command reach a real service.
SANDBOX_UNSET = (
    "BOOST_HOME", "BOOST_AGENTS_STORE", "BOOST_DEBUG", "BOOST_LOG_LEVEL",
    "BOOST_NO_LOG", "CODEX_HOME", "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_PLUGIN_CACHE_DIR", "VOYAGE_API_KEY", "OPENAI_API_KEY",
    "BOOST_NO_EMBED",
)


def child_env(base: Mapping[str, str], home: Path, shard_manifest: str,
              repo_root: Path) -> dict[str, str]:
    """The environment of the process that taps, built rather than inherited.

    ``base`` is the session's environment as it stood when the run was
    configured -- after the session HOME and the git auto-maintenance setting
    went in, before any test ran -- never the live ``os.environ``. The template
    is first requested from inside some test (see ``tapped``), and the live
    environment is whatever that test's fixtures have patched; a child that
    inherited it would build the one HOME every later test in the worker copies
    from, under that test's variables.
    """
    env = dict(base)
    for name in SANDBOX_UNSET:
        env.pop(name, None)
    env.update(SANDBOX_ENV)
    env["HOME"] = str(home)
    if sys.platform == "win32":
        env["USERPROFILE"] = str(home)      # what `Path.home` reads there
    env["BOOST_SHARD_MANIFEST"] = shard_manifest
    # The repo first, as the suite's other child-process tests do, so the child
    # imports the checkout under test whether or not it is installed editable.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(repo_root), base.get("PYTHONPATH", "")) if p)
    env["PYTHONIOENCODING"] = "utf-8"
    # The child runs no mutant. Under mutmut `tapped` never reaches the
    # template; the clean pass leaves "", and a stale name here would only
    # make a trampoline in the child look for a mutant that is not there.
    env.pop("MUTANT_UNDER_TEST", None)
    return env


def check_tapped_home(home: Path, source: Path, env: Mapping[str, str]
                      ) -> list[str]:
    """What is wrong with a HOME that ``boost tap source`` was meant to fill.

    An empty list is the only good answer. These are the three things every
    test that copies the template is going to take for granted, read from the
    files rather than from the command's exit status: a tap that exited 0
    having catalogued nothing is the failure that would otherwise surface as
    dozens of unrelated tests finding no skills.
    """
    problems: list[str] = []
    name = source.name
    boost_home = home / ".boost"

    try:
        taps = json.loads((boost_home / "config.json").read_text(
            encoding="utf-8")).get("taps", [])
    except (OSError, ValueError, AttributeError) as e:
        taps = []
        problems.append("config.json unreadable: %s" % e)
    rows = [t for t in taps if isinstance(t, dict) and t.get("name") == name]
    if not rows:
        problems.append("config.json has no tap row named %r" % name)
    elif Path(str(rows[0].get("url"))).resolve() != source.resolve():
        problems.append("tap %r points at %r, not %s"
                        % (name, rows[0].get("url"), source))

    commit = None
    try:
        cache = json.loads((boost_home / "cache" / (name + ".json")).read_text(
            encoding="utf-8"))
        commit = cache.get("commit")
        if not cache.get("skills"):
            problems.append("the catalog cache %s.json lists no skills" % name)
    except (OSError, ValueError, AttributeError) as e:
        problems.append("the catalog cache %s.json is unreadable: %s" % (name, e))

    git_dir = boost_home / "repos" / name / ".git"
    head = subprocess.run(
        ["git", "--git-dir", str(git_dir), "rev-parse", "--verify", "-q", "HEAD"],
        env=dict(env), stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False)
    if head.returncode:
        problems.append("the clone at %s has no HEAD" % git_dir.parent)
    elif commit and head.stdout.strip() != commit:
        problems.append("the cache describes commit %s but the clone is at %s"
                        % (commit, head.stdout.strip()))
    return problems


def build_tapped_home(root: Path, source: Path, base_env: Mapping[str, str],
                      repo_root: Path) -> Path:
    """Run ``boost tap source`` in a child process under ``root``; return its HOME.

    A child process, not a call to ``main`` in this one, so that nothing the
    requesting test has done to *this* process -- a ``monkeypatch`` of
    ``catalog.scan_dir``, of ``subprocess``, of ``sys.platform``, of the
    environment -- can reach the build. The template is cached for every later
    test in the worker, and a test's patch is meant to last one test: an
    in-process build under a fixture that stubbed the scanner cached an empty
    catalog, and the next test to ask for ``tapped`` failed with ``0 > 0``,
    which one runs-in-isolation never shows. Cost: one interpreter start per
    worker (~0.3 s), against the ~0.15 s the in-process build took.

    The result is checked before it is returned, and a fixture that raises is
    not cached as a value, so a template that is wrong fails loudly and
    everywhere it is asked for, instead of being copied.
    """
    home = root / "home"
    cwd = root / "cwd"      # a sibling of HOME with no VCS marker, as `sandbox`'s
    home.mkdir(parents=True)
    cwd.mkdir()
    env = child_env(base_env, home, (root / "no-manifest.json").as_uri(),
                    repo_root)
    proc = subprocess.run(
        [sys.executable, "-m", "boost_cli", "tap", str(source)],
        cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    problems = ["boost tap exited %d" % proc.returncode] if proc.returncode else []
    problems += check_tapped_home(home, source, env)
    if problems:
        raise AssertionError(
            "the tapped-HOME template is bad, so no test may copy it:\n  - %s\n"
            "--- boost tap %s ---\n--- stdout ---\n%s--- stderr ---\n%s"
            % ("\n  - ".join(problems), source, proc.stdout, proc.stderr))
    return home


def copy_template(template: Path, dest: Path) -> Path:
    """Copy a built template to ``dest``; return ``dest``.

    ``symlinks=True``: a link stays a link rather than becoming a file, or
    (dangling) an error. The default ``copy2`` keeps file times -- the refresh
    marker and the catalog cache are read by mtime
    (``registry.refresh_age_days``, ``catalog._ENTRY_CACHE``'s stamp), so a copy
    stamped "now" would make a fresh template look newer than the clone it
    describes. Bytes, not hard links: a local ``git clone`` hard-links its
    objects, and a link shared with the template would let one test's ``untap``
    delete the next test's clone.

    What a copy cannot keep is git's index stat data (inode and ctime): plumbing
    such as ``git diff-files`` calls the copied tree modified until something
    refreshes the index. Porcelain re-reads the content and finds it clean, and
    nothing in ``boost_cli`` calls the plumbing (``gitutil.narrow`` runs
    ``update-index --refresh`` itself for this reason).
    """
    dest = Path(dest)
    shutil.copytree(template, dest, symlinks=True, dirs_exist_ok=True)
    return dest
