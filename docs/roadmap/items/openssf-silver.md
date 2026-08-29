---
id: openssf-silver
board: code
section: health
status: inflight
category: Security · Posture
complexity: S
impact: Med
wow: 3
note: 55 criteria, 31% → the gap was two documents, not fifty
order: 7
owner: loop/openssf-silver
pr:
title: OpenSSF silver — reachable solo, and mostly already true
---
Silver reads like a wall — <b>55 criteria</b> on top of passing — and the board showed 31%
with 37 unanswered. Reading them rather than assuming turned the estimate from "a day" into
<b>two documents</b>. The same lesson <a href="roadmap.html#osps-baseline-levels">the Baseline
audit</a> taught: most unanswered criteria are already satisfied and merely unrecorded.
Eighteen were <b>already answered</b>, because the badge site carries a justification across
levels wherever a criterion name repeats — so <code>assurance_case</code>,
<code>signed_releases</code>, <code>dco</code> and <code>roles_responsibilities</code> arrived
already Met from the passing and Baseline work. Most of the remaining 37 are evidence that
exists and had never been written into a form: the coverage and mutation gates, the
hash-pinned toolchain, the C4 architecture docs, the generated command reference with its
freshness check.
<b>The two genuine gaps.</b> <code>governance</code> wanted the decision-making model, which
<code>MAINTAINERS.md</code> did not cover — it lists roles, not how a decision gets made or
what happens when people disagree. <code>GOVERNANCE.md</code> now says it plainly: a
benevolent-dictator model, the gates decide what they can, a "no" is recorded rather than
dropped, and the real backstop on a single maintainer is the licence and a public history —
anyone who thinks it is run badly can fork and prove it. <code>documentation_achievements</code>
wanted the badges hyperlinked from the front page.
<b>What stays honestly Unmet</b>, all SHOULD or SUGGESTED, so the badge still passes:
<code>bus_factor</code> (one maintainer), <code>version_tags_signed</code> (tags are
unsigned; releases carry SLSA provenance instead), <code>crypto_algorithm_agility</code>
(minisign is Ed25519-only by format) and <code>internationalization</code> (the CLI is
English-only). Gold remains out of reach for the reason it always was — it needs a second
human, not a commit.
