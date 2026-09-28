# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Functional tests: the repo-root guard's probe list covers what really lands.

`tests/unit/test_repo_root_guard.py` pins each probe against the table it is
derived from. That proves the derivation, not the coverage — a slot boost
writes to and no table names would pass every one of those tests and still be
invisible. So these drive the real commands into a throwaway repo and ask the
guard, pointed at that repo, whether it noticed.

If one of these fails, the guard has a hole and the checkout is unprotected
against that command. The fix is a probe, not an assertion.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


def load_conftest():
    spec = importlib.util.spec_from_file_location("boost_conftest_e2e_guard",
                                                  CONFTEST)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def watch(sandbox, tmp_path, monkeypatch):
    """A repo-shaped directory, cd'd into, with the guard watching it.

    Returns a callable that answers "what did the guard see change here?".

    Depends on `sandbox` explicitly rather than relying on the test signature
    listing `boost` first. Both fixtures chdir through the *same* `monkeypatch`
    instance, so the one created later wins; without this dependency the order
    would come from argument order, and reordering a signature would make
    `test_an_untouched_repo_reports_nothing` pass vacuously while the other
    three failed. It also keeps `project_scope_probes` off the real `$HOME`.
    """
    guard = load_conftest()
    repo = tmp_path / "victim"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)
    probes = guard.project_scope_probes(repo)
    before = guard.fingerprint_paths(probes)

    def changed():
        return guard.repo_root_intruders(before,
                                         guard.fingerprint_paths(probes))
    changed.repo = repo
    return changed


def test_a_project_skill_install_is_caught(boost, tapped, watch):
    boost("install", "brainstorming", "--local")
    hits = watch()
    assert hits, "a --local skill install went unnoticed"
    # The lock by name, because it is the artifact the original incident left
    # behind and the one the next suite run reads back.
    assert any(h.endswith("skill-lock.json") for h in hits), hits


def test_a_project_skill_install_is_caught_in_every_agent_dotdir(boost, tapped,
                                                                 watch):
    boost("install", "brainstorming", "--local")
    hits = watch()
    # `Path(h).parts` rather than a "/<dotdir>/" substring: the guard reports
    # `str(Path)`, which is backslash-separated on Windows, so the substring
    # form matched nothing there and failed only on the Windows runners.
    parts = [Path(h).parts for h in hits]
    for dotdir in (".claude", ".cursor", ".windsurf", ".gemini", ".codex"):
        assert any(dotdir in p for p in parts), (dotdir, hits)


def test_a_project_mcp_registration_is_caught(watch):
    # `<repo>/.mcp.json` is the one project-scope artifact that is committable
    # and the one no table the probe list is derived from names — `store.
    # register_project_mcp` joins it straight onto the base. Driving the real
    # writer rather than the fixture tap, because no fixture skill declares an
    # MCP server and adding one to a tap the whole functional suite shares
    # would change what every other test installs.
    from boost_cli.core import store
    rows = [{"name": "probe", "spec": {"command": "true"}}]
    assert store.register_project_mcp(watch.repo, rows, "brainstorming") \
        == ["probe"]
    hits = watch()
    assert any(h.endswith(".mcp.json") for h in hits), hits


def test_an_untouched_repo_reports_nothing(boost, tapped, watch):
    # The other half of every guard: it has to be silent when nothing happened,
    # or it teaches people to ignore it. `tapped` has already run a user-scope
    # tap and install path through this process.
    boost("install", "brainstorming")
    assert watch() == []


def test_a_project_uninstall_is_caught_too(boost, tapped, watch):
    boost("install", "brainstorming", "--local")
    guard = load_conftest()
    probes = guard.project_scope_probes(watch.repo)
    after_install = guard.fingerprint_paths(probes)
    boost("uninstall", "brainstorming", "--local")
    # A test that *removes* the developer's state is the worse bug of the two,
    # so the diff has to be symmetric rather than append-only.
    assert guard.repo_root_intruders(after_install,
                                     guard.fingerprint_paths(probes))
