"""Unit tests: scripts/a11y_check.py — the WCAG 2.1 AA gate for the docs pages.

The gate itself only reports what it finds, so these pin that it *finds* the
right things: every rule fires on a page that violates it and stays quiet on one
that does not, and the contrast math matches the WCAG reference values.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "a11y_check.py"

spec = importlib.util.spec_from_file_location("a11y_check", SCRIPT)
a11y = importlib.util.module_from_spec(spec)
sys.modules["a11y_check"] = a11y
spec.loader.exec_module(a11y)


def _audit(html, tmp_path):
    page = tmp_path / "page.html"
    page.write_text(html, encoding="utf-8")
    return a11y.audit_page(page)


def _rules(findings):
    return sorted({rule for _line, rule, _msg in findings})


GOOD = """<!doctype html><html lang="en"><body>
<h1>Title</h1><h2>Section</h2><h3>Sub</h3>
<a href="/x">a link</a>
<button>press</button>
<img src="a.png" alt="a picture">
<label for="q">Query</label><input id="q" type="text">
</body></html>"""


class TestCleanPage:
    def test_a_conforming_page_has_no_findings(self, tmp_path):
        assert _audit(GOOD, tmp_path) == []


class TestStructuralRules:
    def test_missing_lang(self, tmp_path):
        assert "html-has-lang" in _rules(_audit(
            "<!doctype html><html><body><h1>T</h1></body></html>", tmp_path))

    def test_empty_lang_counts_as_missing(self, tmp_path):
        assert "html-has-lang" in _rules(_audit(
            '<html lang="  "><body><h1>T</h1></body></html>', tmp_path))

    def test_image_without_alt(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<img src="x.png"></body></html>', tmp_path)
        assert "image-alt" in _rules(found)

    def test_empty_alt_is_allowed(self, tmp_path):
        # alt="" is the correct markup for a decorative image, not a failure.
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<img src="x.png" alt=""></body></html>', tmp_path)
        assert "image-alt" not in _rules(found)

    def test_link_without_a_name(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<a href="/x"></a></body></html>', tmp_path)
        assert "link-name" in _rules(found)

    def test_link_named_by_aria_label(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<a href="/x" aria-label="home"></a></body></html>', tmp_path)
        assert "link-name" not in _rules(found)

    def test_button_without_a_name(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<button></button></body></html>', tmp_path)
        assert "button-name" in _rules(found)

    def test_button_named_by_aria_label(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<button aria-label="close"></button></body></html>', tmp_path)
        assert "button-name" not in _rules(found)

    def test_duplicate_id(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<p id="a"></p><p id="a"></p></body></html>', tmp_path)
        assert "duplicate-id" in _rules(found)

    def test_unique_ids_are_fine(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<p id="a"></p><p id="b"></p></body></html>', tmp_path)
        assert "duplicate-id" not in _rules(found)

    def test_unlabelled_input(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<input type="text"></body></html>', tmp_path)
        assert "form-label" in _rules(found)

    def test_hidden_and_submit_inputs_are_exempt(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1>'
                       '<input type="hidden"><input type="submit">'
                       '</body></html>', tmp_path)
        assert "form-label" not in _rules(found)


class TestHeadingOrder:
    def test_skipped_level_is_flagged(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1><h3>S</h3></body></html>',
                       tmp_path)
        assert "heading-order" in _rules(found)

    def test_the_message_names_the_missing_level(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>T</h1><h3>S</h3></body></html>',
                       tmp_path)
        message = next(m for _l, r, m in found if r == "heading-order")
        assert "skips h2" in message

    def test_descending_levels_are_fine(self, tmp_path):
        html = ('<html lang="en"><body><h1>T</h1><h2>A</h2><h3>B</h3>'
                '<h2>C</h2></body></html>')
        assert "heading-order" not in _rules(_audit(html, tmp_path))

    def test_missing_h1(self, tmp_path):
        found = _audit('<html lang="en"><body><h2>S</h2></body></html>', tmp_path)
        assert "page-has-h1" in _rules(found)

    def test_two_h1s(self, tmp_path):
        found = _audit('<html lang="en"><body><h1>A</h1><h1>B</h1></body></html>',
                       tmp_path)
        assert "page-has-h1" in _rules(found)


class TestContrastMath:
    def test_black_on_white_is_21(self):
        assert round(a11y.contrast("#000000", "#ffffff"), 2) == 21.0

    def test_identical_colors_are_1(self):
        assert round(a11y.contrast("#7f7f7f", "#7f7f7f"), 2) == 1.0

    def test_is_symmetric(self):
        assert a11y.contrast("#22d3ee", "#07080f") == a11y.contrast("#07080f", "#22d3ee")

    def test_shorthand_hex_expands(self):
        assert a11y.contrast("#fff", "#000") == a11y.contrast("#ffffff", "#000000")

    def test_luminance_endpoints(self):
        assert a11y.luminance("#000000") == 0.0
        assert a11y.luminance("#ffffff") == 1.0

    def test_aa_floor_is_the_wcag_value(self):
        assert a11y.AA_NORMAL == 4.5


class TestTokenReading:
    def test_reads_hex_tokens(self):
        assert a11y.read_tokens(":root { --bg: #07080f; --text: #e9ebf5; }") == {
            "--bg": "#07080f", "--text": "#e9ebf5"}

    def test_skips_non_hex_values(self):
        tokens = a11y.read_tokens(
            ":root { --bg: #07080f; --panel: rgb(255 255 255 / 3.5%); "
            "--grad: linear-gradient(96deg, red, blue); }")
        assert list(tokens) == ["--bg"]

    def test_shorthand_hex_is_read(self):
        assert a11y.read_tokens(":root { --x: #abc; }") == {"--x": "#abc"}


class TestContrastGate:
    def test_the_real_stylesheet_passes(self):
        css = (ROOT / "style" / "boost.css").read_text(encoding="utf-8")
        assert a11y.check_contrast(css) == []

    def test_a_failing_pair_is_reported(self):
        # --text-3's predecessor (#676d86, 3.9:1) is the exact regression this
        # guards: it shipped below AA and was fixed to #767c96.
        css = ":root { --bg: #07080f; --text-3: #676d86; }"
        findings = a11y.check_contrast(css)
        assert any(r == "contrast" and "--text-3" in m for _l, r, m in findings)

    def test_a_missing_token_is_reported(self):
        findings = a11y.check_contrast(":root { --bg: #07080f; }")
        assert any("no longer exists" in m for _l, _r, m in findings)

    def test_every_declared_pair_names_real_tokens(self):
        css = (ROOT / "style" / "boost.css").read_text(encoding="utf-8")
        tokens = a11y.read_tokens(css)
        for ink, ground in a11y.PAIRS:
            assert ink in tokens, ink
            assert ground in tokens, ground


class TestRuleRegistry:
    def test_every_rule_has_a_description(self):
        for rule, description in a11y.RULES.items():
            assert description and rule.islower()

    @pytest.mark.parametrize("rule", sorted(a11y.RULES))
    def test_rule_cites_a_wcag_criterion(self, rule):
        assert "WCAG" in a11y.RULES[rule]


class TestEntryPoint:
    def test_list_flag_exits_zero(self, capsys):
        assert a11y.main(["--list"]) == 0
        assert "heading-order" in capsys.readouterr().out

    def test_the_repo_passes_its_own_gate(self, capsys):
        assert a11y.main([]) == 0
        assert "OK" in capsys.readouterr().out
