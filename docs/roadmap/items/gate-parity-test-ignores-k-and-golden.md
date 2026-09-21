---
id: gate-parity-test-ignores-k-and-golden
board: code
section: planned
status: shipped
category: Quality · Retrieval eval
complexity: M
impact: Med
wow: 3
note: the parity test now parses the whole eval_retrieval.py call in the Makefile, ci.yml and the refresh workflow with the script's own parser; a -k 5 in ci.yml alone fails it
order: 213
owner: loop/gate-parity-k
pr:
title: The CI-vs-Makefile floor-parity test compares only the floor VALUES, so changing <code>-k</code> in ci.yml turns a PASS into a FAIL with the test still green
---
<b>Measured.</b> Changing <code>-k 10</code> to <code>-k 5</code> in ci.yml alone leaves <code>TestTheGateIsDefinedOnce</code> at "2 passed" while the required gate flips from exit 0 to exit 1 — recall@k drops 0.852 to 0.753 against the 0.780 floor — and <code>make eval</code> stays green; the same test catches a floor-VALUE edit (hit@1 0.40 -&gt; 0.10) with "1 failed", proving the guard runs and simply cannot see <code>-k</code>.

<b>Reproduce it.</b>

<code>cd &lt;repo&gt;</code><br>
<code># 1. the k=5 vs k=10 measurement, against the shared read-only corpus:</code><br>
<code>H=$TMPDIR/audit-k; rm -rf "$H"; mkdir -p "$H/.boost"</code><br>
<code>cp -R "$TMPDIR/eval-home/cache" "$H/.boost/cache"; cp "$TMPDIR/eval-home/config.json" "$H/.boost/config.json"</code><br>
<code>export HOME=$H BOOST_HOME=$H/.boost BOOST_NO_AI=1</code><br>
<code>.venv/bin/python scripts/eval_retrieval.py -k 10 --fail-under 0.78 --floor hit@1=0.40 --floor MRR=0.52 --floor nDCG@k=0.58 --regression-eps 1 | tail -8</code><br>
<code>.venv/bin/python scripts/eval_retrieval.py -k 5  --fail-under 0.78 --floor hit@1=0.40 --floor MRR=0.52 --floor nDCG@k=0.58 --regression-eps 1 | tail -8</code><br>
<code># 2. the parity-test blindness, in a scratch copy (never edit the repo):</code><br>
…

<b>What adversarial verification corrected.</b> This card's numbers are the re-measured ones, not the ones first reported.

Four stated details are wrong. The defect itself reproduces exactly.

1. <code>why_it_matters</code> says a <code>-k</code> edit is "a silent redefinition of three of the four floored metrics". Measured, it is TWO: recall@k (0.852 -&gt; 0.753) and nDCG@k (0.657 -&gt; 0.624). hit@1 and MRR are k-independent by construction — <code>scripts/eval_retrieval.py:111-112</code> reads <code>"hit@1": lambda r, rel, k: hit_at_1(r, rel)</code> and <code>"MRR": lambda r, rel, k: reciprocal_rank(r, rel)</code>, both discarding <code>k</code> — and both measured identical at 0.473 / 0.605 at k=10 and k=5. (The <code>claim</code> field says "recall@k and nDCG@k", which is right; only <code>why_it_matters</code> contradicts it.)

2. "The comment block in ci.yml (twelve lines at :232-243)". The FLAGS-MUST-MATCH paragraph is EIGHT lines, <code>.github/workflows/ci.yml:232-239</code>. Line :240 is a bare <code>#</code> and :241 onward is the unrelated "THE CLONES ARE CACHED" block about cache availability.

3. C's stated mechanism is stale. "dropping <code>--regression-eps 1</code> restores the 0.02 default, so upstream corpus drift reddens every open PR" — <code>tests/eval/taps.txt</code> now pins a 40-char commit SHA per row, so upstream HEAD can no longer move the corpus. Measured: dropping the flag today exits 0 with no REGRESSION lines.

<b>What is NOT established.</b> Recorded because a card that overstates its own evidence is worse than no card.

SOURCE VERIFIED, NOT ALREADY_FIXED. <code>tests/unit/test_eval_corpus.py:404-412</code> still reads exactly as claimed: <code>_flags</code> does <code>re.findall(r"--floor\s+([\w@]+)=([\d.]+)", text)</code> plus <code>re.search(r"--fail-under\s+([\d.]+)", text)</code> and returns only that dict. <code>.github/workflows/ci.yml:232</code> still says "THE FLAGS MUST MATCH <code>make eval</code> — tests/unit/test_eval_corpus.py fails the build if they drift." Both file:line references in the finding are accurate.

