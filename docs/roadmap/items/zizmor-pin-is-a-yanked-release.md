---
id: zizmor-pin-is-a-yanked-release
board: code
section: pipeline
status: shipped
category: Security · CI/CD
complexity: S
impact: Med
wow: 4
note: already fixed by a4450f76 twelve hours before this card was filed
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

<b>Already shipped when this card was written &mdash; the card was filed stale, and that is the
more useful finding.</b> Commit <code>a4450f76</code>, "ci(security): zizmor 1.27.0 is yanked
&mdash; take 1.28.0", landed at <b>08:07Z</b>; this card was filed at <b>20:18Z</b>, twelve hours
later, against a base that already carried <code>1.28.0</code>. The yank was observed correctly
against a tree extracted earlier in the day and then never re-checked against the branch point.
<code>ci.yml</code> now runs <code>pipx run zizmor==1.28.0</code>.

Two things worth keeping from it. The predicted risk did not materialise: <code>zizmor
1.28.0</code> runs clean over all 25 workflows (exit 0, "no findings to report"), and the
line-anchored ignores in <code>.github/zizmor.yml</code> &mdash; including
<code>sbom.yml:29</code> &mdash; all still resolve, so the bump needed no config change. And the
gap the card names remains real and unclosed: <b>nothing checks whether an exact pin has been
yanked</b>. <code>pip-audit</code> scans the resolved dependency closure and
<code>osv-scanner</code> diffs the manifest; a yanked <em>pinned tool</em> is neither, so this was
caught by a human noticing a pip warning, twice, by luck.
