---
id: pin-the-lint-toolchain
board: code
section: dx
status: shipped
category: CI · Reproducibility
complexity: S
impact: High
wow: 3
note: unpinned ruff 0.16 reddened every PR
order: 9
owner: loop/pinlint
pr: 216
title: Pin the lint toolchain so a release can't redden the gate
---
The <code>lint</code> job installed its tools unpinned
           (<code>pip install ruff mypy …</code>), so every run pulled the latest
           release. When <code>ruff 0.16.0</code> shipped it began flagging rule
           families this repo deliberately does not select
           (<code>UP</code>/<code>BLE</code>/<code>PLW</code> — ~1100 findings of
           exactly the pyupgrade-style churn the roadmap already declined),
           turning the gate red on every open PR and on <code>main</code> with no
           code change. A gate whose meaning can shift out from under you on an
           upstream release is not a gate. Froze the eight lint tools to their
           known-good versions in one <code>requirements/lint-tools.txt</code>
           that both CI and the Makefile install from, so upgrades become a
           deliberate, reviewable bump. (The broader runtime/build reproducibility
           story is the <code>uv.lock</code> item; this is the lint-gate slice
           that was actively on fire.)
