"""pytest-benchmark suite for perf-sensitive core paths + a few CLI commands
end-to-end. Opt-in (`make bench`) — not part of `make check`. Deliberately
small fixtures (the shared fixture-tap, 5 items) so the suite stays cheap.
"""
from __future__ import annotations

import contextlib
import io

from boost_cli.core import catalog, rag


def _cli(argv):
    """boost_cli.cli.main, stdout/stderr swallowed so benchmark rounds stay quiet."""
    from boost_cli.cli import main
    with contextlib.redirect_stdout(io.StringIO()), \
            contextlib.redirect_stderr(io.StringIO()):
        try:
            return main(argv)
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 0


def test_catalog_scan_dir(benchmark, fixture_tap_src):
    result = benchmark(catalog.scan_dir, fixture_tap_src, "bench-tap")
    assert len(result) == 5  # the fixture's 5 SKILL.md skills


def test_rag_build(benchmark, boost, tapped):
    entries = catalog.all_entries()
    assert entries
    stats = benchmark(rag.build, entries, force=True)
    assert stats["docs"] >= 1


def test_rag_retrieve(benchmark, boost, tapped):
    rag.build(force=True)

    def _search():
        return rag.retrieve("commit messages", k=10)

    hits = benchmark(_search)
    assert hits
    assert any(h["entry"]["name"] == "commit-messages" for h in hits)


def test_cli_search_end_to_end(benchmark, boost, tapped):
    rc = benchmark(_cli, ["search", "commit", "messages"])
    assert rc == 0


def test_cli_count_end_to_end(benchmark, boost, tapped):
    rc = benchmark(_cli, ["count"])
    assert rc == 0


def test_cli_list_end_to_end(benchmark, boost, installed):
    rc = benchmark(_cli, ["list"])
    assert rc == 0
