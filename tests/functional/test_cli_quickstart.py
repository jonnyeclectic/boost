# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`boost quickstart` and `reindex --fetch-shards` end to end.

The behaviour worth pinning here is what these commands DON'T do, because both
failure modes are expensive rather than loud:

* quickstart must never start a multi-hour local embed on a user's behalf. It
  reports the taps with no published shard and leaves them alone.
* neither command may change anything as a side effect of being asked what it
  would do. `--dry-run` taps nothing, and `--no-vectors` never fetches a
  manifest. Without the `[rag]` extra the manifest is still read, for its
  pins: the run ends by promising that installing the extra and rerunning
  brings the vectors, and a tap left at HEAD would make that a lie.

Every test here runs against the sandbox HOME and a manifest served from a
`file:` URL, so nothing in the suite depends on a release existing.
"""
from __future__ import annotations

import hashlib
import json
import re

import pytest

SPACE = {"provider": "local", "model": "BAAI/bge-small-en-v1.5", "dim": 384}


@pytest.fixture()
def manifest(tmp_path, monkeypatch):
    """A published manifest with one shard, served from disk."""
    body = json.dumps({"tap": "a/b", "commit": "1" * 40, **SPACE,
                       "chunks": [{"name": "x", "embedding": "AAAA"}]})
    shard = tmp_path / "a__b.shard.json"
    shard.write_text(body, encoding="utf-8")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "version": 1, "generated": "2026-01-01T00:00:00Z", **SPACE,
        "shards": [{"tap": "a/b", "commit": "1" * 40, "chunks": 1,
                    "bytes": len(body.encode()),
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "url": shard.as_uri()}]}), encoding="utf-8")
    monkeypatch.setenv("BOOST_SHARD_MANIFEST", path.as_uri())
    return path


class TestQuickstartDryRun:
    def test_dry_run_taps_nothing(self, boost, sandbox):
        res = boost("quickstart", "--dry-run")
        assert "would tap" in res.out
        # The proof it changed nothing: no clone, no config, no index.
        assert not (sandbox / ".boost" / "repos").exists()

    def test_dry_run_names_every_default_tap(self, boost):
        from boost_cli.core import config
        res = boost("quickstart", "--dry-run")
        for default in config.DEFAULT_TAPS:
            assert str(default["name"]) in res.out


class TestQuickstartDryRunListOrCount:
    """The dry run lists pending registries up to the shared threshold.

    It used a bare 12 while the closing failure note used
    `bootstrap.MAX_NAMED_REGISTRIES`; they now share the constant, and this
    pins the dry run's side at the boundary. The second parametrisation moves
    the constant, so a literal of any value fails one case or the other.
    """

    @pytest.fixture(params=["shipped", "moved"])
    def cap(self, request, monkeypatch):
        from boost_cli.core import bootstrap
        if request.param == "moved":
            monkeypatch.setattr(bootstrap, "MAX_NAMED_REGISTRIES", 3)
        return bootstrap.MAX_NAMED_REGISTRIES

    @staticmethod
    def _pending(monkeypatch, count):
        from boost_cli.core import config
        # Zero-padded, so "reg/p01" is never a substring of "reg/p10".
        names = ["reg/p%02d" % i for i in range(count)]
        monkeypatch.setattr(config, "DEFAULT_TAPS",
                            [{"name": n, "url": "https://example.invalid/%s" % n}
                             for n in names])
        return names

    def test_exactly_the_threshold_is_listed_by_name(self, boost, monkeypatch,
                                                     cap):
        names = self._pending(monkeypatch, cap)
        lines = [ln.strip() for ln in boost("quickstart",
                                            "--dry-run").out.splitlines()]
        for name in names:
            assert "would tap %s" % name in lines
        assert not any(ln.startswith("would tap %d registries" % cap)
                       for ln in lines)

    def test_one_past_the_threshold_is_counted_instead(self, boost,
                                                       monkeypatch, cap):
        names = self._pending(monkeypatch, cap + 1)
        out = boost("quickstart", "--dry-run").out
        assert "would tap %d registries (0 pinned" % (cap + 1) in out
        for name in names:
            assert name not in out


class TestQuickstartCatalog:
    """`--catalog` is the "search everything" entry point."""

    def test_it_plans_every_catalogued_registry(self, boost):
        from boost_cli.core import config
        catalogued = [e for e in config.load_registry_catalog()
                      if not e.get("list_only")]
        res = boost("quickstart", "--catalog", "--dry-run")
        # Past a handful the dry run reports the shape: 463 lines of "would
        # tap" is a wall of text, not a preview.
        assert "would tap %d registries" % len(catalogued) in res.out

    def test_the_default_scope_is_still_the_seven_starters(self, boost):
        from boost_cli.core import config
        res = boost("quickstart", "--dry-run")
        for default in config.DEFAULT_TAPS:
            assert str(default["name"]) in res.out

    def test_catalog_scope_excludes_index_repos(self, boost):
        from boost_cli.core import config
        lists = [e for e in config.load_registry_catalog()
                 if e.get("list_only")]
        if not lists:
            pytest.skip("no list-only repos in the bundled catalogue")
        res = boost("quickstart", "--catalog", "--dry-run")
        total = len([e for e in config.load_registry_catalog()
                     if not e.get("list_only")])
        # An awesome-list repo indexes other repos and ships nothing of its
        # own, so tapping it for vectors buys nothing.
        assert "would tap %d registries" % total in res.out


class TestQuickstartWithoutTheExtra:
    """The default install: no `rag` extra, so no vectors — but still pins."""

    def test_an_unreadable_manifest_still_taps(self, boost, monkeypatch):
        # Pointed at a URL that fails: the pins are lost, the taps are not.
        monkeypatch.setenv("BOOST_SHARD_MANIFEST",
                           "https://127.0.0.1:1/manifest.json")
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        res = boost("quickstart", "--dry-run")
        assert "would tap" in res.out
        assert " @ " not in res.out

    @pytest.mark.parametrize("dry", [True, False])
    def test_an_unreadable_manifest_offers_no_remedy_that_needs_the_extra(
            self, boost, monkeypatch, dry):
        # The transport hint says `boost reindex --dense` embeds locally
        # instead, which cannot run without the extra. Here the manifest was
        # read for its pins alone: say it failed, and offer nothing else.
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError

        def boom(*_a, **_k):
            raise BoostError("cannot reach the manifest",
                             hint=shards.LOCAL_EMBED_HINT)

        monkeypatch.setattr(dense, "have_backend", lambda: False)
        monkeypatch.setattr(shards, "fetch_manifest", boom)
        calls = _fake_add_many(monkeypatch, ["ok"] * 7)
        out = _flat(boost("quickstart", *(["--dry-run"] if dry else [])).out)
        assert "could not read the shard manifest: cannot reach" in out
        assert "shards are optional" not in out
        assert "reindex --dense" not in out
        if not dry:
            assert calls["pins"] == {}

    def test_a_hint_that_needs_no_extra_is_still_shown_without_it(
            self, boost, monkeypatch):
        # Only the local-embed hint needs the extra. A manifest URL that is
        # not https is a fix this machine can make either way.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        monkeypatch.setenv("BOOST_SHARD_MANIFEST", "http://example.invalid/m.json")
        _fake_add_many(monkeypatch, ["ok"] * 7)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "refusing to fetch a shard manifest over 'http'" in out
        assert "shard URLs must be https" in out

    def test_the_taps_are_pinned_without_the_extra(
            self, boost, defaults_manifest, monkeypatch):
        """The six taps landed `pin: null`, and the rerun could not fix it.

        `add_many` skips a configured tap, so the second run printed "already
        tapped" seven times, and `sync` then refused every shard built for a
        commit the tap had moved past.
        """
        from boost_cli.core import config, dense, shards
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        calls = _fake_add_many(monkeypatch, ["ok"] * 7)
        synced: list = []
        monkeypatch.setattr(shards, "sync",
                            lambda *a, **k: synced.append(a) or [])
        res = boost("quickstart")
        assert calls["pins"] == {str(d["name"]): "1" * 40
                                 for d in config.DEFAULT_TAPS}
        assert "@ 1111111" in res.out
        # Pinned, not imported: no vectors can load without the extra.
        assert synced == []
        assert "then `boost quickstart` again" in _flat(res.out)

    def test_the_dry_run_shows_the_pins_the_live_run_uses(
            self, boost, defaults_manifest, monkeypatch):
        from boost_cli.core import config, dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        out = boost("quickstart", "--dry-run").out
        for d in config.DEFAULT_TAPS:
            assert "would tap %s @ 1111111" % d["name"] in out
        assert "import 0 shard(s)" in out

    @pytest.mark.parametrize("dry", [True, False])
    def test_no_vectors_reads_no_manifest_and_pins_nothing(
            self, boost, defaults_manifest, monkeypatch, dry):
        # The opt-out: taps that track HEAD, so `boost update` moves them.
        from boost_cli.core import dense, shards
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        calls = _fake_add_many(monkeypatch, ["ok"] * 7)
        fetched: list = []
        monkeypatch.setattr(shards, "fetch_manifest",
                            lambda *a, **k: fetched.append(a) or {})
        res = boost("quickstart", "--no-vectors", *(["--dry-run"] if dry
                                                     else []))
        assert fetched == []
        assert " @ " not in res.out
        if not dry:
            assert calls["pins"] == {}

    def test_both_lines_print_the_command_doctor_prints(
            self, boost, monkeypatch):
        # quickstart hard-coded a pipx line while doctor and search read
        # `dense.fix_hint`: two answers to one question.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        _fake_add_many(monkeypatch, ["ok"] * 7)
        cmd = re.search(r"`[^`]*\[rag\][^`]*`",
                        dense.fix_hint("no-backend")).group(0)
        dry = _flat(boost("quickstart", "--dry-run").out)
        live = _flat(boost("quickstart").out)
        assert cmd in dry and cmd in live
        assert (dry.count("boost-skill-cli[rag]")
                == live.count("boost-skill-cli[rag]") == 1)

    def test_zero_shards_says_why_it_is_zero(self, boost, monkeypatch):
        """"import 0 shard(s)" reads as "none are published".

        The cause here is local — no `rag` extra — and `--dry-run` is exactly
        what a cautious new user runs first, so the preview was the one surface
        that reported the symptom and withheld the reason. The live path
        already explains both cases.
        """
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: False)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "boost-skill-cli[rag]" in out
        # Named as the working default, not as a downgrade — BM25 is what
        # ships and what the required eval gate floors.
        assert "keyword search works without it" in out

    def test_no_vectors_is_reported_as_a_choice_not_a_gap(self, boost,
                                                          monkeypatch):
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        out = _flat(boost("quickstart", "--dry-run", "--no-vectors").out)
        assert "import 0 shard(s)" in out
        assert "--no-vectors was asked for" in out
        # It must not blame the missing extra for a flag the user passed.
        assert "boost-skill-cli[rag]" not in out


class TestATapThatMovedPastItsVectors:
    """The rerun after installing the extra, on a tap no longer at its shard.

    A registry first tapped before quickstart pinned anything sits at HEAD,
    and any tap falls behind once a weekly republish moves the manifest.
    `sync` refuses those shards, and the only remedy named was hours of local
    embedding, while `update --shards` moves the tap and downloads them.
    """

    @pytest.fixture()
    def space_matches(self, monkeypatch):
        from boost_cli.core import shards
        monkeypatch.setattr(shards, "incompatible", lambda _m: None)

    def test_the_refusal_is_marked_as_a_commit_that_moved(
            self, manifest, space_matches):
        from boost_cli.core import shards
        rows = shards.sync(["a/b"], {"a/b": "2" * 40},
                           manifest=shards.fetch_manifest())
        assert rows[0]["status"] == "refused"
        assert rows[0]["commit_moved"] is True

    def test_the_report_names_update_shards(self, manifest, space_matches,
                                            capsys):
        from boost_cli.commands import quickstart
        from boost_cli.core import shards
        quickstart._report(shards.sync(["a/b"], {"a/b": "2" * 40},
                                       manifest=shards.fetch_manifest()))
        out = capsys.readouterr().out
        assert "a/b: shard refused (tap is at 2222222" in out
        assert "moved past their vectors: `boost update --shards`" in out

    def test_other_refusals_do_not_send_the_user_to_move_taps(self, capsys):
        # A refused space or an import that said no is not fixed by moving.
        from boost_cli.commands import quickstart
        quickstart._report([{"tap": "a/b", "status": "refused",
                             "detail": "provider mismatch"},
                            {"tap": "c/d", "status": "failed",
                             "detail": "sha256 mismatch"}])
        assert "update --shards" not in capsys.readouterr().out


def _flat(text: str) -> str:
    """Output with its wrapping collapsed.

    These lines go through ``out.info(..., wrap=True)``, which folds prose to
    the pane — so "keyword search is unaffected" arrives split across two lines
    and a naive substring assertion fails on formatting rather than on
    behaviour. Collapsing whitespace asserts the sentence, not the column it
    happened to break at.
    """
    return " ".join(text.split())


class TestEveryZeroShardReasonNamesItself:
    """All four branches, because a preview that reports a symptom without its
    reason is the defect — and three-quarters covered is three-quarters of the
    defect still shipped."""

    def test_an_unreadable_manifest_says_keyword_search_is_unaffected(
            self, boost, monkeypatch):
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError

        def boom(*_a, **_k):
            raise BoostError("manifest unreachable")

        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", boom)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "the shard manifest could not be read" in out
        # The reassurance is the point: the tapping half still worked.
        assert "keyword search is unaffected" in out

    def test_a_wrapped_muted_line_terminates_its_colour_on_every_line(
            self, capsys, monkeypatch):
        # Colour first, fold after, and line 1 ends inside an open dim span
        # while the rest carry none — CLAUDE.md's wrap rule. Wrap first.
        from boost_cli.commands import quickstart
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setenv("COLUMNS", "40")
        capsys.readouterr()
        quickstart._muted("the shard manifest could not be read; "
                          "`boost update --shards` retries it, and "
                          "`boost reindex --dense` builds them locally")
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) > 1                       # it really did fold
        for line in lines:
            assert line.startswith("  \033[2m") and line.endswith("\033[0m")
        # A backticked command is one token: never split across lines.
        for cmd in ("`boost update --shards`", "`boost reindex --dense`"):
            assert any(cmd in ln for ln in lines)

    @pytest.mark.parametrize("hint", [
        "a proxy or a dropped connection cut the stream — retry",
        "LOCAL_EMBED_HINT"])
    def test_a_manifest_error_keeps_its_hint_and_names_the_real_cause(
            self, boost, monkeypatch, hint):
        # "no published shards" said the project has none; the cause is
        # local. And the hint — the only actionable line, carried by every
        # transport-shaped failure — was thrown away. With the extra even the
        # local-embed hint applies, so it is kept too.
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError
        if hint == "LOCAL_EMBED_HINT":
            hint = shards.LOCAL_EMBED_HINT

        def boom(*_a, **_k):
            raise BoostError("cannot reach the manifest", hint=hint)

        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", boom)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "could not read the shard manifest: cannot reach" in out
        assert hint in out
        assert "no published shards" not in out

    def test_a_manifest_with_no_matching_shard_says_so(self, boost,
                                                       monkeypatch):
        # The one branch where zero really does mean "none published for
        # these" — and it must not be worded like a local misconfiguration.
        from boost_cli.core import dense, embed, shards
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        # A machine whose space matches the manifest's: without that, the
        # manifest is refused before its rows are looked at, which is a
        # different zero with a different reason.
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        monkeypatch.setattr(shards, "fetch_manifest",
                            lambda *a, **k: dict(SPACE))
        monkeypatch.setattr(shards, "rows", lambda _m: {})
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "none of these registries have a published shard yet" in out
        assert "boost-skill-cli[rag]" not in out


def _fake_add_many(monkeypatch, outcomes, entries=3, index=None):
    """Answer `registry.add_many` with one scripted outcome per default tap.

    `outcomes` holds "ok", "fail" or "skip" per registry in
    `config.DEFAULT_TAPS` order; `entries` is what the keyword index reports
    afterwards, and `index` replaces `catalog.rebuild_tap`. Returns the dict
    the fake records its arguments in.
    """
    from boost_cli.core import catalog, config, registry

    class FakeTap:
        def __init__(self, name):
            self.name = name
            self.safe_name = name.replace("/", "__")

    names = [str(d["name"]) for d in config.DEFAULT_TAPS]
    assert len(outcomes) == len(names), "one outcome per default registry"
    calls: dict = {}

    def add_many(urls, curated=False, pins=None, jobs=None, on_done=None):
        calls["pins"] = pins
        calls["urls"] = list(urls)
        rows = []
        for name, kind in zip(names, outcomes, strict=True):
            if kind == "skip":
                rows.append({"spec": name, "name": name, "ok": False,
                             "skipped": True, "error": "already tapped"})
            elif kind == "fail":
                rows.append({"spec": name, "name": name, "ok": False,
                             "error": "repository not found"})
            else:
                rows.append({"spec": name, "name": name, "ok": True,
                             "tap": FakeTap(name)})
        return rows

    monkeypatch.setattr(registry, "add_many", add_many)
    monkeypatch.setattr(catalog, "rebuild_tap",
                        index or (lambda tap: [{"name": "x"}]))
    monkeypatch.setattr("boost_cli.core.rag.build",
                        lambda *a, **k: {"entries": entries})
    return calls


class TestQuickstartTapping:
    """The real tap path, with the network replaced rather than the command."""

    @pytest.fixture()
    def fake_taps(self, monkeypatch):
        """`add_many` answers already-tapped, not-found, then five clones."""
        return _fake_add_many(monkeypatch, ["skip", "fail"] + ["ok"] * 5)

    def test_it_reports_each_outcome_and_survives_a_bad_registry(
            self, boost, fake_taps):
        res = boost("quickstart", "--no-vectors")
        both = res.out + res.err
        assert "already tapped" in both
        # One registry failing must not stop the other six.
        assert "repository not found" in both
        assert both.count("tapped ") >= 2
        assert "ready" in both

    def test_a_live_run_says_the_vector_step_was_skipped(
            self, boost, fake_taps, monkeypatch):
        # The whole vector step is skipped when the manifest cannot be read,
        # and the run used to end "✓ ready" with nothing said about it after
        # one warning many lines earlier.
        from boost_cli.core import dense, shards
        from boost_cli.errors import BoostError

        def boom(*_a, **_k):
            raise BoostError("cannot reach the manifest")

        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(shards, "fetch_manifest", boom)
        res = boost("quickstart")
        both = _flat(res.out + res.err)
        assert "no vectors imported" in both
        assert "boost update --shards" in both and "reindex --dense" in both
        assert "ready" in both              # still not fatal

    def test_shard_commits_are_passed_as_pins(self, boost, fake_taps,
                                              manifest, monkeypatch):
        from boost_cli.core import dense, embed, shards
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        monkeypatch.setattr(shards, "sync",
                            lambda *a, **k: [])
        boost("quickstart")
        # The manifest names a/b, which is not a default tap, so no pin applies
        # — but the pins dict must still have been threaded through rather than
        # dropped, or a pinned registry would be tapped at HEAD.
        assert fake_taps["pins"] == {}

    def test_the_urls_tapped_are_the_default_registries(self, boost,
                                                        fake_taps):
        from boost_cli.core import config
        boost("quickstart", "--no-vectors")
        assert fake_taps["urls"] == [str(d["url"]) for d in config.DEFAULT_TAPS]


@pytest.fixture()
def defaults_manifest(tmp_path, monkeypatch):
    """A keyless manifest with a row for every default registry."""
    from boost_cli.core import config
    rows = [{"tap": str(d["name"]), "commit": "1" * 40, "chunks": 1,
             "bytes": 4, "sha256": "0" * 64,
             "url": (tmp_path / "never-fetched.json").as_uri()}
            for d in config.DEFAULT_TAPS]
    path = tmp_path / "defaults-manifest.json"
    path.write_text(json.dumps({"version": 1, **SPACE, "shards": rows}),
                    encoding="utf-8")
    monkeypatch.setenv("BOOST_SHARD_MANIFEST", path.as_uri())
    return path


@pytest.fixture()
def keyed_machine(monkeypatch):
    """The `[rag]` extra installed and VOYAGE_API_KEY exported.

    The machine the card measured: its queries embed with voyage-4 at 1024-d,
    so the keyless 384-d vectors quickstart exists to deliver are unusable
    here — and nothing is downloaded to find that out. Returns the list every
    attempted shard download is appended to, which must stay empty.
    """
    from boost_cli.core import dense, embed, shards
    monkeypatch.setattr(dense, "have_backend", lambda: True)
    monkeypatch.setattr(embed, "provider", lambda: "voyage")
    monkeypatch.setattr(embed, "model", lambda: "voyage-4")
    monkeypatch.setattr(embed, "dimension", lambda: 1024)
    # Both seams: `remedy` words the free path from `local_installed`
    # (the look-up that imports nothing), and the embedding path that
    # would follow the advice still asks `local_available`.
    monkeypatch.setattr(embed, "local_available", lambda: True)
    monkeypatch.setattr(embed, "local_installed", lambda: True)
    downloads: list = []
    monkeypatch.setattr(shards, "download",
                        lambda *a, **k: downloads.append(a))
    return downloads


REFUSAL = "published shards are local, this machine embeds with voyage"


class TestQuickstartWithAKeyExported:
    """`sync` refuses every shard as `incompatible`, and quickstart said
    nothing about it: no line named voyage, the space, or the free path —
    only "embed the rest locally", which with a key set bills the API."""

    def _live(self, boost, monkeypatch):
        from boost_cli.core import config, dense, rag, registry
        _fake_add_many(monkeypatch, ["ok"] * 7)
        names = [str(d["name"]) for d in config.DEFAULT_TAPS]
        # Seven configured taps, so `sync` — were it reached — would stamp
        # the same machine-level detail on seven rows.
        monkeypatch.setattr(registry, "list_taps", lambda: [
            registry.Tap(name=n, url="file:///x") for n in names])
        monkeypatch.setattr(rag, "_tap_commits", lambda: {
            n.replace("/", "__"): "1" * 40 for n in names})
        monkeypatch.setattr(dense, "tap_commits", lambda: {})
        return boost("quickstart")

    def test_the_refusal_is_named_once_with_both_remedies(
            self, boost, defaults_manifest, keyed_machine, monkeypatch):
        res = self._live(boost, monkeypatch)
        both = _flat(res.out + res.err)
        # Once, not seven times: the reason is the machine's, not each tap's.
        assert both.count(REFUSAL) == 1
        assert "no vectors imported — " + REFUSAL in both
        assert "`unset VOYAGE_API_KEY`" in both
        assert "`boost update --shards`" in both
        assert "paid" in both
        # "locally" was false with a key set: reindex embeds through voyage.
        assert "embed the rest locally" not in both
        assert keyed_machine == []          # decided before any download
        assert "ready" in both              # keyword search still works

    def test_the_dry_run_no_longer_promises_shards_it_cannot_import(
            self, boost, defaults_manifest, keyed_machine):
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "import 7 shard(s)" not in out
        assert "(0 because %s)" % REFUSAL in out
        assert "`unset VOYAGE_API_KEY`" in out

    def test_the_dry_run_says_what_the_live_run_will(
            self, boost, defaults_manifest, keyed_machine, monkeypatch):
        from boost_cli.core import shards
        fix = _flat(shards.remedy(shards.fetch_manifest()))
        dry = _flat(boost("quickstart", "--dry-run").out)
        res = self._live(boost, monkeypatch)
        live = _flat(res.out + res.err)
        assert REFUSAL in dry and REFUSAL in live
        assert fix in dry and fix in live

    def test_a_store_built_with_the_key_hears_it_cannot_take_the_shards(
            self, boost, defaults_manifest, keyed_machine, vector_store):
        assert vector_store()["ready"]
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "(0 because %s)" % REFUSAL in out
        assert "unset" not in out
        assert "cannot merge" in out

    def test_the_refusal_is_muted_like_every_other_zero_reason(
            self, capsys, monkeypatch):
        # Its siblings — "(0 because the manifest could not be read)",
        # "(0 because none … published)" — are muted; this one printed at
        # full strength, in both the dry run and the live run.
        from boost_cli.commands import quickstart
        from boost_cli.core import bootstrap
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("CLICOLOR_FORCE", "1")
        monkeypatch.setenv("COLUMNS", "40")
        outcome = bootstrap.SetupOutcome(vectors_refused=REFUSAL,
                                         vectors_remedy="`boost x` fixes it")
        for dry_run in (True, False):
            capsys.readouterr()
            quickstart._vectors_refused(outcome, dry_run=dry_run)
            lines = capsys.readouterr().out.splitlines()
            assert len(lines) > 2                   # the reason folded
            for line in lines:
                assert line.startswith("  \033[2m") and line.endswith("\033[0m")

    def test_the_kill_switch_is_named_as_the_reason_and_the_remedy(
            self, boost, defaults_manifest, monkeypatch):
        # The extra is installed, so "no embedding backend" was false; the
        # user switched embedding off, and that is the one thing to undo.
        from boost_cli.core import dense
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setenv("BOOST_NO_EMBED", "1")
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "import 0 shard(s)" in out
        assert "BOOST_NO_EMBED" in out
        assert "`unset BOOST_NO_EMBED`" in out
        assert "no embedding backend" not in out


class TestQuickstartReadiness:
    """quickstart may only say "ready" when `boost search` can answer.

    With every registry unreachable it failed 0-for-7, printed "✓ indexed 0
    items" and "✓ ready — try `boost search brainstorming`", and exited 0 —
    while that `boost search` exits 1 with "no taps configured". The two traps
    a fix must dodge are pinned beside it: a rerun where everything is already
    tapped (zero clones succeed, and it is fine) and one bad registry among
    good ones (named, never fatal).
    """

    @pytest.fixture()
    def seven(self):
        from boost_cli.core import config
        return [str(d["name"]) for d in config.DEFAULT_TAPS]

    def test_every_tap_failing_exits_non_zero_and_claims_nothing(
            self, boost, monkeypatch, seven):
        _fake_add_many(monkeypatch, ["fail"] * len(seven), entries=0)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert "not ready — none of the %d registries could be tapped" \
            % len(seven) in both
        assert "check the network" in both
        # The claim has to go, not just the exit code: a human reads the last
        # green tick, not `$?`.
        assert "✓ ready" not in both
        assert "✓ indexed" not in both
        # The error already says "none of the 7"; a note saying "7 of 7" beside
        # it would be the same fact twice.
        assert "of %d registries could not be tapped" % len(seven) not in both

    def test_every_tap_failing_beside_an_existing_index_still_fails(
            self, boost, monkeypatch, seven):
        # Items from an earlier run are real — so they are reported, not
        # called empty — but this run tapped nothing it set out to.
        _fake_add_many(monkeypatch, ["fail"] * len(seven), entries=500)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert "✓ indexed 500 items" in both
        assert "the 500 items already indexed are unaffected" in both

    @staticmethod
    def _unreadable(tap):
        from boost_cli.errors import BoostError
        raise BoostError("catalog unreadable")

    def test_clones_that_cannot_be_indexed_are_not_blamed_on_the_network(
            self, boost, monkeypatch, seven):
        # Every clone arrived and add_many configured it; only the index
        # failed. "Could not be tapped … check the network" was wrong on both
        # counts, and a rerun would skip every one as already tapped.
        _fake_add_many(monkeypatch, ["ok"] * len(seven), entries=0,
                       index=self._unreadable)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert "could not index %s: catalog unreadable" % seven[0] in both
        assert ("not ready — none of the %d registries could be indexed, so "
                "nothing is searchable" % len(seven)) in both
        assert "configured, so a rerun skips them" in both
        assert "`boost doctor` names what each one is missing" in both
        assert "could be tapped" not in both
        assert "network" not in both

    def test_clones_that_cannot_be_indexed_beside_an_existing_index(
            self, boost, monkeypatch, seven):
        _fake_add_many(monkeypatch, ["ok"] * len(seven), entries=500,
                       index=self._unreadable)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert ("none of the %d registries could be indexed; the 500 items "
                "already indexed are unaffected" % len(seven)) in both
        assert "network" not in both

    def test_clone_and_index_failures_together_name_both_remedies(
            self, boost, monkeypatch, seven):
        _fake_add_many(monkeypatch, ["fail"] + ["ok"] * (len(seven) - 1),
                       entries=0, index=self._unreadable)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert ("none of the %d registries could be set up: 1 could not be "
                "tapped and %d could not be indexed"
                % (len(seven), len(seven) - 1)) in both
        assert "check the network" in both
        assert ("`boost doctor` names what each registry that could not be "
                "indexed is missing") in both

    def test_one_unindexable_registry_is_named_as_such_and_exits_clean(
            self, boost, monkeypatch, seven):
        from boost_cli.errors import BoostError

        def first_unreadable(tap):
            if tap.name == seven[0]:
                raise BoostError("catalog unreadable")
            return [{"name": "x"}]

        _fake_add_many(monkeypatch, ["ok"] * len(seven),
                       index=first_unreadable)
        res = boost("quickstart", "--no-vectors", expect=0)
        both = _flat(res.out + res.err)
        assert ("1 of %d registries could not be indexed: %s"
                % (len(seven), seven[0])) in both
        assert "could not be tapped" not in both
        assert "ready — try `boost search brainstorming`" in both

    def test_one_bad_registry_is_named_at_the_end_and_still_exits_clean(
            self, boost, monkeypatch, seven):
        _fake_add_many(monkeypatch, ["fail"] + ["ok"] * (len(seven) - 1))
        res = boost("quickstart", "--no-vectors", expect=0)
        both = _flat(res.out + res.err)
        assert "ready — try `boost search brainstorming`" in both
        # Named twice: once as it happened, once where the eye lands.
        assert "could not tap %s: repository not found" % seven[0] in both
        assert ("1 of %d registries could not be tapped: %s"
                % (len(seven), seven[0])) in both

    def test_a_rerun_with_everything_already_tapped_exits_clean(
            self, boost, monkeypatch, seven):
        # The trap: add_many answers `skipped` for all seven, so zero results
        # carry ok=True on a machine that is perfectly set up.
        _fake_add_many(monkeypatch, ["skip"] * len(seven), entries=42)
        res = boost("quickstart", "--no-vectors", expect=0)
        both = res.out + res.err
        assert "ready — try `boost search brainstorming`" in both
        assert "could not be tapped" not in both

    def test_a_top_up_whose_only_new_registry_fails_exits_clean(
            self, boost, monkeypatch, seven):
        # Six already here, the seventh 404s: nothing cloned this run, but the
        # machine is set up, so this is a partial failure and not a total one.
        _fake_add_many(monkeypatch, ["skip"] * (len(seven) - 1) + ["fail"])
        res = boost("quickstart", "--no-vectors", expect=0)
        both = _flat(res.out + res.err)
        assert ("1 of %d registries could not be tapped: %s"
                % (len(seven), seven[-1])) in both
        assert "ready — try `boost search brainstorming`" in both

    def test_registries_that_arrive_empty_are_not_ready(
            self, boost, monkeypatch, seven):
        _fake_add_many(monkeypatch, ["ok"] * len(seven), entries=0)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert "✓ indexed 0 items" not in both
        assert "not ready — the keyword index is empty" in both
        assert "boost doctor" in both

    def test_a_clean_run_prints_exactly_what_it_printed_before(
            self, boost, monkeypatch, seven):
        """No failure, no change — the regression guard on the happy path."""
        _fake_add_many(monkeypatch, ["ok"] * len(seven))
        res = boost("quickstart", "--no-vectors", expect=0)
        lines = [ln for ln in (res.out + res.err).splitlines() if ln.strip()]
        assert lines == (
            ["  ✓ tapped %s (1 items)" % n for n in seven]
            + ["  ✓ indexed 3 items for keyword search",
               "  skipped vectors as asked",
               "  ✓ ready — try `boost search brainstorming`"])

    def test_a_dry_run_claims_no_readiness_either_way(self, boost):
        # It changed nothing, so it has nothing to be ready or unready about.
        res = boost("quickstart", "--dry-run", expect=0)
        assert "ready" not in res.out + res.err


class TestQuickstartReadinessOverRealClones:
    """The same verdict with nothing faked: real `add_many`, real index.

    The registries are local paths — the fixture tap, and a path that does not
    exist — so a clone genuinely succeeds or genuinely fails, offline.
    """

    @pytest.fixture()
    def registries(self, monkeypatch):
        from boost_cli.core import config

        def use(*urls):
            monkeypatch.setattr(config, "DEFAULT_TAPS",
                                [{"name": "r%d" % i, "url": str(u)}
                                 for i, u in enumerate(urls)])
        return use

    def test_no_reachable_registry_exits_one_and_search_agrees(
            self, boost, registries, tmp_path):
        registries(tmp_path / "gone-a", tmp_path / "gone-b")
        res = boost("quickstart", "--no-vectors", expect=1)
        assert "not ready" in res.out + res.err
        # The command README runs next reaches the same verdict.
        boost("search", "brainstorming", expect=1)

    def test_a_reachable_registry_beside_a_dead_one_is_ready(
            self, boost, registries, fixture_tap_src, tmp_path):
        registries(fixture_tap_src, tmp_path / "gone")
        res = boost("quickstart", "--no-vectors", expect=0)
        both = _flat(res.out + res.err)
        assert "1 of 2 registries could not be tapped" in both
        assert "ready — try `boost search brainstorming`" in both

    def test_a_real_clone_that_will_not_index_is_configured_not_offline(
            self, boost, registries, fixture_tap_src, monkeypatch):
        # The premise of the index-failure hint, over the real add_many and
        # the real rebuild_tap. Its one BoostError today is "not cloned", so
        # the clone is taken away between the two — the clone succeeded, the
        # registry is in the config, and the network was never the problem.
        import shutil

        from boost_cli.core import catalog, registry
        real = catalog.rebuild_tap

        def clone_gone(tap):
            shutil.rmtree(tap.path)
            return real(tap)

        registries(fixture_tap_src)
        monkeypatch.setattr(catalog, "rebuild_tap", clone_gone)
        res = boost("quickstart", "--no-vectors", expect=1)
        both = _flat(res.out + res.err)
        assert "is not cloned" in both
        assert "the registry could not be indexed" in both
        assert "none of the 1" not in both
        assert "`boost doctor` names what it is missing" in both
        assert "network" not in both
        # Configured by add_many before the index ran — which is why a rerun
        # skips it, and why the hint sends the user to doctor instead.
        assert [t.name for t in registry.list_taps()] == ["fixture-tap"]
        # And doctor does name the fix, as the hint promises.
        doctor = _flat(boost("doctor", expect=None).out)
        assert "tap fixture-tap not cloned — run `boost update`" in doctor

    def test_a_rerun_over_a_working_machine_stays_ready(
            self, boost, registries, fixture_tap_src):
        registries(fixture_tap_src)
        boost("quickstart", "--no-vectors", expect=0)
        res = boost("quickstart", "--no-vectors", expect=0)
        assert "already tapped" in res.out + res.err
        assert "ready — try `boost search brainstorming`" in res.out + res.err


class TestFetchShards:
    def test_no_taps_is_a_clear_error_not_a_fetch(self, boost, manifest):
        res = boost("reindex", "--fetch-shards", expect=1)
        assert "no taps configured" in (res.out + res.err)

    def test_a_space_mismatch_is_refused_with_the_one_next_action(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        boost("tap", str(fixture_tap_src))
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "voyage")
        monkeypatch.setattr(embed, "model", lambda: "voyage-4")
        monkeypatch.setattr(embed, "dimension", lambda: 1024)
        res = boost("reindex", "--fetch-shards", expect=1)
        both = res.out + res.err
        # Named before any download: the 129 MB it did not spend is the point.
        assert "cannot serve this machine" in both
        assert "1024" in both or "voyage" in both

    def test_a_space_mismatch_names_the_free_path_beside_the_paid_one(
            self, boost, fixture_tap_src, manifest, keyed_machine):
        # The hint was `dense.fix_hint(status reason)`, a table about the
        # store, which for this user answered "install the extra" — which
        # they have. The remedy for a refused manifest is the manifest's.
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards", expect=1)
        both = _flat(res.out + res.err)
        assert "`unset VOYAGE_API_KEY`" in both
        assert "`boost reindex --dense`" in both and "paid" in both
        assert keyed_machine == []

    def test_a_store_built_with_the_key_is_not_told_to_unset_it(
            self, boost, fixture_tap_src, manifest, keyed_machine,
            vector_store):
        # The free path is a refused import for this user, and a paid store
        # knocked offline on the way there.
        boost("tap", str(fixture_tap_src))
        assert vector_store()["ready"]
        res = boost("reindex", "--fetch-shards", expect=1)
        both = _flat(res.out + res.err)
        assert "unset" not in both
        assert "cannot merge" in both
        assert "`boost reindex --dense` keeps them current" in both
        assert "--force" not in both
        assert keyed_machine == []

    def test_a_tap_with_no_published_shard_is_reported_not_embedded(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards")
        # Not a tick: nothing landed, and this user's vectors are still missing.
        assert "no published vectors" in (res.out + res.err)
        # The remedy is offered, never taken on the user's behalf.
        assert "reindex --dense" in res.out

    def test_json_output_lists_every_tap_and_its_status(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        from boost_cli.core import embed
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards", "--json")
        data = json.loads(res.out)
        assert [r["status"] for r in data["shards"]] == ["unpublished"]

    def test_a_tap_already_built_at_the_published_commit_is_not_redownloaded(
            self, boost, manifest, monkeypatch):
        """A rerun must not re-pay for a shard the store already holds.

        This is the bug the card describes: `sync` used to have no `built`
        map at all, so every rerun of `--fetch-shards` re-downloaded every
        shard unconditionally, even one imported moments before.
        """
        from boost_cli.core import dense, embed, rag, registry, shards
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        monkeypatch.setattr(registry, "list_taps",
                            lambda: [registry.Tap(name="a/b", url="file:///x")])
        monkeypatch.setattr(rag, "_tap_commits", lambda: {"a__b": "1" * 40})
        monkeypatch.setattr(dense, "tap_commits", lambda: {"a__b": "1" * 40})

        def boom(*a, **k):
            raise AssertionError("sync must not download an already-current shard")
        monkeypatch.setattr(shards, "download", boom)

        res = boost("reindex", "--fetch-shards")
        assert "already up to date" in res.out
        # Never reported as a tap that still needs local embedding.
        assert "reindex --dense" not in res.out

    def test_imported_and_current_shards_are_both_reported(
            self, boost, fixture_tap_src, manifest, monkeypatch):
        """A run that imports some and finds the rest current has two things
        to say, and must say both.

        The first cut of this reporting chained them as `if got / elif
        current`, so the already-up-to-date line vanished the moment anything
        imported — which is the common case on a partial refresh, and the one
        case where the count of what was skipped is worth the most.
        """
        from boost_cli.core import embed, shards
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)
        monkeypatch.setattr(shards, "sync", lambda *a, **k: [
            {"tap": "a/b", "status": "imported", "chunks": 12},
            {"tap": "c/d", "status": "current"},
        ])
        boost("tap", str(fixture_tap_src))
        res = boost("reindex", "--fetch-shards")
        assert "imported 1 shard(s)" in res.out
        assert "1 shard(s) already up to date" in res.out
        # Neither status is a gap, so neither earns the local-embed remedy.
        assert "reindex --dense" not in res.out


class TestTapAt:
    """`--at` is what makes a shard importable; a bad pin must not tap HEAD."""

    def test_an_abbreviated_sha_is_refused(self, boost, fixture_tap_src):
        res = boost("tap", str(fixture_tap_src), "--at", "abc1234", expect=1)
        assert "full commit SHA" in (res.out + res.err)

    def test_at_without_a_spec_is_a_usage_error(self, boost):
        res = boost("tap", "--defaults", "--at", "a" * 40, expect=2)
        assert "SPEC" in (res.out + res.err)

    def test_a_real_pin_lands_the_tap_at_that_commit(self, boost,
                                                     fixture_tap_src):
        from boost_cli.core import gitutil, registry
        head = gitutil.head_commit(fixture_tap_src)
        boost("tap", str(fixture_tap_src), "--at", head)
        tap = registry.list_taps()[0]
        assert gitutil.head_commit(tap.path) == head

    def test_a_pin_that_cannot_be_honoured_leaves_no_tap_behind(
            self, boost, fixture_tap_src):
        from boost_cli.core import registry
        # A well-formed SHA that does not exist in the repo: the clone succeeds
        # and the checkout cannot, and a tap silently left on HEAD would have
        # every shard refused later for a reason three steps away.
        boost("tap", str(fixture_tap_src), "--at", "b" * 40, expect=1)
        assert registry.list_taps() == []


class TestTheShardDownloadIsNamed:
    """Before and during: what the shard step downloads, in one phrase.

    The dry run printed "import 459 shard(s)" and never the 1.5 GB those rows
    add up to, though it had already read the manifest that carries every
    row's `bytes`; the live run then downloaded them with no line at all
    until the last one landed. And the preview counted every tap with a row,
    so on a rerun over current vectors it promised imports the run skipped.
    `defaults_manifest` gives each of the seven defaults a 4-byte row.
    """

    @pytest.fixture()
    def keyless(self, monkeypatch):
        from boost_cli.core import dense, embed
        monkeypatch.setattr(dense, "have_backend", lambda: True)
        monkeypatch.setattr(embed, "provider", lambda: "local")
        monkeypatch.setattr(embed, "model", lambda: SPACE["model"])
        monkeypatch.setattr(embed, "dimension", lambda: 384)

    @staticmethod
    def _configured(monkeypatch, at, built=None):
        """Taps already configured: name -> commit, and the store's commits."""
        from boost_cli.core import dense, rag, registry
        monkeypatch.setattr(registry, "list_taps", lambda: [
            registry.Tap(name=n, url="file:///x") for n in at])
        monkeypatch.setattr(rag, "_tap_commits", lambda: {
            n.replace("/", "__"): c for n, c in at.items()})
        monkeypatch.setattr(dense, "tap_commits", lambda: {
            n.replace("/", "__"): c for n, c in (built or {}).items()})

    def _live(self, boost, monkeypatch, built=None):
        """A live run whose seven taps land at their pins; downloads faked."""
        from boost_cli.core import config, dense, shards
        _fake_add_many(monkeypatch, ["ok"] * 7)
        self._configured(monkeypatch,
                         {str(d["name"]): "1" * 40 for d in config.DEFAULT_TAPS},
                         built)
        fetched: list = []

        def download(row, dest, manifest, timeout=300.0):
            fetched.append(row["tap"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("{}", encoding="utf-8")
            return dest

        monkeypatch.setattr(shards, "download", download)
        monkeypatch.setattr(dense, "import_shard",
                            lambda shard, commit="": (True, ""))
        return boost("quickstart"), fetched

    def test_the_dry_run_names_what_the_import_downloads(
            self, boost, sandbox, defaults_manifest, keyless):
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 7 shard(s) (28B)" in out
        # Planning reads the tap caches and the vector store; it writes
        # neither, and taps nothing.
        assert not (sandbox / ".boost" / "repos").exists()
        assert not (sandbox / ".boost" / "cache" / "rag_vectors.sqlite").exists()

    def test_the_catalog_dry_run_sums_only_rows_for_taps_it_will_tap(
            self, boost, defaults_manifest, keyless):
        from boost_cli.core import config
        catalogued = {e["name"] for e in config.load_registry_catalog()
                      if not e.get("list_only")}
        rows = sum(1 for d in config.DEFAULT_TAPS if d["name"] in catalogued)
        out = _flat(boost("quickstart", "--catalog", "--dry-run").out)
        assert "then import %d shard(s) (%dB)" % (rows, 4 * rows) in out

    def test_a_shard_already_built_is_not_counted_or_sized(
            self, boost, defaults_manifest, keyless, monkeypatch):
        at = {"anthropics/skills": "1" * 40}
        self._configured(monkeypatch, at, built=at)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 6 shard(s) (24B)" in out
        assert "1 shard already up to date — nothing to fetch" in out

    def test_a_tap_that_moved_past_its_row_is_not_counted(
            self, boost, defaults_manifest, keyless, monkeypatch):
        self._configured(monkeypatch, {"anthropics/skills": "2" * 40})
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 6 shard(s) (24B)" in out
        assert "1 tap(s) moved past their vectors" in out
        assert "`boost update --shards`" in out

    def test_a_rerun_over_current_vectors_plans_nothing_and_says_why(
            self, boost, defaults_manifest, keyless, monkeypatch):
        from boost_cli.core import config
        at = {str(d["name"]): "1" * 40 for d in config.DEFAULT_TAPS}
        self._configured(monkeypatch, at, built=at)
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 0 shard(s)" in out
        assert "import 0 shard(s) (" not in out
        assert "7 shards already up to date — nothing to fetch" in out
        # Every tap has a row: the zero is not the manifest's.
        assert "none of these registries have a published shard" not in out

    def test_every_tap_moved_is_a_zero_the_manifest_is_not_blamed_for(
            self, boost, defaults_manifest, keyless, monkeypatch):
        from boost_cli.core import config
        self._configured(monkeypatch, {str(d["name"]): "2" * 40
                                       for d in config.DEFAULT_TAPS})
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 0 shard(s)" in out
        assert "7 tap(s) moved past their vectors" in out
        assert "none of these registries have a published shard" not in out

    def test_a_registry_not_tapped_yet_is_judged_at_its_pin(
            self, boost, defaults_manifest, keyless, monkeypatch):
        # The store still holds vectors for a registry that is not tapped
        # (untapped, say). The live run taps it at its pin, finds them
        # current and fetches nothing; judged at "" the preview would count
        # a download that never happens.
        self._configured(monkeypatch, {},
                         built={"anthropics/skills": "1" * 40})
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 6 shard(s) (24B)" in out
        assert "1 shard already up to date" in out

    def test_a_row_without_a_size_makes_the_total_a_floor(
            self, boost, defaults_manifest, keyless):
        data = json.loads(defaults_manifest.read_text(encoding="utf-8"))
        del data["shards"][0]["bytes"]
        defaults_manifest.write_text(json.dumps(data), encoding="utf-8")
        out = _flat(boost("quickstart", "--dry-run").out)
        assert "then import 7 shard(s) (at least 24B)" in out

    def test_the_live_run_says_what_it_fetches_and_counts_each_one(
            self, boost, defaults_manifest, keyless, monkeypatch):
        from boost_cli.core import config
        res, fetched = self._live(boost, monkeypatch)
        lines = [ln.strip() for ln in res.out.splitlines()]
        names = [str(d["name"]) for d in config.DEFAULT_TAPS]
        assert fetched == names
        head = lines.index("fetching 7 shard(s) (28B)")
        # One numbered line per download, in order, after the total.
        assert lines[head + 1:head + 8] == [
            "fetching %s 4B (%d/7)" % (n, i) for i, n in enumerate(names, 1)]
        assert "imported 7 prebuilt shards" in res.out

    def test_the_dry_run_and_the_live_run_agree(
            self, boost, defaults_manifest, keyless, monkeypatch):
        at = {"anthropics/skills": "1" * 40}
        self._configured(monkeypatch, at, built=at)
        dry = _flat(boost("quickstart", "--dry-run").out)
        res, fetched = self._live(boost, monkeypatch, built=at)
        planned = re.search(r"then import (\d+ shard\(s\) \([^)]*\))",
                            dry).group(1)
        assert "fetching %s" % planned in _flat(res.out)
        assert planned.startswith("%d shard(s)" % len(fetched))

    def test_a_single_download_is_announced_too(
            self, boost, defaults_manifest, keyless, monkeypatch):
        from boost_cli.core import config
        at = {str(d["name"]): "1" * 40 for d in config.DEFAULT_TAPS[1:]}
        res, fetched = self._live(boost, monkeypatch, built=at)
        lines = [ln.strip() for ln in res.out.splitlines()]
        assert fetched == [str(config.DEFAULT_TAPS[0]["name"])]
        assert "fetching 1 shard(s) (4B)" in lines
        assert "fetching %s 4B (1/1)" % fetched[0] in lines

    def test_a_live_run_with_nothing_to_fetch_prints_no_fetch_line(
            self, boost, defaults_manifest, keyless, monkeypatch):
        from boost_cli.core import config
        at = {str(d["name"]): "1" * 40 for d in config.DEFAULT_TAPS}
        res, fetched = self._live(boost, monkeypatch, built=at)
        assert fetched == []
        assert "fetching" not in res.out
        assert "7 shards already up to date" in res.out

    def test_progress_is_one_line_per_download_and_nothing_else(self, capsys):
        from boost_cli.commands import quickstart
        event = quickstart._progress(3)
        for status in ("current", "unpublished", "refused", "failed",
                       "imported"):
            event("a/b", status, "detail")
        assert capsys.readouterr().out == ""
        event("a/b", "downloading", "")
        event("c/d", "downloading", "1.0KB")
        assert [ln.strip() for ln in capsys.readouterr().out.splitlines()] == [
            "fetching a/b (1/3)", "fetching c/d 1.0KB (2/3)"]
