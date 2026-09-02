---
id: audit-export-o-cohort-create-and-profile-save-silently-overwrite-e
board: code
section: dx
status: inflight
category: Safety · Bug
complexity: S
impact: Med
wow: 1
note: export -o same.tar.gz twice — both runs say "exported", the first archive is gone
order: 237
owner: loop/silent-overwrites
pr:
title: "<code>export -o</code>, <code>cohort create</code> and <code>profile save</code> silently overwrite existing outputs and still say created/saved"
---
Three commands replace an existing archive/cohort/profile with no warning, no delta and no
<code>--force</code>. <code>export -o same.tar.gz</code> twice: both runs print
<em>&ldquo;&#10003; exported 1 skill &rarr; &hellip;/same.tar.gz (2.9KB)&rdquo;</em> and the first
file is replaced without a word. <code>cohort create pilot</code> over an existing cohort prints
<em>&ldquo;&#10003; created cohort pilot (100% rollout, 1 skills)&rdquo;</em> while
<code>cohorts.json</code> shows the old 50%/2-skill spec gone and the <code>created</code>
timestamp reset &mdash; a replacement misreported as a creation. <code>profile save daily</code>
over an existing profile likewise says <em>&ldquo;&#10003; saved profile daily&rdquo;</em> and
rewrites the file. No exists check anywhere: <code>team.py</code> cohort-create assigns
<code>cohorts[name]</code> unconditionally (<code>team.py:95-108</code>), profile-save
<code>write_text</code>s unconditionally (<code>team.py:269-277</code>), and <code>pkg.py</code>
export opens the destination <code>'w'</code>/<code>'w:gz'</code>
(<code>pkg.py:1650-1663</code>). A typo in the name destroys saved state.

It also breaks the file's own conventions: <code>cohort delete</code> in the same module confirms
before destroying, and the shipped onboard-overwrites-generated-files-without-confirm item
(PR&nbsp;287) already established the exists-check precedent for generated outputs &mdash; which is
what makes this a defect rather than taste.

Verified fix, per command: <code>export</code> refuses when the destination exists without
<code>--force</code>, naming the file; <code>cohort create</code> refuses or prints
&ldquo;updated cohort X (was N% / M skills)&rdquo; and preserves the original <code>created</code>;
<code>profile save</code> prints &ldquo;updated profile X (was N skills)&rdquo; &mdash;
snapshot-like semantics make delta wording the better fix than <code>--force</code> there.
Regenerate docs/commands.html for the new <code>export --force</code> flag. Found by the 2026-08
CLI audit (cluster <code>silent-output-overwrite</code>); repro in the audit log.
