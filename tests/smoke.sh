#!/usr/bin/env bash
# End-to-end smoke test for boost, fully sandboxed under a throwaway HOME.
# Usage: bash tests/smoke.sh [--online]   (--online also taps anthropics/skills)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Honor $TMPDIR (defaults to /tmp, i.e. unchanged on CI and a normal dev box).
# Hardcoding /tmp made the whole suite fail opaquely wherever it is not
# writable — macOS per-user temp dirs, sandboxed agents, hardened CI images:
# mktemp fails, SB is empty, HOME becomes "", and every check dies on `/.boost`.
SB="$(mktemp -d "${TMPDIR:-/tmp}/boost-smoke-XXXXXX")" || {
  echo "smoke: cannot create a sandbox dir under ${TMPDIR:-/tmp}" >&2; exit 1; }
export HOME="$SB" BOOST_NO_AI=1 BOOST_ASSUME_YES=1 NO_COLOR=1
cd "$ROOT"

if command -v timeout >/dev/null 2>&1; then
  TIMEOUT=(timeout 60)
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT=(gtimeout 60)
else
  TIMEOUT=()   # macOS without coreutils: run without a watchdog
fi

PASS=0; FAIL=0; FAILED=()
run() {  # run <desc> <expected-exit> <cmd...>
  local desc="$1" want="$2"; shift 2
  local out rc
  out="$(${TIMEOUT[@]+"${TIMEOUT[@]}"} "$@" </dev/null 2>&1)"; rc=$?
  if [ "$rc" -eq "$want" ] && ! grep -q "Traceback" <<<"$out"; then
    PASS=$((PASS+1)); printf '  ok   %s\n' "$desc"
  else
    FAIL=$((FAIL+1)); FAILED+=("$desc (exit $rc, want $want)")
    printf '  FAIL %s (exit %s, want %s)\n' "$desc" "$rc" "$want"
    sed 's/^/       | /' <<<"$out" | head -12
  fi
}

echo "== sandbox: $SB"
FIX="$(python3 tests/make_fixture.py "$SB/fixture-tap")"
echo "== fixture: $FIX"

echo "== taps"
run "tap fixture"            0 ./boost tap "$FIX"
run "taps list"              0 ./boost taps
run "outdated (clean)"       0 ./boost outdated

echo "== everyday loop"
run "search jira"            0 ./boost search jira
run "install brainstorming"  0 ./boost install brainstorming
# --no-deps: install each fixture skill independently. jira-integration declares
# `requires: commit-messages`, which install now resolves — without this the
# separate `install commit-messages` below would hit the already-installed path.
run "install jira-integration" 0 ./boost install jira-integration --no-deps
run "install commit-messages"  0 ./boost install commit-messages
run "install tdd-workflow"     0 ./boost install tdd-workflow
run "install cowboy-coding"    0 ./boost install cowboy-coding
run "install duplicate fails"  1 ./boost install brainstorming
run "list"                   0 ./boost list
run "list --json"            0 ./boost list --json
run "info"                   0 ./boost info brainstorming
run "cat"                    0 ./boost cat brainstorming
run "preview"                0 ./boost preview brainstorming
run "explain (no AI)"        0 ./boost explain brainstorming
run "stats"                  0 ./boost stats brainstorming
run "adapt crewai"           0 ./boost adapt brainstorming --to crewai
run "adapt bad framework"    1 ./boost adapt brainstorming --to nope
run "count"                  0 ./boost count
run "log (journal)"          0 ./boost log
run "log skill"              0 ./boost log brainstorming
run "home --print"           0 ./boost home brainstorming --print
run "deps unmet/conflict"    1 ./boost deps
run "tag add"                0 ./boost tag brainstorming +ideation
run "trending"               0 ./boost trending
run "recommend"              0 ./boost recommend

echo "== quality & health"
run "doctor"                 0 ./boost doctor
run "lint"                   0 ./boost lint
run "verify"                 0 ./boost verify
run "drift"                  0 ./boost drift
run "test"                   0 ./boost test
run "fingerprint"            0 ./boost fingerprint
run "audit (fixture clean)"  0 ./boost audit
# rc 1 because the fixture installs a declared conflict pair (see the next
# check) and a conflict is MED. The unsigned fixture tap is only LOW, so this
# asserts both halves of the severity contract at once: the conflict is what
# raises rc, and the LOW findings alone would not have.
run "audit --skills (conflict)" 1 ./boost audit --skills
run "conflict finds pair"    1 ./boost conflict
run "changelog"              0 ./boost changelog brainstorming
run "attest"                 0 ./boost attest
run "health"                 0 ./boost health
run "quarantine"             0 ./boost quarantine cowboy-coding
run "quarantine --list"      0 ./boost quarantine --list
run "quarantine release"     0 ./boost quarantine --release cowboy-coding
run "decay"                  0 ./boost decay
run "heal"                   0 ./boost heal

