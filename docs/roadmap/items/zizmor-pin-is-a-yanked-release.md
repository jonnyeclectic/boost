---
id: zizmor-pin-is-a-yanked-release
board: code
section: pipeline
status: planned
category: Security · CI/CD
complexity: S
impact: Med
wow: 4
note: the only yanked release of 66 — and the required lint job pins exactly it
order: 63
owner:
pr:
title: The required <code>lint</code> job pins <code>zizmor==1.27.0</code> &mdash; a yanked release
---
<code>ci.yml</code> runs the workflow SAST step as
<code>pipx run zizmor==1.27.0 .github/workflows</code>. PyPI marks <b>1.27.0 as yanked</b>, with
<code>yanked_reason: GHSA-f42p-wjw5-97qh</code>. It is the <b>only yanked release out of 66</b>,
and <b>1.28.0</b> is the successor.

Exact-pinning the security scanner is correct &mdash; an unpinned linter is how
<code>ruff-defaults-broke-boost-lint</code> happened. Pinning to a version its maintainer has
<em>withdrawn for a security advisory</em> is the failure mode on the other side, and it is
quieter: a yank does not stop an exact pin from resolving. <code>pip</code> installs
<code>1.27.0</code> and emits a warning nobody reads in CI logs, so the required <code>lint</code>
gate goes on passing while running a withdrawn build of the tool that audits the workflows
driving a Trusted-Publisher release.

Two things worth doing together. Bump to <code>1.28.0</code> and confirm the four documented
<code>dangerous-triggers</code> exemptions in <code>.github/zizmor.yml</code> still suppress
cleanly &mdash; the line-anchored ignore entries (<code>publish.yml:19</code>,
<code>sbom.yml:29</code>, &hellip;) are exactly the kind of thing a version bump can invalidate.
And sweep the other exact pins for yanks: nothing currently checks for this. <code>pip-audit</code>
catches CVEs in the resolved dependency closure, but a yanked <em>pinned tool</em> is neither a
CVE in the closure nor a manifest diff, so <code>osv-scanner</code> does not see it either. This
was found by accident, while installing zizmor locally to verify an unrelated change.
