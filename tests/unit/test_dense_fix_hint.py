# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`dense.fix_hint()` — the one next action, shared by every surface that reports it.

This table used to be a private dict inside `boost_cli/commands/quality.py`, read
only by `boost doctor`, and it had no tests at all. That combination is how it
went stale: the keyless-embeddings work made an API key optional, but the
"no-key" remedy still told users to set `VOYAGE_API_KEY` as though it were the
entry fee. Nothing failed, because nothing asserted anything about it.

So the tests here are deliberately about the *coupling* rather than the wording:
every reason `status()` can emit must have an entry, and no entry may name a key
as the only way forward. A reason added to `status()` without a remedy now fails
here instead of silently degrading to the generic fallback in front of a user.
"""
import pytest

from boost_cli.core import dense


def _table(reason: str) -> str:
    """The table's answer for `reason`, as a user reads it.

    Two rows name the command that installs the extra, which depends on how
    boost was installed, so the table holds a placeholder for it.
    """
    return dense._FIX[reason].replace(dense._INSTALL, dense.install_extra())


# Every reason `status()` can assign, read off the branch ladder in that
# function. Kept as a literal rather than introspected: the point is to fail
# when the two drift, and a derived list would drift along with it.
ALL_REASONS = [
    "disabled",
    "no-backend",
    "no-key",
    "no-store",
    "version-changed",
    "provider-changed",
    "model-changed",
    "dim-changed",
    "empty",
    "model-unavailable",
]


class TestCoverage:
    """The map must answer for every state `status()` can actually report."""

    @pytest.mark.parametrize("reason", ALL_REASONS)
    def test_every_status_reason_has_a_remedy(self, reason):
        assert reason in dense._FIX, (
            "dense.status() can report %r but fix_hint() has no remedy for it, "
            "so users hitting that state get the generic fallback" % reason)

    def test_no_remedy_for_a_reason_status_cannot_emit(self):
        # A stale entry is dead advice nobody will ever see reported.
        assert set(dense._FIX) == set(ALL_REASONS)

    def test_status_reasons_match_the_ladder(self, sandbox):
        # Guards the literal above against `status()` growing a new branch:
        # whatever it reports on a clean sandbox must be a reason we know.
        st = dense.status()
        assert st["reason"] is None or st["reason"] in ALL_REASONS


class TestWording:
    """Each hint names an action; none of them lies about needing a key."""

    @pytest.mark.parametrize("reason", ALL_REASONS)
    def test_hint_names_a_runnable_command(self, reason):
        hint = dense.fix_hint(reason)
        assert "`" in hint, "%r gives no command to run: %r" % (reason, hint)
        # Three families, because the third one is the point: the kill switch
        # is fixed by neither pip nor boost, and a rule that admitted only
        # those two is what left BOOST_NO_EMBED advertising an API key.
        assert any(cmd in hint for cmd in
                   ("boost reindex", "pip install", "unset BOOST_NO_EMBED")), hint

    def test_missing_backend_says_install_not_set_a_key(self):
        # The [rag] extra carries a local embedding model, so the extra alone is
        # sufficient. Sending this user to buy an API key is the stale advice.
        hint = dense.fix_hint("no-backend")
        assert "pip install" in hint
        assert "VOYAGE_API_KEY" not in hint and "OPENAI_API_KEY" not in hint

    def test_no_key_offers_the_keyless_route_first(self):
        # "no-key" now means no key AND no local backend. Reinstalling the extra
        # is the cheaper fix, so it must come before the key upgrade.
        hint = dense.fix_hint("no-key")
        assert hint.index("pip install") < hint.index("VOYAGE_API_KEY")

    def test_unbuilt_store_says_build_without_force(self):
        # There is nothing to force-rebuild yet; --force here is cargo cult.
        assert dense.fix_hint("no-store") == "build it: `boost reindex --dense`"

    @pytest.mark.parametrize("reason", ["version-changed", "provider-changed",
                                        "model-changed", "dim-changed", "empty"])
    def test_stale_store_says_force(self, reason):
        # A store built under different settings is not repaired incrementally;
        # without --force `reindex` sees a store and leaves the stale one.
        assert "--force" in dense.fix_hint(reason)


class TestKillSwitch:
    """BOOST_NO_EMBED is the user's own decision, and every other remedy is inert under it.

    `embed.provider()` reads the switch before any key or backend, so on a
    machine that set it the previous "no-key" remedy was a measured no-op:
    against a 5-chunk voyage-4 store, exporting VOYAGE_API_KEY produced a
    byte-identical status dict and the byte-identical hint.
    """

    def test_it_names_the_switch_and_nothing_else(self):
        hint = dense.fix_hint("disabled")
        assert "unset BOOST_NO_EMBED" in hint
        assert "pip install" not in hint
        assert "VOYAGE_API_KEY" not in hint and "OPENAI_API_KEY" not in hint
        assert "reindex" not in hint

    def test_a_built_store_does_not_reach_the_key_remedy(self):
        # `fix_hint`'s store-aware branch is keyed on "no-key"; a built store
        # behind the kill switch must not inherit it, or the user is told to
        # export a key that provider() never reads.
        st = {"reason": "disabled", "built_provider": "voyage",
              "built_model": "voyage-4", "chunks": 5, "store_exists": True}
        assert dense.fix_hint("disabled", st) == dense._FIX["disabled"]

    @pytest.mark.parametrize("cols", [40, 50, 60, 80])
    def test_the_command_survives_a_narrow_pane(self, cols):
        # Backtick spans are atomic tokens for `out.wrap`, so assert the
        # wrapping rather than a length: a `unset BOOST_NO_EMBED` split across
        # two lines is not a command anyone can run.
        from boost_cli.core import output as out
        span = "`%s`" % dense._FIX["disabled"].split("`")[1]
        lines = out.wrap("semantic search is off — %s" % dense.fix_hint("disabled"),
                         cols)
        assert any(span in line for line in lines), lines


class TestNoKeyReadsTheStore:
    """"no-key" has two states behind it, and the generic answer ruins one.

    The reason ladder checks `no-key` *before* it looks at the store, so an
    unfinished install (no vectors yet) and a working install whose key went
    missing are indistinguishable by reason alone. The table's answer —
    reinstall the extra — is right for the first and actively destructive for
    the second: it installs the local model, which flips `provider()` to
    `local`, which makes the next status `provider-changed`, whose remedy is
    `reindex --dense --force`. That re-embeds every vector the user already
    paid for.

    Found on a real machine: sqlite-vec installed, a 750,416-chunk store built
    with voyage-4, and no key exported into the MCP server's environment. Both
    `boost doctor` and the MCP `SEARCH ENGINE` line told it to reinstall.
    """

    def _status(self, **over):
        st = {"reason": "no-key", "built_provider": "voyage",
              "built_model": "voyage-4", "built_dim": 1024,
              "chunks": 750416, "store_exists": True}
        st.update(over)
        return st

    def test_a_voyage_built_store_is_told_to_set_the_key(self):
        hint = dense.fix_hint("no-key", self._status())
        assert "VOYAGE_API_KEY" in hint

    def test_a_voyage_built_store_is_not_told_to_reinstall(self):
        # The whole point: this is the advice that costs the re-embed.
        hint = dense.fix_hint("no-key", self._status())
        assert "pip install" not in hint

    def test_it_names_the_provider_that_built_the_store_not_the_first_one(self):
        # An openai-built store must not be handed voyage's variable — the key
        # would be accepted, the provider would differ, and the user would land
        # on `provider-changed` anyway, one wasted step later.
        hint = dense.fix_hint("no-key", self._status(built_provider="openai",
                                                     built_model="text-embedding-3-small"))
        assert "OPENAI_API_KEY" in hint and "VOYAGE_API_KEY" not in hint

    def test_it_says_what_reinstalling_would_cost(self):
        # A hint that only names the action leaves the user free to do the
        # expensive thing anyway; the number is why they won't.
        assert "750,416" in dense.fix_hint("no-key", self._status())

    def test_an_unfinished_install_still_gets_the_table_answer(self):
        # No vectors on disk means no key can revive anything: reinstalling the
        # extra really is the next step, exactly as before.
        hint = dense.fix_hint("no-key", self._status(built_provider=None,
                                                     chunks=0, store_exists=False))
        assert hint == _table("no-key")

    def test_a_locally_built_store_still_gets_the_table_answer(self):
        # `local` has no API key to set — this user genuinely dropped the
        # package and needs it back.
        hint = dense.fix_hint("no-key", self._status(built_provider="local",
                                                     built_model="BAAI/bge-small-en-v1.5"))
        assert hint == _table("no-key")

    def test_no_status_argument_keeps_the_old_answer(self):
        # Every pre-existing caller passes one argument; none may regress.
        assert dense.fix_hint("no-key") == _table("no-key")

    @pytest.mark.parametrize("reason", [r for r in ALL_REASONS if r != "no-key"])
    def test_other_reasons_ignore_the_status_dict(self, reason):
        # Only "no-key" reads the built store. ("no-store" reads the live
        # provider, which this dict leaves out — see TestKeyedMachineWithNoStore.)
        # If a status dict started steering the rest, the "these never chain"
        # property would be back in play.
        assert dense.fix_hint(reason, self._status(reason=reason)) == _table(reason)

    def test_the_env_var_names_come_from_embed_not_a_local_copy(self):
        # A second copy of these strings is how the hint would keep naming
        # VOYAGE_API_KEY after embed.py renamed it.
        from boost_cli.core import embed
        assert embed.KEY_ENV["voyage"] == "VOYAGE_API_KEY"
        assert set(embed.KEY_ENV) == {"voyage", "openai"}
        for provider, env in embed.KEY_ENV.items():
            hint = dense.fix_hint("no-key", self._status(built_provider=provider))
            assert env in hint

    def test_the_state_aware_hint_also_wraps_into_a_narrow_pane(self):
        # Same invariant TestFitsANarrowTerminal holds for the table; this
        # string bypasses the table, so it needs its own guard.
        import textwrap
        msg = "semantic search is off — %s" % dense.fix_hint("no-key", self._status())
        for line in textwrap.wrap(msg, 60, break_long_words=False,
                                  break_on_hyphens=False):
            assert len(line) <= 60, "overflowing line: %r" % line

    def test_the_state_aware_hint_still_names_a_command(self):
        assert "`" in dense.fix_hint("no-key", self._status())


class TestFallback:
    """An unknown reason must degrade to advice, not a KeyError in front of a user."""

    def test_unknown_reason_returns_generic_advice(self):
        assert dense.fix_hint("something-new") == "see `boost reindex --dense`"

    def test_non_string_reason_does_not_raise(self):
        # `status()` returns None for a healthy install; a caller passing that
        # straight through must not crash the command it was decorating.
        assert dense.fix_hint(None) == "see `boost reindex --dense`"  # type: ignore[arg-type]


class TestFitsANarrowTerminal:
    """No remedy may contain a token too long to wrap into a narrow pane.

    `boost search` wraps this text with `break_long_words=False` so the shell
    command it names stays copy-pasteable. That choice only holds the
    terminal-width invariant if no single whitespace-delimited token is itself
    wider than the pane — otherwise the wrapped line overflows and the hint
    becomes the one row in the output that breaks the layout, which is exactly
    how this shipped broken the first time (caught by the free-threaded canary
    at COLUMNS=60, not locally at 80).
    """

    # The narrowest pane the search output is tested against.
    NARROW = 60

    @pytest.mark.parametrize("reason", ALL_REASONS)
    def test_no_token_is_wider_than_a_narrow_pane(self, reason):
        prefix = "semantic search is off — "
        longest = max(dense.fix_hint(reason).split(), key=len)
        assert len(longest) <= self.NARROW, (
            "%r contains the token %r (%d chars), which cannot wrap into a "
            "%d-column terminal without being broken mid-command"
            % (reason, longest, len(longest), self.NARROW))
        # The prefix shares the first line, so it must not crowd out the text.
        assert len(prefix) < self.NARROW

    @pytest.mark.parametrize("reason", ALL_REASONS)
    def test_every_hint_wraps_within_a_narrow_pane(self, reason):
        import textwrap
        msg = "semantic search is off — %s" % dense.fix_hint(reason)
        for line in textwrap.wrap(msg, self.NARROW, break_long_words=False,
                                  break_on_hyphens=False):
            assert len(line) <= self.NARROW, "overflowing line: %r" % line


class TestKeyedMachineWithNoStore:
    """A key that outranks the local model, and no vectors on disk yet.

    `boost doctor` and `boost search` answered this state from the table —
    "build it: `boost reindex --dense`" — which with the key in force embeds
    the whole catalogue through the paid API. `boost quickstart`, `boost
    update --shards` and `boost reindex --fetch-shards` read
    `shards.remedy()`, which told the same user to unset the key and take the
    published vectors for free. Two answers to one state is the thing this
    function exists to prevent, and the one doctor gave was the costly one.
    """

    @pytest.fixture()
    def keyed(self, monkeypatch):
        """A status for the state, with the local model importable."""
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "local_installed", lambda: True)
        for env in embed.KEY_ENV.values():
            monkeypatch.delenv(env, raising=False)

        def make(provider="voyage", **over):
            st = {"reason": "no-store", "provider": provider,
                  "store_exists": False, "built_provider": None,
                  "chunks": None}
            st.update(over)
            return st

        return make

    def test_the_free_path_comes_first(self, keyed):
        hint = dense.fix_hint("no-store", keyed())
        assert "`unset VOYAGE_API_KEY`" in hint
        assert "`boost update --shards`" in hint
        assert hint.index("`unset") < hint.index("`boost reindex --dense`")

    def test_keeping_the_key_is_named_with_its_cost(self, keyed):
        hint = dense.fix_hint("no-store", keyed())
        tail = hint.split("`boost reindex --dense`")[1]
        assert "voyage" in tail and "paid" in tail

    def test_every_key_that_outranks_local_is_named(self, keyed, monkeypatch):
        # Unsetting VOYAGE alone falls through to OPENAI, which is no nearer
        # the published space: a remedy that names one key is a no-op here.
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        hint = dense.fix_hint("no-store", keyed())
        assert "`unset VOYAGE_API_KEY OPENAI_API_KEY`" in hint
        assert "keep the keys," in hint

    def test_only_the_key_in_force_is_named(self, keyed):
        hint = dense.fix_hint("no-store", keyed("openai"))
        assert "`unset OPENAI_API_KEY`" in hint
        assert "VOYAGE" not in hint
        assert "openai's paid API" in hint

    def test_it_is_the_answer_the_shard_surfaces_give(self, sandbox,
                                                       monkeypatch):
        # The real status of a keyed machine with no store, not a stub, and
        # the remedy quickstart and `update --shards` print for the keyless
        # manifest they are refused. One line, not two that happen to agree.
        from boost_cli.core import embed, shards
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "local_installed", lambda: True)
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        st = dense.status()
        assert (st["reason"], st["provider"]) == ("no-store", "voyage")
        space = {"provider": "local", "model": embed.LOCAL_MODEL,
                 "dim": embed.LOCAL_DIM}
        assert dense.fix_hint("no-store", st) == shards.remedy(space)

    def test_without_the_local_model_there_is_no_free_path(self, keyed,
                                                            monkeypatch):
        # Drop the key with nothing to take over and `provider()` is None:
        # the published vectors still cannot load. The table stands.
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "local_installed", lambda: False)
        assert dense.fix_hint("no-store", keyed()) == _table("no-store")

    def test_a_keyless_machine_keeps_the_table(self, keyed):
        # No key outranks anything: building is the free path already.
        assert dense.fix_hint("no-store", keyed("local")) == _table("no-store")

    def test_a_status_that_does_not_name_a_provider_keeps_the_table(self):
        # Callers that stub a two-key status (the MCP note's tests do) must
        # not be read as keyed.
        st = {"ready": False, "reason": "no-store"}
        assert dense.fix_hint("no-store", st) == _table("no-store")

    @pytest.mark.parametrize("reason", ["version-changed", "provider-changed",
                                        "model-changed", "dim-changed", "empty"])
    def test_a_keyed_user_with_a_store_is_never_told_to_unset(self, keyed,
                                                               reason):
        # #925's rule: vectors built with the key are not merged into by the
        # keyless shards, so "unset it" buys a refused import. `no-store`
        # means no store, so a store in any space lands on these reasons.
        st = keyed(reason=reason, store_exists=True,
                   built_provider="voyage", chunks=5)
        assert "unset" not in dense.fix_hint(reason, st)

    def test_the_state_is_read_from_the_status_not_the_reason_alone(self):
        # Every single-argument caller keeps the table's answer.
        assert dense.fix_hint("no-store") == _table("no-store")

    @pytest.mark.parametrize("cols", [40, 50, 60, 80])
    def test_both_keys_stay_one_runnable_span(self, keyed, monkeypatch, cols):
        # The longest atomic span this hint can hold is the two-key `unset`;
        # `- 2` is the indent `out.info` adds, as `boost search` budgets it.
        from boost_cli.core import output as out
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        hint = dense.fix_hint("no-store", keyed())
        lines = out.wrap("semantic search is off — %s" % hint, cols - 2)
        assert any("`unset VOYAGE_API_KEY OPENAI_API_KEY`" in line
                   for line in lines), lines
        assert any("`boost update --shards`" in line for line in lines), lines

    @pytest.mark.parametrize("cols", [40, 50, 60, 80])
    def test_it_wraps_within_the_pane(self, keyed, monkeypatch, cols):
        # Same invariant TestFitsANarrowTerminal holds for the table; this
        # answer bypasses the table, so it needs its own guard.
        from boost_cli.core import output as out
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        hint = dense.fix_hint("no-store", keyed())
        lines = out.wrap("semantic search is off — %s" % hint, cols - 2)
        assert all(out.visible_len(line) <= cols - 2 for line in lines), lines


class TestWordingTheHintLoadsNoBackend:
    """Naming the local model must not import the ONNX runtime.

    `boost search` and `boost doctor` print this hint on a keyed machine with
    no store, and the machines that reach it are exactly the ones that have
    the `[rag]` extra installed — so asking "can the local model take over?"
    by importing it charges every one of those runs for a backend the command
    never uses. The question is whether the packages are *there*, which
    `importlib.util.find_spec` answers without executing them.
    """

    @pytest.fixture()
    def counted(self, monkeypatch):
        """Count every import of the backend, and force the packages present."""
        from boost_cli.core import embed, localembed
        calls: list = []

        def _deps():
            calls.append(1)
            return object(), object()

        monkeypatch.setattr(localembed, "_deps", _deps)
        monkeypatch.setattr(localembed, "installed", lambda: True)
        embed.reset_local_cache()
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        yield calls
        embed.reset_local_cache()

    def test_the_free_path_is_worded_without_importing_the_runtime(self,
                                                                    counted):
        assert "`unset VOYAGE_API_KEY`" in (dense.free_shard_path("voyage") or "")
        assert counted == [], "the hint imported the embedding backend"

    def test_a_backend_this_process_already_loaded_is_not_asked_again(
            self, counted, monkeypatch):
        # Once `local_available` has run, the memoised answer is the honest
        # one — importable, not merely present — and costs nothing.
        from boost_cli.core import embed
        assert embed.local_available() is True
        assert counted == [1]
        assert embed.local_installed() is True
        assert counted == [1]

    def test_a_backend_that_failed_to_import_is_not_installed(self, monkeypatch):
        from boost_cli.core import embed, localembed
        monkeypatch.setattr(localembed, "available", lambda: False)
        embed.reset_local_cache()
        assert embed.local_available() is False
        # `installed` would say yes; the memoised failure outranks it.
        monkeypatch.setattr(localembed, "installed", lambda: True)
        assert embed.local_installed() is False
        embed.reset_local_cache()

    @pytest.mark.parametrize("missing", ["onnxruntime", "tokenizers"])
    def test_either_package_missing_means_no_local_model(self, monkeypatch,
                                                          missing):
        import importlib.util

        from boost_cli.core import embed, localembed
        real = importlib.util.find_spec
        monkeypatch.setattr(importlib.util, "find_spec",
                            lambda n, *a: None if n == missing else real("json"))
        embed.reset_local_cache()
        assert localembed.installed() is False
        embed.reset_local_cache()

    def test_a_package_the_import_system_refuses_to_locate_is_not_a_crash(
            self, monkeypatch):
        # `find_spec` raises rather than returning None for a few shapes (a
        # module in `sys.modules` with no spec, an unimportable parent). A
        # hint must not turn that into a traceback out of `boost search`.
        import importlib.util

        from boost_cli.core import embed, localembed
        monkeypatch.setattr(importlib.util, "find_spec",
                            lambda *a: (_ for _ in ()).throw(ValueError("no spec")))
        embed.reset_local_cache()
        assert localembed.installed() is False
        embed.reset_local_cache()
