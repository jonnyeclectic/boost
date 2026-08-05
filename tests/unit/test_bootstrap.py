"""Unit tests: boost_cli/core/bootstrap.py — the one-command setup seam.

`boost mcp` is the only command a new user is told to run. Before this module
it registered the server against an empty catalog, so the first thing any agent
asked came back "no skills match" — indistinguishable from a real miss, and the
fastest possible way to teach an agent that boost is not worth asking.

These tests pin the three properties that make seeding safe to do on that path:
it is idempotent (a machine with taps is left alone), it never raises (a failed
clone must not take the MCP registration down with it), and it reports what it
did in terms the caller can print.
"""
from __future__ import annotations

from boost_cli.core import bootstrap


class _FakeTap:
    def __init__(self, name):
        self.name = name


class _Added(list):
    """The names that were really added, plus the journal calls made.

    A list subclass so every ``added == [...]`` assertion below still reads
    like one, while the journal record rides along for the tests that check
    boost recorded the tap it just made.
    """

    def __init__(self):
        super().__init__()
        self.logged: list = []


def _stub(monkeypatch, *, existing=(), fail=(), oserror=(), counts=None):
    """Point bootstrap at fakes: no network, no disk, deterministic counts.

    Clearing BOOST_NO_SEED is the explicit opt-in the conftest asks for: the
    sandbox fixture sets it so no test clones seven repositories by accident,
    and a test whose whole subject IS the seed says so here. The fakes above
    are what make that safe — nothing below reaches the network either way.
    """
    from boost_cli.core import catalog, journal, registry
    monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
    added = _Added()

    def fake_add(url, curated=None, **kw):
        name = url.split("github.com/")[-1]
        # Every default is a curated registry; dropping the flag would
        # silently demote all seven in `boost taps` listings.
        assert curated is True, "seeded taps must be marked curated"
        if name in fail:
            from boost_cli.errors import BoostError
            raise BoostError("clone failed: %s" % name)
        if name in oserror:
            raise OSError("disk full: %s" % name)
        added.append(name)
        return _FakeTap(name)

    monkeypatch.setattr(registry, "list_taps",
                        lambda: [_FakeTap(n) for n in existing])
    monkeypatch.setattr(registry, "add", fake_add)
    monkeypatch.setattr(catalog, "rebuild_tap",
                        lambda tap: [{}] * (counts or {}).get(tap.name, 3))
    monkeypatch.setattr(journal, "log",
                        lambda *a, **kw: added.logged.append(tuple(a)))
    return added


class TestSeedIsIdempotent:
    def test_a_machine_with_taps_is_left_alone(self, sandbox, monkeypatch):
        # The whole point of seeding at register time is the EMPTY machine.
        # Re-tapping someone's configured machine because they re-ran
        # `boost mcp` would be boost editing state it was not asked to touch.
        added = _stub(monkeypatch, existing=("someone/their-tap",))
        res = bootstrap.seed_catalog()
        assert res.skipped is True
        assert res.tapped == []
        assert added == []

    def test_an_empty_machine_taps_every_default(self, sandbox, monkeypatch):
        from boost_cli.core import config
        added = _stub(monkeypatch)
        res = bootstrap.seed_catalog()
        assert res.skipped is False
        assert added == [t["name"] for t in config.DEFAULT_TAPS]
        assert [n for n, _count in res.tapped] == added

    def test_force_seeds_even_when_taps_exist(self, sandbox, monkeypatch):
        # `boost mcp --seed` is the repair path for a machine that tapped
        # something once and lost it; without force there would be no way to
        # ask for the defaults back except by name.
        added = _stub(monkeypatch, existing=("someone/their-tap",))
        res = bootstrap.seed_catalog(force=True)
        assert res.skipped is False
        assert added


