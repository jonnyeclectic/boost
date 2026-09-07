---
id: audit-trust-findings
board: code
section: trust
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: trust add of a missing .pub path blames "invalid base64 in minisign data"
order: 298
owner: loop/trust-audit-findings
pr:
title: "boost trust: CLI audit findings (2026-08)"
---
<b><code>trust add</code> blames base64 for a nonexistent <code>.pub</code> path</b> (med).
<code>trust add acme /nonexistent/acme.pub</code> answers <em>&ldquo;Error: not a valid minisign
public key: invalid base64 in minisign data / hint: pass the .pub file or its base64 line&rdquo;</em>
&mdash; same for a relative <code>./missing-key.pub</code>. <code>quality.py:1285-1288</code> reads
the file only when <code>key_path.is_file()</code> and otherwise silently treats the argument string
itself as a base64 key line, so <code>provenance.add_trusted_key</code>
(<code>provenance.py:93-97</code>) blames the wrong thing. Fix: when the KEY argument looks like a
path (<code>os.sep</code> in it or ending <code>.pub</code>) and is not a file, raise
<code>no such key file: &lt;path&gt;</code> before falling back to text parsing.

<b><code>trust verify &lt;tap&gt;</code> exits 1 without saying why</b> (low). The named-tap form
prints the provenance table row (<em>&ldquo;sickn33/antigravity-awesome-skills&nbsp;&nbsp;unsigned&nbsp;&nbsp;no
.boost/tap.manifest.minisig&rdquo;</em>) and returns exit 1 with no closing line &mdash;
<code>cmd_trust</code>'s <code>args.name</code> branch (<code>quality.py:1313-1329,:1358-1363</code>)
calls <code>_print_provenance</code> and returns the status with no <code>out.warn</code>. Fix: after
the table, when the result is not ok, print <code>out.warn('%s: not verified (%s)')</code> before
returning 1.

<b>The trusted-keys table right-aligns an all-digit fingerprint as numeric</b> (low). With the
<code>1122334455667788</code> test key the FINGERPRINT column right-aligns
(<em>&ldquo;NAME &#9474;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;FINGERPRINT&rdquo;</em>) because
<code>out.table</code>'s <code>_numeric_col</code> (<code>output.py:683-695</code>) fullmatches
digits. Verification found it narrower than the audit stated &mdash; it fires only when
<em>every</em> fingerprint is all-decimal, ~0.06% per random real key &mdash; but the heuristic
itself is the defect, and the hazard is latent for every hex-id column rendered via
<code>out.table</code>. Fix: give <code>out.table</code> a per-column numeric override and pass
<code>numeric=False</code> for FINGERPRINT in <code>cmd_trust</code>
(<code>quality.py:1344-1345</code>). No doc changes for any of the three.

Found by the 2026-08 CLI audit (clusters <code>trust-add-path-error</code>,
<code>trust-verify-silent-fail</code>, <code>trust-fingerprint-alignment</code>); repro in the audit
log.

<b>Status.</b> All three findings implemented and covered by new unit/functional tests (PR
linked above): <code>trust add</code> now raises <code>no such key file: &lt;path&gt;</code> before
falling back to base64 parsing; <code>trust verify &lt;tap&gt;</code> prints an
<code>out.warn</code> line naming why a specific tap didn't verify; and <code>out.table</code>
gained a <code>text=</code> parameter (columns that must never right-align as numeric,
however their cells look), used for the trusted-keys FINGERPRINT column. Left
<code>inflight</code> rather than <code>shipped</code> because this session's sandbox has no
network egress to PyPI/GitHub and runs Python 3.11 (repo floor is 3.12), so
<code>make check</code> could not be run here. ruff, mypy, and the full unit+functional suites
were run directly and diff identically to a clean checkout of main modulo the new tests, which
pass. CI should confirm the full gate before merge.
