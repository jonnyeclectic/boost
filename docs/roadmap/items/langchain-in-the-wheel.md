---
id: langchain-in-the-wheel
board: code
section: compat
status: shipped
owner: loop/langchain-extra
pr: 472
category: Release
complexity: M
impact: High
wow: 3
note: same import, same tests, zero new infrastructure — the wheel that already ships on every merge carries the integration too
order: 89
title: ship the LangChain integration inside the wheel, behind a <code>[langchain]</code> extra
---
The LangChain integration shipped as a separate <code>boost-langchain</code> distribution — and then
its release path stalled on the one step no loop can do: creating a second PyPI project with its own
Trusted Publisher. Meanwhile the research that was supposed to justify the standalone package
undermined it: <b>langchain-community is sunset</b> (archived read-only, June 2026), LangChain's
integrations listing accepts any PyPI name — the YAML already lists vendor SDKs that are not
<code>langchain-*</code> packages — and the in-host pattern is common practice
(<code>ragatouille</code> ships a retriever with a hosted LangChain docs page,
<code>langfuse</code>, <code>nemoguardrails</code> and <code>mlflow.langchain</code> all ship the
integration inside the main package). A standalone distribution was buying a cadence nobody needed:
boost releases far <i>more</i> often than langchain, not less.

<b>The fold.</b> <code>boost_langchain</code> becomes a second top-level package in the
<code>boost-skill-cli</code> wheel; a new <code>[langchain]</code> extra carries
<code>langchain-core&gt;=1,&lt;2</code> (and <code>pydantic</code>, which the retriever imports
directly). The base install stays zero-dependency — extras are opt-in metadata — and publishing
rides the existing every-merge <code>publish.yml</code> Trusted Publisher with no new
infrastructure. Deliberately top-level, <b>not</b> <code>boost_cli.langchain</code>: a submodule
would land inside the coverage and mutation gates while being unimportable in the base test venv,
dragging both 80% floors down for free. An import guard translates a missing
<code>langchain_core</code> into the one actionable message
(<code>pip install 'boost-skill-cli[langchain]'</code>), because the module files are now always
present.

<b>The honest caveat, and its expiry.</b> <code>[eval]</code> pins <code>langchain-core&lt;0.4</code>
(the ragas conflict), so <code>[eval]</code> and <code>[langchain]</code> cannot co-install —
requesting both fails loudly with <code>ResolutionImpossible</code> rather than silently breaking
one of them. Conflicting extras are legal, uploadable metadata; the pair stops conflicting the day
ragas ships its already-merged langchain-1.x fix. The path-filtered conformance leg keeps testing
the folded package against the real langchain stack, and the escape hatch stays open: if a
standalone distribution is ever wanted again, the extra's contents become a dependency on it and
<code>import boost_langchain</code> keeps working for everyone.
