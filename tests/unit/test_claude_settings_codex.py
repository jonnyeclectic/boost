# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: writing hooks for Codex CLI, the host whose file boost moves to.

Three things are Codex's alone on this path, and each is silent when wrong.
All were measured against **Codex CLI 0.156.1** (2026-09-27); the sources are
named in ``core/hookhost.py``.

* **The filename.** ``hooks.json``, not ``settings.json``. Codex never opens a
  ``settings.json``, so a hook written there is a file nothing reads.
* **The user-scope root moves.** ``$CODEX_HOME`` relocates it, and the
  measured resolution — including that a *relative* value is honoured against
  the current directory — lives once, in ``mcphost.config_home``. The
  **project** root does not move: it is the literal ``<project>/.codex``
  whatever ``CODEX_HOME`` says, the same asymmetry ``agents.project_dotdir``
  exists for.
* **Position is identity.** A Codex hook's trust key is
  ``<sourcePath>:<event>:<group_index>:<handler_index>``, so a re-add that
  removes a group and appends a new one re-keys every group after it and voids
  the user's trust grant on each. Measured: an untouched neighbour moved
  ``:0:0`` -> ``:1:0``. ``add_hook`` therefore replaces in place.
"""
from __future__ import annotations

import json

import pytest

from boost_cli.core import claude_settings as cs
from boost_cli.core import hookhost as hh
from boost_cli.errors import BoostError


class TestSettingsPath:
    def test_codex_user_scope_is_hooks_json_under_the_codex_home(self, sandbox):
        assert cs.settings_path("global", host=hh.CODEX) == \
            sandbox / ".codex" / "hooks.json"

    def test_codex_honours_an_absolute_codex_home(self, sandbox, monkeypatch,
                                                  tmp_path):
        elsewhere = tmp_path / "moved"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        assert cs.settings_path("global", host=hh.CODEX) == \
            elsewhere / "hooks.json"

    def test_the_project_root_does_not_move_with_codex_home(
            self, sandbox, monkeypatch, tmp_path):
        # The user dir is movable and the repo dir is not — writing the project
        # copy under a relocated home puts it where the CLI never looks.
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "moved"))
        proj = tmp_path / "repo"
        assert cs.settings_path("project", proj, host=hh.CODEX) == \
            proj / ".codex" / "hooks.json"

    def test_the_other_hosts_are_unmoved_by_codex_home(self, sandbox,
                                                       monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "moved"))
        assert cs.settings_path("global", host=hh.CLAUDE) == \
            sandbox / ".claude" / "settings.json"
        assert cs.settings_path("global", host=hh.GEMINI) == \
            sandbox / ".gemini" / "settings.json"

    def test_claudes_bytes_are_unchanged(self, sandbox):
        assert cs.settings_path("global") == sandbox / ".claude" / "settings.json"


class TestRoundTrip:
    def test_a_codex_hook_lands_in_hooks_json_in_claudes_shape(self, sandbox):
        cs.add_hook("global", "SessionStart", "brief", "boost bmad orient",
                    timeout=10, host=hh.CODEX)
        p = sandbox / ".codex" / "hooks.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        block, = data["hooks"]["SessionStart"]
        entry, = block["hooks"]
        assert entry["type"] == "command"
        assert entry["timeout"] == 10          # seconds, verbatim
        assert "# boost:brief" in entry["command"]
        assert "name" not in entry             # Gemini's field, not Codex's

    def test_a_codex_hook_is_found_and_removed_by_name(self, sandbox):
        cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX)
        assert cs.has_hook("global", "SessionStart", "brief", host=hh.CODEX)
        assert cs.remove_hook_by_name("global", "brief", host=hh.CODEX) == 1
        assert not cs.has_hook("global", "SessionStart", "brief", host=hh.CODEX)

    def test_a_codex_write_does_not_touch_claudes_file(self, sandbox):
        cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX)
        assert not (sandbox / ".claude" / "settings.json").exists()

    def test_list_reports_the_timeout_in_seconds(self, sandbox):
        cs.add_hook("global", "SessionStart", "brief", "x", timeout=7,
                    host=hh.CODEX)
        # Scope-explicit on purpose. A bare `list_hooks()` also reads the
        # *project* file, which for Codex is `<cwd>/.codex/hooks.json` — the
        # one path the `sandbox` fixture cannot move, since it hangs off the
        # working directory rather than `$HOME`. A stray hooks.json anywhere
        # a run happens to start from then joins the rows, and this assertion
        # fails on debris rather than on behaviour. (Measured: mutmut runs the
        # suite from `mutants/`, and something left one there.)
        rows = cs.list_hooks("global", host=hh.CODEX)
        row, = [r for r in rows if r["name"] == "brief"]
        assert row["timeout"] == 7

    def test_a_scoped_list_reads_only_that_scope(self, sandbox, tmp_path,
                                                 monkeypatch):
        """Naming a scope is what keeps the working directory out of it.

        Codex's project file is `<cwd>/.codex/hooks.json`, so an unscoped
        read answers with whatever the caller happens to be standing in as
        well as with `$CODEX_HOME`. Both answers are correct; they are not
        the same answer.
        """
        proj = tmp_path / "proj"
        proj.mkdir()
        monkeypatch.chdir(proj)
        cs.add_hook("project", "SessionStart", "brief", "p",
                    project_dir=proj, host=hh.CODEX)
        cs.add_hook("global", "SessionStart", "brief", "g", host=hh.CODEX)

        assert [r["scope"] for r in cs.list_hooks("global", host=hh.CODEX)] \
            == ["global"]
        assert sorted(r["scope"] for r in cs.list_hooks(host=hh.CODEX)) \
            == ["global", "project"]


class TestReAddKeepsItsPosition:
    """The trust key is positional, so a re-add must not move anything."""

    def _groups(self, sandbox):
        p = sandbox / ".codex" / "hooks.json"
        return json.loads(p.read_text(encoding="utf-8"))["hooks"]["SessionStart"]

    def test_a_re_add_replaces_in_place(self, sandbox):
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        # A hook boost does not own, added after ours: its trust key is
        # `…:session_start:1:0` and must still be that afterwards.
        p = sandbox / ".codex" / "hooks.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["hooks"]["SessionStart"].append(
            {"hooks": [{"type": "command", "command": "theirs"}]})
        p.write_text(json.dumps(data), encoding="utf-8")

        cs.add_hook("global", "SessionStart", "brief", "two", host=hh.CODEX)
        groups = self._groups(sandbox)
        assert len(groups) == 2
        assert "# boost:brief" in groups[0]["hooks"][0]["command"]
        assert groups[0]["hooks"][0]["command"].startswith("two")
        assert groups[1]["hooks"][0]["command"] == "theirs"

    def test_an_idempotent_re_add_rewrites_nothing(self, sandbox):
        """`boost bmad on` twice must leave the bytes — and so the hash — alone."""
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        p = sandbox / ".codex" / "hooks.json"
        before = p.read_text(encoding="utf-8")
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        assert p.read_text(encoding="utf-8") == before

    def test_a_first_add_still_appends(self, sandbox):
        p = sandbox / ".codex" / "hooks.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "theirs"}]}]}}),
            encoding="utf-8")
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        groups = self._groups(sandbox)
        assert groups[0]["hooks"][0]["command"] == "theirs"
        assert "# boost:brief" in groups[1]["hooks"][0]["command"]

    def test_a_shared_block_keeps_its_slot_and_ours_follows_it(self, sandbox):
        """The other half of the slot arithmetic: the block does *not* empty.

        When boost's entry shares a block with someone else's, that block
        survives the strip, so the vacated slot is the one *after* it — not
        the block's own index, which is still occupied.
        """
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        p = sandbox / ".codex" / "hooks.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        groups = data["hooks"]["SessionStart"]
        groups[0]["hooks"].append({"type": "command", "command": "shared"})
        groups.append({"hooks": [{"type": "command", "command": "after"}]})
        p.write_text(json.dumps(data), encoding="utf-8")

        cs.add_hook("global", "SessionStart", "brief", "two", host=hh.CODEX)
        groups = self._groups(sandbox)
        assert len(groups) == 3
        assert groups[0]["hooks"] == [{"type": "command", "command": "shared"}]
        assert groups[1]["hooks"][0]["command"].startswith("two")
        assert groups[2]["hooks"][0]["command"] == "after"

    def test_only_the_first_block_we_own_decides_the_slot(self, sandbox):
        """Two owned blocks collapse to one, in the earlier one's place."""
        cs.add_hook("global", "SessionStart", "brief", "one", host=hh.CODEX)
        p = sandbox / ".codex" / "hooks.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        groups = data["hooks"]["SessionStart"]
        mine = json.loads(json.dumps(groups[0]))
        groups.insert(0, {"hooks": [{"type": "command", "command": "first"}]})
        groups.append(mine)             # a duplicate of ours, further down
        p.write_text(json.dumps(data), encoding="utf-8")

        cs.add_hook("global", "SessionStart", "brief", "two", host=hh.CODEX)
        groups = self._groups(sandbox)
        assert len(groups) == 2
        assert groups[0]["hooks"][0]["command"] == "first"
        assert groups[1]["hooks"][0]["command"].startswith("two")

    def test_the_rule_holds_for_claude_too(self, sandbox):
        # Not Codex-specific behaviour bolted on: reordering a user's file for
        # no reason was never right, it was only never load-bearing before.
        cs.add_hook("global", "SessionStart", "brief", "one")
        p = sandbox / ".claude" / "settings.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["hooks"]["SessionStart"].append(
            {"hooks": [{"type": "command", "command": "theirs"}]})
        p.write_text(json.dumps(data), encoding="utf-8")
        cs.add_hook("global", "SessionStart", "brief", "two")
        groups = json.loads(p.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
        assert groups[1]["hooks"][0]["command"] == "theirs"


class TestTheWriteIsRefusedOutsideThisHome:
    """`$CODEX_HOME` is read from the ambient environment, like `mcp register`.

    boost resolves this path itself rather than shelling out, so the hole is
    the same one `tests/unit/test_mcp_install_sandbox_home.py` closes for
    ``mcp add``: a sandboxed ``HOME`` does not move ``CODEX_HOME``, so a test
    run — or a `boost bmad on` under a temp home — wrote into the developer's
    live `~/.codex`.
    """

    def test_a_codex_home_outside_this_home_is_refused(self, sandbox,
                                                       monkeypatch, tmp_path):
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        with pytest.raises(BoostError, match="outside this"):
            cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX)
        assert not (elsewhere / "hooks.json").exists()

    def test_the_refusal_names_the_file(self, sandbox, monkeypatch, tmp_path):
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        with pytest.raises(BoostError) as excinfo:
            cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX)
        assert str(elsewhere / "hooks.json") in str(excinfo.value)

    def test_removal_is_refused_too(self, sandbox, monkeypatch, tmp_path):
        # Otherwise `bmad off` reaches the file `bmad on` was stopped from
        # reaching, and a no-op read-modify-write still rewrites it.
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "real-codex"))
        with pytest.raises(BoostError, match="outside this"):
            cs.remove_hook("global", "SessionStart", "brief", host=hh.CODEX)

    def test_force_allows_it(self, sandbox, monkeypatch, tmp_path):
        # A genuinely relocated Codex must not be locked out.
        elsewhere = tmp_path / "real-codex"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX,
                    force=True)
        assert (elsewhere / "hooks.json").exists()

    def test_a_contained_codex_home_is_allowed(self, sandbox, monkeypatch):
        inside = sandbox / "elsewhere-but-mine"
        monkeypatch.setenv("CODEX_HOME", str(inside))
        cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CODEX)
        assert (inside / "hooks.json").exists()

    def test_project_scope_is_not_judged_by_this_guard(self, sandbox,
                                                       monkeypatch, tmp_path):
        """A project write is `<cwd>/.codex`, the one scope no `$HOME` contains.

        Judging it against the *user* path would vouch for a file nothing was
        going to write — the same reason `pkg._register_mcp_server` refuses a
        project scope rather than guessing.
        """
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "real-codex"))
        proj = tmp_path / "repo"
        cs.add_hook("project", "SessionStart", "brief", "x", project_dir=proj,
                    host=hh.CODEX)
        assert (proj / ".codex" / "hooks.json").exists()

    def test_the_variable_does_not_hold_back_the_other_hosts(
            self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "real-codex"))
        cs.add_hook("global", "SessionStart", "brief", "x", host=hh.CLAUDE)
        assert (sandbox / ".claude" / "settings.json").exists()


