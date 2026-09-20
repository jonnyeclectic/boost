---
id: claude-md-instructs-the-wrong-licence-header
board: code
section: planned
status: shipped
category: Docs · Bug
complexity: S
impact: Med
wow: 3
note: CLAUDE.md tells every contributor and agent to open a new source file with GPL-3.0-o…
order: 326
owner: loop/spdx-licence-drift
pr:
title: CLAUDE.md instructs the wrong licence: every new source file is told to carry <code>GPL-3.0-only</code> in a repo whose 373 headers, LICENSE and pyproject all say Apache-2.0
---
<b>Measured.</b> <code>CLAUDE.md:296</code> reads "Every <code>.py</code>/<code>.sh</code> under <code>boost_cli</code>, <code>boost_langchain</code>, <code>evals</code>, <code>scripts</code>, <code>tests</code> plus <code>./boost</code> and <code>noxfile.py</code> opens with <code># Copyright the boost contributors.</code> and <code># SPDX-License-Identifier: GPL-3.0-only</code>". Nothing in the repo agrees: <code>scripts/add_spdx_headers.py:40</code> is <code>SPDX_ID = "Apache-2.0"</code>, all <b>373</b> existing headers are <code>Apache-2.0</code> (counted across boost_cli, scripts, tests, ./boost and noxfile.py — zero GPL), <code>LICENSE</code> is the Apache License, and <code>pyproject.toml:27</code> is <code>license = "Apache-2.0"</code>.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code>grep -n "GPL-3.0" CLAUDE.md</code><br>
<code>grep -n "SPDX_ID" scripts/add_spdx_headers.py</code><br>
<code>grep -rh "SPDX-License-Identifier" boost_cli scripts tests ./boost noxfile.py | sort | uniq -c</code><br>
<code>grep -n "^license" pyproject.toml ; head -2 LICENSE</code>

<b>Why it is worth doing.</b> CLAUDE.md is not commentary — it is the file every agent working this repo reads before it writes a line, and the same paragraph tells the reader that the expression lives in one place "so changing <code>-only</code> to <code>-or-later</code> is one edit rather than 314". A contributor who follows the instruction literally, in a file the script has not yet swept, hand-writes a GPL header into an Apache-2.0 project — a licence claim, in a file's own header, that contradicts the repository's LICENSE and its published package metadata. The repo has the machinery to prevent exactly this (<code>scripts/check_licenses.py</code> denies a dependency that is not Apache-compatible, and <code>add_spdx_headers.py</code> is idempotent) and the one surface that is read by a human or an agent is the one that is wrong.

<b>When it drifted.</b> <code>git log -S</code> dates both sides exactly: the sentence arrived in <code>0ec5bca</code> ("docs: how far OpenSSF gold goes without a second human", #575) when the tree really was GPL-3.0-only, and <code>5a18793</code> ("Relicense boost from GPL-3.0-only to Apache-2.0", #587) rewrote <code>LICENSE</code>, <code>pyproject.toml</code>, <code>SPDX_ID</code> and every header — and did not touch CLAUDE.md. So the instruction has named a licence the project does not use since #587, in the file every agent reads first.

<b>What is NOT established.</b> Whether anyone acted on it. No file in the tree carries a GPL header today, so if a contributor or agent ever hand-wrote one, the sweep or review caught it. The count of files the sweep manages is 384 today; the "314" the same paragraph quotes is stale for the same reason, and the fix stops quoting a number that has to be maintained by hand.

<em>Found while shipping another item in this loop: a subagent following CLAUDE.md's header rule noticed its instruction and the script it names disagree, and the disagreement was then measured directly.</em>
