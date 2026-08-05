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


def _stub(monkeypatch, *, existing=(), fail=(), counts=None):
    """Point bootstrap at fakes: no network, no disk, deterministic counts.

    Clearing BOOST_NO_SEED is the explicit opt-in the conftest asks for: the
    sandbox fixture sets it so no test clones seven repositories by accident,
    and a test whose whole subject IS the seed says so here. The fakes above
    are what make that safe — nothing below reaches the network either way.
    """
    from boost_cli.core import catalog, journal, registry
    monkeypatch.delenv(bootstrap.NO_SEED_ENV, raising=False)
    added = []

    def fake_add(url, **kw):
        name = url.split("github.com/")[-1]
        if name in fail:
            from boost_cli.errors import BoostError
            raise BoostError("clone failed: %s" % name)
        added.append(name)
        return _FakeTap(name)

    monkeypatch.setattr(registry, "list_taps",
                        lambda: [_FakeTap(n) for n in existing])
    monkeypatch.setattr(registry, "add", fake_add)
    monkeypatch.setattr(catalog, "rebuild_tap",
                        lambda tap: [{}] * (counts or {}).get(tap.name, 3))
    monkeypatch.setattr(journal, "log", lambda *a, **kw: None)
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
