# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""A real SIGTERM, from outside, rolls an install back the way Ctrl-C does.

Measured before the fix: `timeout`-style SIGTERM at the lock write exited
-15 (killed by the signal) and left ``~/.agents/skills/tdd-workflow`` and its
links with no lock row; the rerun refused with "already in the store ... the
lock file does not record it".
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import boost_cli
from boost_cli.core import catalog, lockfile, paths, registry, store

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="POSIX signal delivery")

# The child parks inside the lock write, after the copy and the links, and
# says so through a marker file, so the parent signals at a known point.
CHILD = """
import sys, time
from pathlib import Path
from boost_cli.core import lockfile
marker = Path(sys.argv[1])
real = lockfile.write
def write(lock):
    marker.write_text("parked", encoding="utf-8")
    time.sleep(60)
    return real(lock)
lockfile.write = write
from boost_cli.cli import main
sys.exit(main(["install", "tdd-workflow"]))
"""


def test_sigterm_mid_install_rolls_back_and_exits_143(
        sandbox, fixture_tap_src, tmp_path):
    src = tmp_path / "sigterm-tap"
    shutil.copytree(fixture_tap_src, src, symlinks=True)
    catalog.rebuild_tap(registry.add(str(src)))
    marker = tmp_path / "parked"
    pkg_root = Path(boost_cli.__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(pkg_root), PYTHONIOENCODING="utf-8")
    # cwd = the package root: under the mutation gate the child's import is
    # mutmut's trampoline, which reads setup.cfg from the current directory.
    proc = subprocess.Popen([sys.executable, "-c", CHILD, str(marker)],
                            env=env, cwd=pkg_root, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding="utf-8")
    try:
        deadline = time.monotonic() + 60
        while not marker.exists():
            assert proc.poll() is None, proc.communicate()
            assert time.monotonic() < deadline, "child never reached the write"
            time.sleep(0.05)
        # The copy and links are on disk at this point: there is something
        # to roll back.
        assert store.skill_store_dir("tdd-workflow").is_dir()
        proc.send_signal(signal.SIGTERM)
        _out, err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
    assert proc.returncode == 143, err
    assert "Traceback" not in err
    assert not os.path.lexists(store.skill_store_dir("tdd-workflow"))
    assert store.linked_agents("tdd-workflow") == []
    assert lockfile.get_skill("tdd-workflow") is None
    assert [p.name for p in paths.store_dir().iterdir()
            if p.name.startswith(".boost-")] == []
    # ...so a plain rerun installs it, with its tap.
    store.install(catalog.resolve_one("tdd-workflow"))
    assert lockfile.get_skill("tdd-workflow")["tap"] == "sigterm-tap"
