# boost's security design

boost installs code that an AI coding agent will read and act on. That is the
whole threat: the interesting attack is not against boost's process, it is
against the *agent* that loads what boost installed, through a file boost put
where the agent looks. This document names the trust boundaries, applies the
classic design principles to them, and lists the error classes that actually
apply to a package manager written in Python — each with the mitigation in this
repository that counters it.

Report a vulnerability through the process in [SECURITY.md](../SECURITY.md).
Do not open a public issue.

## What boost is, in security terms

boost is a local CLI. It has no server, no accounts, no inbound authentication,
and no network listener except the explicitly-invoked `boost serve`. It:

1. **clones** third-party git repositories ("taps") into `~/.boost/repos/`,
2. **parses** Markdown out of them into a catalogue,
3. **copies** selected items into `~/.agents/skills/` and symlinks or renders
   them into each agent's directory (`~/.claude/`, `~/.cursor/`,
   `~/.windsurf/`, `~/.gemini/`).

Step 3 is the consequential one. A **skill** is a file the agent may load; a
**rule** is materialised *into the agent's standing context file* — the text the
agent reads every session. Installing a rule is therefore the most invasive
thing boost does, and the code path treats it that way.

## Trust boundaries

| Boundary | Trusted side | Untrusted side |
|---|---|---|
| **Tap content** | boost's own code | every byte of a cloned registry: file names, paths, YAML frontmatter, body text |
| **Catalogue bundle** | the importing machine | a `boost catalog export` tarball received from elsewhere |
| **The agent** | — | boost cannot police what an agent does with a file it has loaded |
| **The toolchain** | the pinned hashes in `requirements/` | PyPI, and anything it resolves to |
| **CI** | the workflow files in this repo | every third-party action, and anything a fork's PR can influence |

The single most important consequence: **a tap author is an attacker for
modelling purposes.** They choose the frontmatter `name`, the file paths, the
body, and the repository layout. Every one of those reaches a filesystem
operation.

## Design principles applied

These are Saltzer and Schroeder's eight, plus the two that a supply-chain tool
has to answer for. Each is a claim about this codebase, not a general aspiration.

**Economy of mechanism.** boost's runtime is standard library only — no
third-party import is permitted anywhere in `boost_cli/`, and `import-linter`
plus the lint gate enforce it. There is no runtime dependency tree to be
compromised. The optional dense-retrieval extra (`[rag]`) is the sole exception
and is opt-in, off by default, and never on the install path.

**Fail-safe defaults.** Installation is deny-by-default at each hazardous point:
tar members are accepted only if they are regular files with plain basenames
directly under `catalog/`; a path component is accepted only if it matches
`_SAFE_COMPONENT` and is neither `.` nor `..`; a served skill name must match
`^[A-Za-z0-9._-]+$`. Where rejection is not an option — the catalogue indexer
must not fail the whole scan on one hostile entry — the unsafe name is
*rewritten* by `util.safe_component`, never passed through.

**Complete mediation.** There is exactly one place to ask "may this name be
joined onto a directory?" (`util.is_safe_component`) and exactly one place to
join a relative path inside a base (`serve._safe_join_within`). Archive
extraction validates a member's name *and then discards it*, rebuilding the
destination from the basename — a check that feeds its own input forward is one
refactor away from being decorative.

**Open design.** Everything here is public: the source, the workflows, the
pinned hashes, the threat model you are reading. No security property depends on
an attacker not knowing how boost works. Tap provenance rests on Ed25519 public
keys, which are meant to be published.

**Separation of privilege.** Publishing to PyPI requires *both* a merge to
`main` through a protected branch with required checks *and* the OIDC identity
that GitHub mints for `publish.yml` specifically — there is no long-lived PyPI
token anywhere. Release artifacts additionally carry SLSA build provenance
attestations.

**Least privilege.** boost never runs as root, never asks for elevation, never
executes tap content, and never invokes a shell (`shell=True` appears nowhere in
the codebase; every subprocess is an argument vector). Each CI job declares its
own `permissions:` block; the default is read-only and write scopes sit on the
one job that needs them, which is what `zizmor`'s excessive-permissions audit
checks on every PR.

**Least common mechanism.** A tap clone is not a shared writable area. Clones
are `--filter=blob:none --sparse` with a cone covering exactly the Markdown that
`catalog.scan_dir` opens, so a tap's non-Markdown payload is *not fetched at
all* — 458 taps hold 12 GB unrestricted and 1.9 GB under the cone. Anything that
needs a skill's real files must go through `store.source_dir_for`, which
materialises the narrow set deliberately.

