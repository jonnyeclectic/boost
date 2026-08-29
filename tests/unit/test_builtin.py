# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/builtin.py — boost's own tap and rule.

`boost-first` is the most invasive thing boost ships: standing text in a file
the user reads every session, in every project. Two properties make that
defensible, and both are pinned here.

**It is an ordinary catalog item.** boost's product is asking users to accept
standing text from strangers under `boost install`, reversible with
`boost uninstall`. Its own standing text is the same kind of thing, in a real
tap, visible to the same commands — not a privileged block hidden from them.

**Its tap directory is never inside the wheel.** A `Tap` whose `path` pointed
at package data would sit one `boost untap` away from `registry.remove`, which
ends in `util.rmtree(tap.path)` and would delete part of the user's installed
package. That is the single defect this module is shaped to avoid, and
`test_the_tap_path_is_never_inside_the_wheel` is the test that would catch a
refactor reintroducing it.
"""
from __future__ import annotations

import pytest

from boost_cli.core import builtin, config, paths, registry


class TestTheTapNeverPointsIntoTheInstalledPackage:
    def test_the_tap_path_is_never_inside_the_wheel(self, sandbox):
        # The destructive shape this module exists to avoid: registry.remove()
        # rmtree's tap.path, so a path under the installed package would make
        # `boost untap boost/builtin` delete part of boost itself.
        tap = builtin.ensure_tap()
        assert builtin.source_dir() not in tap.path.parents
        assert tap.path != builtin.source_dir()
        assert tap.path.is_relative_to(paths.repos_dir())

    def test_the_source_dir_is_only_ever_read(self, sandbox):
        before = sorted(p.name for p in builtin.source_dir().iterdir())
        builtin.ensure_tap()
        assert sorted(p.name for p in builtin.source_dir().iterdir()) == before


class TestEnsureTapIsIdempotent:
    def test_calling_twice_registers_one_tap(self, sandbox):
        builtin.ensure_tap()
        builtin.ensure_tap()
        rows = [r for r in config.load().get("taps", [])
                if r.get("name") == builtin.BUILTIN_TAP]
        assert len(rows) == 1

    def test_the_rule_lands_on_disk_and_matches_the_wheel(self, sandbox):
        tap = builtin.ensure_tap()
        landed = tap.path / (builtin.BUILTIN_RULES[0] + ".mdc")
        shipped = builtin.source_dir() / (builtin.BUILTIN_RULES[0] + ".mdc")
        assert (landed.read_text(encoding="utf-8")
                == shipped.read_text(encoding="utf-8"))

    def test_a_hand_edited_copy_is_restored_from_the_wheel(self, sandbox):
        # The rule tracks boost's version rather than drifting once written:
        # its source of truth is the wheel, so there is nothing to fetch and
        # `boost update` re-copies instead of pulling. See
        # TestTheBuiltinTapRefreshesFromTheWheelRatherThanGit for the path
        # that makes that true of `boost update` and not just of this call.
        tap = builtin.ensure_tap()
        landed = tap.path / (builtin.BUILTIN_RULES[0] + ".mdc")
        landed.write_text("clobbered", encoding="utf-8")
        builtin.ensure_tap()
        assert landed.read_text(encoding="utf-8") != "clobbered"


class TestTheBuiltinTapRefreshesFromTheWheelRatherThanGit:
    """A revised rule has to be able to reach a machine that already has it.

    `ensure_tap()` has exactly one caller — the `boost mcp register` offer —
    and that offer never runs twice (`TestItNeverAsksTwice`). So once a user
    accepts, the copy under `~/.boost/repos/boost__builtin/` is written once
    and never again. `boost update` then reached for git against a directory
    that is not a clone, the tap landed in `failures`, and every downstream
    loop skipped it on `tapname not in results`.

    Measured end to end before this fix, on a sandbox HOME holding the older
    rule: wheel NEW, tap copy OLD, CLAUDE.md OLD, GEMINI.md OLD — after both
    `boost update` and `boost sync`. The rule was unreachable for the entire
    installed base, and `boost update` additionally reported "1 of 1 taps
    could not be refreshed" on every run, advising `boost untap` for a tap
    that was working exactly as designed.

    `_update_materialized` already hashes file content rather than consulting
    a git HEAD, so landing the tap in `results` is the whole fix; nothing
    below it needed to learn about the wheel.
    """

    def test_it_lands_in_results_rather_than_failures(self, sandbox):
        builtin.ensure_tap()
        results, failures = registry.update()
        assert builtin.BUILTIN_TAP in results
        assert builtin.BUILTIN_TAP not in failures

    def test_no_git_is_invoked_for_it(self, sandbox, monkeypatch):
        # `is_cloned` is false for a directory with no .git, so the old code
        # took the *clone* branch and handed git the `builtin:boost` sentinel
        # as a remote URL. Any git call here is that bug returning.
        from boost_cli.core import gitutil
        builtin.ensure_tap()

        def boom(*_a, **_k):
            raise AssertionError("git was invoked for the builtin tap")
        monkeypatch.setattr(gitutil, "clone_shallow", boom)
        monkeypatch.setattr(gitutil, "pull", boom)
        registry.update()

    def test_a_newer_wheel_reaches_the_on_disk_copy(self, sandbox, monkeypatch,
                                                   tmp_path):
        builtin.ensure_tap()
        landed = (registry.get(builtin.BUILTIN_TAP).path
                  / (builtin.BUILTIN_RULES[0] + ".mdc"))
        assert "REVISED" not in landed.read_text(encoding="utf-8")
        newer = tmp_path / "wheel-rules"
        newer.mkdir()
        (newer / (builtin.BUILTIN_RULES[0] + ".mdc")).write_text(
            "---\nname: boost-first\ndescription: d\n---\n\nREVISED\n",
            encoding="utf-8")
        monkeypatch.setattr(builtin, "source_dir", lambda: newer)
        registry.update()
        assert "REVISED" in landed.read_text(encoding="utf-8")

    def test_naming_the_builtin_tap_explicitly_works_too(self, sandbox):
        # `boost update boost/builtin` re-raises on failure rather than
        # collecting, so the git path made the named form a hard error.
        builtin.ensure_tap()
        results, failures = registry.update(builtin.BUILTIN_TAP)
        assert results and not failures

    def test_a_revised_rule_reaches_the_agent_context_file(
            self, sandbox, monkeypatch, tmp_path, capsys):
        """End to end, because every link in this chain was individually fine
        and the chain was still broken."""
        from boost_cli.commands import pkg
        from boost_cli.core import agents, catalog, rules, store
        builtin.ensure_tap()
        catalog.rebuild_tap(registry.get(builtin.BUILTIN_TAP))
        store.install(catalog.resolve_one(builtin.BUILTIN_RULES[0]))
        # Ask the same resolver the installer used rather than guessing the
        # layout: claude-code has no rules dir, so the rule merges into a
        # managed block in CLAUDE.md, which is not at the root of $HOME.
        ctx = rules.rule_target("claude-code",
                                agents.enabled_agents()["claude-code"],
                                builtin.BUILTIN_RULES[0])[1]
        assert ctx.is_file(), "the rule should have materialized on install"
        assert "REVISED" not in ctx.read_text(encoding="utf-8")

        newer = tmp_path / "wheel-rules"
        newer.mkdir()
        (newer / (builtin.BUILTIN_RULES[0] + ".mdc")).write_text(
            "---\nname: boost-first\ndescription: d\n---\n\nREVISED\n",
            encoding="utf-8")
        monkeypatch.setattr(builtin, "source_dir", lambda: newer)

        assert pkg.cmd_update([]) == 0
        assert "REVISED" in ctx.read_text(encoding="utf-8"), (
            "a rule fixed in the wheel has to reach the file the agent reads")

    def test_update_stops_reporting_a_failure_that_was_never_one(
            self, sandbox, capsys):
        # Every run printed "1 of 1 taps could not be refreshed" and pointed
        # at `boost untap` — for boost's own tap, behaving as designed.
        builtin.ensure_tap()
        from boost_cli.commands import pkg
        pkg.cmd_update([])
        out = capsys.readouterr().out
        assert "could not be refreshed" not in out
        assert "boost untap" not in out


class TestTheBuiltinTapDoesNotAnswerHasThisUserConfiguredAnything:
    """`tapped == 0` drives the one-command setup message. Guard it.

    `mcp.no_results` and `boost_doctor` both ask "has this user configured
    anything yet" by counting taps and print `boost tap --defaults` when the
    answer is zero. A machine holding nothing but `boost-first` has an
    effectively empty catalog — suppressing the setup message there would
    strand a new user with a search that can never match.
    """

    def test_a_machine_with_only_the_builtin_reads_as_unconfigured(self, sandbox):
        builtin.ensure_tap()
        assert registry.list_taps()                    # it IS a real tap
        assert builtin.configured_tap_count() == 0     # but not a user's

    def test_a_user_tap_counts(self, sandbox, monkeypatch):
        builtin.ensure_tap()
        monkeypatch.setattr(
            registry, "list_taps",
            lambda: [registry.Tap(name=builtin.BUILTIN_TAP, url="builtin:boost"),
                     registry.Tap(name="someone/theirs", url="https://x/y")])
        assert builtin.configured_tap_count() == 1

    def test_is_builtin_matches_only_the_builtin_name(self):
        assert builtin.is_builtin(builtin.BUILTIN_TAP)
        assert not builtin.is_builtin("anthropics/skills")
        assert not builtin.is_builtin("")


class TestThePackagingIsReal:
    """A missing package-data entry makes this dev-checkout-only.

    The feature would then be simply absent for every pip and pipx user —
    which is every real user — while passing the whole test suite in a git
    checkout. `rule_is_available` is what turns that into "no offer" rather
    than a traceback on the one command new users are told to run.
    """

    def test_the_rule_ships_in_the_package(self):
        assert builtin.rule_is_available()

    def test_package_data_declares_the_rules_glob(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        assert "data/rules/*.mdc" in text, (
            "package-data must ship the .mdc or the rule vanishes in the wheel")

    def test_the_rule_is_an_mdc_so_the_scanner_calls_it_a_rule(self):
        # catalog.RULE_SUFFIXES is {".mdc"} — a .md would be classified as a
        # workflow and materialize into commands/ instead of the context file.
        from boost_cli.core import catalog
        assert ".mdc" in catalog.RULE_SUFFIXES


class TestTheRuleBodyHoldsTheSameLineAsTheMcpSurface:
    """Same discipline as tests/unit/test_mcp.py — this text is shipped prose.

    It goes somewhere far more invasive than a tool description, so it is held
    to the same bar and then some: no order, no number boost cannot compute,
    and the skip list stays visible.
    """

    def _body(self):
        return (builtin.source_dir()
                / (builtin.BUILTIN_RULES[0] + ".mdc")).read_text(
                    encoding="utf-8")

    def test_it_does_not_order_the_agent(self):
        low = self._body().lower()
        for coercive in ("always call", "you must", "never skip",
                         "required before", "do not proceed", "is never enough"):
            assert coercive not in low, coercive

    def test_the_skip_list_is_visible(self):
        low = self._body().lower()
        assert "not for:" in low
        for skip in ("a question", "one-line edit", "just handed"):
            assert skip in low, skip

    def test_it_carries_the_defeater(self):
        # The whole reason this rule exists: an active skill answers a
        # different question. Without this clause it is just another trigger,
        # and the trigger already fired and lost.
        low = self._body().lower()
        assert "already loaded is a different question" in low
        assert "one kind of three" in low

    def test_it_says_the_task_stays_the_readers(self):
        assert "the task stays yours" in self._body().lower()

    def test_it_names_only_tools_that_exist(self):
        from boost_cli.commands import configuration
        names = {s["name"] for s in configuration.REGISTRY.specs()}
        body = self._body()
        for mentioned in ("boost_list", "boost_search"):
            assert mentioned in body and mentioned in names

    def test_it_quotes_no_number_boost_cannot_compute(self):
        # The catalog-size claim was cut from the MCP surface because
        # un-de-duplicated index entries are not distinct capabilities. The
        # same bar applies here, where the text is read every session.
        import re
        assert not re.search(r"\d[\d,]{3,}", self._body())


def _rule_body() -> str:
    """The shipped rule, whitespace-collapsed so phrase pins survive a reflow.

    The .mdc is hard-wrapped prose. Matching it raw makes every assertion here
    hostage to where a line happens to break — "touch more than one\\nfile" is
    the same sentence as "touch more than one file" and must not read as a
    missing trigger. The sibling pins in test_mcp.py match a single-string
    constant and never had this problem.
    """
    raw = (builtin.source_dir() / (builtin.BUILTIN_RULES[0] + ".mdc")).read_text(
        encoding="utf-8")
    return " ".join(raw.split()).lower()


class TestTheTriggerIsReadOffTheRequestRatherThanJudgedAboutTheWork:
    """The rule shipped the one trigger boost had already measured as losing.

    `core/mcp.py` carries the forensics: a Gemini CLI session paraphrased
    "a new project or subsystem, an architecture decision, environment and
    tooling config" back when asked, and had still skipped the call. #479
    answered that two ways — a defeater for the veto, and triggers that are
    properties of the REQUEST rather than a judgement about work not yet done,
    because "deciding a task is non-trivial takes judgement while 'this turn
    looks small' is free, and every turn looks small when it opens".

    This rule took the defeater and left the triggers behind, so it carried the
    losing half on its own. That matters more here than on any other surface:
    Gemini CLI never delivers server `instructions` in interactive mode and
    starts no MCP servers at all in an untrusted folder, so on the host where
    the failure was observed this file is the ONLY boost text in context — and
    it was the one surface with no observable trigger on it.
    """

    def test_it_carries_the_cheapest_trigger_of_all(self):
        # "does the task have a name you could say out loud" costs nothing to
        # evaluate and predates the observable pair. Both sibling surfaces
        # carry it; the rule did not.
        assert "has a name" in _rule_body()

    def test_it_names_both_request_readable_signals(self):
        low = _rule_body()
        assert "more than one file" in low
        assert "outlives this session" in low

    def test_it_reopens_when_a_small_task_turns_out_to_be_large(self):
        # The miss that prompted this change. A first check only ever fires at
        # a boundary recognised at the time, so a question that grew into an
        # investigation never got one — and never will, without this clause.
        assert "turns out to be a large one" in _rule_body()

    def test_the_lock_in_list_survives_ahead_of_the_defeater(self):
        # Additive, not a swap. The defeater is written to sit against that
        # list — "a skill already matched" was the veto over exactly it — and
        # test_mcp pins the same adjacency on the search description. A rewrite
        # that dropped the list would strand the defeater from what it defends.
        low = _rule_body()
        assert low.index("new project or subsystem") < low.index("one kind of three")

    def test_boost_list_is_not_given_a_threshold_it_does_not_need(self):
        # The two signals gate `boost_search`, which costs seconds. `boost_list`
        # is a local file read, and a threshold copied onto it is a threshold
        # invented — its own tool description says "call it whenever".
        assert "free" in _rule_body()


class TestTheRuleDoesNotDriftFromTheMcpSurface:
    """One shelf, three surfaces — and only this one survives a host that
    drops the other two.

    A phrase added to `INSTRUCTIONS` and not mirrored here is precisely how
    this rule came to ship a trigger its siblings had already retired. Pinning
    parity is the part of this change that outlives the wording.
    """

    PARITY = ("has a name", "more than one file", "outlives this session",
              "turns out to be a large one", "one kind of three",
              "the task stays yours")

    @pytest.mark.parametrize("phrase", PARITY)
    def test_a_load_bearing_phrase_sits_on_both_surfaces(self, phrase):
        from boost_cli.core import mcp
        assert phrase in mcp.INSTRUCTIONS.lower(), (
            "%r left the MCP instructions — retire it from the rule in the "
            "same change, or the two surfaces disagree" % phrase)
        assert phrase in _rule_body(), (
            "%r is in the MCP instructions but not in boost-first. That rule "
            "is the only surface a Gemini CLI session in an untrusted folder "
            "ever sees, so a trigger that lands only in `instructions` is "
            "absent on the host the trigger was written for." % phrase)


class TestASkippedCheckLeavesATrace:
    """The failure this change answers is not a refused check — it is one that
    was never visibly considered.

    Text that only says *when* to call something cannot distinguish a
    deliberate skip from an unnoticed one, and neither can the reader. Asking
    for one clause either way is the cheapest thing that makes the rule
    falsifiable in the transcript rather than only in hindsight.

    It stays a disclosure obligation, not an order to search: naming the reason
    you skipped is a complete answer, and the skip list below it stays exactly
    as wide as it was.
    """

    def test_it_asks_for_the_outcome_whichever_way_it_went(self):
        low = _rule_body()
        assert "skipped" in low
        # Both branches, or it is a standing order to search wearing a
        # reporting clause — the capture every boost surface avoids by design.
        assert "or the reason you skipped it" in low

    def test_the_bound_still_bounds_it(self):
        # Regression guard in the other direction: a disclosure clause that
        # quietly ate the skip list would widen the gate to "every turn".
        low = _rule_body()
        assert "not for:" in low
        for skip in ("a question", "one-line edit", "just handed"):
            assert skip in low, skip

    def test_asking_for_a_trace_did_not_make_the_text_coercive(self):
        # The same bar as the sibling surfaces, restated because this clause is
        # the one most likely to drift into an order.
        low = _rule_body()
        for coercive in ("always call", "you must", "never skip",
                         "required before", "do not proceed", "is never enough",
                         "must report", "always report"):
            assert coercive not in low, coercive
