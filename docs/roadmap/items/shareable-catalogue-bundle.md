---
id: shareable-catalogue-bundle
board: code
section: dx
status: shipped
category: Feature
complexity: M
impact: High
wow: 5
note: 10.9 MB replaces a 12 GB clone — a fresh machine reaches 59,972 searchable items in 4 seconds
order: 106
owner: feat/catalog-bundle
pr:
title: Share the catalogue instead of making everyone re-tap it
---
<b>Tapping is the slowest thing a new install does, and almost none of the cost is the part anyone
needs.</b> Measured on a real machine with <b>458 registries</b> tapped: the shallow clones are
<b>12&nbsp;GB</b> on disk, while the catalogue they produce — the JSON boost actually searches — is
<b>101.1&nbsp;MB</b>, and <b>10.9&nbsp;MB</b> gzipped. Three orders of magnitude, for the artifact
that carries all of the value.

That gap is only worth acting on if the catalogue is genuinely sufficient on its own, so that was
checked before a line was written: a <code>HOME</code> holding one cache file and a config entry, no
clone anywhere, and <code>boost search</code> returned the right skill. The clone is what
<code>install</code> needs, not what <code>search</code> needs.

<b><code>boost catalog</code> — export, show, import.</b> Verified end-to-end against the real
458-tap cache rather than a fixture:

<code>--export</code> packed <b>458 taps · 59,972 entries · 10.9 MB</b>. On a brand-new
<code>HOME</code> reporting <code>available 0 (across 0 taps)</code>, <code>--import</code> took
<b>0.26&nbsp;s</b>, <code>boost reindex</code> a further <b>3.8&nbsp;s</b>, and
<code>boost search "code review"</code> then returned real ranked hits over all 59,972 items with
<b>zero repositories cloned</b> and 170&nbsp;MB on disk. The whole path, cold, is under four seconds.

<b>What the format deliberately omits, and why each one is a decision rather than an oversight.</b>
The <i>derived indexes</i> (<code>rag_index.json</code>, <code>rag_postings.sqlite</code>,
<code>rag_vectors.sqlite</code>) are <b>3.8&nbsp;GB of that machine's 3.9&nbsp;GB cache
directory</b> and rebuild from the catalogue in seconds, so shipping them would trade a 350x size
increase for four seconds. Vectors are excluded for a second, stronger reason: they are only
meaningful inside the embedding space that produced them, which is why
<code>dense.export_shard</code> carries provider/model/dim/commit and <code>import_shard</code>
refuses a mismatch outright. A bundle carries none of that, so it must not carry vectors either —
<code>reindex --export-shard</code> is the reviewed path, and this format stays honestly narrower
than it. The <i>repositories</i> are omitted because that is the point: every tap's URL rides in the
manifest so the receiver can clone the one repo it ends up wanting, instead of all 458 up front.

<b>Import merges, and never replaces.</b> The receiving machine may already have taps of its own,
and silently discarding them would be a worse outcome than the slow tap this exists to avoid.
Re-importing the same bundle is idempotent. A configured tap whose catalogue has not been built yet
is <i>skipped and named</i> on export rather than being fatal — taps build one at a time, and
refusing to export the other 457 because one is mid-build would break the feature exactly when it is
most useful.

<b>A bundle is a file people send each other, which makes it untrusted input in the most ordinary
way there is.</b> Tar member names are the classic path-traversal vector, so extraction never lets
the archive choose a destination: members must be regular files directly under
<code>catalog/</code> with a plain <code>.json</code> basename, and the write path is then rebuilt
here from that basename — validating the name <i>and</i> discarding it, because a check that feeds
its own input forward is one refactor from being decorative. Symlink and hardlink members are
refused (that is how an archive escapes its tree with no <code>..</code> anywhere in it), member
count and member size are capped against a decompression bomb, and a manifest declaring an unknown
<code>format</code> is refused rather than guessed at. Seven of the nineteen tests are that hostile
archive, and each asserts on <i>where the bytes landed</i>, not merely that the call raised — a
traversal that raises after writing the file has still written the file.
