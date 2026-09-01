---
id: audit-lint-findings
board: code
section: health
status: inflight
category: CLI · Bug
complexity: M
impact: Med
wow: 2
note: lint can't lint a path on disk, counts 6307 "skills" for 1997 names, misreads one missing ---
order: 274
owner: loop/lint-audit-findings
pr:
title: "<code>boost lint</code>: CLI audit findings (2026-08)"
---
<b>A path on disk cannot be linted</b> <em>(med)</em>. <code>lint ./my-skill</code> and
<code>lint &hellip;/SKILL.md</code> both fail <em>&ldquo;Error: not installed: &hellip; / hint: see
what is with <code>boost list</code>&rdquo;</em> &mdash; only installed names and <code>--tap</code>
clones reach the linter (<code>quality.py:707-728</code>), so an author cannot lint before
installing. <code>util.score_skill</code> already takes a directory; dispatch to it when a NAME
contains a path separator or exists on disk, document the path form, and regenerate
<code>docs/commands.html</code>. (Cluster <code>lint-path-target</code>.)

<br><br><b><code>--tap</code> counts per-agent mirrors as skills</b> <em>(med)</em>. Two names in
<code>sickn33/antigravity-awesome-skills</code> print nine indistinguishable rows
(test-driven-development 90/100 &times;6) and <em>&ldquo;&#10003; 9 skills pass lint&rdquo;</em>;
over the whole tap, <em>&ldquo;6307 skills pass&rdquo;</em> for 1997 distinct names. The house
convention (<code>measure_registry</code>) is to dedupe mirrors on the content digest, and this
command reports the opposite. Group <code>lint_targets</code> by <code>entry["content"]</code>
(absent digest never matches), show <code>rel_dir</code> for names that still collide, and count
distinct items in the summary (<code>quality.py:719-725</code>, <code>:762-779</code>).
(Cluster <code>lint-tap-mirror-rows</code>.)

<br><br><b>An unclosed frontmatter block is misdiagnosed as three missing fields</b> <em>(med)</em>.
A SKILL.md opening with <code>---</code> and carrying name/description/version but no closing fence
gets <em>&ldquo;error: missing required field: name / &hellip; description / frontmatter missing
<code>version</code>&rdquo;</em> &mdash; <code>frontmatter.split</code>
(<code>frontmatter.py:21-31</code>) falls back to no-frontmatter and the fields go unparsed. Detect
<code>startswith('---')</code> with an empty parsed block and emit one <em>&ldquo;frontmatter is not
closed (no terminating ---)&rdquo;</em> error instead. (Cluster
<code>lint-unclosed-frontmatter</code>.)

<br><br><b>No description length cap</b> <em>(low)</em>. A 5,000-character description lints
100/100 with no note, though the Agent Skills format caps descriptions at 1024 chars and hosts
truncate them; the only length check is whole-file size (&gt;48KB) and it blames the file. Add to
<code>util.score_skill</code> (<code>util.py:289-296</code>): over 1024 chars, deduct 10 and note
&ldquo;agent hosts truncate it&rdquo; &mdash; core change, needs a mutant-killing unit test.
(Cluster <code>lint-description-length</code>.)

<br><br><b><code>--tap</code> silently ignores unknown names</b> <em>(low)</em>.
<code>lint --tap first-fluke/oh-my-agent nosuchskill</code> prints <em>&ldquo;nothing to
lint&rdquo;</em>, exit 0 &mdash; and mixed with a valid name the typo vanishes behind a success line,
so a misspelt name passes CI silently, while the installed-name path errors (exit 1). After
<code>catalog.lint_targets</code>, raise <code>BoostError</code> for any requested name matching
neither targets nor skipped, on the <code>--json</code> path too (<code>quality.py:729</code>,
<code>catalog.py:303-329</code>). Found by the 2026-08 CLI audit (cluster
<code>lint-tap-unknown-name</code>); repro in the audit log.
