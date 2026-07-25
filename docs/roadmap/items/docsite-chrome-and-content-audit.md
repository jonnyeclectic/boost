---
id: docsite-chrome-and-content-audit
board: code
section: docsite
status: shipped
category: Docs · Design system
complexity: M
impact: Med
wow: 3
note: 7 pages · one nav, one footer
order: 13
owner: loop/docsite-chrome
pr:
title: Docsite audit — stale counts, dev-noise footers, and a nav that breaks on mobile
---
<a href="#promote-nav-footer-into-the-shared-style-system">Promoting the chrome</a>
into <code>style/boost.css</code> gave the docsite <code>.site-nav</code> and
<code>footer</code> primitives, but nothing adopted them: three pages still had
<b>no nav at all</b> (<code>eval</code>, <code>adapters</code>,
<code>mcp-hub</code>), <code>commands.html</code> had neither nav nor footer,
and <code>design-roadmap.html</code> had <b>no footer</b>. Alongside that,
<b>stale content</b> — the Visual Guide advertised <b>&ldquo;73 commands&rdquo;</b>
in three places while <code>cli.py</code>'s <code>COMMANDS</code> held <b>78</b>,
its embedded array missing <code>adapt</code>, <code>run</code>,
<code>trust</code>, <code>hooks</code> and <code>bmad</code> — and
<b>unprofessional footers</b>: four pages signed off with &ldquo;Styled with the
shared Aurora design system&rdquo; over a raw <code>../style/boost.css</code>
link, the roadmap credited &ldquo;the boost quality loop&rdquo;, and the MCP Hub
listed three internal PR numbers.
<b>Shipped:</b> every page now carries the same nav and the same footer &mdash;
brand line, install line, the page index, GitHub/PyPI/Portfolio and the licence,
and nothing else. The command inventory is regenerated from <code>COMMANDS</code>.
On phones the link row drops to its own full-width line and scrolls with
40&nbsp;px tap targets (WCAG&nbsp;2.5.5) and a faded trailing edge, replacing
both <code>roadmap.html</code>'s <code>display:none</code> below 560&nbsp;px
&mdash; which deleted the nav outright &mdash; and the column stack that turned
fourteen links into six rows of sticky header. Two latent bugs fell out:
<code>roadmap.html</code>'s hero was a second bare <code>&lt;header&gt;</code>, so
it silently inherited the shared sheet's sticky chrome, and generated cards had
no <code>id</code>, so no item could link another. Locked by
<code>tests/unit/test_docsite_chrome.py</code>.
