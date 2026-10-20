# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Install, repair and uninstall must give back exactly what they were handed.

Three ways the lifecycle used to change things it had no business changing:

* a rule round trip rewrote the user's whole context file (CRLF folded to LF,
  a missing final newline added, trailing blank lines cut);
* `boost sync` repaired a missing project copy from the tap's HEAD and
  rewrote the committed project lock, leaving one skill on two versions;
* a second repo's ``install --local`` of a rule was refused as a "different
  scope" when the scope was the same and only the repo differed.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from boost_cli.core import (
    catalog,
    lockfile,
    paths,
    projectlock,
    registry,
    rules,
    store,
    util,
)
from boost_cli.errors import BoostError

START = "<!-- boost:rule:r start -->"
END = "<!-- boost:rule:r end -->"


@pytest.fixture()
def tap(sandbox, fixture_tap_src):
    t = registry.add(str(fixture_tap_src))
    catalog.rebuild_tap(t)
    return t


@pytest.fixture()
def entry(tap):
    return catalog.resolve_one("brainstorming")


def _rule_entry(tap, name="team-conventions", rel="rules/team.mdc"):
    src = tap.path / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("---\nname: Team Conventions\n---\n\nAlways write tests first.\n",
                   encoding="utf-8")
    return {
        "name": name, "kind": "rule", "tap": tap.name, "version": "1.0.0",
        "rel_dir": str(src.parent.relative_to(tap.path)), "skill_md": rel,
        "description": "team rules", "curated": False,
        "meta": {"name": "Team Conventions"},
    }


# ── rules.merge_block / strip_block: the pure half ───────────────────────────

ORIGINALS = [
    "# Mine\r\n\r\nKeep this.\r\n",     # CRLF throughout
    "A\nno trailing nl",                # no final newline
    "A\n\n\n",                          # trailing blank lines
    "x\r\ny",                           # CRLF, no final newline
    "# notes\n",
    "",
]


class TestBlockRoundTrip:
    @pytest.mark.parametrize("original", ORIGINALS)
    def test_merge_then_strip_is_byte_identical(self, original):
        assert rules.strip_block(rules.merge_block(original, "r", "B"), "r") \
            == original

    @pytest.mark.parametrize("original", ORIGINALS)
    def test_two_blocks_strip_back_in_either_order(self, original):
        both = rules.merge_block(rules.merge_block(original, "a", "A"), "b", "B")
        assert rules.strip_block(rules.strip_block(both, "a"), "b") == original
        assert rules.strip_block(rules.strip_block(both, "b"), "a") == original

    def test_crlf_file_gets_a_crlf_block(self):
        out = rules.merge_block("A\r\n", "r", "line1\nline2\n")
        assert out == ("A\r\n\r\n" + START + "\r\nline1\r\nline2\r\n"
                       + END + "\r\n")

    def test_no_final_newline_stays_that_way(self):
        assert rules.merge_block("A", "r", "B") == \
            "A\n\n" + START + "\nB\n" + END

    def test_trailing_blank_lines_are_kept(self):
        assert rules.merge_block("A\n\n\n", "r", "B") == \
            "A\n\n\n\n" + START + "\nB\n" + END + "\n"

    def test_empty_file_gets_block_and_newline(self):
        assert rules.merge_block("", "r", "B") == START + "\nB\n" + END + "\n"

    def test_replace_in_place_keeps_surrounding_bytes(self):
        text = "top\r\n\r\n" + START + "\r\nold\r\n" + END + "\r\ntail  \r\n\r\n"
        assert rules.merge_block(text, "r", "new") == (
            "top\r\n\r\n" + START + "\r\nnew\r\n" + END + "\r\ntail  \r\n\r\n")

    def test_a_crlf_rule_body_is_not_doubled(self):
        out = rules.merge_block("A\n", "r", "x\r\ny\r\n")
        assert out == "A\n\n" + START + "\nx\ny\n" + END + "\n"

    def test_gap_deleted_by_hand_keeps_the_users_newline(self):
        assert rules.strip_block("A\n" + START + "\nB\n" + END + "\n", "r") \
            == "A\n"

    def test_lone_unterminated_block_strips_to_empty(self):
        assert rules.strip_block(START + "\nB\n" + END, "r") == ""

    def test_text_written_right_after_the_block_is_left_alone(self):
        text = "A\n\n" + START + "\nB\n" + END + "tail\n"
        assert rules.strip_block(text, "r") == "A\n\ntail\n"

    def test_read_block_of_crlf_text_is_lf(self):
        merged = rules.merge_block("A\r\n", "r", "x\ny")
        assert rules.read_block(merged, "r") == "x\ny"

    @pytest.mark.parametrize(("text", "eol"), [
        ("", "\n"), ("no newline", "\n"), ("a\nb\n", "\n"),
        ("a\r\nb\r\n", "\r\n"), ("a\r\nb\n", "\n"),         # a tie is LF
        ("a\r\nb\r\nc\n", "\r\n"), ("a\r\nb\nc\n", "\n"),
    ])
    def test_line_ending_is_the_majority(self, text, eol):
        assert rules.line_ending(text) == eol


