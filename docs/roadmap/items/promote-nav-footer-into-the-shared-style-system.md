---
id: promote-nav-footer-into-the-shared-style-system
board: code
section: dx
status: inflight
category: DX · Design system
complexity: S
impact: Med
wow: 3
note: <code>style/boost.css</code>
order: 1
owner: loop/theme
pr:
title: Promote nav / footer into the shared style system
---
Canonical <code>style/boost.css</code> ships tokens + primitives but
           <strong>no nav, logo, or footer</strong>, so every page (the guide and
           both roadmaps) redefines that chrome inline — and the Design Roadmap
           currently renders its nav <strong>unstyled</strong> because of the gap.
           Add <code>.site-nav</code>/<code>.logo</code>/<code>footer</code>
           primitives to the one sheet so the chrome is defined once and can't drift.
