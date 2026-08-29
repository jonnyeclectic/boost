# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Web ↔ CLI palette lockstep (BOOST-D20).

Enforces that the CLI's single source of truth, ``output.TOKENS``, stays in
lockstep with the web design system's tokens in ``style/boost.css``. If a hex
is changed in one place and not the other, this test fails.

Skips when ``style/boost.css`` isn't reachable (e.g. the mutation sandbox,
which only copies ``boost_cli/``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from boost_cli.core import output

_CSS = Path(__file__).resolve().parents[2] / "style" / "boost.css"


@pytest.mark.skipif(not _CSS.exists(),
                    reason="style/boost.css not reachable (e.g. mutation sandbox)")
def test_cli_tokens_match_style_css():
    text = _CSS.read_text(encoding="utf-8")
    for name, rgb in output.TOKENS.items():
        m = re.search(r"--%s:\s*#([0-9a-fA-F]{6})" % name, text)
        assert m, "style/boost.css is missing a --%s token" % name
        css_rgb = tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        assert css_rgb == rgb, (
            "palette drift: output.TOKENS[%r]=%r but style/boost.css --%s=#%s"
            % (name, rgb, name, m.group(1)))