# ── the store round trip, on disk ────────────────────────────────────────────

class TestContextFileRoundTrip:
    @pytest.mark.parametrize("original", [
        b"# Mine\r\n\r\nKeep this.\r\n", b"A\nno trailing nl", b"A\n\n\n"])
    def test_user_scope_install_uninstall_is_byte_identical(self, tap, original):
        claude_md = paths.home() / ".claude" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_bytes(original)
        store.install(_rule_entry(tap), only_agents=["claude-code"])
        merged = claude_md.read_bytes()
        assert merged.startswith(original)
        assert b"boost:rule:team-conventions start" in merged
        if b"\r\n" in original:
            assert b"\n" not in merged.replace(b"\r\n", b"")
        store.uninstall("team-conventions")
        assert claude_md.read_bytes() == original

    def test_project_scope_crlf_files_round_trip(self, tap, tmp_path):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        agents_md = repo / "AGENTS.md"
        local_md = repo / "CLAUDE.local.md"
        agents_md.write_bytes(b"Team rules\r\nline2\r\n")
        local_md.write_bytes(b"mine\r\nno final newline")
        store.install(_rule_entry(tap), scope="project", base=str(repo),
                      only_agents=["codex", "claude-code"])
        for f in (agents_md, local_md):
            body = f.read_bytes()
            assert b"boost:rule:team-conventions start" in body
            assert b"\n" not in body.replace(b"\r\n", b"")
        store.uninstall("team-conventions")
        assert agents_md.read_bytes() == b"Team rules\r\nline2\r\n"
        assert local_md.read_bytes() == b"mine\r\nno final newline"

    def test_install_hashes_the_block_verify_reads_back(self, tap):
        claude_md = paths.home() / ".claude" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_bytes(b"# Mine\r\n")
        store.install(_rule_entry(tap), only_agents=["claude-code"])
        import hashlib
        m = lockfile.get_rule("team-conventions")["materializations"][0]
        block = rules.read_block(util.read_user_text(claude_md),
                                 "team-conventions")
        assert block is not None
        assert m["sha256"] == hashlib.sha256(block.encode("utf-8")).hexdigest()

    def test_read_user_text_keeps_crlf(self, tmp_path):
        f = tmp_path / "x.md"
        f.write_bytes(b"a\r\nb\r\n")
        assert util.read_user_text(f) == "a\r\nb\r\n"


# ── project sync restores the locked content, never HEAD ─────────────────────

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                    "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                    *args], check=True, capture_output=True)


