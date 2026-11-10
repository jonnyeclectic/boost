# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Re-installing an unversioned skill whose body has not changed is a no-op.

A skill whose frontmatter names no version is catalogued at
``catalog.UNDECLARED_VERSION``, and two of those say nothing about whether the
bodies agree. `store.same_install` asks the content digest instead -- but no
lock row recorded one, so the branch never matched and every unversioned
re-install still failed with rc 1. Install now stamps the catalog entry's
``content`` digest into the row, user and project lock alike.
"""
from __future__ import annotations

import subprocess

import pytest

from boost_cli.core import catalog, lockfile, paths, projectlock, registry, store
from boost_cli.errors import AlreadyInstalled, BoostError


def _tap(root):
    (root / "skills" / "plain").mkdir(parents=True)
    (root / "skills" / "plain" / "SKILL.md").write_text(
        "---\nname: plain\ndescription: no version here\n---\n\nplain body\n",
        encoding="utf-8")

    def run(*a):
        subprocess.run(a, cwd=root, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@boost.test")
    run("git", "config", "user.name", "T")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "items")
    tap = registry.add(str(root))
    catalog.rebuild_tap(tap)
    [entry] = catalog.find("plain")
    return entry


@pytest.fixture
def plain(sandbox, tmp_path):
    entry = _tap(tmp_path / "tap")
    assert entry["version"] == catalog.UNDECLARED_VERSION
    assert entry["content"]
    return entry


class TestContentField:
    def test_a_digest_is_recorded(self):
        assert store.content_field({"content": "abc"}) == {"content": "abc"}

    @pytest.mark.parametrize("entry", [{}, {"content": ""},
                                       {"content": None}])
    def test_no_digest_records_no_key(self, entry):
        assert store.content_field(entry) == {}


class TestUserScope:
    def test_install_records_the_digest(self, plain):
        store.install(plain)
        assert lockfile.get_skill("plain")["content"] == plain["content"]

    def test_the_same_body_again_is_already_installed(self, plain):
        store.install(plain)
        with pytest.raises(AlreadyInstalled) as ei:
            store.install(plain)
        assert ei.value.name == "plain"
        assert ei.value.version == catalog.UNDECLARED_VERSION

    def test_a_changed_body_is_refused(self, plain):
        store.install(plain)
        with pytest.raises(BoostError) as ei:
            store.install({**plain, "content": "0" * 16})
        assert type(ei.value) is BoostError
        assert ei.value.message == "plain is already installed (v0.0.0)"

    def test_a_forced_reinstall_rerecords_the_digest(self, plain):
        store.install({**plain, "content": "0" * 16})
        store.install(plain, force=True)
        assert lockfile.get_skill("plain")["content"] == plain["content"]


class TestProjectScope:
    @pytest.fixture
    def repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        return repo

    def test_install_records_the_digest(self, plain, repo):
        store.install(plain, scope="project", base=str(repo))
        row = projectlock.get_skill(repo, "plain")
        assert row["content"] == plain["content"]

    def test_the_same_body_again_is_already_installed(self, plain, repo):
        store.install(plain, scope="project", base=str(repo))
        with pytest.raises(AlreadyInstalled):
            store.install(plain, scope="project", base=str(repo))

    def test_a_changed_body_is_refused(self, plain, repo):
        store.install(plain, scope="project", base=str(repo))
        with pytest.raises(BoostError) as ei:
            store.install({**plain, "content": "0" * 16}, scope="project",
                          base=str(repo))
        assert type(ei.value) is BoostError



class TestARecoveredRecordCarriesTheDigest:
    """`boost sync` re-records a skill whose lock row was lost; the row it
    writes must carry the digest too, or the next re-install refuses again."""

    def test_the_re_record_keeps_the_no_op(self, plain):
        store.install(plain)
        paths.lockfile_path().unlink()
        store.sync_apply(store.sync_plan())
        assert lockfile.get_skill("plain")["content"] == plain["content"]
        with pytest.raises(AlreadyInstalled):
            store.install(plain)


@pytest.fixture(params=["user", "project"])
def scope(request, tmp_path):
    """``(install kwargs, get row, put row)`` for one lock: the user lock or
    a --local project's."""
    if request.param == "user":
        return {}, lambda: lockfile.get_skill("plain"), \
            lambda row: lockfile.set_skill("plain", row)
    repo = tmp_path / "repo"
    repo.mkdir()
    return ({"scope": "project", "base": str(repo)},
            lambda: projectlock.get_skill(repo, "plain"),
            lambda row: projectlock.set_skill(repo, "plain", row))


class TestNoDigestIsNeverAMatch:
    def test_a_legacy_row_without_a_digest_is_refused(self, plain, scope):
        kw, get, put = scope
        store.install(plain, **kw)
        row = get()
        del row["content"]
        put(row)
        assert "content" not in get()
        with pytest.raises(BoostError) as ei:
            store.install(plain, **kw)
        assert type(ei.value) is BoostError

    def test_two_absent_digests_are_refused(self, plain, scope):
        kw, get, _put = scope
        bare = {k: v for k, v in plain.items() if k != "content"}
        store.install(bare, **kw)
        assert "content" not in get()
        with pytest.raises(BoostError) as ei:
            store.install(bare, **kw)
        assert type(ei.value) is BoostError
