---
id: markdownlint-lints-the-fuzz-corpus
board: code
section: pipeline
status: shipped
category: Bug
complexity: S
impact: Med
wow: 3
note: 12 of 21 linted files were malformed on purpose
order: 56
owner: loop/ci-reporting-defects
pr:
title: markdownlint linted the fuzzer's corpus, so shipping a crash reproducer would redden a prose gate
---
<code>.markdownlint-cli2.jsonc</code> globs <code>**/*.md</code> and its <code>ignores</code>
list carved out <code>.claude/**</code> and <code>docs/roadmap/items/**</code> but not
<code>tests/fuzz/corpus/**</code>. So <b>12 of the 21 files being prose-linted</b> were
deliberately-malformed YAML-frontmatter seeds for the atheris fuzzer —
<code>07-unterminated.md</code>, <code>09-unbalanced-quote.md</code>, <code>12-bom.md</code>
and friends. Malformed is their entire purpose, and they passed the gate only by luck.

That luck was going to run out by design. <code>fuzz.yml</code> exists to mine <em>new</em>
malformed inputs and ship them as reproducers
(<code>-artifact_prefix=artifacts/</code>, uploaded as <code>fuzz-crash-&lt;target&gt;</code>),
and one such crash artifact already exists from a real run. The moment anyone committed it into
<code>tests/fuzz/corpus/frontmatter/</code> — exactly what the workflow is for — an unrelated
prose-style gate would have gone red for a reason with nothing to do with prose, on a file
whose whole point is to be invalid.

Fixed by adding <code>tests/fuzz/corpus/**</code> to <code>ignores</code>. Verified with the
pinned <code>markdownlint-cli2@0.18.1</code>: 21 → 9 files linted, 0 errors, and a planted
crash reproducer no longer reddens the gate.
