---
id: audit-output-wrap-tokens-splits-punctuation-off-backtick-spans-ins
board: code
section: dx
status: planned
category: CLI · Bug
complexity: S
impact: Low
wow: 1
note: the wrapper rejoins span + ")" with a space; one fix covers doctor, reindex and all help
order: 240
owner:
pr:
title: "<code>output._wrap_tokens</code> splits punctuation off backtick spans, inserting a stray space"
---
CLAUDE.md's wrap law makes a backtick span one atomic token so pasteable commands survive folding
&mdash; but <code>output._wrap_tokens</code> (<code>boost_cli/core/output.py:383&ndash;391</code>) also makes the
punctuation <em>next to</em> the span its own token, and <code>wrap()</code> rejoins tokens with a space. The
source strings are glued (<code>dense.py:320,325</code> ends <code>&hellip;[rag]'`;</code>, doctor wraps the hint in
<code>(%s)</code>); the space is manufactured entirely by the wrapper. Observed verbatim: <b>doctor</b> &mdash;
<code>(install the extra: `pip install 'boost-skill-cli[rag]'` )</code>; <b>reindex --dense</b> &mdash;
<code>`pip install boost-skill-cli[rag]` ; using the BM25 full-content engine</code>; <b>profile --help</b> &mdash;
<code>--prune  with `use` : fully uninstall skills not in the profile</code>; <b>replay --help</b> &mdash;
<code>id  history entry id (from `boost replay list` )</code>.

The reach is wider than three commands: verification showed the stray space is width-independent
(reproduced at <code>COLUMNS=60</code> under a TTY), and <code>cliparse._BoostHelpFormatter._split_lines</code>
(<code>cliparse.py:38&ndash;44</code>) delegates to <code>out.wrap</code>, so <b>every help screen</b> that puts
punctuation beside a code span shares the one defect. Cosmetic &mdash; nothing broken pastes &mdash; but it is the
output layer undoing its own typography, in the hints users are most likely to copy.

Fix, verified against the source: in <code>_wrap_tokens</code>, extend each span token to absorb adjacent
non-whitespace &mdash; match <code>\S*`[^`]*`\S*</code> (or merge a span with the preceding/following fragment
when the source had no whitespace between them). The span stays atomic and pasteable; doctor, <code>reindex
--dense</code> and all <code>_BoostHelpFormatter</code> help text are fixed in one place. Add a unit test in
<code>tests/unit</code> asserting <code>wrap('(see `x y`)')</code> keeps the paren glued. Help text renders into
<code>docs/commands.html</code>, so regenerate it (<code>make generate</code>). Roadmap item BOOST-D27 lists other
wrap gaps but not this one. Found by the 2026-08 CLI audit (cluster backtick-span-punctuation); repro in the
audit log.
