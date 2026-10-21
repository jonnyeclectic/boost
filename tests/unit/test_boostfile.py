# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""``core.boostfile`` — the Boostfile line grammar, parsed and rendered.

Exact values throughout: the grammar is a reproducibility contract, so a
parse that drops one option or a render that reorders one is the bug.
"""
from __future__ import annotations

import pytest

from boost_cli.core import boostfile
from boost_cli.errors import BoostError

SHA = "0123456789abcdef0123456789abcdef01234567"


class TestParseTap:
    @pytest.mark.parametrize("rest, want", [
        ("", ("", "")),
        ("  https://x/y  ", ("https://x/y", "")),
        ("/a path/with spaces", ("/a path/with spaces", "")),
        ("https://x/y --at %s" % SHA, ("https://x/y", SHA)),
        ("/a path/with spaces --at %s" % SHA, ("/a path/with spaces", SHA)),
        ("--at %s" % SHA, ("", SHA)),
        ("/p\t--at\t%s" % SHA, ("/p", SHA)),
    ])
    def test_url_and_pin(self, rest, want):
        assert boostfile.parse_tap(rest) == want

    def test_at_without_a_value(self):
        with pytest.raises(BoostError) as e:
            boostfile.parse_tap("https://x/y --at")
        assert e.value.message == "--at needs a commit SHA"

    def test_a_short_sha_is_refused(self):
        with pytest.raises(BoostError) as e:
            boostfile.parse_tap("https://x/y --at abc1234")
        assert e.value.message == ("--at needs a full 40-character commit "
                                   "SHA, got 'abc1234'")


class TestParseSkill:
    def test_a_bare_line(self):
        assert boostfile.parse_skill("t:n@1.0") == boostfile.SkillLine(
            tap="t", name="n", version="1.0")

    def test_owner_repo_and_no_version(self):
        line = boostfile.parse_skill("o/r:name")
        assert (line.tap, line.name, line.version) == ("o/r", "name", "")

    def test_unqualified(self):
        line = boostfile.parse_skill("name@2")
        assert (line.tap, line.name, line.version) == ("", "name", "2")

    def test_every_option(self):
        line = boostfile.parse_skill(
            "t:n@1", "--agent cursor --agent=claude-code --agent cursor --pin "
                     "--commit-pin %s --tag b --tag=#a" % SHA)
        assert line == boostfile.SkillLine(
            tap="t", name="n", version="1", local=False,
            agents=["cursor", "claude-code"], pin=True, commit_pin=SHA,
            tags=["a", "b"])

    def test_local_and_pin(self):
        line = boostfile.parse_skill("t:n", "--local --pin")
        assert (line.local, line.pin, line.agents) == (True, True, [])

    @pytest.mark.parametrize("spec, rest, message", [
        ("t:", "", "no skill name in 't:'"),
        ("t:@1", "", "no skill name in 't:@1'"),
        ("", "", "no skill name in ''"),
        ("t:n", "--locl", "unknown option '--locl'"),
        ("t:n", "-x", "unknown option '-x'"),
        ("t:n", "--local=yes", "unknown option '--local=yes'"),
        ("t:n", "stray", "unexpected 'stray'"),
        ("t:n", "--agent", "--agent needs a value"),
        ("t:n", "--agent=", "--agent needs a value"),
        ("t:n", "--tag", "--tag needs a value"),
        ("t:n", "--tag ##", "empty tag in '+##'"),
        ("t:n", "--commit-pin", "--commit-pin needs a value"),
        ("t:n", "--commit-pin abc",
         "--commit-pin needs a full 40-character commit SHA, got 'abc'"),
        ("t:n", "--local --tag x",
         "--tag applies to user-scope skills, not a --local one"),
        ("t:n", "--commit-pin %s --local" % SHA,
         "--commit-pin applies to user-scope skills, not a --local one"),
    ])
    def test_errors_name_the_token(self, spec, rest, message):
        with pytest.raises(BoostError) as e:
            boostfile.parse_skill(spec, rest)
        assert e.value.message == message


class TestRender:
    def test_tap_without_and_with_pin(self):
        assert boostfile.render_tap("t", "/p") == "tap t /p"
        assert boostfile.render_tap("t", "") == "tap t"
        assert boostfile.render_tap("t", "/p", SHA) == "tap t /p --at %s" % SHA

    def test_a_plain_skill(self):
        assert boostfile.render_skill({"tap": "t", "version": "1.0"}, "n") \
            == "skill t:n@1.0"
        assert boostfile.render_skill({"tap": "t"}, "n") == "skill t:n@0.0.0"

    def test_every_field_in_a_fixed_order(self):
        entry = {"tap": "t", "version": "1", "only_agents": ["cursor", "x"],
                 "pinned": True, "commit_pin": SHA, "tags": ["b", "a"]}
        assert boostfile.render_skill(entry, "n") == (
            "skill t:n@1 --agent cursor --agent x --pin --commit-pin %s "
            "--tag a --tag b" % SHA)

    def test_project_scope_carries_no_user_lock_fields(self):
        entry = {"tap": "t", "version": "1", "only_agents": ["cursor"],
                 "pinned": True, "commit_pin": SHA, "tags": ["a"]}
        assert boostfile.render_skill(entry, "n", local=True) == (
            "skill t:n@1 --local --agent cursor --pin")

    def test_unset_fields_write_nothing(self):
        entry = {"tap": "t", "version": "1", "only_agents": None,
                 "pinned": False, "commit_pin": "", "tags": []}
        assert boostfile.render_skill(entry, "n") == "skill t:n@1"

    @pytest.mark.parametrize("entry, local", [
        ({"tap": "t", "version": "1"}, False),
        ({"tap": "o/r", "version": "2.0", "only_agents": ["cursor"],
          "pinned": True, "commit_pin": SHA, "tags": ["a", "b"]}, False),
        ({"tap": "t", "version": "1", "only_agents": ["a", "b"],
          "pinned": True}, True),
    ])
    def test_render_then_parse_round_trips(self, entry, local):
        text = boostfile.render_skill(entry, "n", local=local)
        spec, _, rest = text.partition(" ")[2].partition(" ")
        line = boostfile.parse_skill(spec, rest)
        assert line == boostfile.SkillLine(
            tap=entry["tap"], name="n", version=entry["version"], local=local,
            agents=entry.get("only_agents") or [], pin=bool(entry.get("pinned")),
            commit_pin="" if local else entry.get("commit_pin", ""),
            tags=[] if local else entry.get("tags", []))


def test_the_grammar_constant_names_every_option():
    for opt in ("--at", "--local", "--agent", "--pin", "--commit-pin", "--tag"):
        assert opt in boostfile.GRAMMAR
