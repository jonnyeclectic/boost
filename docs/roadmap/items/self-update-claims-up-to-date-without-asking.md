---
id: self-update-claims-up-to-date-without-asking
board: code
section: compat
status: shipped
category: Bug
complexity: S
impact: High
wow: 4
note:
order: 11
owner: loop/self-update-freshness
pr:
title: <code>self-update</code> said "already up to date" without asking PyPI
---
<code>boost self-update</code> inferred "already up to date (vN)" from the fact that
<code>observed_version()</code> came back unchanged. Those are two different propositions, and the
gap between them is exactly one stale HTTP cache wide. Observed on the 1.0.422 → 1.0.423 release:
PyPI serves the simple index with <code>Cache-Control: max-age=600</code> and pip honours it, so a
<code>pipx upgrade</code> at 13:15 — eight minutes before the 1.0.423 wheel existed — cached an
index that had never heard of it, and the two retries at 13:22 and 13:23 (the second one
<em>after</em> the upload) were both answered from that cache. pip's own words each time:
<code>Requirement already satisfied: boost-skill-cli in ./lib/python3.14/site-packages
(1.0.422)</code>. pipx exited 0, the version did not move, and boost reported that the user was
current while they were a release behind — the most expensive kind of wrong answer, because it
tells you to stop looking.

Fixed at both ends. <code>upgrade_command()</code> now tells each manager to refresh its index
(<code>--pip-args=--no-cache-dir</code> for pipx, <code>--no-cache-dir</code> for pip,
<code>--refresh</code> for uv — pip has no index-only refresh and uv does, so the flag is
per-manager rather than one shape), which removes the cause. And <code>selfupdate.latest_version()</code>
asks PyPI's JSON API what the newest release actually is, so a no-op upgrade now has three
distinct outcomes instead of one claim: PyPI is ahead → a <code>BoostError</code> naming both
versions plus <code>force_command()</code>, which pins the exact version and forces the install
(a plain upgrade is no help — the resolver has already declined); PyPI agrees → "already up to
date"; PyPI unreachable → "boost is unchanged (vN); could not reach PyPI to confirm it is the
latest", because an unearned claim with a different cause is the same bug. <code>None</code> is
the load-bearing third answer throughout, as in <code>scripts/release_guard.py</code>, and
<code>is_behind()</code> compares release numbers rather than text — <code>"1.0.9" &gt; "1.0.10"</code>
lexicographically, which is how a version check ships a nag that never clears.

Two findings came out of pointing the new code at real PyPI rather than only at fakes. The
payload is ~735 KB (the JSON API embeds every release's file list), and a body that drops
mid-read raises <code>http.client.IncompleteRead</code> — which on CPython ≤ 3.13 was also a
<code>ValueError</code> and was caught by accident, but on 3.14 has <code>HTTPException</code> as
its only base and escaped as a traceback out of a check that must never fail. It is now caught
explicitly. The endpoint stays the fatter one on purpose: <code>info.version</code> excludes
yanked releases, and computing the max over the leaner simple-API version list would offer a
yanked release as "newer" and hand the user a force command that installs it.
<code>BOOST_NO_NET=1</code> skips the request entirely, the same contract as
<code>BOOST_NO_AI</code> / <code>BOOST_NO_SEED</code>, and the test sandbox sets it so no test
reaches the network as a side effect of checking what a command prints.
