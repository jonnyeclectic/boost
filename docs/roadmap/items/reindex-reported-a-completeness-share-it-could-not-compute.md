---
id: reindex-reported-a-completeness-share-it-could-not-compute
board: code
section: internals
status: shipped
category: Correctness · Bug
complexity: S
impact: High
wow: 4
note: shipped in v1.2.108 and caught by an adversarial review of the merge that carried it
order: 315
owner: batch/train-23
pr: 847
title: "<code>reindex</code> reported a completeness share it could not compute"
---
The completeness warning added alongside the keyword-index work said
<em>&ldquo;this index holds N% of the searchable text&rdquo;</em> &mdash; a share of the
<strong>corpus</strong>. The number behind it, <code>body_share</code>, is
<code>1 - metadata_only_tokens / tokens</code>: a share of the tokens
<strong>already in the index</strong> that came from a document carrying a body. Those
are different quantities, and they move in opposite directions.

The corpus share is not computable here, which is why this is not a sign error. The
bodies that were never read have no token count to compare against, by construction, so
no rearrangement of what <code>_save</code> records can recover it.

Because a body runs about an order of magnitude longer than the metadata standing in for
it, the printed figure overstated completeness in exactly the partly-cloned case the
warning exists for. Measured against the shipped code: a half-cloned index holding 53% of
its corpus announced <strong>94.3%</strong>; a single unreadable <code>SKILL.md</code>
among 1,001 documents rendered as <strong>100.0% of the searchable text</strong> inside a
warning whose first clause says text is missing; and the bundle-only shape the feature was
built for &mdash; the one the card measured at 6.0% &mdash; printed <strong>0.0%</strong>.

Two things kept it invisible. The docstring asserted the value
<em>&ldquo;reproduces the measurement the roadmap card made by hand &hellip; or 6.0% of
the searchable text&rdquo;</em>, which it never did. And the tests pinned the mismatch
rather than catching it: the functional test asserted the literal string
<code>0.0% of the searchable text</code>, while the unit test's only guard on a mixed
corpus was <code>0.0 &lt; body_share &lt; 1.0</code> &mdash; satisfied by every overstated
value &mdash; under a comment claiming the share would sit <em>&ldquo;well under
0.5&rdquo;</em> when it is in fact above it.

The remedy the line printed was inert in both halves. <code>boost tap &lt;owner/repo&gt;</code>
raises <code>tap &lt;x&gt; is already configured</code> for a tap the bundle has already written
into <code>config.json</code>, which is precisely the <code>catalog --import</code> shape;
and a plain <code>boost reindex</code> reuses any tap whose commit has not moved &mdash;
<code>build</code>'s predicate never consults whether a clone is present &mdash; so the
flagged documents are carried forward verbatim and the bodies are never read. The line now
says <code>boost update</code>, then <code>boost reindex --force</code>.

The warning now quotes <code>metadata_only_tokens / tokens</code> and names it: how much of
what this index holds is catalog metadata. That reads 100% for the bundle-only shape, which
is the sentence the feature wanted all along, and it stays true in the two cases that
previously inverted.
