# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: `boost_read` lets an agent look before it installs.

Before this tool the MCP surface had no route to an item's body. ``boost_info``
promised "the whole picture" and returned five fields, of which ``description``
was byte-identical to the one-liner ``boost_search`` had already returned — so
an agent deciding whether to adopt a procedure had one sentence written by
whoever published it, and its only way to read the actual steps was to install
into the user's real ``~/.agents/skills`` and read it off disk.

That is the failure these tests are about: **installing was the only way to
read**, which inverts the surface's own pitch. ``boost_search`` spends 10-15 s
of LLM rerank so the top result is worth acting on rather than skimming ten,
and then nothing let the agent look at it.

The body is also the only thing separating a written skill from a generated
stub, and the catalogue holds both — indexed, not reviewed. The eval gate
cannot catch that: ``golden.jsonl`` grades by *name*, and a stub matches its
own name perfectly.
"""
from __future__ import annotations

from boost_cli.core import mcp


class TestTheReplyCarriesTheBody:
    """The whole point: what comes back is the item's text, not its blurb."""

    def test_the_body_is_in_the_reply(self):
        text = mcp.read_reply("x", "# Title\n\nreal procedure here")
        assert "real procedure here" in text

    def test_the_header_names_the_item_and_its_install_state(self):
        # Both are decisions the body cannot answer: which of several items
        # sharing a bare name this is, and whether the next call is
        # boost_install or nothing at all.
        text = mcp.read_reply("brainstorming", "body", installed=True)
        assert text.startswith("name: brainstorming\n")
        assert "installed: yes" in text
        assert mcp.read_reply("b", "body", installed=False).count("installed: no") == 1

    def test_kind_is_marked_only_when_it_is_not_a_skill(self):
        # Same convention as hit_line: a marker on every line would spend a
        # token per reply to say "nothing unusual here".
        assert "kind:" not in mcp.read_reply("s", "body", kind="skill")
        assert "kind: rule" in mcp.read_reply("r", "body", kind="rule")
        assert "kind: workflow" in mcp.read_reply("w", "body", kind="workflow")

    def test_the_header_is_separated_from_the_body(self):
        # A header run into Markdown reads as part of the document.
        assert "\n\n" in mcp.read_reply("x", "body")


class TestTruncationIsAnnounced:
    """A silent cut is worse than no body at all.

    A body cut without saying so reads as a complete document that simply ends.
    For a *procedure* that is the dangerous case: the agent acts on the half it
    can see and never learns there was a second half.
    """

    def test_a_short_body_is_returned_whole_and_unmarked(self):
        text = mcp.read_reply("x", "short")
        assert "truncated" not in text
        assert text.endswith("short")

    def test_a_long_body_is_cut_and_says_so(self):
        body = "\n".join("line %d" % i for i in range(4000))
        assert len(body) > mcp.READ_LIMIT
        text = mcp.read_reply("x", body)
        assert "truncated" in text
        assert len(text) < len(body)

    def test_the_notice_names_the_command_that_returns_the_rest(self):
        # tool-design: an agent-facing reply carries its own recovery path.
        body = "z" * (mcp.READ_LIMIT + 500)
        assert "`boost cat x`" in mcp.read_reply("x", body)

    def test_the_notice_reports_both_the_cut_and_the_true_size(self):
        # Without the true size the agent cannot tell "a bit more" from
        # "forty times more", which is the whole decision it is making.
        body = "z" * (mcp.READ_LIMIT + 500)
        text = mcp.read_reply("x", body)
        assert str(len(body)) in text

    def test_it_cuts_on_a_line_boundary_when_there_is_one(self):
        # A Markdown body cut mid-fence or mid-sentence is text an agent must
        # guess about. A whole-line cut is unambiguously "this continues".
        body = "\n".join("line %d" % i for i in range(4000))
        text = mcp.read_reply("x", body)
        cut = text.split("\n\n[truncated")[0]
        # every line the reply kept is a line the body actually had
        kept = cut.split("\n\n", 1)[1]
        assert all(ln in body.splitlines() for ln in kept.splitlines())

    def test_a_body_with_no_line_break_still_gets_cut(self):
        # rpartition returns "" when there is no boundary — falling through to
        # the untruncated body would defeat the cap entirely on exactly the
        # input most likely to be enormous (a minified or single-line file).
        body = "z" * (mcp.READ_LIMIT * 3)
        text = mcp.read_reply("x", body)
        assert "truncated" in text
        assert len(text) < len(body)

    def test_the_limit_is_honoured_not_merely_approached(self):
        body = "\n".join("line %d" % i for i in range(4000))
        kept = mcp.read_reply("x", body).split("\n\n[truncated")[0]
        assert len(kept.split("\n\n", 1)[1]) <= mcp.READ_LIMIT

    def test_the_caller_can_override_the_limit(self):
        # Keyword-only with a default, so every call site renders as before.
        assert "truncated" in mcp.read_reply("x", "abcdef", limit=3)
        assert "truncated" not in mcp.read_reply("x", "abcdef", limit=100)

    def test_the_shipped_limit_is_the_measured_one(self):
        # Measured over 63,053 items in a real 467-tap install: 12,000 chars
        # delivers 80.3% whole (8,000 delivers 62.8%). The constant exists so
        # moving it is one edit; this pins that it was not moved by accident.
        assert mcp.READ_LIMIT == 12000


