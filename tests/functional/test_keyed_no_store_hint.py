# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""One answer for a keyed machine with no vector store, on every surface.

With ``VOYAGE_API_KEY`` exported, the local model installed and no store yet,
`boost doctor` and `boost search` said "build it: `boost reindex --dense`" —
which, with that key in force, embeds the whole catalogue through the paid
API — while `boost quickstart`, `boost update --shards` and `boost reindex
--fetch-shards` told the same user to unset the key and take the published
vectors for free. The first pair read ``dense.fix_hint``; the second read
``shards.remedy``. Each surface is run here, in-process, on the real status of
that machine, and must print the one line both functions now share.
"""
import json

import pytest

from boost_cli.core import dense, embed, shards

SPACE = {"provider": "local", "model": embed.LOCAL_MODEL, "dim": embed.LOCAL_DIM}


def _flat(text: str) -> str:
    """Output with its wrapping collapsed, so the sentence is what is compared."""
    return " ".join(text.split())


@pytest.fixture()
def keyed(boost, tapped, tmp_path, monkeypatch):
    """The machine: key exported, local model importable, a tap, no store.

    The key is a real environment variable rather than a stubbed
    ``embed.provider``, so the status, the remedy and the list of keys to
    unset all read it the way a user's shell supplies it. Returns the list
    every attempted shard download is appended to; it must stay empty.
    """
    monkeypatch.setattr(dense, "have_backend", lambda: True)
    monkeypatch.setattr(embed, "local_installed", lambda: True)
    monkeypatch.setattr(embed, "local_available", lambda: True)
    monkeypatch.setenv("VOYAGE_API_KEY", "not-a-real-key")
    rows = [{"tap": "a/b", "commit": "1" * 40, "chunks": 1, "bytes": 4,
             "sha256": "0" * 64, "url": (tmp_path / "never.json").as_uri()}]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"version": 1, **SPACE, "shards": rows}),
                    encoding="utf-8")
    monkeypatch.setenv(shards.MANIFEST_ENV, path.as_uri())
    downloads: list = []
    monkeypatch.setattr(shards, "download",
                        lambda *a, **k: downloads.append(a))
    st = dense.status()
    assert (st["reason"], st["provider"]) == ("no-store", "voyage")
    return downloads


# (argv, exit code): the two shard commands refuse the manifest and exit 1.
SURFACES = [
    (("doctor",), None),
    (("search", "brainstorming"), 0),
    (("quickstart", "--dry-run"), 0),
    (("update", "--shards"), 1),
    (("reindex", "--fetch-shards"), 1),
]


class TestOneAnswer:

    def test_the_line_is_the_free_path_with_its_cost_beside_it(self, keyed):
        line = dense.fix_hint("no-store", dense.status())
        assert line == shards.remedy(shards.fetch_manifest())
        assert line.startswith("`unset VOYAGE_API_KEY`, then "
                               "`boost update --shards`")
        assert "through voyage's paid API" in line

    @pytest.mark.parametrize(("argv", "rc"), SURFACES,
                             ids=[" ".join(a) for a, _ in SURFACES])
    def test_every_surface_prints_it(self, boost, keyed, argv, rc):
        line = _flat(dense.fix_hint("no-store", dense.status()))
        res = boost(*argv, expect=rc)
        both = _flat(res.out + res.err)
        assert line in both, both
        # The table's answer is the paid build; it must not ride alongside.
        assert "build it: `boost reindex --dense`" not in both
        assert keyed == []

    def test_the_mcp_engine_note_says_it_too(self, keyed):
        # `boost mcp` hands the agent the same hint in its instructions.
        from boost_cli.core import mcp
        note = _flat(mcp.engine_note())
        assert _flat(dense.fix_hint("no-store", dense.status())) in note
        assert "`unset VOYAGE_API_KEY`" in note
