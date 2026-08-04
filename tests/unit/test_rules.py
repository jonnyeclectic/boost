"""Unit tests: core.rules — pure rule-materialization logic (mutation-gated).

rules.py has no side effects: it decides where a rule lands per agent and
splices the CLAUDE.md managed block. The assertions pin the marker format, the
per-agent target map, and every branch of the block merge/strip so a broken
splice can't silently corrupt a user's CLAUDE.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from boost_cli.core import rules
from boost_cli.errors import BoostError


class TestMarkers:
    def test_name_scoped_start_end(self):
        start, end = rules.markers("foo")
        assert start == "<!-- boost:rule:foo start -->"
        assert end == "<!-- boost:rule:foo end -->"

    def test_different_names_differ(self):
        assert rules.markers("a")[0] != rules.markers("b")[0]


class TestContextFiles:
    """The context-file map replaced a bare set of agent names, so the (user,
    project) filename *pair* — not just membership — is what decides where a
    rule lands. Pin both entries exactly."""

    def test_exact_map(self):
        assert rules.CONTEXT_FILES == {
            "claude-code": ("CLAUDE.md", "CLAUDE.local.md"),
            "gemini": ("GEMINI.md", "GEMINI.md"),
        }

    def test_claude_user_and_project_filenames_differ(self):
        # ~/.claude/CLAUDE.md is personal, but <repo>/CLAUDE.md is committed and
        # team-reviewed — so project scope must divert to CLAUDE.local.md.
        user_name, project_name = rules.CONTEXT_FILES["claude-code"]
        assert user_name != project_name
        assert project_name == "CLAUDE.local.md"

    def test_gemini_uses_the_same_file_in_both_scopes(self):
        # Gemini CLI documents no ".local" variant: <repo>/GEMINI.md is the
        # per-project context file, so the pair is deliberately identical.
        assert rules.CONTEXT_FILES["gemini"] == ("GEMINI.md", "GEMINI.md")

    def test_rules_dir_agents_are_absent(self):
        # membership here is what routes an agent away from its rules/ dir
        for agent in ("cursor", "windsurf", "cline", "zed"):
            assert agent not in rules.CONTEXT_FILES

    def test_mode_claude_value_is_frozen(self):
        # written verbatim into every rule's lock record; renaming it would
        # orphan already-installed materializations (see store._uninstall_rule).
        assert rules.MODE_CLAUDE == "claude"
        assert rules.MODE_FILE == "file"


class TestRuleTarget:
    def test_claude_merges_into_claude_md_at_root(self):
        mode, path = rules.rule_target("claude-code", Path("/h/.claude/skills"), "r")
        assert mode == rules.MODE_CLAUDE
        assert path == Path("/h/.claude/CLAUDE.md")

    def test_gemini_merges_into_gemini_md_at_root(self):
        mode, path = rules.rule_target("gemini", Path("/h/.gemini/skills"), "r")
        assert mode == rules.MODE_CLAUDE
        assert path == Path("/h/.gemini/GEMINI.md")

    def test_context_file_ignores_the_rule_name(self):
        # the block is name-scoped *inside* the file, so two rules must merge
        # into the SAME context file rather than one file each.
        _m, a = rules.rule_target("gemini", Path("/h/.gemini/skills"), "alpha")
        _m2, b = rules.rule_target("gemini", Path("/h/.gemini/skills"), "beta")
        assert a == b == Path("/h/.gemini/GEMINI.md")

    def test_cursor_drops_mdc_in_rules_dir(self):
        mode, path = rules.rule_target("cursor", Path("/h/.cursor/skills"), "r")
        assert mode == rules.MODE_FILE
        assert path == Path("/h/.cursor/rules/r.mdc")

    def test_windsurf_uses_md(self):
        mode, path = rules.rule_target("windsurf", Path("/h/.windsurf/skills"), "r")
        assert mode == rules.MODE_FILE
        assert path == Path("/h/.windsurf/rules/r.md")

    def test_unknown_agent_defaults_to_md_file(self):
        mode, path = rules.rule_target("zed", Path("/h/.zed/skills"), "r")
        assert mode == rules.MODE_FILE
        assert path == Path("/h/.zed/rules/r.md")

    # --- project scope (base=<repo>) ---
    def test_project_claude_uses_claude_local_md_at_repo_root(self):
        mode, path = rules.rule_target("claude-code", Path("/h/.claude/skills"),
                                       "r", base=Path("/repo"))
        assert mode == rules.MODE_CLAUDE
        assert path == Path("/repo/CLAUDE.local.md")   # personal, not ~/.claude

    def test_project_gemini_uses_plain_gemini_md_at_repo_root(self):
        mode, path = rules.rule_target("gemini", Path("/h/.gemini/skills"),
                                       "r", base=Path("/repo"))
        assert mode == rules.MODE_CLAUDE
        assert path == Path("/repo/GEMINI.md")         # no .local variant exists

    def test_project_scope_claude_and_gemini_diverge(self):
        # the two context-file agents share a mode but NOT a filename rule:
        # Claude diverts to a .local file in project scope, Gemini does not.
        _m, claude = rules.rule_target("claude-code", Path("/h/.claude/skills"),
                                       "r", base=Path("/repo"))
        _m2, gemini = rules.rule_target("gemini", Path("/h/.gemini/skills"),
                                        "r", base=Path("/repo"))
        assert claude != gemini
        assert claude.name == "CLAUDE.local.md"
        assert gemini.name == "GEMINI.md"
        assert claude.parent == gemini.parent == Path("/repo")

    def test_project_scope_context_file_ignores_the_agent_dotdir(self):
        # unlike the rules-dir agents, a context file lands at the repo ROOT —
        # not under <repo>/.gemini/.
        _mode, path = rules.rule_target("gemini", Path("/h/.gemini/skills"), "r",
                                        base=Path("/repo"))
        assert ".gemini" not in path.parts

    def test_project_cursor_uses_repo_dotcursor_rules(self):
        mode, path = rules.rule_target("cursor", Path("/h/.cursor/skills"),
                                       "r", base=Path("/repo"))
        assert mode == rules.MODE_FILE
        assert path == Path("/repo/.cursor/rules/r.mdc")

    def test_project_windsurf_uses_repo_dotwindsurf(self):
        _mode, path = rules.rule_target("windsurf", Path("/h/.windsurf/skills"),
                                        "r", base=Path("/repo"))
        assert path == Path("/repo/.windsurf/rules/r.md")


class TestRenderClaudeBody:
    def test_title_header_then_body(self):
        assert rules.render_claude_body("Team", "a\nb") == "# Team\n\na\nb"

    def test_surrounding_newlines_stripped(self):
        assert rules.render_claude_body("T", "\n\nx\n\n") == "# T\n\nx"

    def test_title_whitespace_stripped(self):
        assert rules.render_claude_body("  T  ", "x") == "# T\n\nx"

    def test_empty_body_is_title_only(self):
        assert rules.render_claude_body("T", "\n\n") == "# T"


class TestMergeBlock:
    def test_append_to_empty_file(self):
        assert rules.merge_block("", "r", "BODY") == (
            "<!-- boost:rule:r start -->\nBODY\n<!-- boost:rule:r end -->\n")

    def test_append_after_existing_content_with_one_blank_line(self):
        assert rules.merge_block("# notes\n", "r", "B") == (
            "# notes\n\n<!-- boost:rule:r start -->\nB\n<!-- boost:rule:r end -->\n")

    def test_reinstall_replaces_block_in_place_not_appends(self):
        first = rules.merge_block("# notes\n", "r", "OLD")
        second = rules.merge_block(first, "r", "NEW")
        assert "NEW" in second and "OLD" not in second
        assert second.count("boost:rule:r start") == 1
        assert second.startswith("# notes\n")

    def test_replace_preserves_content_after_the_block(self):
        base = rules.merge_block("head\n", "r", "OLD") + "tail line\n"
        out = rules.merge_block(base, "r", "NEW")
        assert "tail line" in out and "NEW" in out and "OLD" not in out

    def test_ends_in_a_single_trailing_newline(self):
        out = rules.merge_block("x\n\n\n", "r", "B")
        assert out.endswith("end -->\n")
        assert not out.endswith("\n\n")

    def test_two_rules_coexist(self):
        out = rules.merge_block(rules.merge_block("", "a", "A"), "b", "B")
        assert "boost:rule:a start" in out
        assert "boost:rule:b start" in out
        assert out.count("boost:rule:a start") == 1

    def test_body_inner_newlines_trimmed(self):
        out = rules.merge_block("", "r", "\n\nX\n\n")
        assert out == "<!-- boost:rule:r start -->\nX\n<!-- boost:rule:r end -->\n"


class TestStripBlock:
    def test_absent_block_is_a_noop(self):
        assert rules.strip_block("# notes\n", "r") == "# notes\n"

    def test_removing_sole_block_yields_empty(self):
        assert rules.strip_block(rules.merge_block("", "r", "B"), "r") == ""

    def test_preserves_content_before_and_after(self):
        base = rules.merge_block("before\n", "r", "B") + "after line\n"
        out = rules.strip_block(base, "r")
        assert "boost:rule" not in out
        assert out == "before\n\nafter line\n"

    def test_preserves_leading_content_only(self):
        t = rules.merge_block("# notes\n", "r", "B")
        assert rules.strip_block(t, "r") == "# notes\n"

    def test_malformed_missing_end_marker_left_untouched(self):
        t = "<!-- boost:rule:r start -->\nB\n"  # no end marker
        assert rules.strip_block(t, "r") == t

    def test_only_strips_the_named_block(self):
        both = rules.merge_block(rules.merge_block("", "a", "A"), "b", "B")
        out = rules.strip_block(both, "a")
        assert "boost:rule:a" not in out
        assert "boost:rule:b start" in out

    def test_merge_then_strip_round_trips_to_original(self):
        original = "# my standing notes\n"
        merged = rules.merge_block(original, "r", "B")
        assert rules.strip_block(merged, "r") == original


class TestRuleNameTraversal:
    """A tap controls its rule frontmatter, so `name` reaches rule_target as
    attacker input. Before the guard, `../../../../.ssh/authorized_keys`
    resolved clean outside the rules dir — and under project scope, into the
    victim's own repo."""

    EVIL = "../../../../.ssh/authorized_keys"

    def test_user_scope_refuses_traversal(self):
        with pytest.raises(BoostError, match="invalid rule name"):
            rules.rule_target("cursor", Path("/home/v/.cursor/skills"), self.EVIL)

    def test_project_scope_refuses_traversal(self):
        with pytest.raises(BoostError, match="invalid rule name"):
            rules.rule_target("cursor", Path("/x/.cursor/skills"), self.EVIL,
                              base=Path("/home/v/myrepo"))

    @pytest.mark.parametrize("name", ["..", ".", "a/b", "with space", ""])
    def test_refuses_other_non_components(self, name):
        with pytest.raises(BoostError):
            rules.rule_target("cursor", Path("/home/v/.cursor/skills"), name)

    def test_ordinary_name_still_lands_in_the_rules_dir(self):
        _mode, p = rules.rule_target("cursor", Path("/home/v/.cursor/skills"),
                                     "my_rule-1.2")
        assert p.parent.name == "rules"
        assert p.name.startswith("my_rule-1.2")
        # the guard must not have rewritten a legitimate name
        assert Path(p).resolve().is_relative_to(Path("/home/v/.cursor").resolve())

    def test_claude_md_path_is_guarded_too(self):
        # Claude takes the CLAUDE.md branch before any join, but the name still
        # reaches the managed-block markers, so it must be refused just as early.
        with pytest.raises(BoostError, match="invalid rule name"):
            rules.rule_target("claude-code", Path("/home/v/.claude/skills"), self.EVIL)

    @pytest.mark.parametrize("agent", ["claude-code", "gemini"])
    def test_every_context_file_agent_is_guarded(self, agent):
        # the guard must precede the CONTEXT_FILES lookup, not sit in the
        # rules-dir branch only — every agent takes it.
        with pytest.raises(BoostError, match="invalid rule name"):
            rules.rule_target(agent, Path("/home/v/.x/skills"), self.EVIL,
                              base=Path("/home/v/myrepo"))


class TestReadBlock:
    """The inverse of `merge_block` — the left-hand side an update diffs against."""

    def test_round_trips_what_merge_block_wrote(self):
        body = "# House style\n\nUse tabs."
        text = rules.merge_block("# notes\n", "house-style", body)
        assert rules.read_block(text, "house-style") == body

    def test_absent_block_is_none(self):
        text = rules.merge_block("", "one", "body")
        assert rules.read_block(text, "two") is None

    def test_a_start_marker_with_no_end_is_none(self):
        # Malformed, and `strip_block` already declines to guess here — reading
        # to end-of-file would hand the diff the rest of the user's CLAUDE.md.
        start, _end = rules.markers("x")
        assert rules.read_block(start + "\nbody\n", "x") is None

    def test_it_reads_only_its_own_block(self):
        text = rules.merge_block(rules.merge_block("", "a", "AAA"), "b", "BBB")
        assert rules.read_block(text, "a") == "AAA"
        assert rules.read_block(text, "b") == "BBB"

    def test_surrounding_user_content_is_not_returned(self):
        text = rules.merge_block("my own notes\n", "r", "managed")
        assert rules.read_block(text, "r") == "managed"
        assert "my own notes" not in (rules.read_block(text, "r") or "")
