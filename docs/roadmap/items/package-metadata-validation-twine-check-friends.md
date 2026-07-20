---
id: package-metadata-validation-twine-check-friends
board: code
section: compat
status: planned
category: Quality · Packaging
complexity: S
impact: Med
wow: 3
note: pre-publish gate
order: 6
owner: loop/pkg-metadata-check
pr: 135
title: Package-metadata validation — <code>twine check</code> + friends
---
Before every publish, <code>twine check</code> confirms the long
           description renders on PyPI, <code>check-wheel-contents</code> catches
           stray or missing files, and <code>pyroma</code> scores the metadata
           completeness. Stops a broken PyPI page or an empty wheel from reaching
           users — the release path currently trusts the build blindly.
