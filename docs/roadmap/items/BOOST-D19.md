---
id: BOOST-D19
board: design
track: system
status: done
impact: med
complexity: S
wow: 3
category: system
ref: style/boost.css · docs/style/boost.css
order: 1
owner:
pr:
title: "Resolve theme drift: <code>style/</code> vs <code>docs/style/</code>"
---
Two copies of <code>boost.css</code> have <b>diverged</b>: the root <code>style/</code> uses a cyan→violet→pink gradient (<code>--violet #a855f7</code>), while <code>docs/style/</code> uses an orange→pink→violet one (<code>--violet #a78bfa</code>). Same brand, two looks. Pick <code>style/</code> as canonical and make <code>docs/style/</code> a generated copy or symlink so the portfolio, roadmaps and CLI can't drift again.