**Psychological acceptability.** The safe path is the easy one. `boost install`
does the right thing with no flags; `boost doctor` names the single next action
for each problem it finds rather than a menu; the digest tripwire below reports
drift by default and only *enforces* when the user opts in, so the secure
posture is reachable without a surprise breakage first.

**Verifiable provenance.** `core/minisign.py` and `core/ed25519.py` verify
minisign signatures over tap content against a trusted Ed25519 public key. Both
are **verify-only** — boost holds no private key material and cannot sign.
Correctness is pinned by the RFC 8032 §7.1 test vectors in the unit suite.

**Tamper evidence.** Every installed item records a sha256 of its content and
the commit it came from in the v3 lock file. `core/integrity.py` promotes that
digest from advisory to binding: with `security.enforce_digest` set, any command
that reads a skill's content first checks the on-disk tree against its locked
digest and refuses to serve a tree that has drifted. `boost verify` reports the
drift either way. boost cannot control what the agent loads, but it can refuse
to hand back bytes that no longer match what the user installed and reviewed.

## Common error classes, and what counters each

These are the CWE/OWASP classes that genuinely apply to a Python CLI that clones
repositories and writes files. Classes that do not apply (SQL injection — no
database; XSS — no rendered web application beyond the static docs site) are
omitted rather than padded.

| Error class | Where it would bite boost | Mitigation in this repo |
|---|---|---|
| **Path traversal** (CWE-22) | a tap's frontmatter `name` or a bundle member named `../../../.ssh/authorized_keys` | `util.is_safe_component` / `safe_component`; `catalogbundle._safe_members` rebuilds the destination from a validated basename; `serve._safe_join_within` |
| **OS command injection** (CWE-78) | a tap or skill name interpolated into a `git` invocation | no `shell=True` anywhere; every subprocess call is an argument list |
| **Archive extraction / "zip slip"** (CWE-22, CWE-409) | `boost catalog import` of a hostile tarball | members capped at `MAX_MEMBERS`; symlink, device and directory-traversing entries rejected outright |
| **Link following** (CWE-59) | a symlink planted in a tap clone or an agent skills directory | the store is the single source of truth and agent directories are links *out* of it; stale-link sweeps iterate `agents.linking_agents()` |
| **Untrusted deserialization** (CWE-502) | YAML frontmatter, JSON caches | frontmatter is parsed by boost's own line parser, never `yaml.load`; ruff's `S` (flake8-bandit) family fails the build on unsafe YAML loading |
| **Supply-chain / dependency compromise** (CWE-1357) | a tampered lint or test tool | `requirements/*.txt` pin an exact version *and* every artifact's sha256 for the full transitive closure; pip enforces them. Runtime has no dependencies to compromise |
| **Compromised CI action** (CWE-829) | a mutable action tag moved by an attacker | every `uses:` is pinned to a commit SHA; `zizmor` fails a PR on an unpinned or mismatched ref; `harden-runner` audits egress |
| **Leaked credentials** (CWE-798) | a token committed to the repository | `gitleaks` runs in CI on every push with an allowlist covering only boost's own synthetic scanner fixtures |
| **Known-vulnerable dependencies** (CWE-1104) | the optional extras and the dev toolchain | `osv-scanner`, `pip-audit` and Dependabot; an SBOM is published per release |
| **Insecure download** (CWE-494, CWE-319) | fetching a tool or a tap over plaintext HTTP | every download in CI is HTTPS; taps clone over HTTPS or SSH; release artifacts are attested |
| **Improper input validation** (CWE-20) | any of the above, reached through a field boost did not think was input | the fuzz workflow runs `atheris` against the parsers; the mutation gate (≥80% of `boost_cli/core` mutants killed) makes an unexercised validation branch fail the build |

## Cryptography boost uses

boost implements no cryptographic protocol and holds no secret. It uses:

- **Ed25519 signature verification** (RFC 8032) — tap provenance, verify-only.
- **BLAKE2b-512** — the prehash mode minisign uses for large inputs.
- **SHA-512** — internal to Ed25519, per RFC 8032.
- **SHA-256** — content digests and lock-file integrity.

All four are publicly published and expert-reviewed. Nothing here uses MD5,
SHA-1, DES or RC4 in any role. boost generates no keys and no nonces, so it
needs no random number generator — `random` is imported nowhere in `boost_cli/`.

The one place boost departs from "call a library, do not reimplement" is
`core/ed25519.py`, and it is a deliberate trade the stdlib-only rule forces:
CPython ships no Ed25519 primitive, so verifying a signature without a runtime
dependency means implementing the verify half of RFC 8032. The exposure is
bounded — it is *verification only*, over public keys and public signatures,
with no secret to leak through a timing side channel, and its correctness is
pinned to the published RFC 8032 test vectors. Signing stays with the
publisher's real tools (`minisign`, Sigstore).