class TestSeedNeverTakesTheCallerDown:
    def test_a_failed_tap_is_collected_not_raised(self, sandbox, monkeypatch):
        # Registration must survive a dead network. A user who ran one command
        # gets a working MCP server plus a line saying what could not be
        # fetched — never a traceback where the server should have been.
        from boost_cli.core import config
        first = config.DEFAULT_TAPS[0]["name"]
        added = _stub(monkeypatch, fail=(first,))
        res = bootstrap.seed_catalog()
        assert first not in added                      # it really did fail
        assert any(first in msg for msg in res.failed)
        assert res.tapped                              # the rest still landed

    def test_every_tap_failing_is_still_not_an_exception(self, sandbox,
                                                         monkeypatch):
        from boost_cli.core import config
        _stub(monkeypatch, fail=tuple(t["name"] for t in config.DEFAULT_TAPS))
        res = bootstrap.seed_catalog()
        assert res.tapped == []
        assert len(res.failed) == len(config.DEFAULT_TAPS)
        assert res.skipped is False


class TestSeedReportsWhatItDid:
    def test_summary_counts_items_not_just_repos(self, sandbox, monkeypatch):
        from boost_cli.core import config
        names = [t["name"] for t in config.DEFAULT_TAPS]
        _stub(monkeypatch, counts=dict.fromkeys(names, 7))
        res = bootstrap.seed_catalog()
        assert res.item_count == 7 * len(names)
        assert "%d" % res.item_count in res.summary()

    def test_summary_of_a_skipped_seed_says_so(self, sandbox, monkeypatch):
        _stub(monkeypatch, existing=("someone/their-tap",))
        res = bootstrap.seed_catalog()
        assert "already" in res.summary().lower()


class TestSeedRespectsTheEscapeHatch:
    """`boost mcp` must be able to stay a local, offline operation.

    Seeding turns one command into seven network clones. That is right for a
    new user and wrong for a CI image, an air-gapped machine, or a test run —
    so the same escape-hatch shape `BOOST_NO_MCP_OFFER` already uses applies
    here, with an explicit flag outranking it.
    """

    def test_the_env_var_suppresses_the_implicit_seed(self, sandbox,
                                                      monkeypatch):
        added = _stub(monkeypatch)
        monkeypatch.setenv(bootstrap.NO_SEED_ENV, "1")
        res = bootstrap.seed_catalog()
        assert res.skipped is True
        assert added == []

    def test_an_explicit_force_outranks_the_env_var(self, sandbox, monkeypatch):
        # A flag the user typed beats an environment default they may not
        # know is set — otherwise `boost mcp --seed` silently does nothing
        # and there is no way to find out why.
        added = _stub(monkeypatch)
        monkeypatch.setenv(bootstrap.NO_SEED_ENV, "1")
        res = bootstrap.seed_catalog(force=True)
        assert res.skipped is False
        assert added


