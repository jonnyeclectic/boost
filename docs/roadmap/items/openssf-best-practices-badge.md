---
id: openssf-best-practices-badge
board: code
section: health
status: shipped
category: Security · Posture
complexity: M
impact: Med
wow: 3
note: 66 Met/N-A · 1 justified Unmet · registration is the only step left
order: 4
owner: loop/openssf-best-practices-badge
pr:
title: OpenSSF Best Practices — all 67 passing criteria answered
---
The <a href="roadmap.html#scorecard-findings-triage">Scorecard triage</a> left
<code>CIIBestPracticesID</code> as the one finding that "needs a human, not a commit". That
was half right. Registration needs a human; <b>answering the criteria</b> was a commit, and
until it was made, "the prerequisites are already in place" was an assumption nobody had
tested against the actual criteria text.
<b>Tested it.</b> All 67 passing-level criteria, parsed from the badge project's own
<code>criteria.yml</code> rather than a summary of it, are answered in
<code>docs/openssf-badge.md</code> — each with the artifact that backs it. Two were genuine
gaps, not paperwork:
<b><code>know_secure_design</code> and <code>know_common_errors</code></b> are MUST criteria
that no gate in this repo could satisfy, because they ask for a written threat model.
<code>docs/security-design.md</code> is that document: boost's trust boundaries (a tap author
is an attacker for modelling purposes), Saltzer and Schroeder's eight principles as concrete
claims about this code, the CWE classes that actually apply to a Python CLI that clones
repositories and writes files — each with its mitigation — and the residual limits stated
plainly, including that boost cannot vet what a skill tells an agent to do.
<b><code>crypto_call</code> is answered Unmet, with justification</b>, and that is the honest
answer rather than a defect. <code>core/ed25519.py</code> reimplements RFC 8032 verification
in pure Python because the stdlib-only runtime rule leaves no alternative — CPython ships no
Ed25519. The exposure is bounded (verify-only, public keys, public signatures, no secret to
leak through timing) and pinned to the RFC's own test vectors. A SHOULD may be Unmet with a
justification; stretching it to "Met" would have been the lie.
The audit also surfaced three settings a branch cannot change — the empty repository
<code>homepage</code> field, the registration itself, and CodeQL alert 54, which is a false
positive whose suggested autofix would print a constant instead of a minisign <b>public</b>
key fingerprint, deleting the only verification <code>boost trust add</code> offers. All
three are listed as human actions at the end of the badge document.
