---
id: sbom-release-event-never-fires
board: code
section: trust
status: shipped
category: Supply chain
complexity: S
impact: High
wow: 4
note: 253 releases shipped with no SBOM; fixed with workflow_run
order: 50
owner: loop/sbom-trigger
pr: 295
title: <code>sbom.yml</code> has never run — it waits for an event <code>GITHUB_TOKEN</code> cannot emit
---
<code>sbom.yml</code> triggers on <code>release: types: [published]</code> and promises
"a CycloneDX SBOM for every release, attached to the GitHub Release as an asset".
It has <b>0 runs</b>. Releases here are created by <code>release-drafter</code> inside
<code>publish.yml</code> authenticated with <code>GITHUB_TOKEN</code>, and <b>events created
with <code>GITHUB_TOKEN</code> do not trigger workflows</b>. <code>publish.yml</code>'s own
header states that rule verbatim — "we never rely on the release event to trigger a second
workflow" — and <code>sbom.yml</code> is exactly that pattern.

So the <code>if: github.event_name == 'release'</code> guard on its upload step is dead code,
<code>workflow_dispatch</code> is the only reachable path and has never been used, and every
one of the last ten releases carries <code>assets: []</code>. Zero SBOMs have been produced
since the file landed on 2026-07-22. Same shape as the LangGraph conformance leg: wired up,
looks covered, never executed once.

By the time it was fixed the count was <b>253 releases, 0 runs, 0 SBOM assets</b>.

<b>Fixed with a third option neither branch of that decision considered:</b>
<code>workflow_run</code>. The <code>GITHUB_TOKEN</code> restriction applies to
<em>events</em> a token creates; <code>workflow_run</code> is documented as exempt and fires
on the upstream <em>run</em> completing regardless of what triggered it &mdash; which is
already how <code>ci &rarr; release</code> works in this repo. Chaining
<code>release &rarr; sbom</code> makes this the third link, inside GitHub's documented
three-level <code>workflow_run</code> limit. So no PAT is needed, and the SBOM logic stays
out of <code>publish.yml</code>.

That separation turned out to matter more than "keeps the logic in its own file":
<code>publish.yml</code>'s job holds PyPI Trusted-Publishing OIDC credentials, and generating
the SBOM means installing a third-party build plugin (<code>cyclonedx-bom</code>). Inlining it
would have put that plugin inside the one job that can publish to PyPI. Kept separate, it
holds only <code>contents: write</code>.

Two details the trigger change forced. The workflow now resolves its tag from the release
commit (<code>git tag --points-at</code>) rather than "newest release" &mdash; releases here
land minutes apart, so <code>gh release view</code> would race and SBOM the <em>next</em>
version; and two tags on one commit is real (<code>v1.0.248</code> and <code>v1.0.249</code>
both point at <code>c750651</code>), so it takes the highest. And per the original note, a
final step re-reads the release and fails unless the asset is actually attached &mdash; a
silent upload no-op is indistinguishable from success, which is the same class of quiet
nothing that produced this bug.
