---
id: command-carousel-page
board: code
section: docsite
status: shipped
category: Docs · Design system
complexity: M
impact: Med
wow: 4
note: 8 GIFs · one flagship per group
order: 14
owner: loop/carousel
pr:
title: A GIF carousel touring one flagship command per group
---
<code>README</code> shipped a single <code>demo.gif</code> and the guide described
78 commands entirely in prose — nothing showed what a boost session actually
<em>looks like</em>. <b>Shipped:</b> <code>docs/carousel.html</code>, a keyboard-
and swipe-navigable carousel of <b>8 terminal recordings</b>, one flagship command
per command group — <code>install</code>, <code>search</code>, <code>explain</code>,
<code>tap</code>, <code>distill</code>, <code>doctor</code>, <code>hooks</code> and
<code>pulse</code>. Every recording is scripted as a
<a href="https://github.com/charmbracelet/vhs">VHS</a> tape checked in beside the
GIF it produces, so a stale frame is one <code>make carousel</code> away from being
regenerated rather than re-recorded by hand. Each GIF carries descriptive alt text
covering what the terminal actually does, so the page is usable without images.
The counts on the page are hand-typed no longer: the per-slide
&ldquo;N commands in this group&rdquo; notes and the headline total are asserted
against <code>cli.py</code>'s <code>COMMANDS</code> by
<code>tests/unit/test_docsite_chrome.py</code>, the same guard that covers the
guide — the page arrived claiming <b>76</b> commands with two group counts already
adrift. Built on the shared chrome from
<a href="#docsite-chrome-and-content-audit">the docsite audit</a>, so it carries the
same nav and footer as every other page.
