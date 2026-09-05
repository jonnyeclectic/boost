---
id: audit-tap-findings
board: code
section: dx
status: inflight
category: CLI · Bug
complexity: S
impact: Med
wow: 1
note: a missing local dir is cloned as https://github.com//private/tmp/… before any check
order: 295
owner: loop/tap-findings
pr: 772
title: "boost tap: CLI audit findings (2026-08)"
---
<b>tap misdiagnoses local paths</b> (med). A path-shaped SPEC that is not an existing directory falls
through <code>registry.parse_spec</code>'s <code>'/' in spec</code> branch
(<code>registry.py:106-107</code>) and goes to the network: <code>tap /private/tmp/claude-501/nonexistent-dir-zz</code>
&rarr; <em>&ldquo;git clone failed: fatal: repository 'https://github.com//private/tmp/claude-501/nonexistent-dir-zz/'
not found&rdquo;</em> &mdash; and verification showed <code>./relative</code> paths hit the same fall-through.
An <em>existing</em> directory that is not a git repo gets git's <em>&ldquo;repository '&hellip;/plain-skill-dir'
does not exist&rdquo;</em>, which is false (the dir exists and holds a SKILL.md), while the help promises
&ldquo;a local directory&rdquo;. Fix: in <code>parse_spec</code>, a spec starting with <code>/</code>,
<code>./</code>, <code>../</code> or <code>~</code> whose expanded path is not a directory raises
<code>no such directory: &hellip;</code> before the owner/repo branch; an existing dir without
<code>.git</code> raises <em>is not a git repository</em> with a <code>git init</code> /
<code>boost import</code> hint. Regenerate <code>docs/commands.html</code> only if the spec help gains
the git-repo caveat.

<b><code>tap --at</code> validates the SHA only after cloning</b> (low). <code>tap --at deadbeef
obra/superpowers</code> answers <em>&ldquo;'deadbeef' is not a full commit SHA&rdquo;</em> after
1.62&nbsp;s &mdash; <code>registry.add</code> calls <code>clone_shallow</code>
(<code>registry.py:196-198</code>) before <code>checkout_commit</code> runs the pure-string
<code>_is_sha</code> check (<code>gitutil.py:314</code>). Cleanup is correct; the cost is one wasted
clone per typo. Validate <code>at</code> with <code>gitutil._is_sha</code> before
<code>clone_shallow</code>, keeping the in-checkout check as a backstop.

<b>Single-SPEC and multi-SPEC paths disagree</b> (low). Fresh: <em>&ldquo;&#10003; Tapped
obra/superpowers&rdquo;</em> vs <em>&ldquo;&#10003; tapped pbakaus/impeccable&rdquo;</em>; re-tap:
single errors exit 1 (<em>&ldquo;Error: tap minio/skills is already configured&rdquo;</em>), multi
prints a muted <em>&ldquo;already tapped&rdquo;</em> and exits 0. The split keys purely on
<code>len(spec)==1</code> (<code>taps.py:152-166</code>), so any 2+ SPEC argv takes the idempotent
path &mdash; defeating the file's own stated goal that <code>xargs boost tap</code> be correct. Route
the single-spec branch through the same skip logic (lowercase verb, muted line + update hint,
exit 0), <em>except</em> <code>--at</code> on an existing tap, which must keep erroring &mdash; a
skipped pin is silent staleness (<code>registry.py:200-205</code>). Update
<code>tests/functional/test_cli_taps.py:46,:91</code>.

Found by the 2026-08 CLI audit (clusters <code>tap-local-path-diagnosis</code>,
<code>tap-at-late-validation</code>, <code>tap-path-inconsistency</code>); repro in the audit log.