class TestTheHandlerReadsRatherThanInstalls:
    """This is the tool that exists so an agent does *not* have to install to
    look. It must never become a second install path."""

    def test_it_returns_the_resolved_text(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, info
        monkeypatch.setattr(info, "_resolve_text",
                            lambda name: ("# Real Body", "skill", None, None))
        text, is_err = configuration._tool_read({"name": "thing"})
        assert is_err is False
        assert "# Real Body" in text
        assert "installed: no" in text

    def test_an_installed_item_is_reported_as_installed(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, info
        monkeypatch.setattr(info, "_resolve_text",
                            lambda name: ("body", "rule", {"version": "1"}, None))
        text, _ = configuration._tool_read({"name": "thing"})
        assert "installed: yes" in text
        assert "kind: rule" in text

    def test_it_never_installs(self, sandbox, monkeypatch):
        from boost_cli.commands import configuration, info
        monkeypatch.setattr(info, "_resolve_text",
                            lambda name: ("body", "skill", None, None))

        def boom(*_a, **_k):
            raise AssertionError("boost_read installed something")

        monkeypatch.setattr(configuration.store, "install", boom)
        configuration._tool_read({"name": "thing"})

    def test_it_reuses_boost_cats_resolution(self, sandbox, monkeypatch):
        # A second resolver would be a second opinion about what "this item"
        # means — disagreeing with `boost cat`, the very command the truncation
        # notice tells the agent to run for the rest.
        from boost_cli.commands import configuration, info
        seen = {}

        def spy(name):
            seen["name"] = name
            return ("body", "skill", None, None)

        monkeypatch.setattr(info, "_resolve_text", spy)
        configuration._tool_read({"name": "owner/repo:thing"})
        assert seen["name"] == "owner/repo:thing"

    def test_an_empty_name_is_an_error_not_a_traceback(self, sandbox):
        from boost_cli.commands import configuration
        text, is_err = configuration._tool_read({})
        assert is_err is True
        assert "name" in text

    def test_a_blank_name_is_an_error_too(self, sandbox):
        # `.strip()` is the guard; a bare falsiness check would let "  " through
        # to the resolver and surface a BoostError for a caller mistake.
        from boost_cli.commands import configuration
        _text, is_err = configuration._tool_read({"name": "   "})
        assert is_err is True

    def test_a_missing_item_surfaces_as_an_error_result(self, sandbox):
        # BoostError from the resolver is turned into isError by the server,
        # never into a dead session — pinned here end to end.
        from boost_cli.commands import configuration
        resp = mcp.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "boost_read",
                        "arguments": {"name": "no-such-item-anywhere"}}},
            version="0", registry=configuration.REGISTRY)
        assert resp["result"]["isError"] is True


class TestTheToolIsOnTheSurface:
    """A handler that is not registered is a fix nobody can call."""

    def test_boost_read_is_registered(self):
        from boost_cli.commands import configuration
        assert "boost_read" in configuration.REGISTRY.names()

    def test_it_takes_a_name_the_way_the_other_tools_do(self):
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_read")
        assert spec["inputSchema"]["required"] == ["name"]

    def test_its_description_promises_the_body(self):
        # The tool declarations are the only boost text reliably in context at
        # the moment an agent chooses a tool (Gemini CLI files server
        # instructions into a memory tier, and never delivers them at all in
        # interactive mode), so the trigger has to live here.
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_read")
        d = spec["description"]
        assert "install" in d          # names the alternative it replaces
        assert "truncat" in d          # discloses the cap rather than hiding it

    def test_boost_info_no_longer_promises_the_whole_picture(self):
        # It returns five fields, one of which is the description boost_search
        # already gave. An overstated description costs a wasted call and
        # teaches an agent to discount the rest of the surface.
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_info")
        assert "whole picture" not in spec["description"]

    def test_boost_info_points_at_the_tool_that_has_the_body(self):
        from boost_cli.commands import configuration
        spec = next(s for s in configuration.REGISTRY.specs()
                    if s["name"] == "boost_info")
        assert "boost_read" in spec["description"]


