# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""The suite runs every child ``git`` with auto-maintenance off.

``git commit``, ``fetch``, ``merge`` and ``rebase`` spawn a *detached*
``git maintenance run --auto``, which creates and deletes
``.git/objects/maintenance.lock`` after the command has returned. A test that
then ``copytree``s the repo lists the lock, finds it gone, and raises
``shutil.Error`` — measured under ``pytest -n auto`` with git 2.56. Repo-local
config protects a repo and its copies but not a fresh ``git clone`` of it, and
dozens of tests build and commit repos of their own, so ``pytest_configure``
sets it once for the whole process tree through ``GIT_CONFIG_COUNT``, which
survives the per-test ``sandbox`` HOME swap and ``GIT_CONFIG_GLOBAL=/dev/null``.
"""

from __future__ import annotations

import os
import subprocess

import conftest


def test_a_fresh_repo_sees_auto_maintenance_off(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True,
                   capture_output=True)
    got = subprocess.run(["git", "-C", str(tmp_path), "config", "--get",
                          "maintenance.auto"], capture_output=True, text=True)
    assert got.stdout.strip() == "false"


def test_it_survives_an_empty_global_config(tmp_path):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_NOSYSTEM="1")
    got = subprocess.run(["git", "config", "--get", "maintenance.auto"],
                         cwd=tmp_path, env=env, capture_output=True, text=True)
    assert got.stdout.strip() == "false"


def test_existing_entries_are_appended_to_not_clobbered():
    env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.quotepath",
           "GIT_CONFIG_VALUE_0": "off"}
    conftest._disable_git_auto_maintenance(env)
    assert env == {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "core.quotepath", "GIT_CONFIG_VALUE_0": "off",
        "GIT_CONFIG_KEY_1": "maintenance.auto", "GIT_CONFIG_VALUE_1": "false",
    }


def test_a_second_call_adds_nothing():
    # An xdist worker inherits the controller's environment and then runs
    # pytest_configure itself; a second entry would be harmless to git but
    # would grow the list once per process generation.
    env: dict[str, str] = {}
    conftest._disable_git_auto_maintenance(env)
    conftest._disable_git_auto_maintenance(env)
    assert env == {"GIT_CONFIG_COUNT": "1",
                   "GIT_CONFIG_KEY_0": "maintenance.auto",
                   "GIT_CONFIG_VALUE_0": "false"}


def test_an_unset_or_garbled_count_starts_from_zero():
    env = {"GIT_CONFIG_COUNT": "x"}
    conftest._disable_git_auto_maintenance(env)
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "maintenance.auto"