## Assurance: what actually runs

Every one of these gates blocks a merge to `main`.

| Gate | What it buys |
|---|---|
| CodeQL | semantic static analysis for vulnerability patterns |
| `ruff` with the `S` (flake8-bandit) family | Python SAST: `shell=True`, `tempfile.mktemp`, unsafe YAML, weak hashing |
| `mypy` + `pyright` | two type checkers; `pyright` adds None-flow and narrowing over `core/` |
| `gitleaks` | committed-secret scan |
| `zizmor` | GitHub Actions misconfiguration and unpinned-ref audit |
| `osv-scanner`, `pip-audit`, Dependabot | known-vulnerable dependency detection |
| `atheris` fuzzing | dynamic analysis over the parsers |
| mutation testing (≥80% killed) | proves the tests would notice if a check stopped working |
| ≥90% coverage (statements + branches), ≥80% of the diff | new code arrives tested |
| `import-linter` | the layering that keeps `core/` free of CLI concerns |
| SLSA provenance + PyPI Trusted Publishing | a released artifact traces to the commit and workflow that built it |

## Security review record

OpenSSF Best Practices `security_review` asks for a review performed within the
last five years that considers the security requirements and the security
boundary, by people or by tools with human judgement on top. This is the log of
those reviews. It is deliberately a log and not a claim: a review with no date
and no findings is indistinguishable from no review.

### 2026-08-28 — full design and code review

**Scope.** The whole of this document, re-derived rather than re-read: the
trust boundaries in [Trust boundaries](#trust-boundaries), the design
principles as concrete claims about code, the CWE table, and the cryptographic
surface (`core/ed25519.py`, `core/minisign.py`, `core/provenance.py`). Plus the
supply-chain path — `publish.yml`, Trusted Publishing, SLSA attestation — and
the open CodeQL and Scorecard findings.

**Conducted by.** The maintainer, assisted by an AI agent, with static analysis
(CodeQL, `ruff` `S`, Snyk, `zizmor`, `gitleaks`) as input rather than as the
review. Tooling does not find the two classes below; that is why the criterion
requires a human.

**Findings, and what happened to them.**

| Finding | Class | Outcome |
|---|---|---|
| `boost trust add` had silently lost the key fingerprint from its output — the value a user compares against the publisher's. A merged automated fix removed it, and every gate stayed green because no test asserted the line. | Verification that reports success without verifying | Fixed, and pinned by a test. |
| `resolves_into_store()` caught only `OSError` to fail closed on a symlink cycle. On Python 3.12 — the oldest supported interpreter — `Path.resolve(strict=True)` raises `RuntimeError`, which is not an `OSError`, so the guard failed *open* there. | A safety property true on the developer's interpreter and false on a supported one | Fixed; regression test runs on 3.12. |
| Two claims in this document overstated what had been verified: `repo_track` said changes were reviewed, when the ruleset requires passing checks and not approval; `no_leaked_credentials` asserted secret scanning was enabled, which is not readable without administrative credentials. | Documentation asserting more assurance than exists | Both rewritten to what is actually enforced. |
| `publish.yml`'s `workflow_run` trigger filtered on branch name only. A fork pull request from a branch named `main` produced a `ci` run satisfying that filter, which would have fired the release job with `contents: write` and PyPI OIDC. | Trigger reachable from outside the trust boundary | Closed before this review, by requiring the triggering run to be a `push` from this repository. Re-verified. |

**Residual risk.** Unchanged and listed under [Known limits](#known-limits)
below. The largest is not technical: boost has one maintainer, so no change
this project ships has been read by a second person. See
[docs/code-review.md](code-review.md).

**Next review.** On any change to the trust boundaries, the cryptographic
surface or the release pipeline, and otherwise annually.

## Known limits

Stated plainly, because a threat model that claims no residual risk is not a
threat model.

- **boost cannot vet what a skill tells an agent to do.** A skill is prose, and
  prose that instructs an agent is the actual payload. boost gives you
  provenance, integrity and a diff; judging the content is yours. Review what
  you install, especially rules, which enter the agent's standing context.
- **Digest enforcement is off by default** so it cannot break an existing
  install on upgrade. `boost verify` reports drift regardless; turn enforcement
  on with `security.enforce_digest`.
- **Signature verification is opt-in per tap.** A tap that publishes no
  `.minisig` cannot be verified, and most do not yet.
- **`boost serve` binds a local HTTP listener** when you ask it to. It is a
  development convenience for a trusted local network, not a hardened server.