class TestTheKindLabelIsTrueBeforeInstall:
    """`_resolve_text` reported every uninstalled item as a skill.

    Its contract says "content for a named item of any kind", and for an
    INSTALLED item the lock file answers correctly. For one that is only in a
    tap the lock file has no opinion at all, and the branch returned the
    literal `"skill"` — so an uninstalled rule or workflow was labelled a
    skill, which is precisely the case `boost_read` exists to serve.

    It was invisible until now because every earlier caller discarded the
    value (`_kind`): the resolution and the text were always right, only the
    label was wrong. `boost_read` is the first consumer, and the label decides
    whether the agent knows that installing this edits the file it reads every
    session — the difference `boost_install`'s own description calls "the more
    invasive change".
    """

    @staticmethod
    def _body_file(tmp_path, text="real body"):
        # A real file, because `info._read` calls `Path(p)` on what it is
        # handed — a stand-in object that only implements `read_text` passes
        # a type check that does not exist and fails at the one that does.
        p = tmp_path / "SKILL.md"
        p.write_text(text, encoding="utf-8")
        return p

    def _kind_of(self, tmp_path, monkeypatch, kind):
        from boost_cli.commands import info
        path = self._body_file(tmp_path)
        monkeypatch.setattr(info.lockfile, "find_any", lambda n: None)
        monkeypatch.setattr(
            info, "_resolve_skill_md",
            lambda n: (path, None, {"kind": kind, "tap": "t"}))
        return info._resolve_text("thing")[1]

    def test_an_uninstalled_rule_is_labelled_a_rule(self, sandbox, tmp_path,
                                                    monkeypatch):
        assert self._kind_of(tmp_path, monkeypatch, "rule") == "rule"

    def test_an_uninstalled_workflow_is_labelled_a_workflow(self, sandbox,
                                                            tmp_path,
                                                            monkeypatch):
        assert self._kind_of(tmp_path, monkeypatch, "workflow") == "workflow"

    def test_an_uninstalled_skill_is_still_a_skill(self, sandbox, tmp_path,
                                                   monkeypatch):
        assert self._kind_of(tmp_path, monkeypatch, "skill") == "skill"

    def test_an_entry_with_no_kind_falls_back_to_skill(self, sandbox, tmp_path,
                                                       monkeypatch):
        # Thin scanner output must never surface `None` to an agent — the same
        # rule `mcp.hit_line` follows.
        from boost_cli.commands import info
        path = self._body_file(tmp_path)
        monkeypatch.setattr(info.lockfile, "find_any", lambda n: None)
        monkeypatch.setattr(info, "_resolve_skill_md",
                            lambda n: (path, None, {"tap": "t"}))
        assert info._resolve_text("thing")[1] == "skill"

    def test_resolve_skill_md_always_returns_a_catalog_entry_when_lock_is_none(
            self, sandbox, tmp_path, monkeypatch):
        """The invariant this labelling relies on, pinned rather than guarded.

        `_resolve_skill_md` returns `(path, lock, None)` only from inside
        `if lock:`; every other path falls through to `catalog.resolve_one`.
        So `cat is None` implies `lock` is truthy, and a `cat is None` fallback
        guarded by `lock is None` can never run. An earlier draft of this fix
        carried one — unreachable code whose test reached it only by faking a
        return shape the real function cannot produce.

        This drives the REAL `_resolve_skill_md`, with the lock file empty
        (nothing installed) and the catalog answering — the exact branch the
        invariant is about.
        """
        import types

        from boost_cli.commands import info
        (tmp_path / "s").mkdir()
        (tmp_path / "s" / "SKILL.md").write_text("body", encoding="utf-8")
        entry = {"name": "x", "tap": "t", "skill_md": "s/SKILL.md",
                 "kind": "rule"}
        monkeypatch.setattr(info.lockfile, "get_skill", lambda n: None)
        monkeypatch.setattr(info.catalog, "resolve_one", lambda n: entry)
        monkeypatch.setattr(info.registry, "get",
                            lambda tap: types.SimpleNamespace(path=tmp_path))

        path, lock, cat = info._resolve_skill_md("x")
        assert lock is None
        assert cat is entry, "the catalog entry is missing on the lock-is-None branch"
        assert path.read_text(encoding="utf-8") == "body"
        # ...and the label that reads it therefore gets the true kind.
        assert info._resolve_text("x")[1] == "rule"

    def test_an_installed_items_kind_still_comes_from_the_lock(
            self, sandbox, tmp_path, monkeypatch):
        # The lock file stays the authority where it has one — this branch
        # must only fill the gap, never override it.
        from boost_cli.commands import info
        path = self._body_file(tmp_path)
        monkeypatch.setattr(info.lockfile, "find_any",
                            lambda n: ("skill", {"tap": "t"}))
        monkeypatch.setattr(
            info, "_resolve_skill_md",
            lambda n: (path, {"tap": "t"}, {"kind": "rule", "tap": "t"}))
        # Installed as a skill, catalog says rule: the lock wins.
        assert info._resolve_text("thing")[1] == "skill"