NO SECOND GUARD EXISTS. <code>_flags</code> is the only comparison of ci.yml against the Makefile anywhere in the file (used at lines 423 and 439, the two tests in the class), and grepping <code>tests/unit</code> + <code>tests/functional</code> for any <code>-k</code> parity assertion found only unrelated <code>dense.retrieve(k=10)</code> and <code>boost chat -k</code> arg-validation tests.

NOT A DUPLICATE, BUT NAME THE ORIGIN CARD. <code>docs/roadmap/items/eval-corpus-was-not-actually-pinned.md</code> (status: shipped) is the card that INTRODUCED this parity test, and its body overclaims: "a unit test now compares the flags in <code>Makefile</code> and <code>ci.yml</code> and fails the build when they disagree — the drift was invisible precisely because two files each looked right on their own." That sentence is what this finding falsifies for three of the four flags. A card author should link it as the contradicted claim, not merge into it. I re-checked all 432 titles and grepped every item body for <code>TestTheGateIsDefinedOnce</code>, <code>test_eval_corpus</code>, <code>FLAGS MUST MATCH</code>, <code>_flags</code>, <code>regression-eps</code>, <code>golden-natural</code>, and for files mentioning both <code>ci.yml</code> and <code>Makefile</code> — the only hit is that origin card.

<b>Why it is worth doing.</b> The comment block in ci.yml (twelve lines at :232-243) and the test's own docstring both promise that the required check and the documented gate cannot diverge — that promise is why nobody re-reads the two invocations. It holds for one of the four flags that decide the gate. A <code>-k</code> edit in either file is a silent redefinition of three of the four floored metrics, and the measured gap at k=5 (0.753 vs a 0.780 floor) is on the failing side, so the first symptom is a red required check on an unrelated PR with a green <code>make eval</code> locally.

<b>What shipped.</b> <code>TestTheGateIsDefinedOnce</code> no longer pulls floor values out with a regex. It takes the one <code>scripts/eval_retrieval.py</code> call from the <code>eval</code> recipe and from each workflow step (continuations joined, comment lines skipped, the command cut at the first pipe, list operator or redirection), parses its argv with the script's own parser — now <code>build_parser()</code>, which <code>main</code> uses — and compares everything that comes back. Every flag the script accepts is covered, including one added later, and a flag it does not accept fails the test. Floors are compared as a mapping and <code>--golden</code> is resolved from the repo root, so <code>-k10</code>, reordered floors and <code>0.4</code> for <code>0.40</code> still match. Measured in a scratch copy with <code>-k 5</code> in ci.yml alone: the old class reports "2 passed"; the new one fails with <code>Differing items: {'k': 5} != {'k': 10}</code>. Dropping <code>--build</code>, adding <code>--golden</code> or <code>--engines</code>, or changing <code>--regression-eps</code> fail it the same way. Each case is a test that edits the real ci.yml text.

<b>The refresh workflow, decided by reading it.</b> Its scoring step must match exactly: everything it does differently (<code>set -o pipefail</code>, <code>tee</code>, keeping the exit code for the next step) sits outside the argv, and its PASS/FAIL banner claims to be the required gate's verdict. Its re-baseline step differs on purpose, since it saves rather than judges: no floors, no <code>--build</code> (the step before built the index), and no regression check to tune. But it must match the gate on <code>-k</code>, <code>--golden</code> and <code>--engines</code>, because the baseline records the cutoff and query set it was taken at, and every later <code>make eval</code> compares against it. That is now its own test.

<b>The claim this contradicts.</b> [[eval-corpus-was-not-actually-pinned]] says "a unit test now compares the flags in <code>Makefile</code> and <code>ci.yml</code> and fails the build when they disagree". It compared the floors, not the flags. The prose that repeated it is fixed. ci.yml's comment block now says what the test checks. The Makefile comment no longer says the corpus "tracks upstream HEAD rather than pinned commits", and its twenty-repo figures are the ones <code>tests/eval/baseline.json</code> records (0.841 / 0.484 / 0.607 / 0.655 — the card's 0.852 / 0.473 was an older measurement; the k=5 drop is the same 0.099). CLAUDE.md now says "identical arguments" where it said "identical floors".

<b>Not covered.</b> Only the <code>eval_retrieval.py</code> argv is compared. <code>BOOST_HOME</code> is spelled differently in each file (<code>$(EVAL_HOME)</code> and <code>${{ github.workspace }}/.eval-home</code>) and is not checked. Neither is <code>ensure_eval_corpus.sh</code>, where ci.yml's <code>FORCE=1</code> is a documented difference. <code>eval-scale.yml</code> is a separate, floorless measurement over another corpus and is out of scope.

<em>Found by an automated audit of retrieval/eval quality, the search &amp; browse surfaces, and first-run onboarding; every finding was then re-measured from scratch by an independent adversarial verifier whose instruction was to refute it. Verdict: <b>CORRECTED</b>. No fix is prescribed here — the measurement is the contribution.</em>
