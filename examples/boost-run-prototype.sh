#!/usr/bin/env bash
# boost-run-prototype.sh — the thinnest slice of a future `boost run`.
#
# Shows the "one command → a live agent doing the task" wow that turns
# `boost adapt` from a code generator into an outcome:
#
#     search/author a skill  →  boost adapt (the brain)
#                            →  + a file-read tool (the hands)
#                            →  Runner.run on boost's model (Claude)
#                            →  a real review of a real file
#
# boost adapt gives the agent DEFINITION; this script adds a tool and executes
# it — exactly what a shipped `boost run` would fold into one command.
#
# Needs ANTHROPIC_API_KEY for the actual run (everything before it is offline).
# Sandboxed on HOME; clean up with:  rm -rf "${DEMO_DIR:-/tmp/boost-run-demo}"
#
# Usage:  ANTHROPIC_API_KEY=sk-ant-... bash boost-run-prototype.sh
set -euo pipefail

DEMO="${DEMO_DIR:-/tmp/boost-run-demo}"
SKILL="code-reviewer"
PYBIN=""
for v in 3.13 3.12 3.11; do PYBIN="$(command -v "python$v" || true)"; [ -n "$PYBIN" ] && break; done
[ -n "$PYBIN" ] || { echo "Need python3.11-3.13 (LiteLLM/tiktoken); brew install python@3.13"; exit 1; }

c()  { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
dim(){ printf '\033[2m%s\033[0m\n' "$*"; }
ok() { printf '\033[1;32m%s\033[0m\n' "$*"; }

c "1/4  sandbox + install (boost + openai-agents[litellm])"
rm -rf "$DEMO"; mkdir -p "$DEMO"; export HOME="$DEMO/home"; mkdir -p "$HOME"
"$PYBIN" -m venv "$DEMO/.venv"
BOOST="$DEMO/.venv/bin/boost"; PY="$DEMO/.venv/bin/python"
dim "installing … (~2-3 min first run)"
"$DEMO/.venv/bin/pip" -q install -U boost-skill-cli "openai-agents[litellm]"

c "2/4  a skill = the agent's brain (author locally; or 'boost search' any catalog skill)"
mkdir -p "$DEMO/src/$SKILL"
cat > "$DEMO/src/$SKILL/SKILL.md" <<'MD'
---
name: code-reviewer
description: Reviews a file for correctness, security, and error handling
---
You are a precise code reviewer. Use the read_file tool to read the file you are
asked to review, then list concrete issues as a short bulleted list — each with
the line and a one-line fix. Focus on real bugs (crashes, unhandled errors,
injection, missing checks). Be terse.
MD
"$BOOST" import "$DEMO/src/$SKILL" >/dev/null
"$BOOST" adapt "$SKILL" --to agents-sdk -o "$DEMO/agent_def.py"    # wired to boost's model
ok "adapted '$SKILL' → agent_def.py (on boost's model, Claude)"

# a target file with an obvious bug for the agent to actually find
cat > "$DEMO/target.py" <<'PY'
def get_user(users, uid):
    # BUG: no membership check — KeyError on unknown uid
    return users[uid]

def run_query(db, name):
    # BUG: SQL built by string concat — injection
    return db.execute("SELECT * FROM users WHERE name = '" + name + "'")
PY
dim "target file with two planted bugs: $DEMO/target.py"

c "3/4  give the brain HANDS (a read_file tool) — what a shipped 'boost run' would wire"
cat > "$DEMO/run.py" <<'PY'
import pathlib, sys
import agent_def
from agents import Agent, Runner, function_tool

base = next(v for v in vars(agent_def).values() if isinstance(v, Agent))  # the adapted agent

@function_tool
def read_file(path: str) -> str:
    """Read a text file and return its contents."""
    return pathlib.Path(path).read_text()[:8000]

# boost gave the brain (instructions + model); we add the hands (tools)
reviewer = Agent(name=base.name, instructions=base.instructions,
                 model=base.model, tools=[read_file])
print(f"  wired agent: {reviewer.name}  model={reviewer.model.model}  tools={[t.name for t in reviewer.tools]}")

target = sys.argv[1] if len(sys.argv) > 1 else "target.py"
result = Runner.run_sync(reviewer, f"Review the file at {target}.")
print("\n----- review -----\n" + result.final_output)
PY

c "4/4  RUN it — a live agent reviewing the file, on Claude"
cd "$DEMO"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  "$PY" run.py target.py
  ok "^ an agent you searched/authored, wired with a tool, found the bugs — on boost's model"
else
  # still prove the wiring works with no key
  "$PY" - <<'PY'
import agent_def
from agents import Agent, function_tool
import pathlib
base = next(v for v in vars(agent_def).values() if isinstance(v, Agent))
@function_tool
def read_file(path: str) -> str: return pathlib.Path(path).read_text()
reviewer = Agent(name=base.name, instructions=base.instructions, model=base.model, tools=[read_file])
print(f"  wired agent: {reviewer.name}  model={reviewer.model.model}  tools={[t.name for t in reviewer.tools]}")
print("  \033[1;32m✓ agent + tool constructed (no key). Set ANTHROPIC_API_KEY to see it review.\033[0m")
PY
  dim "  run for real:  ANTHROPIC_API_KEY=sk-ant-... bash $0"
fi

c "done"
dim "artifacts in $DEMO :  agent_def.py (from boost adapt)  run.py (the +tools+run wrapper)  target.py"
dim "clean up:  rm -rf $DEMO"