class TestProjectSyncKeepsTheLock:
    @staticmethod
    def _install(entry, tmp_path):
        repo = tmp_path / "proj"
        (repo / ".git").mkdir(parents=True)
        store.install(entry, scope="project", base=str(repo),
                      only_agents=["claude-code", "cursor"])
        return repo

    @staticmethod
    def _lock_bytes(repo):
        return (repo / ".boost" / "skill-lock.json").read_bytes()

    @staticmethod
    def _advance(tap, entry, *, touch_skill: bool):
        if touch_skill:
            md = tap.path / entry["rel_dir"] / "SKILL.md"
            md.write_text(md.read_text(encoding="utf-8") + "\nUPSTREAM CHANGE\n",
                          encoding="utf-8")
        else:
            (tap.path / "UNRELATED.md").write_text("x\n", encoding="utf-8")
        _git(tap.path, "add", "-A")
        _git(tap.path, "commit", "-q", "-m", "advance")
        catalog.rebuild_tap(tap)

    def test_moved_source_is_declined_and_nothing_is_written(
            self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        before = self._lock_bytes(repo)
        claude_copy = repo / ".claude" / "skills" / "brainstorming"
        claude_sha = util.sha256_dir(claude_copy)
        self._advance(tap, entry, touch_skill=True)
        shutil.rmtree(repo / ".cursor" / "skills" / "brainstorming")

        plan = store.project_sync_plan(base=str(repo))
        line = ("brainstorming's tap source has moved since the project lock "
                "was written — repair declined (`boost install --local "
                "brainstorming --force` takes the new content and updates "
                "the lock)")
        assert store.project_sync_preview(plan, base=str(repo)) == [line]
        assert store.project_sync_apply(plan, base=str(repo)) == [line]
        assert store.is_unrepaired(line)
        assert not (repo / ".cursor" / "skills" / "brainstorming").exists()
        assert util.sha256_dir(claude_copy) == claude_sha
        assert self._lock_bytes(repo) == before

    def test_tap_moved_but_skill_unchanged_restores_without_a_lock_write(
            self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        before = self._lock_bytes(repo)
        self._advance(tap, entry, touch_skill=False)
        cursor_copy = repo / ".cursor" / "skills" / "brainstorming"
        shutil.rmtree(cursor_copy)

        plan = store.project_sync_plan(base=str(repo))
        assert store.project_sync_apply(plan, base=str(repo)) == [
            "re-materialized brainstorming from %s" % tap.name]
        assert util.sha256_dir(cursor_copy) == \
            projectlock.get_skill(repo, "brainstorming")["sha256"]
        assert self._lock_bytes(repo) == before

    def test_same_commit_restores_without_a_lock_write(self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        before = self._lock_bytes(repo)
        cursor_copy = repo / ".cursor" / "skills" / "brainstorming"
        shutil.rmtree(cursor_copy)
        plan = store.project_sync_plan(base=str(repo))
        assert store.project_sync_apply(plan, base=str(repo)) == [
            "re-materialized brainstorming from %s" % tap.name]
        assert (cursor_copy / "SKILL.md").is_file()
        assert self._lock_bytes(repo) == before

    def test_no_recorded_sha_and_a_moved_commit_is_declined(
            self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        rec.pop("sha256")
        projectlock.set_skill(repo, "brainstorming", rec)
        self._advance(tap, entry, touch_skill=False)
        shutil.rmtree(repo / ".cursor" / "skills" / "brainstorming")
        actions = store.project_sync_apply(
            store.project_sync_plan(base=str(repo)), base=str(repo))
        assert len(actions) == 1 and "repair declined" in actions[0]

    def test_a_skill_blocklisted_since_install_is_not_restored(
            self, tap, entry, tmp_path):
        from boost_cli.core import policy
        repo = self._install(entry, tmp_path)
        cursor_copy = repo / ".cursor" / "skills" / "brainstorming"
        shutil.rmtree(cursor_copy)
        pol = policy.load()
        pol["blocked_skills"] = ["brainstorming"]
        policy.save(pol)
        rec = projectlock.get_skill(repo, "brainstorming")
        with pytest.raises(BoostError, match="policy blocks restoring "
                           "brainstorming: skill 'brainstorming' is on the "
                           "blocklist"):
            store._restore_project_copies(repo, "brainstorming", rec, entry,
                                          ["cursor"])
        plan = store.project_sync_plan(base=str(repo))
        gone = [store._project_gone("brainstorming")]
        assert store.project_sync_preview(plan, base=str(repo)) == gone
        assert store.project_sync_apply(plan, base=str(repo)) == gone
        assert not cursor_copy.exists()

    def test_an_agent_dir_symlinked_out_of_the_repo_is_not_written(
            self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        skills = repo / ".cursor" / "skills"
        shutil.rmtree(skills)
        outside = tmp_path / "outside"
        outside.mkdir()
        skills.symlink_to(outside, target_is_directory=True)
        actions = store.project_sync_apply(
            store.project_sync_plan(base=str(repo)), base=str(repo))
        assert actions == [store._project_gone("brainstorming")]
        assert list(outside.iterdir()) == []

    def test_restore_with_nothing_writable_reports_gone(self, tap, entry, tmp_path):
        repo = self._install(entry, tmp_path)
        rec = projectlock.get_skill(repo, "brainstorming")
        with pytest.raises(BoostError, match="no recorded copy of brainstorming"):
            store._restore_project_copies(repo, "brainstorming", rec, entry,
                                          ["cursor"])  # present: nothing to do


# ── a rule --local in a second repo ──────────────────────────────────────────

class TestSecondRepoRefusal:
    def test_names_the_repo_and_the_kind(self, tmp_path):
        existing = {"scope": "project", "base": str(tmp_path), "kind": "workflow"}
        with pytest.raises(BoostError) as ei:
            store._check_scope_conflict("w", existing, "project",
                                        Path("/repo2"), force=False)
        assert ei.value.message == (
            "w is already installed --local in %s, and a workflow can be "
            "installed --local into only one repo per machine"
            % paths.tilde(tmp_path))

    def test_a_row_without_a_base_says_another_repo(self):
        existing = {"scope": "project", "kind": "rule"}
        with pytest.raises(BoostError) as ei:
            store._check_scope_conflict("r", existing, "project",
                                        Path("/repo2"), force=True)
        assert ei.value.message.startswith(
            "r is already installed --local in another repo, and a rule ")

    def test_user_row_against_project_keeps_the_scope_wording(self):
        with pytest.raises(BoostError) as ei:
            store._check_scope_conflict("r", {"scope": "user"}, "project",
                                        Path("/repo2"), force=True)
        assert ei.value.message == "r is already installed at user scope"
        assert "different scope" in ei.value.hint
