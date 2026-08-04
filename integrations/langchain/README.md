# boost-langchain

LangChain bindings for [boost](https://github.com/jonnyeclectic/boost), the
package manager for AI coding skills. This package puts boost's tapped catalog
— skills, rules and workflows — behind LangChain's retriever and document
loader contracts, so a LangChain program can search it, stuff it into context,
or route on it.

**Scope check first:** if you are a LangChain developer who just wants skills
in your *editor* (Claude Code, Cursor, Windsurf, Gemini CLI), you do not need
this package — install the [boost CLI](https://pypi.org/project/boost-skill-cli/)
and run `boost install <skill>`. This package exists for the other direction:
putting the skill catalog *inside* a LangChain application.

## Install

```bash
pip install boost-langchain          # pulls in boost-skill-cli + langchain-core
boost tap anthropics/skills          # give boost something to search (once)
```

## Quickstart

```python
from boost_langchain import BoostRetriever

retriever = BoostRetriever(k=4)
docs = retriever.invoke("set up code review for a python repo")
for d in docs:
    print(d.metadata["name"], d.metadata["kind"], d.metadata["tap"])

# It is a standard Runnable retriever, so the usual chain shape works:
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt          # your ChatPromptTemplate
    | model           # your chat model
    | StrOutputParser()
)
chain.invoke("how should this repo handle commit messages?")
```

Each `Document` carries the item's full body as `page_content` (pass
`full_content=False` for just the one-line description) and
`name` / `kind` / `tap` / `version` / `source` / `engine` in `metadata`.

## Filtering by kind

boost indexes three item kinds; `kind` narrows retrieval to one of them:

```python
BoostRetriever(kind="rule")       # only rules (.mdc, .cursorrules, ...)
BoostRetriever(kind="workflow")   # only slash commands / subagents
BoostRetriever(kind="skill")      # only SKILL.md skills
```

## No key required — the degrade story

The retriever reuses boost's own engine rather than re-embedding the catalog,
which is the point: boost's retrieval quality is measured (its CI floors
recall@k, hit@1, MRR and nDCG@k over a golden query set), so this retriever
ships with numbers rather than claims. It also inherits boost's degrade
ladder:

- **No API key needed, ever.** The always-on engine is a pure-stdlib BM25
  full-content index that builds itself on first use.
- **Dense retrieval is an upgrade, not an entry fee.** With boost's `[rag]`
  extra installed the two engines are fused by reciprocal rank fusion; a
  Voyage or OpenAI key improves embedding quality but a local model ships
  with the extra.
- **Nothing tapped means `[]`, not an exception** — a chain keeps running
  without boost context rather than crashing on it.

`metadata["engine"]` names which engine actually answered
(`"BM25 full-content"`, `"dense vectors"`, or `"hybrid RRF (BM25 + dense)"`).

## LangGraph: skills as mid-run procedures

Instead of stuffing every procedure into the system prompt, let the graph
pull the right one for its current state (`pip install boost-langchain[langgraph]`):

```python
from boost_langchain import skill_context_node
from langgraph.graph import StateGraph, MessagesState, START

builder = StateGraph(MessagesState)
builder.add_node("skills", skill_context_node(k=3))   # or kind="workflow", or a configured BoostRetriever
builder.add_node("agent", call_model)                 # your model node
builder.add_edge(START, "skills")
builder.add_edge("skills", "agent")
```

The node retrieves against the last human message and injects the matching
procedures as one `SystemMessage`, each prefixed with its name, tap, path and
version — so a bad injection is traceable from the transcript. Nothing
retrieved (or nothing tapped) is a no-op, never an error. The node itself
imports only `langchain_core`; langgraph stays an optional extra.

## Loading a single skill

```python
from boost_langchain import SkillMarkdownLoader

# From a path (a SKILL.md, or a directory containing one):
doc = SkillMarkdownLoader("path/to/skill").load()[0]

# From boost's canonical store, for a skill you already installed:
doc = SkillMarkdownLoader.from_installed("brainstorming").load()[0]

doc.page_content        # the markdown body, frontmatter stripped
doc.metadata            # frontmatter keys (name, version, tags, ...) + source
```
