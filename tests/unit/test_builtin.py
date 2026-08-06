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
        # its source of truth is the wheel, and `boost update` cannot refresh
        # it because there is nothing to fetch.
        tap = builtin.ensure_tap()
        landed = tap.path / (builtin.BUILTIN_RULES[0] + ".mdc")
        landed.write_text("clobbered", encoding="utf-8")
        builtin.ensure_tap()
        assert landed.read_text(encoding="utf-8") != "clobbered"


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
