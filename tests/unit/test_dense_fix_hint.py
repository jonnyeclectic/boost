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

# Every reason `status()` can assign, read off the branch ladder in that
# function. Kept as a literal rather than introspected: the point is to fail
# when the two drift, and a derived list would drift along with it.
ALL_REASONS = [
    "no-backend",
    "no-key",
    "no-store",
    "version-changed",
    "provider-changed",
    "model-changed",
    "dim-changed",
    "empty",
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
    def test_hint_names_a_boost_or_pip_command(self, reason):
        hint = dense.fix_hint(reason)
        assert "`" in hint, "%r gives no command to run: %r" % (reason, hint)
        assert "boost reindex" in hint or "pip install" in hint

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
