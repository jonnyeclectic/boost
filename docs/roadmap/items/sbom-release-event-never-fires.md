---
id: sbom-release-event-never-fires
board: code
section: trust
status: planned
category: Supply chain
complexity: S
impact: High
wow: 4
note: 0 runs, 0 SBOMs, 227 releases
order: 50
owner:
pr:
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

Fix is a decision, not a patch: either build and attach the SBOM inside
<code>publish.yml</code>'s release job (it already holds <code>contents: write</code> and is
where the tag is cut), or have <code>publish.yml</code> dispatch this workflow with a PAT
rather than <code>GITHUB_TOKEN</code>. The first is simpler and keeps the release atomic;
the second keeps the SBOM logic in its own file. Worth pairing with a check that fails the
release when the asset is missing, so "never ran" cannot recur silently.
