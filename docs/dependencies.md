# Dependency policy

How boost chooses a dependency, how it obtains one, how it tracks what it has,
and the threshold at which a finding blocks a release. Written down because
"we run a scanner" is not a policy — a policy says what happens when the scanner
finds something.

## The selection rule: the runtime has no dependencies

**Nothing in `boost_cli/` may import a third-party package.** The default
install is pure standard library, and `import-linter` plus the lint gate enforce
it on every pull request, so the rule cannot erode by accident.

That is the whole supply-chain posture in one sentence. A dependency you do not
have cannot be typosquatted, cannot be abandoned, cannot ship a compromised
release, and cannot pull in forty transitive packages you never evaluated. It
costs something — `boost_cli/core/ed25519.py` exists because CPython ships no
Ed25519 and boost will not add a dependency to get one (see
[`security-design.md`](security-design.md)) — and the project pays that cost
deliberately.

Dependencies therefore exist in only two places:

| Where | What | Who is exposed |
|---|---|---|
| **Optional extras** — `[rag]`, `[eval]`, `[bdd]`, `[langchain]` | Declared in `pyproject.toml` | Only users who explicitly install that extra |
| **Development toolchain** | `requirements/*.in` → `requirements/*.txt` | Only contributors and CI |

Neither is on the default install path.

### Before a new dependency is accepted

An extra or a toolchain entry is added only when all of these hold:

1. **It cannot reasonably be standard library.** The first question is always
   whether the thing can be written in `boost_cli/` in under a few hundred
   reviewable lines. Often it can.
2. **It is actively maintained and has a compatible licence.** The licence gate
   (`licenses.yml`) runs on every pull request and fails on a licence outside
   the allowed set, so an incompatible one cannot land quietly.
3. **It earns its transitive closure.** A package that drags in a large tree is
   judged on the whole tree, not on itself.
4. **Its absence degrades cleanly.** Every optional extra must fail soft: with
   the extra missing, boost reports what is missing and names the one command
   that fixes it, rather than crashing.

## How dependencies are obtained

**By hash, over HTTPS, from PyPI — never by version alone.**

`requirements/*.txt` pin an exact version *and every artifact's sha256* for the
full transitive closure. `pip --require-hashes` enforces them, so a yanked,
re-uploaded or tampered artifact fails the install instead of silently changing
a build. A contributor's `make venv` and a CI runner resolve to identical bytes.

```bash
python3 scripts/lock_toolchain.py            # regenerate the .txt files
python3 scripts/lock_toolchain.py --upgrade  # re-resolve to newest allowed
python3 scripts/lock_toolchain.py --check    # what `make lint` runs
```

The `--check` run is part of the lint gate, so a `.txt` that has drifted from
its `.in` declaration fails the build. Commit both.

## How dependencies are tracked

| Mechanism | What it does | Blocking? |
|---|---|---|
| **Dependabot** | Opens a pull request per upgrade; multi-path actions are grouped so a release lands as one PR | Advisory |
| **`pip-audit`** | Fails when a resolved dependency matches a known OSV/PyPI advisory. Also runs weekly, so a newly published advisory against unchanged code is caught | **Required check** |
| **`scan-pr / osv-scan`** | OSV-Scanner diffed against the base branch — fails on what the pull request *adds* | **Required check** |
| **`licenses.yml`** | Fails on a licence outside the allowed set, per extra | Runs on every PR |
| **CycloneDX SBOM** | Generated per released wheel at build time and attached to the GitHub release | Per release |
| **Pinned action SHAs + `zizmor`** | Every `uses:` is a commit SHA; `zizmor` fails a PR on an unpinned or mismatched ref | Runs on every PR |

## Remediation thresholds

What actually happens when something is found.

| Finding | Threshold | Action |
|---|---|---|
| Vulnerability in a **runtime** dependency | Any severity | Cannot occur — there are none. If one ever appears, the import is the bug and it is removed. |
| Vulnerability, **critical or high**, in an extra or the toolchain | Any | Blocks the merge. Upgrade, replace, or remove the dependency before the pull request lands. |
| Vulnerability, **medium**, reachable from boost's own code paths | Any | Treated as high: blocks the merge. |
| Vulnerability, **medium or low**, not reachable | Fix within the next Dependabot cycle | Does not block, but is not ignored — it is tracked to a fix, not closed. |
| Incompatible **licence** | Any | Blocks the merge. |

Because every merge to `main` cuts a release, "blocks the merge" and "is fixed
before release" are the same statement. There is no window in which a known,
unremediated finding sits on `main` waiting for a release train.

### Suppressing a finding

A finding may be suppressed **only** when it is genuinely non-exploitable here,
and only with the reason recorded in the repository where the next reader will
find it — not in a scanner dashboard. The bar is a written argument, in the
config file or the pull request that adds the exemption, naming:

- the advisory or licence being exempted,
- why it cannot affect boost specifically, and
- what would have to change for the exemption to stop being true.

An exemption without that argument is a policy violation, not a shortcut. The
existing licence-gate exemption for `cramjam` — which names the upstream licence
in the exemption itself — is the shape to copy.

Suppressing a finding because it is inconvenient, or because a fix is not
available yet, is not permitted; the dependency is removed instead. The same
rule governs static-analysis findings, and for the same reason: a dismissal that
misrepresents the posture is worse than an open finding that describes it
accurately.

## Related

- [`security-design.md`](security-design.md) — the threat model, including
  supply-chain compromise and the mitigations above in context
- [`openssf-badge.md`](openssf-badge.md) — how this maps to the badge criteria
- [`../SECURITY.md`](../SECURITY.md) — reporting a vulnerability
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — the toolchain and the gates
