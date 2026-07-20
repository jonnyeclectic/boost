# boost examples

Runnable demos of boost features. Each script is self-contained and sandboxes
its state under a throwaway `HOME`, so it never touches your real `~/.agents`.

## `adapt-demo.sh` — the value of `boost adapt`

Shows why [`boost adapt`](../docs/adapters.html) exists: **author one skill,
run it in every framework, with zero drift.**

```bash
bash examples/adapt-demo.sh
```

What it does (all offline — **no `OPENAI_API_KEY` needed**):

1. Spins up an isolated sandbox and installs `boost` + `crewai` +
   `openai-agents` into a fresh venv.
2. Authors **one** `SKILL.md` and imports it into boost.
3. **Value 1** — renders it to *both* frameworks and instantiates each:
   a real `crewai.Agent` and a real `agents.Agent` from the same source, no
   hand-porting. Both are wired to **boost's configured `ai.model` (Claude)** by
   default, so they run on the same LLM boost uses — no OpenAI key. Override per
   run with `boost adapt … --model openai/gpt-4o`, or `--model none` for the
   framework's own default.
4. **Value 2** — edits the skill **once** and re-adapts; the change appears in
   **both** generated files (before/after `0 0` → `1 1`). That is the
   drift-killing payoff: one edit, every runtime current.
5. Optional: if `ANTHROPIC_API_KEY` is set, actually runs the agent on Claude.

Requirements: **Python 3.11–3.13** (CrewAI's `tiktoken` dependency has no 3.14
wheel yet; boost itself supports 3.9–3.14). Clean up with
`rm -rf /tmp/boost-adapt-demo`.

> The same import path is exercised in CI by
> [`.github/workflows/adapter-conformance.yml`](../.github/workflows/adapter-conformance.yml),
> which installs each real framework and asserts the emitted file instantiates.
