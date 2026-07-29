---
id: one-commit-can-cut-two-releases
board: code
section: pipeline
status: planned
category: Release safety
complexity: M
impact: Med
wow: 3
note: v1.0.277 and v1.0.278 are the same commit; so were 246/247 and 248/249
order: 67
owner:
pr:
title: One commit can cut two releases, and the naive guard against it breaks retries
---
<code>publish.yml</code> checks out <code>ref: main</code> rather than the commit whose
<code>ci</code> fired it. <code>release-verifies-the-wrong-commit</code> fixed the
<em>verification</em> half of that &mdash; preflight now waits on the shipped sha's own gates
&mdash; but the same decoupling has a second consequence it does not address: <b>two triggers can
both resolve to the same tip and release it twice.</b>

Observed on <code>5061e756</code>: two <code>release</code> runs created 27 seconds apart
(22:24:32Z and 22:24:59Z), both succeeding, cutting <b>v1.0.277 and v1.0.278 from one commit</b>.
It recurs &mdash; <code>v1.0.246</code>/<code>v1.0.247</code> both point at <code>c1d67c1c</code>,
and <code>v1.0.248</code>/<code>v1.0.249</code> both at <code>c750651</code>. Each duplicate burns
a PyPI version on a byte-identical build and, until the companion fix in this change, left one of
the two GitHub Releases with no SBOM.

Preflight does not stop it and was never going to: both runs check out the same green tip, so both
legitimately pass every gate. The duplication is upstream of verification.

<b>The obvious fix is a trap, which is why this is filed rather than patched.</b> Guarding with
"skip if <code>git tag --points-at HEAD</code> already has a <code>v*</code> tag" would stop the
duplicate &mdash; and would also stop any legitimate <b>retry</b>. release-drafter creates the tag
<em>before</em> the build, attestation, wheel smoke-test and PyPI upload run, so a release that
failed at the upload step leaves a tag behind with nothing on PyPI. Under that guard, re-running it
would skip instead of finishing the job, converting a recoverable failure into a version that can
never be published. The <code>concurrency: group: release</code> block does not help either: it
serialises the two runs rather than collapsing them, which is exactly what happened here.

A correct fix has to distinguish "already released" from "tagged but not published" &mdash; check
whether the version exists on PyPI, or whether the GitHub Release has its expected assets, rather
than whether a tag exists. Alternatives worth weighing: collapse the trigger so only the newest
queued run proceeds (<code>cancel-in-progress</code> on a group keyed by nothing, losing the
serialisation the release job wants), or skip when <code>git rev-parse HEAD</code> already differs
from <code>workflow_run.head_sha</code> &mdash; that is self-healing, since the newer commit's own
ci will trigger its own release, but it means some merges never get their own version.

<b>Already mitigated:</b> <code>sbom.yml</code> now builds and attaches an SBOM for <em>every</em>
tag on the commit rather than only the highest, so a duplicate release no longer produces a release
with no SBOM. Each tag is built separately so its SBOM carries its own version.

<b>Correction:</b> the claim above originally read "because setuptools-scm reads the version from
the tag", and that is false — it reads the version from the <em>commit</em>, so separate checkouts
of two tags on one commit produce the same version. That was a second, quieter consequence of the
duplicate release, fixed separately in <code>sbom-declares-the-wrong-version</code>.
