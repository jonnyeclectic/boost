---
id: complexity-and-dead-code-radar-xenon-vulture
board: code
section: health
status: shipped
category: Quality · Smell
complexity: M
impact: Med
wow: 2
note: commands/ first
order: 5
owner: loop/radar
pr: 191
title: Complexity &amp; dead-code radar — <code>xenon</code> · <code>vulture</code>
---
Gate CI on a maintainability grade with <code>xenon</code> (built on
           <code>radon</code>) and flag unreachable branches, unused arguments and
           orphan helpers with <code>vulture</code>. First target: the
           ~5,000-line <code>commands/</code> layer that has no complexity signal
           today. Surfaces the structural smells mutation testing can't see.
