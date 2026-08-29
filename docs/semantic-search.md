# Semantic search: a quickstart

Two commands turn it on, no account and no API key. This page covers what you
get, what it costs, and how to tell whether it is actually running.

For the design behind it, see [rag-architecture.md](rag-architecture.md). This
page is the user-facing version.

## Why you would want it

boost searches with BM25 by default. BM25 matches words, and it is very good
when your query shares vocabulary with the skill you are looking for. It has
nothing to work with when the query doesn't.

Ask BM25 for `tdd` and it finds the TDD skills, because the word is right there
in the file. Ask it `my app is slow` and it looks for skills containing the
words "app" and "slow", which is not what you meant. Semantic search ranks by
meaning, so that query reaches the profiling and performance skills without
sharing a word with any of them.

You do not choose between the two. When both indexes exist boost runs both and
fuses the rankings, so a query that suits one engine is not penalised by the
other. `boost search` prints `hybrid RRF` when that is what happened.

## Turn it on

```bash
pip install "boost-skill-cli[rag]"   # vector store + a local embedding model
boost reindex --dense                # embed everything you have tapped
```

The first run downloads `BAAI/bge-small-en-v1.5`, about 133 MB. It is pinned by
sha256, cached under `~/.boost/cache/models`, and runs on your CPU. No text
leaves the machine, then or later.

How long `reindex --dense` takes depends on how much you have tapped. The
starter set from `boost tap --defaults` is minutes. A machine with hundreds of
registries is a coffee break, and the command tells you where it is.

## Check that it worked

```bash
boost doctor
```

`doctor` names which engine is serving and, when dense is not, which of the
three links is missing: the extra, a working backend, or a built store. `boost
search` prints the same thing on the results header, so you never have to guess
whether a disappointing result came from the good ranker or the fallback.

Then try a query that BM25 cannot answer:

```bash
boost search "my app is slow"
boost search "how do I stop shipping bugs on friday"
```

## Using an API key instead

A key buys a larger embedding model. Nothing else changes.

| | Needs | Dimensions |
|---|---|---|
| Local (default) | the `[rag]` extra | 384 |
| `VOYAGE_API_KEY` | a Voyage account | 1024 |
| `OPENAI_API_KEY` | an OpenAI account | 1536 |

Set one and boost prefers it automatically, re-embedding on your next
`boost reindex --dense`. Voyage wins if both are set.

Be deliberate about this, because switching providers is not free. Vectors are
only meaningful inside the embedding space that produced them, so changing
provider or model invalidates every vector you have and forces a full re-embed.
On a large catalogue that is a real bill. `boost doctor` will tell you the store
was built by a different provider rather than silently serving nonsense.

## Keeping it current

`boost reindex --dense` after tapping a new registry. It embeds what changed
rather than starting over.

To force a rebuild, add `--force`. You need it after changing provider or model,
and `boost doctor` says so when you do.

## Sharing vectors instead of re-embedding them

Embedding is the expensive step, and its output is portable between machines
running the same backend:

```bash
boost reindex --export-shard <tap> > shard.json   # on the machine that paid
boost reindex --import-shard shard.json           # on the one that didn't
```

An import is refused unless the shard matches this store's backend and the tap's
current commit, so a stale or foreign shard cannot quietly poison your index.

This is separate from `boost catalog --export`, which carries catalogue JSON and
deliberately no vectors, for the same reason.

## When something is wrong

`boost doctor` gives one next action per problem. The full table:

| What doctor says | What to do |
|---|---|
| no backend | `pip install 'boost-skill-cli[rag]'` |
| no store | `boost reindex --dense` |
| store is empty | `boost reindex --dense --force` |
| version, model, provider or dimension changed | `boost reindex --dense --force` |
| no key, and a store built with one | set the key it was built with. Reinstalling the extra swaps in the local model and forces a full re-embed |

That last row is the one worth reading twice. If your store was built against
Voyage or OpenAI and the key later goes missing, the fix is to put the key back.
The generic "reinstall the extra" answer would install the local model, change
the provider, and re-embed every vector you already paid for.

## Search is slow

On a large store, check `boost doctor` for a store that is ready but not
quantized, and run `boost reindex --dense` to quantize it.

Quantizing re-encodes vectors already on disk. It embeds nothing and costs no
API calls. What it buys is the difference between scanning every vector at full
width and scanning a one-bit-per-dimension copy first, then re-ranking a small
pool exactly. On a 750,416-chunk store that took a query from 28.2 seconds to
1.05 seconds, returning the same rows in the same order.

It costs disk while it runs: roughly a 14% increase in the finished store, and
about twice the size at the peak while both copies exist.
