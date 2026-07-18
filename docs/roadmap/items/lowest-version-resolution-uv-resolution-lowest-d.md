---
id: lowest-version-resolution-uv-resolution-lowest-d
board: code
section: compat
status: planned
category: Testing · Deps
complexity: S
impact: Med
wow: 3
note: honours declared floors
order: 3
owner:
pr:
title: Lowest-version resolution — <code>uv --resolution lowest-direct</code>
---
CI always installs the <em>newest</em> compatible dependencies, so the
           lower bounds declared in <code>pyproject.toml</code> are never actually
           exercised. Resolving and testing against the minimum versions catches
           the "works here, breaks on the floor we advertise" class of bug.
