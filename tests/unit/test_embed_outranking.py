# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`KEY_ENV`'s order is the preference order, and two functions read it.

`provider` used to test the two keys in a hardcoded sequence beside a dict
that stated the same order, and `dense._restore_built_space` re-derived it a
third way from the resolved provider's name. That third copy was wrong: it
read "another provider won" as "that provider outranks mine", which is false
for a voyage-built store displaced by an OpenAI key. These tests pin the
order once and pin both readers against it.
"""
from __future__ import annotations

import pytest

from boost_cli.core import embed


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for env in embed.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.delenv("BOOST_NO_EMBED", raising=False)


class TestTheOrderItself:

    def test_key_env_is_in_preference_order(self):
        # Not `set(...)`: insertion order is the contract both readers walk,
        # and a set assertion passes against the reversed dict that would
        # silently invert every answer below.
        assert list(embed.KEY_ENV) == ["voyage", "openai"]

    def test_provider_walks_that_order(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "voyage"

    def test_each_key_alone_selects_its_own_provider(self, monkeypatch):
        for name, env in embed.KEY_ENV.items():
            with monkeypatch.context() as m:
                for other in embed.KEY_ENV.values():
                    m.delenv(other, raising=False)
                m.setenv(env, "k")
                assert embed.provider() == name

    def test_an_empty_key_does_not_select_a_provider(self, monkeypatch):
        # `os.environ.get` is truthiness, not presence: an exported-but-empty
        # variable is how a shell profile leaves a key it failed to read.
        monkeypatch.setenv("VOYAGE_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "openai"

    def test_keys_are_preferred_over_the_local_model(self, monkeypatch):
        monkeypatch.setattr(embed, "local_available", lambda: True)
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.provider() == "openai"

    def test_local_is_the_fallback_when_no_key_is_set(self, monkeypatch):
        monkeypatch.setattr(embed, "local_available", lambda: True)
        assert embed.provider() == "local"

    def test_nothing_at_all_is_none(self, monkeypatch):
        monkeypatch.setattr(embed, "local_available", lambda: False)
        assert embed.provider() is None

    def test_disabled_short_circuits_every_key(self, monkeypatch):
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        assert embed.provider() is None


class TestOutranking:
    """What stands between a named provider and being the one picked."""

    def test_the_first_provider_is_outranked_by_nothing(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.outranking("voyage") == ()

    def test_a_later_provider_names_the_set_key_in_front_of_it(self,
                                                               monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.outranking("openai") == ("VOYAGE_API_KEY",)

    def test_an_unset_key_in_front_does_not_outrank(self, monkeypatch):
        # Rank alone is not the question — the key has to actually be in
        # force. This is the whole difference between "another provider is
        # ahead of you" and "another provider is winning".
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.outranking("openai") == ()

    def test_an_empty_key_in_front_does_not_outrank(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "")
        assert embed.outranking("openai") == ()

    def test_every_set_key_outranks_a_name_that_is_not_a_key(self,
                                                             monkeypatch):
        # `local` comes after all of them, so any key displaces it. A store
        # built locally has no key to restore, which is why `fix_hint`
        # never asks — but the answer still has to be the true one.
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.outranking("local") == ("VOYAGE_API_KEY",
                                             "OPENAI_API_KEY")

    def test_an_unknown_name_is_treated_the_same_way(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        assert embed.outranking("not-a-provider") == ("OPENAI_API_KEY",)

    def test_no_keys_at_all_outranks_nothing(self):
        for name in (*embed.KEY_ENV, "local"):
            assert embed.outranking(name) == ()

    def test_it_returns_env_var_names_not_provider_names(self, monkeypatch):
        # Callers interpolate the result into `unset %s`, so a provider name
        # here produces a command that runs and does nothing.
        monkeypatch.setenv("VOYAGE_API_KEY", "v")
        assert set(embed.outranking("openai")) <= set(embed.KEY_ENV.values())

    def test_it_agrees_with_provider_on_who_is_winning(self, monkeypatch):
        # The property the two functions have to share: nothing outranks the
        # provider that `provider()` actually picked. This is what a third
        # re-derivation of the order elsewhere would break.
        for voyage in (False, True):
            for openai in (False, True):
                with monkeypatch.context() as m:
                    for env, on in (("VOYAGE_API_KEY", voyage),
                                    ("OPENAI_API_KEY", openai)):
                        m.delenv(env, raising=False)
                        if on:
                            m.setenv(env, "k")
                    m.setattr(embed, "local_available", lambda: True)
                    won = embed.provider()
                    assert embed.outranking(won) == (), (voyage, openai, won)
