#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Generate ``docs/commands.html`` — the browsable command reference.

Every command is rendered from the CLI's *own* definitions —
``boost_cli.cli.COMMANDS`` (the single source of truth for name/group/summary)
plus an introspection of each command's argparse parser — so the reference can
never drift from the code. Regenerated exactly like the roadmap:

    python3 scripts/build_command_reference.py            # write docs/commands.html
    python3 scripts/build_command_reference.py --check    # fail (exit 1) on drift

The ``--check`` form runs in CI and in tests/unit/test_command_reference_fresh.py.

Why introspect the parser instead of scraping ``--help`` text: argparse's
*formatted* help is Python-version-dependent ("optional arguments:" pre-3.10,
the short/long option layout changed in 3.13), which would make a byte-exact
drift check flake across the 3.9/3.12/3.14 test matrix. The parser's action
attributes (``option_strings``, ``help``, ``choices``, ``nargs``) are stable, so
we read those and do our own formatting.
"""
from __future__ import annotations

import argparse
import contextlib
import html
import importlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Import boost_cli without an editable install (CI's lint job has none — same as
# the eval gate's PYTHONPATH=.).
sys.path.insert(0, str(ROOT))

from boost_cli import cli, cliparse  # noqa: E402  (after sys.path shim)

OUT = ROOT / "docs" / "commands.html"

# Friendly section headings for the CLI's terse group codes; unknown groups fall
# back to a title-cased code so a newly-added group still renders.
GROUP_LABELS = {
    "pkg": "Install &amp; lifecycle",
    "find": "Find &amp; search",
    "info": "Inspect &amp; explain",
    "tap": "Taps &amp; registries",
    "ai": "AI-assisted",
    "chk": "Health &amp; integrity",
    "cfg": "Config &amp; setup",
    "team": "Team &amp; sharing",
}


def _capture_parser(name: str, module: str):
    """Return the ArgumentParser a command builds (by spying on cliparse.parser).

    Calls ``cmd_*(["--help"])`` so the command builds its parser and argparse
    raises SystemExit *before* any command logic runs; the parser it created is
    recorded by the spy. Output is swallowed — this has no side effects.
    """
    fn = "cmd_" + name.replace("-", "_")
    mod = importlib.import_module("boost_cli.commands.%s" % module)
    created: list = []
    real = cliparse.parser

    def spy(*a, **k):
        p = real(*a, **k)
        created.append(p)
        return p

    cliparse.parser = spy
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
                contextlib.suppress(SystemExit):
            getattr(mod, fn)(["--help"])
    finally:
        cliparse.parser = real
    return created[0] if created else None  # main parser is created first


def _metavar(act) -> str:
    if act.metavar:
        return act.metavar
    if act.choices:
        return "{%s}" % ",".join(str(c) for c in act.choices)
    return act.dest.upper() if act.option_strings else act.dest


def _positional_syn(act) -> str:
    mv = _metavar(act)
    n = act.nargs
    if n == "?":
        return "[%s]" % mv
    if n == "*" or n == argparse.REMAINDER:
        return "[%s ...]" % mv
    if n == "+":
        return "%s [%s ...]" % (mv, mv)
    if isinstance(n, int):
        return " ".join([mv] * n)
    return mv


def _visible_actions(parser):
    """Positional and optional actions worth documenting (drops -h and hidden)."""
    pos, opt = [], []
    for act in parser._actions:
        if isinstance(act, argparse._HelpAction) or act.help == argparse.SUPPRESS:
            continue
        (opt if act.option_strings else pos).append(act)
    return pos, opt


def _extract(name: str, group: str, module: str, summary: str) -> dict:
    parser = _capture_parser(name, module)
    prog = parser.prog if parser else "boost %s" % name
    description = (parser.description or "").strip() if parser else ""
    pos, opt = _visible_actions(parser) if parser else ([], [])

    syn = [prog]
    for act in opt:
        flag = act.option_strings[-1]
        syn.append("[%s]" % (flag if act.nargs == 0 else "%s %s" % (flag, _metavar(act))))
    syn.extend(_positional_syn(act) for act in pos)

    def rows(actions, is_opt):
        out = []
        for act in actions:
            if is_opt:
                label = ", ".join(act.option_strings)
                if act.nargs != 0:
                    label += " " + _metavar(act)
            else:
                label = _metavar(act)
            out.append((label, (act.help or "").strip()))
        return out

    return {
        "name": name, "group": group, "summary": summary,
        # description repeats summary for most commands — only show it if it adds info
        "description": description if description and description != summary else "",
        "synopsis": " ".join(syn),
        "positionals": rows(pos, False),
        "options": rows(opt, True),
    }


def _grouped() -> list[tuple[str, str, list[dict]]]:
    order: list[str] = []
    by_group: dict[str, list[dict]] = {}
    for name, group, module, summary in cli.COMMANDS:
        if group not in by_group:
            by_group[group] = []
            order.append(group)
        by_group[group].append(_extract(name, group, module, summary))
    return [(g, GROUP_LABELS.get(g, g.title()), by_group[g]) for g in order]


def _rows_html(rows) -> str:
    out = []
    for label, help_ in rows:
        out.append(
            '          <div class="arg"><code>%s</code><span>%s</span></div>'
            % (html.escape(label), html.escape(help_)))
    return "\n".join(out)


def render() -> str:
    groups = _grouped()
    total = sum(len(items) for _g, _l, items in groups)

    nav, body = [], []
    for code, label, items in groups:
        nav.append('    <div class="group" data-group="%s">' % code)
        nav.append('      <div class="group-h">%s</div>' % label)
        body.append('      <h2 class="group-h" id="grp-%s">%s</h2>' % (code, label))
        for c in items:
            search = html.escape(
                (" ".join([c["name"], c["summary"], c["description"]]
                          + [label for label, _h in c["options"] + c["positionals"]])).lower(),
                quote=True)
            nav.append(
                '      <a class="cmd-link" href="#cmd-%s" data-search="%s">%s</a>'
                % (c["name"], search, html.escape(c["name"])))

            sec = ['      <section class="cmd" id="cmd-%s" data-search="%s">'
                   % (c["name"], search)]
            sec.append('        <h3><span class="cname">%s</span>'
                       '<span class="gtag">%s</span></h3>' % (html.escape(c["name"]), code))
            sec.append('        <p class="summary">%s</p>' % html.escape(c["summary"]))
            sec.append('        <pre class="syn">%s</pre>' % html.escape(c["synopsis"]))
            if c["description"]:
                sec.append('        <p class="desc">%s</p>' % html.escape(c["description"]))
            if c["positionals"]:
                sec.append('        <div class="args-h">Arguments</div>')
                sec.append('        <div class="args">')
                sec.append(_rows_html(c["positionals"]))
                sec.append('        </div>')
            if c["options"]:
                sec.append('        <div class="args-h">Options</div>')
                sec.append('        <div class="args">')
                sec.append(_rows_html(c["options"]))
                sec.append('        </div>')
            sec.append('      </section>')
            body.append("\n".join(sec))
        nav.append('    </div>')

    return _PAGE % {"total": total, "nav": "\n".join(nav), "body": "\n".join(body)}


# This page used to re-declare the whole palette inline, and it had drifted:
# --text-2 was #a6a9c4 against the sheet's #9298b0, there was no --text-3 at
# all, and the footer chrome was a second copy of rules style/boost.css already
# owns. It now links the shared sheet like every other docs page and keeps only
# what is genuinely local — the sidebar app-shell layout and the command cards.
_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>boost — command reference</title>
<link rel="icon" href="data:image/svg+xml,%%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%%3E%%3Crect width='100' height='100' rx='20' fill='%%2307080f'/%%3E%%3Ctext x='50' y='70' font-size='58' font-family='monospace' font-weight='bold' fill='%%2340cbe3' text-anchor='middle'%%3E%%E2%%9C%%A6%%3C/text%%3E%%3C/svg%%3E">
<!-- Linked before the block below, so a page-local rule still wins at equal
     specificity. Tokens, reset, atmosphere, focus ring and footer come from
     here; nothing about the palette is retyped on this page. -->
<link rel="stylesheet" href="../style/boost.css">
<style>
  /* Denser than a prose page: this is a reference you scan, not read. */
  body { font-size: 15px; }
  a { color: var(--cyan); text-decoration: none; }

  /* An app shell, not a document — a sticky command index beside a scrolling
     body — so .wrap is a flex row here rather than the shared centred column.
     The gutter has to be zeroed explicitly; <aside> and <main> bring their own. */
  .wrap { display: flex; max-width: 1200px; margin: 0 auto; padding: 0; }
  aside { width: 268px; flex: none; border-right: 1px solid var(--line);
          padding: 22px 16px 40px; position: sticky; top: 0; align-self: flex-start;
          height: 100vh; overflow-y: auto; }
  .brand { display: flex; align-items: baseline; gap: 8px; }
  .brand b { font-family: var(--mono); font-size: 18px; color: var(--cyan);
             letter-spacing: -.02em; }
  .brand span { font-size: 11px; color: var(--text-2); }
  .home { display: inline-block; margin: 4px 0 14px; font-size: 12px; color: var(--text-2); }
  #q { width: 100%%; padding: 9px 11px; border-radius: 9px; border: 1px solid var(--line);
       background: var(--surface-1); color: var(--text); font-family: var(--sans);
       font-size: 13.5px; margin-bottom: 14px; }
  /* Was `#q:focus { outline: none }`, which removed the focus ring for keyboard
     users too. Tint the border on any focus; leave the shared ring alone. */
  #q:focus { border-color: var(--cyan); }
  .group { margin-bottom: 14px; }
  .group-h { font-family: var(--mono); font-size: 10.5px; font-weight: 700;
             letter-spacing: .16em; text-transform: uppercase; color: var(--violet);
             margin: 0 0 6px; }
  .cmd-link { display: block; padding: 3px 8px; border-radius: 7px; font-family: var(--mono);
              font-size: 13px; color: var(--text-2); }
  .cmd-link:hover { background: var(--surface-2); color: var(--text); }
  #nohits { display: none; color: var(--text-2); font-size: 13px; padding: 6px 8px; }
  main { flex: 1; min-width: 0; padding: 26px 30px 80px; }
  h1 { font-size: 25px; margin: 0 0 4px; letter-spacing: -.02em; }
  /* The page's one gradient. Everything else reads in ink. */
  h1 b { background: var(--grad); -webkit-background-clip: text; background-clip: text;
         -webkit-text-fill-color: transparent; }
  h1 b::selection { -webkit-text-fill-color: var(--text); background: rgb(64 203 227 / 28%%); }
  .lead { color: var(--text-2); margin: 0 0 8px; font-size: 14px; }
  .lead b { color: var(--cyan); font-family: var(--mono); }
  main .group-h { margin: 30px 0 12px; font-size: 11px; }
  section.cmd { border: 1px solid var(--line); border-radius: 13px; background: var(--surface-1);
                box-shadow: inset 0 1px 0 0 rgb(255 255 255 / 6%%),
                            inset 0 -1px 0 0 rgb(0 0 0 / 30%%);
                padding: 16px 18px; margin-bottom: 14px; scroll-margin-top: 16px; }
  section.cmd h3 { margin: 0 0 6px; display: flex; align-items: center; gap: 10px; }
  .cname { font-family: var(--mono); font-size: 16px; color: var(--cyan); }
  .gtag { font-family: var(--mono); font-size: 10px; font-weight: 700; letter-spacing: .1em;
          text-transform: uppercase; color: var(--text-2); border: 1px solid var(--line);
          border-radius: 999px; padding: 2px 8px; }
  .summary { margin: 0 0 10px; color: var(--text); font-size: 14px; }
  pre.syn { margin: 0 0 10px; padding: 11px 14px; border-radius: 9px; background: var(--term-bg);
            border: 1px solid var(--line); overflow-x: auto; font-size: 12.5px; color: var(--cyan);
            white-space: pre-wrap; word-break: break-word; }
  .desc { margin: 0 0 12px; color: var(--text-2); font-size: 13.5px; }
  .args-h { font-family: var(--mono); font-size: 10.5px; font-weight: 700; letter-spacing: .14em;
            text-transform: uppercase; color: var(--text-2); margin: 12px 0 6px; }
  .args { display: grid; gap: 6px; }
  /* minmax(0, 1fr), not 1fr: a grid track defaults to min-width:auto, so it
     refuses to shrink below its widest unbreakable word. argparse renders a
     choice list as one comma-joined brace token with no spaces in it, and the
     longest here is 68 characters —
     {install,init,startup,orient,uninstall,disable,enable,doctor,status} —
     which offers the line breaker nothing to break on. That one cell sized the
     track and gave the whole page 241px of horizontal scroll at 320px wide,
     171px at 390px and 61px at 768px. The pairing with overflow-wrap below is
     deliberate: the track may now shrink, so the token has to be allowed to
     break mid-word, or it simply overflows its own cell instead of the page.
     pre.syn already carries the same pair; .arg was the one that missed it. */
  .arg { display: grid; grid-template-columns: minmax(120px, 34%%) minmax(0, 1fr);
         gap: 14px; align-items: baseline; }
  .arg code { color: var(--cyan); font-size: 12.5px; overflow-wrap: anywhere; }
  .arg span { color: var(--text); font-size: 13.5px; overflow-wrap: anywhere; }
  @media (max-width: 760px) {
    .wrap { flex-direction: column; } aside { width: auto; height: auto; position: static;
    border-right: none; border-bottom: 1px solid var(--line); }
    .arg { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  }

  /* The footer used to be a second copy of style/boost.css's footer rules,
     drifted (opacity instead of --text-3, --amber instead of --sky). The markup
     already used the shared class names, so the copy is simply gone. */
</style>
</head>
<body>
<a class="skip" href="#top">Skip to content</a>
<div class="wrap">
  <aside>
    <div class="brand"><b>✦ boost</b><span>commands</span></div>
    <a class="home" href="index.html">← back to overview</a>
    <input id="q" type="search" placeholder="Filter %(total)d commands…" autocomplete="off" aria-label="Filter commands">
%(nav)s
    <div id="nohits">No commands match.</div>
  </aside>
  <main id="top">
    <h1>boost <b>command reference</b></h1>
    <p class="lead">All <b>%(total)d</b> commands, generated from the CLI itself —
       run <code>boost &lt;command&gt; --help</code> for the same in your terminal.</p>
%(body)s
  </main>
</div>

<footer>
  <p class="foot-brand"><b>boost</b> &mdash; a package manager for AI coding skills</p>
  <p class="foot-note">Install with <code>pip install boost-skill-cli</code> &middot; requires Python 3.12+ and <code>git</code></p>
  <nav class="foot-links" aria-label="Documentation">
    <a href="index.html">Guide</a>
    <a href="#top" aria-current="page">Commands</a>
    <a href="demo.html">Try the search</a>
    <a href="chat.html">How chat works</a>
    <a href="mcp-hub.html">MCP Hub</a>
    <a href="eval.html">Evaluation</a>
    <a href="adapters.html">Adapters</a>
    <a href="langchain.html">LangChain</a>
    <a href="roadmap.html">Roadmap</a>
    <a href="design-roadmap.html">Design</a>
    <a href="carousel.html">Carousel</a>
  </nav>
  <p class="foot-legal">
    <a href="https://github.com/jonnyeclectic/boost">GitHub</a> &middot;
    <a href="https://pypi.org/project/boost-skill-cli/">PyPI</a> &middot;
    <a href="https://jonnyeclectic.github.io/portfolio/">Portfolio</a> &middot;
    Released under the GPL-3.0 license
  </p>
</footer>
<script>
  (function () {
    var q = document.getElementById('q');
    var links = [].slice.call(document.querySelectorAll('.cmd-link'));
    var secs = [].slice.call(document.querySelectorAll('section.cmd'));
    var groups = [].slice.call(document.querySelectorAll('aside .group'));
    var nohits = document.getElementById('nohits');
    function apply() {
      var t = q.value.toLowerCase().trim(), hits = 0;
      secs.forEach(function (s) {
        s.style.display = (!t || s.getAttribute('data-search').indexOf(t) !== -1) ? '' : 'none';
      });
      links.forEach(function (a) {
        var on = !t || a.getAttribute('data-search').indexOf(t) !== -1;
        a.style.display = on ? '' : 'none';
        if (on) hits++;
      });
      groups.forEach(function (g) {
        var any = [].slice.call(g.querySelectorAll('.cmd-link'))
                    .some(function (a) { return a.style.display !== 'none'; });
        g.style.display = any ? '' : 'none';
      });
      nohits.style.display = hits ? 'none' : 'block';
    }
    q.addEventListener('input', apply);
  })();
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the command reference (docs/commands.html).")
    parser.add_argument(
        "--check", action="store_true",
        help="verify committed HTML matches a fresh render; exit 1 on drift.")
    args = parser.parse_args(argv)

    fresh = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != fresh:
            print(
                "ERROR: docs/commands.html is out of date — regenerate with\n"
                "    python3 scripts/build_command_reference.py\n"
                "and commit the result (see CONTRIBUTING.md).",
                file=sys.stderr)
            return 1
        print("command reference is up to date.")
        return 0
    OUT.write_text(fresh, encoding="utf-8")
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
