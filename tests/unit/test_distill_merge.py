# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: commands/intelligence.py — `_distill_merge`'s heuristic merge.

`_distill_merge` dedupes exact-duplicate body lines across the skills being
merged. The dedupe used to be line-blind: a global `seen` set dropped every
repeat, including structural lines a fenced code block or a Markdown table
needs to repeat verbatim (closing ``` fences, lone `}`/`);` lines, `---`
rules, table separator rows) — corrupting the merged SKILL.md into an
unterminated code block. These tests pin that fences stay balanced and
structural lines survive, while genuine prose duplicates still collapse.
"""
from __future__ import annotations

from boost_cli.commands import intelligence


def _source(name, body, description="d"):
    return {"name": name, "origin": "tap", "text": "",
            "meta": {"description": description}, "body": body}


def _count_fences(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("```"))


class TestDistillMergeFences:
    def test_repeated_closing_fences_all_survive(self):
        # Each source independently opens and closes several fenced blocks
        # with the same fence markers/content — the global seen-set used to
        # drop every repeat after the first, unbalancing the fences.
        body_a = "\n".join([
            "intro",
            "```bash",
            "echo one",
            "```",
            "```bash",
            "echo two",
            "```",
        ])
        body_b = "\n".join([
            "other intro",
            "```bash",
            "echo three",
            "```",
            "```bash",
            "echo four",
            "```",
        ])
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert _count_fences(merged) % 2 == 0
        assert "echo one" in merged and "echo four" in merged

    def test_dedupe_inside_a_fence_is_disabled(self):
        # A code line that happens to repeat verbatim *inside* a fenced
        # block must not be dropped either — only prose outside fences dedupes.
        body_a = "\n".join(["```python", "x = 1", "```"])
        body_b = "\n".join(["```python", "x = 1", "```"])
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert merged.count("x = 1") == 2
        assert _count_fences(merged) == 4

    def test_structural_lines_survive_repetition(self):
        body_a = "\n".join(["```dot", "digraph {", "}", "```", "---"])
        body_b = "\n".join(["```dot", "digraph {", "}", "```", "---"])
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert merged.count("}") == 2
        assert merged.count("---") >= 2
        assert _count_fences(merged) == 4

    def test_table_separator_rows_survive_repetition(self):
        body_a = "\n".join(["| a | b |", "| --- | --- |", "| 1 | 2 |"])
        body_b = "\n".join(["| a | b |", "| --- | --- |", "| 3 | 4 |"])
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert merged.count("| --- | --- |") == 2

    def test_genuine_prose_duplicates_still_dedupe(self):
        # The dedupe's actual purpose — repeated *prose* lines outside any
        # fence still collapse to one occurrence.
        body_a = "shared rule: always write tests first"
        body_b = "shared rule: always write tests first"
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert merged.count("shared rule: always write tests first") == 1

    def test_unclosed_fence_in_one_source_does_not_leak_into_next(self):
        # Fence state is per-source: a malformed/unbalanced source must not
        # put the next source's lines inside a phantom fence.
        body_a = "```python\nx = 1"
        body_b = "plain prose line"
        merged = intelligence._distill_merge(
            "new", [_source("a", body_a), _source("b", body_b)])
        assert "plain prose line" in merged


class TestIsStructuralLine:
    def test_recognizes_fence_and_brace_and_rule(self):
        assert intelligence._is_structural_line("```")
        assert intelligence._is_structural_line("---")
        assert intelligence._is_structural_line("}")
        assert intelligence._is_structural_line(");")

    def test_recognizes_table_separator_row(self):
        assert intelligence._is_structural_line("| --- | --- |")
        assert intelligence._is_structural_line("|---|---|")

    def test_does_not_flag_ordinary_prose(self):
        assert not intelligence._is_structural_line("always write tests first")
        assert not intelligence._is_structural_line("x = 1")
