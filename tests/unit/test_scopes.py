"""Unit tests for core/scopes.py — user vs project install scope."""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import scopes
from boost_cli.errors import BoostError

# ── project_root: the walk-up ────────────────────────────────────────────

def test_project_root_finds_the_marker_in_the_same_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    assert scopes.project_root(tmp_path) == tmp_path.resolve()


def test_project_root_walks_up_from_a_nested_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "src" / "deep" / "nested"
    deep.mkdir(parents=True)
    # The whole point: installing from a subdirectory must land in the repo.
    assert scopes.project_root(deep) == tmp_path.resolve()


def test_project_root_accepts_a_git_file_not_just_a_dir(tmp_path):
    # Worktrees and submodules carry a .git FILE, not a directory.
    (tmp_path / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    assert scopes.project_root(tmp_path) == tmp_path.resolve()


@pytest.mark.parametrize("marker", [".git", ".hg", ".svn"])
def test_every_marker_is_honored(tmp_path, marker):
    d = tmp_path / marker.lstrip(".")
    d.mkdir()
    (d / marker).mkdir()
    assert scopes.project_root(d) == d.resolve()


def test_dot_boost_is_not_a_project_marker(tmp_path):
    """``~/.boost`` is boost's own state dir.

    Treating ``.boost`` as a marker made ``$HOME`` a project root for every
    user the moment they ran ``boost tap``, so ``--local`` from any non-repo
    directory wrote into their real ``~/.claude/skills`` and collided with
    user-scope installs.
    """
    assert ".boost" not in scopes.PROJECT_MARKERS
    (tmp_path / ".boost").mkdir()
    assert scopes.project_root(tmp_path) is None


def test_home_is_never_a_project_root(tmp_path, monkeypatch):
    """Even when $HOME is itself a repo — dotfile setups do exactly that.

    A "project" install into $HOME would target ~/.claude/skills, i.e. the very
    directories user scope owns, collapsing the two scopes into one place.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".git").mkdir()
    assert scopes.project_root(tmp_path) is None
    deep = tmp_path / "notes" / "drafts"
    deep.mkdir(parents=True)
    assert scopes.project_root(deep) is None


def test_a_repo_under_home_still_resolves(tmp_path, monkeypatch):
    # Excluding $HOME must not exclude the repos that live inside it.
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "code" / "myrepo"
    (repo / ".git").mkdir(parents=True)
    assert scopes.project_root(repo) == repo.resolve()


def test_project_root_is_none_when_no_marker_exists(tmp_path, monkeypatch):
    # Neutralize the marker list rather than assuming nothing above the tmpdir
    # is a repo — otherwise this asserts about the machine it runs on.
    monkeypatch.setattr(scopes, "PROJECT_MARKERS", (".no-such-marker",))
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert scopes.project_root(deep) is None


def test_project_root_prefers_the_nearest_root(tmp_path):
    (tmp_path / ".git").mkdir()
    inner = tmp_path / "vendor" / "sub"
    inner.mkdir(parents=True)
    (inner / ".git").mkdir()
    assert scopes.project_root(inner) == inner.resolve()


# ── resolve_base ─────────────────────────────────────────────────────────

def test_user_scope_resolves_to_none(tmp_path):
    assert scopes.resolve_base(scopes.SCOPE_USER, start=tmp_path) is None


def test_explicit_base_wins_over_everything(tmp_path):
    (tmp_path / ".git").mkdir()
    other = tmp_path / "elsewhere"
    # An explicit base is how update/sync re-materialize where the original
    # install landed — it must beat both cwd and the discovered root.
    assert scopes.resolve_base(scopes.SCOPE_USER, base=other) == other
    assert scopes.resolve_base(scopes.SCOPE_PROJECT, base=other,
                               start=tmp_path) == other


def test_project_scope_resolves_the_repo_root_from_a_subdir(tmp_path):
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "src" / "deep"
    deep.mkdir(parents=True)
    assert scopes.resolve_base(scopes.SCOPE_PROJECT, start=deep) == tmp_path.resolve()


def test_project_scope_falls_back_to_start_when_unmarked(tmp_path, monkeypatch):
    monkeypatch.setattr(scopes, "PROJECT_MARKERS", (".no-such-marker",))
    assert scopes.resolve_base(scopes.SCOPE_PROJECT, start=tmp_path) == tmp_path


def test_project_scope_refuses_to_fall_back_to_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert scopes.resolve_base(scopes.SCOPE_PROJECT, start=tmp_path) is None


# ── relative_to_base / resolve_in_base: the committed-path contract ──────

def test_relative_to_base_strips_the_machine_specific_prefix(tmp_path):
    d = tmp_path / ".claude" / "skills" / "x"
    assert scopes.relative_to_base(tmp_path, d) == ".claude/skills/x"


def test_relative_and_resolve_round_trip(tmp_path):
    d = tmp_path / ".cursor" / "skills" / "x"
    rel = scopes.relative_to_base(tmp_path, d)
    assert scopes.resolve_in_base(tmp_path, rel) == d


def test_resolve_in_base_reanchors_onto_a_different_checkout(tmp_path):
    """The whole point of storing relative: another clone, another path."""
    other = tmp_path / "someone-elses-clone"
    other.mkdir()
    assert scopes.resolve_in_base(other, ".claude/skills/x") == \
        other / ".claude" / "skills" / "x"


@pytest.mark.parametrize("bad", ["", None, "/etc", "../../etc", "..", 5])
def test_resolve_in_base_refuses_anything_that_escapes(bad, tmp_path):
    # These come out of a committed file anyone with merge rights can edit.
    # "" is the sharp one: Path(base) / "" is base itself, so a missing key
    # would otherwise resolve to the project root and be handed to rmtree.
    assert scopes.resolve_in_base(tmp_path, bad) is None


# ── check_scope ──────────────────────────────────────────────────────────

def test_check_scope_passes_known_scopes():
    for s in scopes.SCOPES:
        assert scopes.check_scope(s) == s


def test_check_scope_rejects_anything_else():
    with pytest.raises(BoostError) as err:
        scopes.check_scope("workspace")
    # The message names the bad value and the hint lists the real ones — a
    # scope typo is the kind of error where "which are valid?" is the only
    # question the user has.
    assert err.value.message == "unknown scope 'workspace'"
    assert err.value.hint == "use one of: user, project"


# ── agent_root / skill_target ────────────────────────────────────────────

def test_agent_root_user_scope_is_the_parent_of_the_skills_dir():
    assert scopes.agent_root(Path("/home/u/.claude/skills")) == Path("/home/u/.claude")


def test_agent_root_project_scope_reuses_the_dotdir_name(tmp_path):
    assert scopes.agent_root(Path("/home/u/.cursor/skills"), tmp_path) == \
        tmp_path / ".cursor"


def test_skill_target_user_scope_is_inside_the_agent_dir():
    assert scopes.skill_target(Path("/home/u/.claude/skills"), "brainstorm") == \
        Path("/home/u/.claude/skills/brainstorm")


def test_skill_target_project_scope_lands_in_the_repo(tmp_path):
    assert scopes.skill_target(Path("/home/u/.claude/skills"), "brainstorm",
                               base=tmp_path) == \
        tmp_path / ".claude" / "skills" / "brainstorm"


def test_skill_target_carries_a_nonstandard_leaf_name(tmp_path):
    # An agent configured with a different folder name keeps it in the project.
    assert scopes.skill_target(Path("/home/u/.zed/prompts"), "x", base=tmp_path) == \
        tmp_path / ".zed" / "prompts" / "x"


@pytest.mark.parametrize("bad", ["..", ".", "../etc", "a/b", "", "x y", "a\\b"])
def test_skill_target_refuses_an_unsafe_name(bad, tmp_path):
    # This name becomes a path component inside someone's repo.
    with pytest.raises(BoostError) as err:
        scopes.skill_target(Path("/home/u/.claude/skills"), bad, base=tmp_path)
    assert err.value.message == "invalid skill name %r" % bad


# ── describe ─────────────────────────────────────────────────────────────

def test_describe_names_the_project_dir(tmp_path):
    assert scopes.describe(scopes.SCOPE_PROJECT, tmp_path) == \
        "this project (%s)" % tmp_path.name


def test_describe_user_scope_mentions_user_config():
    assert scopes.describe(scopes.SCOPE_USER) == "your user config"


def test_describe_project_without_a_base_says_cwd():
    assert scopes.describe(scopes.SCOPE_PROJECT) == "this project (cwd)"


# ── contains: the delete guard ───────────────────────────────────────────

def test_contains_true_for_a_path_inside(tmp_path):
    inner = tmp_path / ".claude" / "skills" / "x"
    inner.mkdir(parents=True)
    assert scopes.contains(tmp_path, inner) is True


def test_contains_false_for_the_base_itself(tmp_path):
    # Removing the base would delete the user's whole repo.
    assert scopes.contains(tmp_path, tmp_path) is False


def test_contains_false_for_an_escape(tmp_path):
    (tmp_path / "repo").mkdir()
    assert scopes.contains(tmp_path / "repo", tmp_path / "repo" / ".." / "..") is False


def test_contains_false_for_a_sibling(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo-backup").mkdir()
    # A prefix-string check would wrongly call this "inside".
    assert scopes.contains(tmp_path / "repo", tmp_path / "repo-backup") is False


def test_contains_false_for_an_absolute_elsewhere(tmp_path):
    assert scopes.contains(tmp_path, Path("/etc/passwd")) is False


def test_contains_fails_closed_when_paths_share_no_root(tmp_path, monkeypatch):
    """``commonpath`` raises ValueError for paths with no common root.

    On Windows that is any two different drives — a repo on ``C:`` weighed
    against a lock record pointing at ``D:``. Simulated here so the guard is
    covered on every platform, not just the one that can produce it naturally.
    """
    def boom(paths):
        raise ValueError("Paths don't have the same drive")

    monkeypatch.setattr(scopes.os.path, "commonpath", boom)
    assert scopes.contains(tmp_path, tmp_path / "x") is False


def test_contains_fails_closed_when_resolution_errors(tmp_path, monkeypatch):
    """An unresolvable path must read as "outside", never as "inside".

    This is the guard in front of a recursive delete, so the failure mode has
    to be refusing to delete — not deleting something it could not verify.

    Patches the ``Path`` name *inside scopes* rather than ``Path.resolve``
    itself: a global patch also breaks mutmut's instrumentation, which resolves
    its own source paths on every trampoline hit. The stand-in is a plain stub
    rather than a ``Path`` subclass — subclassing ``pathlib.Path`` before 3.12
    needs a ``_flavour`` attribute, and this repo supports 3.9.
    """
    class ExplodingPath:
        def __init__(self, *a, **kw):
            pass

        def resolve(self, *a, **kw):
            raise OSError("cannot resolve")

    monkeypatch.setattr(scopes, "Path", ExplodingPath)
    assert scopes.contains(tmp_path, tmp_path / "x") is False


# ── ensure_in_base: the write guard ──────────────────────────────────────

def test_ensure_in_base_returns_the_path_when_inside(tmp_path):
    dest = tmp_path / ".claude" / "skills" / "x"
    assert scopes.ensure_in_base(tmp_path, dest) == Path(dest)


def test_ensure_in_base_raises_on_a_plain_escape(tmp_path):
    (tmp_path / "repo").mkdir()
    with pytest.raises(BoostError) as err:
        scopes.ensure_in_base(tmp_path / "repo", tmp_path / "elsewhere" / "x")
    assert "outside this project" in err.value.message


def test_ensure_in_base_raises_when_a_symlinked_dir_escapes(tmp_path):
    """The write-side attack contains() is reused for: an agent dir committed as
    a symlink pointing outside the repo, targeting a NEW leaf that does not yet
    exist — so nothing but the containment check can catch it."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / ".claude" / "skills").symlink_to(outside, target_is_directory=True)
    # repo/.claude/skills/authorized_keys resolves to outside/authorized_keys.
    dest = repo / ".claude" / "skills" / "authorized_keys"
    with pytest.raises(BoostError):
        scopes.ensure_in_base(repo, dest)


def test_ensure_in_base_allows_a_real_nested_dir(tmp_path):
    # A legitimate project dir, even several levels deep, must pass untouched.
    repo = tmp_path / "repo"
    (repo / ".claude" / "skills").mkdir(parents=True)
    dest = repo / ".claude" / "skills" / "ok"
    assert scopes.ensure_in_base(repo, dest) == Path(dest)