class TestSeedDecidesPerRegistryNotPerMachine:
    """The gate used to be "does ANY tap exist", and that was wrong twice.

    An interrupted seed left a machine with two of seven registries that read
    as fully configured forever. And `--seed`, the documented repair path,
    called registry.add on registries already present — add rejects those
    before it touches the network, so the repair reported seven failures and
    told the user their connection was down while it was up.
    """

    def test_force_tops_up_only_what_is_missing(self, sandbox, monkeypatch):
        from boost_cli.core import config
        names = [str(t["name"]) for t in config.DEFAULT_TAPS]
        added = _stub(monkeypatch, existing=tuple(names[:2]))
        res = bootstrap.seed_catalog(force=True)
        assert added == names[2:]              # the two present are untouched
        assert res.already == names[:2]
        assert res.failed == []                # and NOT reported as failures

    def test_force_on_a_complete_machine_is_a_skip_not_a_failure(
            self, sandbox, monkeypatch):
        from boost_cli.core import config
        added = _stub(monkeypatch,
                      existing=tuple(str(t["name"]) for t in config.DEFAULT_TAPS))
        res = bootstrap.seed_catalog(force=True)
        assert added == []
        assert res.skipped is True
        assert res.failed == []
        assert "already" in res.summary().lower()
        # The bug this pins: blaming the network on a machine whose network
        # is fine, because "already configured" was collected as a failure.
        assert "network" not in res.summary().lower()

    def test_the_summary_names_what_was_already_there(self, sandbox,
                                                     monkeypatch):
        from boost_cli.core import config
        names = [str(t["name"]) for t in config.DEFAULT_TAPS]
        _stub(monkeypatch, existing=(names[0],))
        res = bootstrap.seed_catalog(force=True)
        assert "1 already tapped" in res.summary()

    def test_will_seed_agrees_with_what_seed_catalog_does(self, sandbox,
                                                          monkeypatch):
        # will_seed exists so the caller can announce the wait before it
        # starts; a will_seed that disagrees with seed_catalog would print
        # "adding the recommended ones" and then add nothing.
        from boost_cli.core import config
        names = [str(t["name"]) for t in config.DEFAULT_TAPS]
        for existing, force, expected in (
                ((), False, True),                  # empty machine
                (("someone/theirs",), False, False),  # configured, implicit
                (("someone/theirs",), True, True),   # configured, forced
                (tuple(names), True, False),         # complete, forced
        ):
            _stub(monkeypatch, existing=existing)
            assert bootstrap.will_seed(force=force) is expected, (
                "will_seed(force=%r) with existing=%r" % (force, existing))
            res = bootstrap.seed_catalog(force=force)
            assert bool(res.tapped) is expected

    def test_will_seed_honors_the_opt_out(self, sandbox, monkeypatch):
        _stub(monkeypatch)
        monkeypatch.setenv(bootstrap.NO_SEED_ENV, "1")
        assert bootstrap.will_seed() is False
        assert bootstrap.will_seed(force=True) is True


class TestSeedRecordsAndReportsFaithfully:
    def test_each_added_tap_is_journalled(self, sandbox, monkeypatch):
        # The journal is how `boost history` explains where a tap came from;
        # a seed that adds seven registries silently leaves the user unable
        # to tell later which command did it.
        from boost_cli.core import config
        added = _stub(monkeypatch)
        bootstrap.seed_catalog()
        assert added.logged == [("tap", n) for n in
                                [str(t["name"]) for t in config.DEFAULT_TAPS]]

    def test_a_disk_error_is_collected_like_a_clone_failure(self, sandbox,
                                                            monkeypatch):
        # registry.add can fail below BoostError — a full disk, a read-only
        # home. Same contract: reported, loop continues, caller survives.
        from boost_cli.core import config
        first = str(config.DEFAULT_TAPS[0]["name"])
        added = _stub(monkeypatch, oserror=(first,))
        res = bootstrap.seed_catalog()
        assert first not in added
        assert res.failed and res.failed[0].startswith(first + ": ")
        assert "disk full" in res.failed[0]
        assert res.tapped                       # the rest still landed

    def test_the_failed_line_names_the_registry_then_the_reason(
            self, sandbox, monkeypatch):
        from boost_cli.core import config
        first = str(config.DEFAULT_TAPS[0]["name"])
        _stub(monkeypatch, fail=(first,))
        res = bootstrap.seed_catalog()
        assert res.failed[0] == "%s: clone failed: %s" % (first, first)

    def test_a_partial_failure_summary_counts_both_sides(self, sandbox,
                                                          monkeypatch):
        from boost_cli.core import config
        names = [str(t["name"]) for t in config.DEFAULT_TAPS]
        _stub(monkeypatch, fail=(names[0], names[1]))
        res = bootstrap.seed_catalog()
        summary = res.summary()
        assert "tapped %d registries" % (len(names) - 2) in summary
        assert "2 could not be fetched" in summary

    def test_a_total_failure_blames_the_network_only_when_it_failed(
            self, sandbox, monkeypatch):
        from boost_cli.core import config
        _stub(monkeypatch,
              fail=tuple(str(t["name"]) for t in config.DEFAULT_TAPS))
        res = bootstrap.seed_catalog()
        assert "could not reach any default registry" in res.summary()
        assert "boost tap --defaults" in res.summary()