echo "== package management"
run "pin"                    0 ./boost pin brainstorming
run "unpin"                  0 ./boost unpin brainstorming
run "sync --diff"            0 ./boost sync --diff
run "sync"                   0 ./boost sync
run "update"                 0 ./boost update
run "reinstall"              0 ./boost reinstall brainstorming
run "bundle dump"            0 bash -c './boost bundle dump > "$0/Boostfile"' "$SB"
run "export"                 0 bash -c 'cd "$0" && "'"$ROOT"'/boost" export brainstorming' "$SB"
run "snapshot save"          0 ./boost snapshot save before-uninstall
run "snapshot list"          0 ./boost snapshot list
run "uninstall"              0 ./boost uninstall cowboy-coding
run "conflict now clean"     0 ./boost conflict
# the other half of the severity contract: with the conflicting peer gone only
# LOW findings remain (the tap is still unsigned), so rc drops back to 0.
run "audit --skills now ok"  0 ./boost audit --skills

echo "== workspace scope (--local)"
# A throwaway repo, so the local install has a real project root to walk up to.
PROJ="$SB/proj"; mkdir -p "$PROJ/.git" "$PROJ/src/deep"
run "install --local"        0 bash -c 'cd "$0" && "'"$ROOT"'/boost" install tdd-workflow --local' "$PROJ"
run "local copy is real"     0 test -f "$PROJ/.claude/skills/tdd-workflow/SKILL.md"
run "local copy not a link"  1 test -L "$PROJ/.claude/skills/tdd-workflow"
run "project lock written"   0 test -f "$PROJ/.boost/skill-lock.json"
run "walk-up from a subdir"  0 bash -c 'cd "$0/src/deep" && "'"$ROOT"'/boost" install cowboy-coding --local' "$PROJ"
run "landed at the root"     0 test -d "$PROJ/.claude/skills/cowboy-coding"
run "no stray subdir store"  1 test -d "$PROJ/src/deep/.claude"
run "list --local"           0 bash -c 'cd "$0" && "'"$ROOT"'/boost" list --local' "$PROJ"
run "dup --local fails"      1 bash -c 'cd "$0" && "'"$ROOT"'/boost" install tdd-workflow --local' "$PROJ"
run "uninstall --local"      0 bash -c 'cd "$0" && "'"$ROOT"'/boost" uninstall tdd-workflow --local' "$PROJ"
run "local copy is gone"     1 test -d "$PROJ/.claude/skills/tdd-workflow"
run "user copy untouched"    0 test -d "$HOME/.agents/skills/tdd-workflow"

echo "== intelligence (heuristic fallbacks)"
run "simulate"               0 ./boost simulate tdd-workflow
run "distill (print)"        0 bash -c 'cd "$0" && "'"$ROOT"'/boost" distill brainstorming commit-messages -o merged-skill' "$SB"
run "infer (print)"          0 bash -c 'cd "'"$ROOT"'" && ./boost infer'
run "absorb (no history)"    0 ./boost absorb
run "context status"         0 ./boost context status
run "focus"                  0 ./boost focus brainstorming
run "focus --clear"          0 ./boost focus --clear
run "impact"                 0 ./boost impact

echo "== configuration"
run "config list"            0 ./boost config list
run "config set/get"         0 bash -c './boost config set ai.enabled false && ./boost config get ai.enabled && ./boost config unset ai.enabled'
run "policy list"            0 ./boost policy list
run "policy check"           0 ./boost policy check
run "create"                 0 bash -c 'cd "$0" && "'"$ROOT"'/boost" create my-test-skill --description "A test"' "$SB"
run "import created"         0 bash -c 'cd "$0" && "'"$ROOT"'/boost" import my-test-skill' "$SB"
run "completions zsh"        0 ./boost completions zsh
run "schedule status"        0 ./boost schedule status
run "clean --dry-run"        0 ./boost clean --dry-run
run "onboard --dry-run"      0 bash -c 'mkdir -p "$0/onboard-repo" && cd "$0/onboard-repo" && git init -q . && "'"$ROOT"'/boost" onboard --dry-run' "$SB"

echo "== team"
run "profile save"           0 ./boost profile save daily
run "profile list"           0 ./boost profile list
run "profile show"           0 ./boost profile show daily
run "cohort create"          0 ./boost cohort create pilot --skills brainstorming --percent 100
run "cohort list"            0 ./boost cohort list
run "pulse"                  0 ./boost pulse
run "replay list"            0 ./boost replay list
run "who"                    0 ./boost who
run "protocol status"        0 ./boost protocol status

echo "== every command answers --help"
while read -r c; do
  run "help: $c" 0 ./boost "$c" --help
done <<'CMDS'
install
uninstall
sync
update
reinstall
bundle
import
pin
unpin
snapshot
export
adapt
search
reindex
discover
recommend
browse
index
trending
stats
count
list
info
cat
edit
preview
explain
log
home
deps
tag
tap
untap
taps
outdated
catalog
distill
simulate
infer
absorb
evolve
context
focus
impact
doctor
lint
audit
verify
drift
test
fingerprint
quarantine
decay
heal
conflict
changelog
attest
health
config
clean
compact
create
policy
onboard
completions
schedule
serve
mcp
self-update
cohort
profile
protocol
pulse
replay
who
bmad
chat
hooks
run
trust
CMDS

if [ "${1:-}" = "--online" ]; then
  echo "== online: real registry"
  run "tap --defaults"       0 ./boost tap --defaults
  run "search pdf"           0 ./boost search pdf
  run "count (online)"       0 ./boost count
fi

echo
echo "== results: $PASS passed, $FAIL failed"
if [ "$FAIL" -gt 0 ]; then
  printf '  - %s\n' "${FAILED[@]}"
  exit 1
fi
