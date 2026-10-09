# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""`scripts/measure_keyword_index.py`: the table behind shrink-the-published-index.

The script rebuilds one store in every layout boost's postings have had and
times each against the golden queries. The numbers it prints are only worth
quoting if every layout holds the *same* postings and reads them back the
same, so that is what these pin, on a tiny store built by boost itself.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from boost_cli.core import rag

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "measure_keyword_index.py"

POSTINGS = {"react": [[0, 2], [3, 1]], "test": [[0, 1], [1, 3], [300, 200]],
            "solo": [[2, 1]]}


@pytest.fixture(scope="module")
def mki():
    spec = importlib.util.spec_from_file_location("measure_keyword_index",
                                                  _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def queries(tmp_path):
    f = tmp_path / "golden.jsonl"
    f.write_text("# comment\n\n"
                 + json.dumps({"query": "React test"}) + "\n"
                 + json.dumps({"query": "solo missing"}) + "\n"
                 + json.dumps({"query": "!!"}) + "\n", encoding="utf-8")
    return f


@pytest.mark.parametrize("layout", ["rows-text", "rows-interned",
                                    "blob-delta-varint"])
def test_every_layout_round_trips_and_is_detected(mki, tmp_path, layout):
    path = tmp_path / "s.sqlite"
    mki.WRITERS[layout](path, POSTINGS)
    con = sqlite3.connect(str(path))
    try:
        assert mki.detect_layout(con) == layout
        assert mki.read_terms(con, layout, ["test", "nope"]) == {
            "test": POSTINGS["test"]}
        assert mki.read_terms(con, layout, []) == {}
    finally:
        con.close()
    assert mki.load_postings(path) == POSTINGS


def test_the_blob_layout_is_the_one_boost_writes(mki, tmp_path, sandbox):
    """`write_blob` must measure the shipped writer, not a copy of it."""
    rag._write_postings(POSTINGS)
    mine = tmp_path / "b.sqlite"
    mki.write_blob(mine, POSTINGS)

    def dump(p):
        con = sqlite3.connect(str(p))
        try:
            return (con.execute("SELECT sql FROM sqlite_master ORDER BY name")
                    .fetchall(),
                    con.execute("SELECT * FROM terms ORDER BY id").fetchall(),
                    con.execute("SELECT * FROM postings ORDER BY term_id")
                    .fetchall())
        finally:
            con.close()
    assert dump(mine) == dump(rag.postings_path())


def test_an_unknown_store_is_refused(mki, tmp_path):
    path = tmp_path / "x.sqlite"
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE postings (a, b)")
        with pytest.raises(ValueError, match="not a boost postings store"):
            mki.detect_layout(con)
    finally:
        con.close()


def test_query_terms_tokenize_and_skip_comments_and_empty_queries(
        mki, queries):
    assert mki.query_terms([queries]) == [["react", "test"],
                                          ["solo", "missing"]]


@pytest.mark.parametrize("codec", ["none", "gzip-6"])
def test_codecs_round_trip(mki, codec):
    data = b"postings " * 1000
    cells = mki.codec_cells(data, codec)
    assert cells["codec"] == codec
    assert mki.decompress(mki.compress(data, codec), codec) == data
    if codec == "none":
        assert cells["bytes"] == len(data)
    else:
        assert cells["bytes"] < len(data)
        assert cells["ratio"] > 1


def test_zstd_round_trips_when_available(mki):
    if not mki.codec_available("zstd-3"):
        pytest.skip("no zstd on this machine")
    data = b"postings " * 1000
    assert mki.decompress(mki.compress(data, "zstd-3"), "zstd-3") == data


def test_an_unavailable_codec_reports_no_size(mki, monkeypatch):
    monkeypatch.setattr(mki, "_zstd_module", lambda: None)
    monkeypatch.setattr(mki.shutil, "which", lambda _n: None)
    assert mki.codec_available("zstd-19") is False
    assert mki.codec_cells(b"x", "zstd-19") == {"codec": "zstd-19",
                                                "bytes": None}


def test_unknown_codecs_are_errors(mki):
    assert mki.codec_available("brotli") is False
    with pytest.raises(ValueError, match="unknown codec"):
        mki.compress(b"x", "brotli")
    with pytest.raises(ValueError, match="unknown codec"):
        mki.decompress(b"x", "brotli")


def test_measure_reports_every_layout_and_the_blob_is_smallest(
        mki, tmp_path, queries):
    # Enough postings that per-row overhead, not page rounding, decides size.
    big = {"t%d" % t: [[d, 1 + d % 3] for d in range(t % 7, 4000, 3)]
           for t in range(40)}
    big["react"] = [[0, 2]]
    src = tmp_path / "src.sqlite"
    mki.write_rows_interned(src, big)
    index = tmp_path / "rag_index.json"
    index.write_text(json.dumps({"docs": []}), encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    report = mki.measure(src, work, list(mki.LAYOUTS), ["none", "gzip-6"],
                         mki.query_terms([queries]), index=index)
    assert report["source"]["terms"] == 41
    assert report["source"]["postings"] == sum(len(v) for v in big.values())
    sizes = {r["layout"]: r["bytes"] for r in report["layouts"]}
    assert set(sizes) == set(mki.LAYOUTS)
    assert sizes["blob-delta-varint"] < sizes["rows-interned"] \
        < sizes["rows-text"]
    for row in report["layouts"]:
        assert row["reads"]["queries"] == 2
        assert [c["codec"] for c in row["codecs"]] == ["none", "gzip-6"]
    assert report["docs_json"]["bytes"] == index.stat().st_size
    md = mki.render_markdown(report)
    assert "| blob-delta-varint |" in md
    assert "41 terms" in md
    assert "rag_index.json" in md


def test_measure_refuses_layouts_that_read_different_postings(
        mki, tmp_path, queries, monkeypatch):
    src = tmp_path / "src.sqlite"
    mki.write_rows_interned(src, POSTINGS)
    real = mki.read_terms

    def lying(con, layout, terms):
        got = real(con, layout, terms)
        if layout == "blob-delta-varint" and "react" in got:
            got["react"] = [[0, 99]]
        return got
    monkeypatch.setattr(mki, "read_terms", lying)
    with pytest.raises(RuntimeError, match="different postings"):
        mki.measure(src, tmp_path, ["rows-interned", "blob-delta-varint"],
                    ["none"], mki.query_terms([queries]))


def test_main_prints_a_table_and_never_writes_the_source(
        mki, tmp_path, queries, capsys):
    src = tmp_path / "src.sqlite"
    mki.write_rows_interned(src, POSTINGS)
    before = src.read_bytes()
    rc = mki.main(["--store", str(src), "--index", str(tmp_path / "none"),
                   "--queries", str(queries), "--codecs", "none",
                   "--workdir", str(tmp_path / "w")])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("\n| ") == 4         # header + 3 layouts
    assert src.read_bytes() == before


def test_main_json_and_missing_store(mki, tmp_path, queries, capsys,
                                    sandbox):
    src = tmp_path / "src.sqlite"
    mki.write_blob(src, POSTINGS)
    rc = mki.main(["--store", str(src), "--queries", str(queries),
                   "--codecs", "none", "--layouts", "blob-delta-varint",
                   "--workdir", str(tmp_path / "w"), "--json"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert [r["layout"] for r in report["layouts"]] == ["blob-delta-varint"]
    assert mki.main(["--store", str(tmp_path / "absent.sqlite")]) == 2


def test_main_rejects_an_unknown_layout(mki, sandbox):
    with pytest.raises(SystemExit):
        mki.main(["--layouts", "rows-text,bogus"])
