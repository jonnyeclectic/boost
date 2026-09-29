---
id: dense-local-built-store-displaced-by-a-key
board: code
section: shipped
status: shipped
category: Quality · Retrieval eval
complexity: S
impact: High
wow: 4
note: Exporting an API key takes a locally built store off the air, and doctor answers with a paid re-embed where `unset` is free. Every user who came in through `boost quickstart` is one `export` away from this.
order: 353
owner: loop/dense-local-displaced
pr: 990
title: A locally built vector store displaced by a new API key is told to re-embed through the paid provider, where unsetting the key is free
---
<b>The mirror of #989, and the expensive direction.</b> #989 taught <code>fix_hint</code> that a store built with an API key can be displaced two ways, and to name the <code>export</code> or the <code>unset</code> that restores it. A store built by the <b>local</b> model is displaced by exactly the same mechanism — a key the resolver prefers appears on the machine — and gets none of it: the branch is gated on <code>env = embed.KEY_ENV.get(built)</code> being truthy, and <code>local</code> has no env var, so it falls through to the table.

<b>Measured.</b> Two stores of 645,592 chunks, same machine, only <code>VOYAGE_API_KEY</code> set. Verbatim, through the real <code>dense.status()</code> ladder:

<code>##### store built with 'local', live key = VOYAGE</code><br>
<code>  status reason : provider-changed</code><br>
<code>  outranking('local') : ('VOYAGE_API_KEY',)</code><br>
<code>  DOCTOR |   ! semantic search silently off — 645592-chunk vector store built with</code><br>
<code>  DOCTOR |     rebuild it: `boost reindex --dense --force`</code><br>
<br>
<code>##### store built with 'openai', live key = VOYAGE</code><br>
<code>  status reason : provider-changed</code><br>
<code>  DOCTOR |     set the key it was built with: `export OPENAI_API_KEY=...`, then</code><br>
<code>  DOCTOR |     `unset VOYAGE_API_KEY` puts it back in front — or …</code>

<code>embed.outranking('local')</code> already computes the answer — <code>unset VOYAGE_API_KEY</code> — and restores that store instantly and for nothing. The line boost actually prints re-embeds 645,592 chunks through a metered API.

<b>Why it is not a corner case.</b> <code>boost quickstart</code> imports the published vector shards, and those are keyless: <code>BAAI/bge-small-en-v1.5</code> at 384 dimensions, built by the local model. So the default on-ramp leaves every user with a local-built store, and the first time one of them exports a Voyage or OpenAI key for anything at all, semantic search goes quiet and doctor bills them to get it back.

<b>The constraint any fix has to clear</b>, and the reason this is a separate card rather than a line in #989: <code>unset</code> is only the right advice for a local-built store <b>if the local model is installed</b>. On a partial <code>[rag]</code> install, unsetting the one key in force sends <code>provider()</code> to <code>None</code> and the ladder to <code>no-key</code> — the advice would switch off the only thing making search work. So the predicate needs to ask whether the local model is there — and the one to ask is <code>embed.local_installed()</code>, not <code>embed.local_available()</code>: <code>local_available</code> answers by importing the ONNX runtime, which is right for a caller about to embed and wrong for one about to word a sentence. <code>dense.free_shard_path</code>, the sibling that words the other keyed-machine hint, already uses <code>local_installed</code> for exactly that reason. Either way it is a check the key-built branches do not need.

Two more things fall out of that. The sentence needs a third variant — "puts the store's own key back in front" is false for a store that has no key; it is the local model being put back in front. And the admission test must be <code>built in embed.KEY_ENV or built == "local"</code>, never "has a recorded provider": <code>embed.outranking("")</code> returns <b>every</b> set key, so a store whose meta records no provider would be told to unset the machine's entire keyring on the strength of a blank field.

<b>Where it was found.</b> The adversarial verification pass on #989, which is also why the measurement exists. #989's PR body originally scoped this out as "not measured here"; it is measured now, and #990 removes the qualifier <code>docs/semantic-search.md</code> was carrying in the meantime.
