#!/usr/bin/env bash
# adapt-demo.sh — prove the VALUE of `boost adapt`.
#
# Author ONE skill in boost, get native agents for CrewAI *and* the OpenAI
# Agents SDK, then edit the skill once and watch the change land in BOTH — the
# zero-drift payoff the feature exists for.
#
# No OPENAI_API_KEY needed: generating + instantiating the agents is fully
# offline. Only the optional final "run live inference" step wants a key.
#
# Everything runs in an ISOLATED sandbox HOME, so your real ~/.agents is never
# touched. Clean up with:  rm -rf "${DEMO_DIR:-/tmp/boost-adapt-demo}"
#
# Usage:  bash examples/adapt-demo.sh
set -euo pipefail

DEMO="${DEMO_DIR:-/tmp/boost-adapt-demo}"
SKILL="code-reviewer"

c()   { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }   # cyan banner
dim() { printf '\033[2m%s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m%s\033[0m\n' "$*"; }

# CrewAI's tiktoken dep has no cp314 wheel yet, so pin to 3.11-3.13.
PYBIN=""
for v in 3.13 3.12 3.11; do
  PYBIN="$(command -v "python$v" || true)"
  [ -n "$PYBIN" ] && break
done
[ -n "$PYBIN" ] || {
  echo "Need python3.11, 3.12, or 3.13 — CrewAI's tiktoken has no 3.14 wheel."
  echo "  macOS:  brew install python@3.13"
  exit 1
}

# ---- 1. isolated sandbox (HOME is boost's home lever, like tests/smoke.sh) --
c "1/5  Fresh, isolated sandbox"
rm -rf "$DEMO"; mkdir -p "$DEMO"
export HOME="$DEMO/home"; mkdir -p "$HOME"          # boost store → $DEMO/home/.agents
"$PYBIN" -m venv "$DEMO/.venv"                       # absolute py: independent of HOME
BOOST="$DEMO/.venv/bin/boost"; PY="$DEMO/.venv/bin/python"
dim "installing boost + crewai + openai-agents … (crewai is a big tree; ~2-3 min first run)"
# [anthropic] / [litellm] extras so the default LLM wiring (boost's ai.model =
# Claude) constructs — see the model line printed in step 3.
"$DEMO/.venv/bin/pip" -q install -U boost-skill-cli "crewai[anthropic]" "openai-agents[litellm]"
dim "boost $("$BOOST" --version | awk '{print $2}')  ·  isolated home = $HOME/.agents"

# ---- 2. author ONE skill (the single source of truth) -----------------------
c "2/5  Author ONE skill"
mkdir -p "$DEMO/src/$SKILL"
cat > "$DEMO/src/$SKILL/SKILL.md" <<'MD'
---
name: code-reviewer
description: Reviews a diff for correctness, security, and test coverage
---
Review the provided diff. Flag unhandled errors, injection-prone string
building, and missing tests on new branches. Rank findings by severity and
cite file:line.
MD
"$BOOST" import "$DEMO/src/$SKILL" >/dev/null
ok "installed '$SKILL' into boost (one SKILL.md — the single source)"

# ---- 3. VALUE (1): author once -> two frameworks, on boost's model (no key) -
c "3/5  VALUE 1 — one skill → native agents for TWO frameworks (no API key)"
# No --model: agents are wired to boost's configured ai.model (Claude) by
# default, so they run on the same LLM boost uses — no OpenAI key needed.
"$BOOST" adapt "$SKILL" --to crewai     -o "$DEMO/crew_agent.py"
"$BOOST" adapt "$SKILL" --to agents-sdk -o "$DEMO/sdk_agent.py"
cd "$DEMO"
"$PY" - <<'PYEOF'
import crew_agent, sdk_agent
from crewai import Agent as CrewAgent
from agents import Agent as SdkAgent
crew = next(v for v in vars(crew_agent).values() if isinstance(v, CrewAgent))
sdk  = next(v for v in vars(sdk_agent).values()  if isinstance(v, SdkAgent))
print(f"  CrewAI     -> {type(crew).__module__}.{type(crew).__name__}   role={crew.role!r}   llm={crew.llm.model!r}")
print(f"  Agents SDK -> {type(sdk).__module__}.{type(sdk).__name__}   name={sdk.name!r}   model={sdk.model.model!r}")
print("  \033[1;32m✓ same SKILL.md, two real Agents — both pinned to boost's model (Claude), no OpenAI key\033[0m")
PYEOF

# ---- 4. VALUE (2): edit once -> both update (zero drift) --------------------
c "4/5  VALUE 2 — edit the skill ONCE → both frameworks update (zero drift)"
SKILL_MD="$("$PY" -c "from boost_cli.core import store; print(store.skill_store_dir('$SKILL')/'SKILL.md')")"
MARKER="Always finish with a ranked shortlist of the top 3 issues."
printf '\n- %s\n' "$MARKER" >> "$SKILL_MD"
dim "edited the one source: $SKILL_MD"
dim "  + \"$MARKER\""
"$BOOST" adapt "$SKILL" --to crewai     -o "$DEMO/crew_after.py"
"$BOOST" adapt "$SKILL" --to agents-sdk -o "$DEMO/sdk_after.py"
bc=$(grep -c "$MARKER" crew_agent.py || true); bs=$(grep -c "$MARKER" sdk_agent.py || true)
ac=$(grep -c "$MARKER" crew_after.py || true); as=$(grep -c "$MARKER" sdk_after.py || true)
printf '  %-14s %-10s %-10s\n' ''            'CrewAI'   'AgentsSDK'
printf '  %-14s %-10s %-10s\n' 'before edit' "$bc"      "$bs"
printf '  %-14s %-10s %-10s\n' 'after  edit' "$ac"      "$as"
ok "one edit → both outputs carry it (1 & 1). Hand-porting means keeping N copies in sync forever."

# ---- 5. optional: run live inference (needs a key) --------------------------
c "5/5  (optional) run the agent — on boost's model, needs ANTHROPIC_API_KEY"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  "$PY" - <<'PYEOF'
from agents import Runner, Agent as SdkAgent
import sdk_agent
sdk = next(v for v in vars(sdk_agent).values() if isinstance(v, SdkAgent))
print("  " + Runner.run_sync(sdk, "Name two things you check in a code review.").final_output.replace("\n", "\n  "))
PYEOF
else
  dim "  ANTHROPIC_API_KEY not set — skipping live run (instantiation above already"
  dim "  proved the contract without a key). The agents default to boost's model"
  dim "  (Claude), so run for real with:"
  dim "    ANTHROPIC_API_KEY=sk-ant-... bash $0"
  dim "  (or export to a different provider: boost adapt … --model openai/gpt-4o)"
fi

c "done"
dim "artifacts in $DEMO :  crew_agent.py  sdk_agent.py  crew_after.py  sdk_after.py"
dim "clean up with:  rm -rf $DEMO"
