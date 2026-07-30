# C4 Dynamic — what `boost install` actually does

The install path is where most of the engine meets. This is the `user`-scope skill case; rules and
workflows branch at step 5 into `_install_rule` / `_install_workflow`, and `project` scope writes
real directories inside the repo instead of symlinking out of the canonical store.

```mermaid
C4Dynamic
  title Dynamic Diagram — boost install <name> (user scope, kind=skill)

  Person(dev, "Developer", "Runs the command")

  Container_Boundary(engine, "boost_cli") {
    Component(cmd, "commands/pkg", "Python", "Thin CLI glue")
    Component(cat, "core/registry + catalog", "Python", "Resolves the entry")
    Component(res, "core/resolve", "Python", "Dependency closure")
    Component(trust, "core/policy + capabilities + scanners", "Python", "Governance gate")
    Component(store, "core/store", "Python", "Copy and link")
    Component(targets, "core/agents + rules + workflows", "Python", "Per-agent materialisation")
    Component(lock, "core/lockfile + integrity", "Python", "Records the digest")
  }

  ContainerDb(canon, "~/.agents/skills", "files", "Canonical store")
  ContainerDb(links, "~/.claude, ~/.cursor, ~/.windsurf", "symlinks", "Linking agents")

  Rel(dev, cmd, "1. boost install <name>")
  Rel(cmd, cat, "2. Look up the entry in the cached catalog")
  Rel(cmd, res, "3. Expand to the full dependency closure")
  Rel(cmd, store, "4. install(entry)")
  Rel(store, trust, "5. Gate: policy, capabilities, typosquat, secrets, injection")
  Rel(store, canon, "6. Copy the skill directory in")
  Rel(store, targets, "7. Link and materialise per agent")
  Rel(targets, links, "8. Symlink into each linking agent")
  Rel(store, lock, "9. Record version + sha256 in .skill-lock.json")
  Rel(store, dev, "10. Report what was written")

  UpdateRelStyle(store, trust, $offsetY="-20")
  UpdateRelStyle(store, lock, $offsetY="20")
```

## The parts that are easy to get wrong

**Step 5 fails closed.** The gate raises `BoostError` rather than warning. A skill whose declared
capabilities exceed policy, or that trips the secret / prompt-injection / typosquat scanners, is
not installed at all — there is no "installed but quarantined" state to reason about later.

**Step 7 is not "symlink into every agent".** Only `agents.linking_agents()` get symlinks. Gemini
CLI reads `~/.agents/skills` natively and is deliberately excluded, because linking into
`~/.gemini/skills` too would put one skill in two of its discovery tiers and produce a "Skill
conflict detected" line per skill per session. Rules and workflows *do* materialise into
`~/.gemini/`, so the right helper depends on what you are writing —
see [c4-containers.md](c4-containers.md).

**Step 9 is binding, not advisory.** `core/integrity` makes the recorded digest enforceable, which
is what lets `boost sync` and `boost doctor` tell "the user edited this skill" apart from "the tap
moved underneath it". `core/staleness` is the single source of truth for the second question.

## Where uninstall differs

Uninstall is not the reverse of this diagram. It removes the canonical copy, sweeps every symlink
that pointed at it — including stale links left by an agent that was disabled since install — and
drops the lock entry. Sweeping links for agents that are *not* currently enabled is the part
hand-rolled reversals miss, which is why `store.uninstall` owns it rather than the command layer.