class TestTheEscapeGuardIsOnEveryWritePath:
    """One guard per public writer, not one guard shared by delegation.

    `remove_hook_by_name` delegates to `remove_hook` with `force=True` on
    purpose — it has already decided — so its own `refuse_escape` call is the
    *only* thing between `boost hooks remove` and a write outside `$HOME`.
    Deleting that line leaves every other test in this file passing, which is
    exactly the mutant these cover.
    """

    @pytest.fixture()
    def escaping(self, sandbox, monkeypatch, tmp_path):
        """A `$CODEX_HOME` outside the sandbox `$HOME`, holding a boost hook.

        Written with `force=True`, which is how a real one gets there: a
        pre-guard boost, a copied config, or a deliberate `--force`.
        """
        elsewhere = tmp_path / "outside"
        monkeypatch.setenv("CODEX_HOME", str(elsewhere))
        cs.add_hook("global", "SessionStart", "t", "echo hi", host=hh.CODEX,
                    force=True)
        assert (elsewhere / "hooks.json").is_file()
        return elsewhere

    def test_remove_by_name_refuses_with_no_event(self, escaping):
        # The branch the docstring argues for: `events` would be read off the
        # file, so delegating the refusal would read it before refusing.
        with pytest.raises(BoostError) as e:
            cs.remove_hook_by_name("global", "t", host=hh.CODEX)
        assert "outside this $HOME" in str(e.value)

    def test_remove_by_name_refuses_with_an_event(self, escaping):
        with pytest.raises(BoostError):
            cs.remove_hook_by_name("global", "t", "SessionStart", host=hh.CODEX)

    def test_remove_by_name_leaves_the_file_untouched(self, escaping):
        before = (escaping / "hooks.json").read_bytes()
        with pytest.raises(BoostError):
            cs.remove_hook_by_name("global", "t", host=hh.CODEX)
        assert (escaping / "hooks.json").read_bytes() == before

    def test_force_gets_through(self, escaping):
        assert cs.remove_hook_by_name("global", "t", host=hh.CODEX,
                                      force=True) == 1

    def test_remove_hook_refuses_too(self, escaping):
        with pytest.raises(BoostError):
            cs.remove_hook("global", "SessionStart", "t", host=hh.CODEX)

    def test_add_hook_refuses_too(self, escaping):
        with pytest.raises(BoostError):
            cs.add_hook("global", "SessionStart", "u", "echo", host=hh.CODEX)


