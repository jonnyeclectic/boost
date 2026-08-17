"""Content identity: the digest a catalog entry carries, and who trusts it.

The whole design rests on one invariant — a catalog entry's ``content`` is the
same string ``rag.read_body`` would hash for that entry. If the two ever
assemble their text differently the digest keeps *looking* right while silently
clustering nothing, so the parity is pinned directly rather than inferred from
behaviour.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from boost_cli.core import browse, catalog, rag


def _write_skill(root, rel, name, description, body, version="1.0.0"):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: %s\nversion: %s\n---\n%s"
        % (name, description, version, body),
        encoding="utf-8")
    return d


def _digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8", "replace")).hexdigest()[:16]


# --------------------------------------------------------------- scan digest

def test_scan_dir_stamps_a_content_digest(tmp_path):
    _write_skill(tmp_path, "skills/alpha", "alpha", "does alpha things", "# Alpha\nbody\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    assert len(entries) == 1
    assert entries[0]["content"], "every scanned entry carries a content digest"
    assert len(entries[0]["content"]) == 16


def test_digest_matches_rag_read_body_exactly(tmp_path, monkeypatch):
    """The invariant. ``content`` must equal what rag hashes for the same item."""
    _write_skill(tmp_path, "skills/alpha", "alpha", "does alpha things",
                 "# Alpha\n\nA longer body with *markdown* and a list:\n- one\n- two\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    e = entries[0]
    # read_body resolves the file through the tap's clone dir; point it here.
    monkeypatch.setattr(rag, "_tap_paths", lambda: {"t/one": tmp_path})
    assert e["content"] == _digest(rag.read_body(e))


def test_identical_bodies_in_one_tap_share_a_digest(tmp_path):
    body = "# Same\n\nidentical content\n"
    _write_skill(tmp_path, "skills/a", "dup", "one description", body)
    _write_skill(tmp_path, "plugins/pack/skills/a", "dup", "one description", body)
    entries = catalog.scan_dir(tmp_path, "t/one")
    assert len({e["content"] for e in entries}) == 1


def test_same_name_and_description_different_body_differ(tmp_path):
    """Key C's failure: these two must NOT collapse."""
    _write_skill(tmp_path, "skills/a", "twin", "same description", "# A\nalpha body\n")
    _write_skill(tmp_path, "skills/b", "twin", "same description", "# B\nbeta body\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    assert len({e["content"] for e in entries}) == 2


def test_same_body_different_description_differ(tmp_path):
    """Name and description are inside the digest, so metadata separates them."""
    body = "# Same\nidentical prose\n"
    _write_skill(tmp_path, "skills/a", "twin", "description one", body)
    _write_skill(tmp_path, "skills/b", "twin", "description two", body)
    entries = catalog.scan_dir(tmp_path, "t/one")
    assert len({e["content"] for e in entries}) == 2


def test_digest_survives_text_that_cannot_be_encoded(tmp_path):
    """A lone surrogate must yield a digest, not kill the tap's whole scan.

    `_make_entry` calls this on every file a scan touches, so an exception here
    is not one bad entry — it aborts `scan_dir` and the tap indexes as empty.
    Registry Markdown is arbitrary third-party text, and a lone surrogate is
    exactly what a mis-decoded file leaves behind, so the encode is lossy on
    purpose. This is what the `errors=` argument buys, and nothing else pins it.
    """
    bad = "lead \ud800 surrogate"
    digest = catalog._content_digest(bad, "d", "body")
    assert len(digest) == 16
    assert digest == catalog._content_digest(bad, "d", "body")
    # The replacement is lossy: an un-encodable char becomes "?", so a lone
    # surrogate collides with a literal "?" in the same position. That is the
    # price of not raising, and it is the right trade — the alternative is
    # losing a whole tap's catalogue to one mis-decoded file. Everything
    # outside the damaged char still separates normally.
    assert digest == catalog._content_digest("lead ? surrogate", "d", "body")
    assert digest != catalog._content_digest(bad, "d", "other body")


def test_rules_and_workflows_carry_a_digest_too(tmp_path):
    (tmp_path / "rules").mkdir(parents=True)
    (tmp_path / "rules" / "r.mdc").write_text(
        "---\nname: r\ndescription: a rule\n---\nrule body\n", encoding="utf-8")
    (tmp_path / "commands").mkdir(parents=True)
    (tmp_path / "commands" / "w.md").write_text(
        "---\nname: w\ndescription: a workflow\ntools: [Bash]\n---\nflow body\n",
        encoding="utf-8")
    entries = catalog.scan_dir(tmp_path, "t/one")
    kinds = {e["kind"]: e for e in entries}
    assert set(kinds) == {"rule", "workflow"}
    for e in entries:
        assert e["content"], "%s entries carry a digest" % e["kind"]


# ------------------------------------------------------------- cache format

def _cloned_tap(name="t/one"):
    """A Tap whose clone dir exists and holds one skill."""
    from boost_cli.core import registry
    tap = registry.Tap(name=name, url="https://example.invalid/x", curated=False)
    tap.path.mkdir(parents=True, exist_ok=True)
    _write_skill(tap.path, "skills/alpha", "alpha", "d", "body\n")
    return tap


def test_cache_carries_a_format_version(sandbox):
    tap = _cloned_tap()
    catalog.rebuild_tap(tap)
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    assert data["format"] == catalog.CACHE_FORMAT


def test_cache_without_format_is_treated_as_stale(sandbox):
    """The backfill mechanism: 460 caches predate the digest and must rescan."""
    tap = _cloned_tap()
    catalog.rebuild_tap(tap)
    # Simulate an old cache: no format key, entries with no digest.
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    data.pop("format", None)
    for e in data["skills"]:
        e.pop("content", None)
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    skills, current = catalog._cached_tap(tap)
    assert current is False, "an unversioned cache reports itself stale"
    assert skills, "but its entries are still readable"


def test_cache_with_no_skills_key_reads_as_empty_not_none(sandbox):
    """A truncated cache is an empty catalogue, never a `None` handed onward.

    `_cached_tap`'s return value goes straight to callers that iterate it, so a
    missing key must land on `[]` — otherwise a half-written cache (an
    interrupted `boost tap`) takes down every command that reads that tap
    instead of the one tap reading as empty.
    """
    tap = _cloned_tap()
    tap.cache_file.parent.mkdir(parents=True, exist_ok=True)
    tap.cache_file.write_text(
        json.dumps({"tap": tap.name, "format": catalog.CACHE_FORMAT}),
        encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    skills, current = catalog._cached_tap(tap)
    assert skills == []
    assert current is True


def test_stale_cache_is_served_when_the_clone_is_gone(sandbox):
    """Never trade a missing digest for a missing catalogue."""
    import shutil
    tap = _cloned_tap()
    catalog.rebuild_tap(tap)
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    data.pop("format", None)
    for e in data["skills"]:
        e.pop("content", None)
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    shutil.rmtree(tap.path)
    catalog._ENTRY_CACHE.clear()
    entries = catalog.load_tap(tap)
    assert len(entries) == 1, "entries survive even though they carry no digest"
    assert "content" not in entries[0]


def test_stale_cache_is_rescanned_and_regains_the_digest(sandbox):
    """End to end: load_tap heals an old cache rather than returning it."""
    tap = _cloned_tap()
    catalog.rebuild_tap(tap)
    data = json.loads(tap.cache_file.read_text(encoding="utf-8"))
    data.pop("format", None)
    for e in data["skills"]:
        e.pop("content", None)
    tap.cache_file.write_text(json.dumps(data), encoding="utf-8")
    catalog._ENTRY_CACHE.clear()
    entries = catalog.load_tap(tap)
    assert entries and entries[0]["content"]
    assert json.loads(tap.cache_file.read_text(
        encoding="utf-8"))["format"] == catalog.CACHE_FORMAT


def test_cache_with_current_format_is_trusted(sandbox):
    tap = _cloned_tap()
    catalog.rebuild_tap(tap)
    catalog._ENTRY_CACHE.clear()
    skills, current = catalog._cached_tap(tap)
    assert current is True
    assert skills[0]["content"]


# ---------------------------------------------------------------- rag reuse

def test_make_docs_reuses_a_present_digest(tmp_path, monkeypatch):
    """rag must not re-read 60k files to recompute a value it was handed."""
    _write_skill(tmp_path, "skills/alpha", "alpha", "d", "# Alpha\nbody text here\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    reads = []
    real = rag.read_body

    def counting(entry, tap_paths=None):
        reads.append(entry["name"])
        return real(entry, tap_paths)

    monkeypatch.setattr(rag, "read_body", counting)
    docs = rag._make_docs(entries, {"t/one": tmp_path})
    assert docs[0]["h"] == entries[0]["content"]


def test_make_docs_computes_a_missing_digest(tmp_path):
    """A stale cache still indexes correctly, with the same hash."""
    _write_skill(tmp_path, "skills/alpha", "alpha", "d", "# Alpha\nbody text here\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    want = entries[0]["content"]
    stripped = [{k: v for k, v in entries[0].items() if k != "content"}]
    docs = rag._make_docs(stripped, {"t/one": tmp_path})
    assert docs[0]["h"] == want


def test_make_docs_takes_the_stored_digest_over_recomputing(tmp_path):
    """The stored value wins outright — that is the whole saving.

    Reuse and recompute agree on every real entry, which is the invariant this
    file exists to pin, and it also means neither path can be observed through
    the other. Forcing them apart is the only way to show the read actually
    happens rather than the fallback quietly running 60k times.
    """
    _write_skill(tmp_path, "skills/alpha", "alpha", "d", "# Alpha\nbody text\n")
    entries = catalog.scan_dir(tmp_path, "t/one")
    entries[0]["content"] = "0123456789abcdef"
    docs = rag._make_docs(entries, {"t/one": tmp_path})
    assert docs[0]["h"] == "0123456789abcdef"


def test_make_docs_skips_an_unindexable_entry_without_dropping_the_rest():
    """One item that tokenizes to nothing must not truncate the whole index.

    Real catalogues carry entries whose file is gone and whose metadata is a
    bare punctuation name, so this is not hypothetical — and the failure is
    silent: every entry after it simply stops being searchable.
    """
    blank = {"name": "!!", "description": "", "tap": "t/one", "skill_md": "a.md"}
    good = {"name": "alpha", "description": "real words", "tap": "t/one",
            "skill_md": "b.md"}
    docs = rag._make_docs([blank, good], {})
    assert [d["n"] for d in docs] == ["alpha"]
    assert docs[0]["c"] == 0, "one document per entry, at chunk zero"


def test_make_docs_fallback_survives_unencodable_text(tmp_path):
    """The recompute path meets the same broken bytes the scanner does."""
    entry = {"name": "odd \ud800 name", "description": "d", "tap": "t/one",
             "skill_md": "a.md"}
    docs = rag._make_docs([entry], {})
    assert len(docs) == 1 and len(docs[0]["h"]) == 16


# ------------------------------------------------------------------- browse

def test_browse_dedupe_collapses_on_the_digest():
    a = {"name": "x", "description": "d", "content": "aaaaaaaaaaaaaaaa"}
    b = {"name": "y", "description": "other", "content": "aaaaaaaaaaaaaaaa"}
    out = browse.dedupe([a, b])
    assert len(out) == 1
    assert out[0][1] == 2


def test_browse_dedupe_keeps_distinct_bodies_under_one_name():
    """The key-C regression: same name+description, different content."""
    a = {"name": "twin", "description": "same", "content": "aaaaaaaaaaaaaaaa"}
    b = {"name": "twin", "description": "same", "content": "bbbbbbbbbbbbbbbb"}
    out = browse.dedupe([a, b])
    assert len(out) == 2


def test_browse_dedupe_falls_back_without_a_digest():
    a = {"name": "twin", "description": "same"}
    b = {"name": "twin", "description": "same"}
    out = browse.dedupe([a, b])
    assert len(out) == 1 and out[0][1] == 2


def test_browse_dedupe_never_merges_digested_with_undigested():
    """Two unknowns must not collapse into a known, which would hide a row."""
    a = {"name": "twin", "description": "same", "content": "aaaaaaaaaaaaaaaa"}
    b = {"name": "twin", "description": "same"}
    out = browse.dedupe([a, b])
    assert len(out) == 2


def test_browse_fallback_key_is_case_insensitive():
    """`Code-Reviewer` and `code-reviewer` are one item wearing two shirts.

    Registries re-case names and descriptions freely when they mirror, so the
    fallback key normalises both halves. Asserted on `_sig` rather than through
    `dedupe`, because `dedupe`'s fuzzy pass would also merge these and so could
    not tell a working key from a broken one.
    """
    a = {"name": "Code-Reviewer", "description": "Reviews Code"}
    b = {"name": "code-reviewer", "description": "reviews code"}
    assert browse._sig(a) == browse._sig(b)


def test_browse_fallback_treats_a_missing_key_as_empty():
    """Absent and empty are the same absence — and neither is the word "None".

    The `.get` defaults are what makes that true. Get one wrong and a row with
    no name keys on the literal string `"none"`, which is a name a real
    registry ships, so two unrelated rows would silently become one.
    """
    absent = {"description": "d"}
    empty = {"name": "", "description": "d"}
    literal = {"name": "None", "description": "d"}
    assert browse._sig(absent) == browse._sig(empty)
    assert browse._sig(absent) != browse._sig(literal)

    absent_d = {"name": "n"}
    empty_d = {"name": "n", "description": ""}
    literal_d = {"name": "n", "description": "None"}
    assert browse._sig(absent_d) == browse._sig(empty_d)
    assert browse._sig(absent_d) != browse._sig(literal_d)


def test_browse_dedupe_keeps_first_occurrence_order():
    rows = [{"name": "a", "description": "1", "content": "1111111111111111"},
            {"name": "b", "description": "2", "content": "2222222222222222"},
            {"name": "a2", "description": "1", "content": "1111111111111111"}]
    out = browse.dedupe(rows)
    assert [e["name"] for e, _ in out] == ["a", "b"]
    assert [n for _, n in out] == [2, 1]


# ------------------------------------------------------- cross-tap resolve

def _entry(tap, name, content, rel="skills/x", curated=False):
    return {"name": name, "description": "d", "version": "1.0.0", "tap": tap,
            "curated": curated, "kind": "skill", "rel_dir": rel,
            "skill_md": rel + "/SKILL.md", "meta": {}, "content": content,
            "search_blob": ""}


def test_resolve_one_picks_a_copy_when_taps_agree_on_content(monkeypatch):
    """A mirrored skill is installable unqualified: there is nothing to choose."""
    a = _entry("owner/one", "mirror", "cccccccccccccccc")
    b = _entry("owner/two", "mirror", "cccccccccccccccc")
    monkeypatch.setattr(catalog, "find", lambda name: [a, b])
    got = catalog.resolve_one("mirror")
    assert got["content"] == "cccccccccccccccc"
    assert got["tap"] == "owner/one"


def test_same_thing_breaks_a_rank_tie_on_the_tap_name(monkeypatch):
    """Equal-ranked mirrors must not resolve to whichever `find` listed first.

    `find`'s order follows the tap iteration order, which follows the config
    file — so without a tie-break the same command installs a different copy on
    two machines holding the same taps in a different order.
    """
    rows = [_entry("owner/zeta", "mirror", "cccccccccccccccc"),
            _entry("owner/alpha", "mirror", "cccccccccccccccc"),
            _entry("owner/mid", "mirror", "cccccccccccccccc")]
    assert catalog._same_thing(rows)["tap"] == "owner/alpha"
    assert catalog._same_thing(list(reversed(rows)))["tap"] == "owner/alpha"


def test_same_thing_breaks_a_tap_tie_on_the_path(monkeypatch):
    """Last resort: same rank, same tap, so only the path can decide."""
    rows = [_entry("owner/one", "mirror", "cccccccccccccccc", rel="skills/z"),
            _entry("owner/one", "mirror", "cccccccccccccccc", rel="skills/a")]
    assert catalog._same_thing(rows)["rel_dir"] == "skills/a"
    assert catalog._same_thing(list(reversed(rows)))["rel_dir"] == "skills/a"


def test_same_thing_sorts_a_missing_key_as_empty_not_as_a_word():
    """A synthesised entry carries neither key, and must sort as absent.

    The `.get` defaults are load-bearing here: get one wrong and a keyless row
    sorts under the literal `"None"`, which puts it in the middle of the tap
    names instead of at the front — so the pick depends on what the other taps
    happen to be called.
    """
    keyless = {"content": "cccccccccccccccc", "name": "mirror"}
    rows = [_entry("AAA/one", "mirror", "cccccccccccccccc"), keyless]
    assert catalog._same_thing(rows) is keyless

    no_path = {"content": "cccccccccccccccc", "name": "mirror",
               "tap": "owner/one"}
    rows = [_entry("owner/one", "mirror", "cccccccccccccccc", rel="AAA"),
            no_path]
    assert catalog._same_thing(rows) is no_path


def test_resolve_one_prefers_the_curated_tap(monkeypatch):
    a = _entry("owner/one", "mirror", "cccccccccccccccc", curated=False)
    b = _entry("owner/two", "mirror", "cccccccccccccccc", curated=True)
    monkeypatch.setattr(catalog, "find", lambda name: [a, b])
    assert catalog.resolve_one("mirror")["tap"] == "owner/two"


def test_resolve_one_still_raises_when_content_differs(monkeypatch):
    from boost_cli.errors import BoostError
    a = _entry("owner/one", "mirror", "cccccccccccccccc")
    b = _entry("owner/two", "mirror", "dddddddddddddddd")
    monkeypatch.setattr(catalog, "find", lambda name: [a, b])
    with pytest.raises(BoostError) as ei:
        catalog.resolve_one("mirror")
    assert "multiple taps" in str(ei.value)


def test_resolve_one_still_raises_when_a_digest_is_missing(monkeypatch):
    """An unknown must never be assumed equal to a known."""
    from boost_cli.errors import BoostError
    a = _entry("owner/one", "mirror", "cccccccccccccccc")
    b = _entry("owner/two", "mirror", "cccccccccccccccc")
    del b["content"]
    monkeypatch.setattr(catalog, "find", lambda name: [a, b])
    with pytest.raises(BoostError):
        catalog.resolve_one("mirror")
