# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/mcpdecl.py — MCP-server declarations on a skill.

Every function is pure, so each branch, each tolerated-garbage path and each
constant literal is pinned here with assertions specific enough to kill mutants.
"""
from __future__ import annotations

import json

from boost_cli.core import frontmatter, mcpdecl


class TestConstants:
    def test_decl_key(self):
        assert mcpdecl.DECL_KEY == "mcp"

    def test_sidecar_filename(self):
        assert mcpdecl.SIDECAR == ".mcp.json"

    def test_servers_key_matches_the_mcp_convention(self):
        assert mcpdecl.SERVERS_KEY == "mcpServers"

    def test_marker_key(self):
        assert mcpdecl.MARKER_KEY == "x-boost-skill"


class TestDeclaredNames:
    def test_none_meta(self):
        assert mcpdecl.declared_names(None) == []

    def test_missing_key(self):
        assert mcpdecl.declared_names({"name": "x"}) == []

    def test_empty_string(self):
        assert mcpdecl.declared_names({"mcp": ""}) == []

    def test_none_value(self):
        assert mcpdecl.declared_names({"mcp": None}) == []

    def test_false_value(self):
        assert mcpdecl.declared_names({"mcp": False}) == []

    def test_comma_string_is_split_and_stripped(self):
        assert mcpdecl.declared_names(
            {"mcp": "github, playwright ,fetch"}) == ["github", "playwright", "fetch"]

    def test_comma_string_drops_blanks(self):
        assert mcpdecl.declared_names({"mcp": "a,,b,"}) == ["a", "b"]

    def test_yaml_list(self):
        assert mcpdecl.declared_names(
            {"mcp": ["github", "playwright"]}) == ["github", "playwright"]

    def test_list_items_are_stripped(self):
        assert mcpdecl.declared_names({"mcp": [" a ", "b"]}) == ["a", "b"]

    def test_list_drops_blanks(self):
        assert mcpdecl.declared_names({"mcp": ["a", "", "  "]}) == ["a"]

    def test_single_name(self):
        assert mcpdecl.declared_names({"mcp": "github"}) == ["github"]

    def test_order_is_preserved(self):
        # NOT sorted: the author's order is their statement of priority.
        assert mcpdecl.declared_names({"mcp": "zeta, alpha"}) == ["zeta", "alpha"]

    def test_duplicates_are_deduped_keeping_first(self):
        assert mcpdecl.declared_names({"mcp": "a, b, a"}) == ["a", "b"]

    def test_non_string_items_are_coerced(self):
        assert mcpdecl.declared_names({"mcp": [7]}) == ["7"]


class TestRealFrontmatterRoundTrip:
    """The declaration must survive boost's actual frontmatter parser.

    This is why the shape is flat. core/frontmatter.py is a stdlib YAML *subset*
    with no nested-mapping support, and it does not fail loudly on one — it
    hoists the inner keys to top level and clobbers their siblings. These tests
    pin both halves: the flat forms work, and the nested form is provably
    unusable, so nobody "simplifies" the design back into a nested block.
    """

    def _meta(self, body):
        return frontmatter.parse("---\n%s---\n\nbody\n" % body)[0]

    def test_comma_form_parses(self):
        meta = self._meta("name: demo\nmcp: github, playwright\n")
        assert mcpdecl.declared_names(meta) == ["github", "playwright"]

    def test_block_list_form_parses(self):
        meta = self._meta("name: demo\nmcp:\n  - github\n  - playwright\n")
        assert mcpdecl.declared_names(meta) == ["github", "playwright"]

    def test_flow_list_form_parses(self):
        meta = self._meta("name: demo\nmcp: [github, playwright]\n")
        assert mcpdecl.declared_names(meta) == ["github", "playwright"]

    def test_declaration_does_not_disturb_siblings(self):
        meta = self._meta("name: demo\nmcp: github\nrequires: [a]\n")
        assert meta["name"] == "demo"
        assert meta["requires"] == ["a"]

    def test_nested_mapping_is_corrupted_by_the_parser(self):
        # The exact failure the flat design exists to avoid: `mcp` comes back
        # empty and the inner keys land at top level.
        meta = self._meta("name: demo\nmcp:\n  servers:\n"
                          "    - name: github\n      command: npx\n")
        assert meta["mcp"] == ""
        assert "servers" in meta          # hoisted out of the mapping
        assert mcpdecl.declared_names(meta) == []


class TestParseSidecar:
    def test_none_text(self):
        assert mcpdecl.parse_sidecar(None) == {}

    def test_empty_text(self):
        assert mcpdecl.parse_sidecar("") == {}

    def test_malformed_json(self):
        assert mcpdecl.parse_sidecar("{not json") == {}

    def test_non_object_document(self):
        assert mcpdecl.parse_sidecar("[1, 2]") == {}
        assert mcpdecl.parse_sidecar('"a string"') == {}

    def test_missing_servers_key(self):
        assert mcpdecl.parse_sidecar('{"other": 1}') == {}

    def test_non_object_servers_key(self):
        assert mcpdecl.parse_sidecar('{"mcpServers": []}') == {}

    def test_well_formed(self):
        text = json.dumps({"mcpServers": {"github": {"command": "npx"}}})
        assert mcpdecl.parse_sidecar(text) == {"github": {"command": "npx"}}

    def test_non_object_individual_spec_is_dropped(self):
        text = json.dumps({"mcpServers": {"ok": {"command": "x"}, "bad": "nope"}})
        assert list(mcpdecl.parse_sidecar(text)) == ["ok"]

    def test_blank_server_name_is_dropped(self):
        text = json.dumps({"mcpServers": {"": {"command": "x"}}})
        assert mcpdecl.parse_sidecar(text) == {}


class TestServersFor:
    def test_nothing_declared(self):
        assert mcpdecl.servers_for({}, None) == []

    def test_frontmatter_only_has_no_spec(self):
        rows = mcpdecl.servers_for({"mcp": "github"}, None)
        assert rows == [{"name": "github", "spec": None,
                         "source": "frontmatter"}]

    def test_sidecar_only(self):
        text = json.dumps({"mcpServers": {"github": {"command": "npx"}}})
        rows = mcpdecl.servers_for({}, text)
        assert rows == [{"name": "github", "spec": {"command": "npx"},
                         "source": "sidecar"}]

    def test_sidecar_spec_wins_over_a_bare_name(self):
        # The frontmatter only names a server; a bundled spec is strictly more
        # information, so it must not be downgraded to spec=None.
        text = json.dumps({"mcpServers": {"github": {"command": "npx"}}})
        rows = mcpdecl.servers_for({"mcp": "github"}, text)
        assert len(rows) == 1
        assert rows[0]["source"] == "sidecar"
        assert rows[0]["spec"] == {"command": "npx"}

    def test_union_of_both_forms(self):
        text = json.dumps({"mcpServers": {"github": {"command": "npx"}}})
        rows = mcpdecl.servers_for({"mcp": "playwright"}, text)
        assert [r["name"] for r in rows] == ["github", "playwright"]

    def test_rows_are_sorted_by_name(self):
        rows = mcpdecl.servers_for({"mcp": "zeta, alpha"}, None)
        assert [r["name"] for r in rows] == ["alpha", "zeta"]

    def test_sidecar_defaults_to_none(self):
        assert mcpdecl.servers_for({"mcp": "a"}) == [
            {"name": "a", "spec": None, "source": "frontmatter"}]


class TestRegistrable:
    def _row(self, name, spec):
        return {"name": name, "spec": spec, "source": "sidecar"}

    def test_spec_with_command_is_registrable(self):
        rows = [self._row("a", {"command": "npx"})]
        assert mcpdecl.registrable(rows) == rows

    def test_name_only_is_not_registrable(self):
        # boost will not invent a command line on an author's behalf.
        assert mcpdecl.registrable([self._row("a", None)]) == []

    def test_spec_without_command_is_not_registrable(self):
        assert mcpdecl.registrable([self._row("a", {"url": "http://x"})]) == []

    def test_blank_command_is_not_registrable(self):
        assert mcpdecl.registrable([self._row("a", {"command": "   "})]) == []

    def test_non_dict_spec_is_not_registrable(self):
        assert mcpdecl.registrable([self._row("a", "npx")]) == []

    def test_filters_a_mixed_list(self):
        rows = [self._row("a", {"command": "npx"}), self._row("b", None)]
        assert [r["name"] for r in mcpdecl.registrable(rows)] == ["a"]


class TestRegisterArgv:
    def test_minimal(self):
        assert mcpdecl.register_argv("gh", {"command": "npx"}) == [
            "claude", "mcp", "add", "gh", "--scope", "user", "--", "npx"]

    def test_args_follow_the_command(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx", "args": ["-y", "pkg"]})
        assert argv[-3:] == ["npx", "-y", "pkg"]

    def test_name_precedes_every_env_flag(self):
        # cmd_mcp's pinned invariant: `claude`'s -e is variadic, so a name after
        # it is swallowed as another env var ("Invalid environment variable
        # format: gh"). Order must be `add <name> [options] -- <command>`.
        argv = mcpdecl.register_argv("gh", {"command": "npx", "env": {"K": "v"}})
        assert argv.index("gh") < argv.index("-e")

    def test_env_is_sorted_for_determinism(self):
        argv = mcpdecl.register_argv(
            "gh", {"command": "npx", "env": {"B": "2", "A": "1"}})
        assert argv[argv.index("--scope") + 2:argv.index("--")] == [
            "-e", "A=1", "-e", "B=2"]

    def test_double_dash_separates_flags_from_the_command(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx", "env": {"K": "v"}})
        assert argv[argv.index("--") + 1] == "npx"

    def test_non_dict_env_is_ignored(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx", "env": "K=v"})
        assert "-e" not in argv

    def test_non_list_args_is_ignored(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx", "args": "-y"})
        assert argv[-1] == "npx"

    def test_args_are_stringified(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx", "args": [3]})
        assert argv[-1] == "3"

    def test_scope_is_overridable(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx"}, scope="project")
        assert argv[argv.index("--scope") + 1] == "project"

    def test_scope_defaults_to_user(self):
        argv = mcpdecl.register_argv("gh", {"command": "npx"})
        assert argv[argv.index("--scope") + 1] == "user"


class TestMergeInto:
    def _rows(self, *names):
        return [{"name": n, "spec": {"command": "npx"}, "source": "sidecar"}
                for n in names]

    def test_into_nothing(self):
        doc, added = mcpdecl.merge_into(None, self._rows("gh"), "sk")
        assert added == ["gh"]
        assert doc["mcpServers"]["gh"]["command"] == "npx"

    def test_marks_ownership_with_the_skill_name(self):
        doc, _ = mcpdecl.merge_into({}, self._rows("gh"), "my-skill")
        assert doc["mcpServers"]["gh"][mcpdecl.MARKER_KEY] == "my-skill"

    def test_never_overwrites_an_existing_server(self):
        existing = {"mcpServers": {"gh": {"command": "mine"}}}
        doc, added = mcpdecl.merge_into(existing, self._rows("gh"), "sk")
        assert added == []
        assert doc["mcpServers"]["gh"] == {"command": "mine"}   # untouched

    def test_adds_alongside_an_unrelated_existing_server(self):
        existing = {"mcpServers": {"other": {"command": "x"}}}
        doc, added = mcpdecl.merge_into(existing, self._rows("gh"), "sk")
        assert added == ["gh"]
        assert set(doc["mcpServers"]) == {"other", "gh"}

    def test_does_not_mutate_the_input(self):
        existing = {"mcpServers": {}}
        mcpdecl.merge_into(existing, self._rows("gh"), "sk")
        assert existing == {"mcpServers": {}}

    def test_unregistrable_rows_are_skipped(self):
        rows = [{"name": "gh", "spec": None, "source": "frontmatter"}]
        doc, added = mcpdecl.merge_into({}, rows, "sk")
        assert added == []
        assert doc["mcpServers"] == {}

    def test_preserves_other_top_level_keys(self):
        doc, _ = mcpdecl.merge_into({"keepMe": 1}, self._rows("gh"), "sk")
        assert doc["keepMe"] == 1

    def test_non_dict_existing_reads_as_empty(self):
        _doc, added = mcpdecl.merge_into("garbage", self._rows("gh"), "sk")
        assert added == ["gh"]


class TestStripOwned:
    def test_removes_only_this_skills_entries(self):
        existing = {"mcpServers": {
            "mine": {"command": "x", mcpdecl.MARKER_KEY: "sk"},
            "theirs": {"command": "y", mcpdecl.MARKER_KEY: "other-skill"},
        }}
        doc, removed = mcpdecl.strip_owned(existing, "sk")
        assert removed == ["mine"]
        assert list(doc["mcpServers"]) == ["theirs"]

    def test_leaves_an_unmarked_user_server_alone(self):
        existing = {"mcpServers": {"hand-rolled": {"command": "x"}}}
        doc, removed = mcpdecl.strip_owned(existing, "sk")
        assert removed == []
        assert list(doc["mcpServers"]) == ["hand-rolled"]

    def test_nothing_to_remove(self):
        doc, removed = mcpdecl.strip_owned({"mcpServers": {}}, "sk")
        assert removed == []
        assert doc["mcpServers"] == {}

    def test_none_existing(self):
        doc, removed = mcpdecl.strip_owned(None, "sk")
        assert removed == []
        assert doc["mcpServers"] == {}

    def test_non_dict_spec_is_not_removed(self):
        existing = {"mcpServers": {"weird": "not-a-dict"}}
        doc, removed = mcpdecl.strip_owned(existing, "sk")
        assert removed == []
        assert list(doc["mcpServers"]) == ["weird"]

    def test_removed_is_sorted(self):
        existing = {"mcpServers": {
            "z": {"command": "x", mcpdecl.MARKER_KEY: "sk"},
            "a": {"command": "x", mcpdecl.MARKER_KEY: "sk"},
        }}
        _doc, removed = mcpdecl.strip_owned(existing, "sk")
        assert removed == ["a", "z"]

    def test_does_not_mutate_the_input(self):
        existing = {"mcpServers": {"mine": {"command": "x",
                                            mcpdecl.MARKER_KEY: "sk"}}}
        mcpdecl.strip_owned(existing, "sk")
        assert "mine" in existing["mcpServers"]

    def test_round_trip_merge_then_strip_is_empty(self):
        rows = [{"name": "gh", "spec": {"command": "npx"}, "source": "sidecar"}]
        doc, _ = mcpdecl.merge_into({}, rows, "sk")
        doc, removed = mcpdecl.strip_owned(doc, "sk")
        assert removed == ["gh"]
        assert doc["mcpServers"] == {}