class TestRefuseEscapeIsPublic:
    """`bmad` needs the refusal *before* it writes personas, so it is public.

    Rebuilding the message at the call site would be a second copy of the one
    sentence that has to name the right environment variable.
    """

    def test_it_is_a_no_op_for_a_contained_write(self, sandbox):
        assert cs.refuse_escape("global", hh.CODEX) is None

    def test_it_is_a_no_op_for_a_fixed_root_host(self, sandbox, monkeypatch,
                                                 tmp_path):
        # CODEX_HOME must not move Claude's or Gemini's file.
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "outside"))
        assert cs.refuse_escape("global", hh.CLAUDE) is None
        assert cs.refuse_escape("global", hh.GEMINI) is None

    def test_it_names_the_variable_that_moved_the_root(self, sandbox,
                                                       monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "outside"))
        with pytest.raises(BoostError) as e:
            cs.refuse_escape("global", hh.CODEX)
        assert "CODEX_HOME" in str(e.value.hint)

    def test_force_silences_it(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "outside"))
        assert cs.refuse_escape("global", hh.CODEX, force=True) is None

    def test_project_scope_is_never_an_escape(self, sandbox, monkeypatch,
                                              tmp_path):
        # `<project>/.codex` is the one root no `$HOME` contains, so judging
        # it here would refuse every project hook on every machine.
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "outside"))
        assert cs.refuse_escape("project", hh.CODEX) is None
