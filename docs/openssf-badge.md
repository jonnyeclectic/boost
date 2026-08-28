# OpenSSF Best Practices badge — passing-level answers

This is boost's worked answer to all 67 **passing**-level criteria of the
[OpenSSF Best Practices badge](https://www.bestpractices.dev/). It exists so the
badge submission is a transcription job rather than a research job, and so the
claims stay reviewable: every "Met" below names the artifact that backs it, and
every "N/A" says why the criterion does not apply.

Criteria text is from the
[badge project's own `criteria.yml`](https://github.com/coreinfrastructure/best-practices-badge/blob/main/criteria/criteria.yml).
`MUST` must be Met (or N/A where the criterion permits it). `SHOULD` may be
Unmet **with a justification**. `SUGGESTED` need only be answered.

**Status: 66 Met or N/A, 1 SHOULD deliberately Unmet with justification
(`crypto_call`).** That clears the passing bar. What remains is registration —
see [Human actions](#human-actions) at the end.

Repository: <https://github.com/jonnyeclectic/boost> · Licence: GPL-3.0 ·
Package: [`boost-skill-cli`](https://pypi.org/project/boost-skill-cli/)

---

## Basics

### Basic project website content

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `description_good` | MUST | **Met** | The README opens with what boost is and who it is for: "a package manager for AI coding skills… finds, installs, and version-tracks skills from GitHub-hosted registries". Mirrored in the repository description and the [Visual Guide](https://jonnyeclectic.github.io/boost/). |
| `interact` | MUST | **Met** | README carries install, quick start and command examples; CONTRIBUTING carries dev setup, the gate list and PR process; both are linked from the site nav. |
| `contribution` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/blob/main/CONTRIBUTING.md> — dev setup, ground rules, the full gate table, generated-file rules and PR expectations. |
| `contribution_requirements` | SHOULD | **Met** | Same file: "Ground rules" states the stdlib-only runtime, the layering rule, and that behaviour changes need tests. [`.github/PULL_REQUEST_TEMPLATE.md`](https://github.com/jonnyeclectic/boost/blob/main/.github/PULL_REQUEST_TEMPLATE.md) pre-fills the checklist. |

### FLOSS license

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `floss_license` | MUST | **Met** | GPL-3.0. |
| `floss_license_osi` | SUGGESTED | **Met** | GPL-3.0 is [OSI-approved](https://opensource.org/license/gpl-3-0). |
| `license_location` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/blob/main/LICENSE>, at the repository root, and declared in `pyproject.toml`. |

### Documentation

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `documentation_basics` | MUST | **Met** | README (install, quick start, concepts) plus the [Visual Guide](https://jonnyeclectic.github.io/boost/), [`docs/DEBUGGING.md`](https://github.com/jonnyeclectic/boost/blob/main/docs/DEBUGGING.md) and [`docs/rag-architecture.md`](https://github.com/jonnyeclectic/boost/blob/main/docs/rag-architecture.md). |
| `documentation_interface` | MUST | **Met** | [`docs/commands.html`](https://jonnyeclectic.github.io/boost/docs/commands.html) documents every command and every flag. It is *generated from the CLI itself* — the `COMMANDS` registry and each command's argparse parser — and a CI `--check` fails the build if it drifts, so the reference cannot go stale. `boost --help` and `boost <cmd> --help` are the same data. |

### Other

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `sites_https` | MUST | **Met** | Every project site is HTTPS-only: `github.com/jonnyeclectic/boost`, `jonnyeclectic.github.io/boost` (GitHub Pages enforces HTTPS), `pypi.org/project/boost-skill-cli`. A link-check workflow runs over the docs. |
| `discussion` | MUST | **Met** | [GitHub Issues](https://github.com/jonnyeclectic/boost/issues), open to anyone, archived and searchable. |
| `english` | SHOULD | **Met** | All documentation, code, commit messages, issues and reviews are in English. A `vale` prose-lint gate runs on the English documentation. |
| `maintained` | MUST | **Met** | Active daily development — 560+ merged pull requests, and *every* merge to `main` cuts a release. The criterion asks only that the project be maintained; the project is not claiming to be unmaintained or seeking new maintainers. (Bus factor is a *silver*-level criterion and out of scope here — boost is a single-maintainer project today, which is worth saying out loud before anyone attempts silver.) |

## Change Control

### Public version-controlled source repository

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `repo_public` | MUST | **Met** | Public repository, full history, at the URL above. |
| `repo_track` | MUST | **Met** | git — every change is a tracked commit with author and message. `main` is protected and takes changes only through a pull request that has passed the full required-check gate. Note what is *not* claimed: the ruleset deliberately does not require a human approval, because the working model is parallel `loop/*` branches that self-merge and there is no second reviewer. The criterion does not ask for review, and the [Scorecard triage card](https://jonnyeclectic.github.io/boost/docs/roadmap.html#scorecard-findings-triage) keeps that finding open rather than dismissing it, because the score is accurate. |
| `repo_interim` | MUST | **Met** | Interim versions are on `main` continuously; the release cadence is *per merge*, so the published version is never more than one merge behind the repository. |
| `repo_distributed` | SUGGESTED | **Met** | git. |

### Unique version numbering

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `version_unique` | MUST | **Met** | Versions come from `setuptools-scm` reading git tags — there is no hand-maintained `__version__` to fall out of sync, and a tag is unique by construction. `boost --version` reports it. |
| `version_semver` | SUGGESTED | **Met** | `vMAJOR.MINOR.PATCH` (current series `v1.2.x`). |
| `version_tags` | SUGGESTED | **Met** | Every release is a git tag, created by the release workflow. |

### Release notes

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `release_notes` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/releases> — one GitHub release per version, notes assembled by [release-drafter](https://github.com/jonnyeclectic/boost/blob/main/.github/release-drafter.yml) from the merged pull-request titles, which is why CONTRIBUTING asks for the PR description to be written as the release note. |
| `release_notes_vulns` | MUST | **N/A** | No publicly known run-time vulnerability in boost itself has ever been reported, assigned a CVE, or fixed, so no release has had one to name. The forward policy is written down in [SECURITY.md](https://github.com/jonnyeclectic/boost/blob/main/SECURITY.md#vulnerability-fixes-in-release-notes): any release fixing a publicly known vulnerability will name it and its identifier in the release notes. Re-answer this as **Met** at the first such release. |

## Reporting

### Bug-reporting process

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `report_process` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/issues/new/choose> — issue templates for bug reports and feature requests; CONTRIBUTING points at the tracker. |
| `report_tracker` | SHOULD | **Met** | GitHub Issues, used as the sole tracker. |
| `report_responses` | MUST | **Met** | The maintainer triages issues as they arrive; the majority of the issue history is resolved rather than left open, and CI failures on `main` are opened automatically ([`ci-failure-issue.yml`](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/ci-failure-issue.yml)) and closed on the fix. |
| `enhancement_responses` | SHOULD | **Met** | Enhancement requests are answered and, where accepted, tracked as cards on the public [code roadmap](https://jonnyeclectic.github.io/boost/docs/roadmap.html). |
| `report_archive` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/issues?q=is%3Aissue> — the full history, open and closed, publicly readable without an account. |

### Vulnerability report process

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `vulnerability_report_process` | MUST | **Met** | <https://github.com/jonnyeclectic/boost/blob/main/SECURITY.md> — states the channel, the expected acknowledgement time, and what a useful report contains. |
| `vulnerability_report_private` | MUST | **Met** | GitHub private vulnerability reporting is **enabled** on the repository (`GET /repos/jonnyeclectic/boost/private-vulnerability-reporting` → `{"enabled": true}`). Reports go to <https://github.com/jonnyeclectic/boost/security/advisories/new>, never a public issue. |
| `vulnerability_report_response` | MUST | **N/A** | No vulnerability report has been received in the last six months — none has been received at all. SECURITY.md commits to an acknowledgement within a few days, well inside the criterion's 14-day bound. |

## Quality

### Working build system

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `build` | MUST | **Met** | Standard PEP 517 build from `pyproject.toml` (`python -m build`), exercised end to end by the release workflow, which builds the wheel and smoke-tests it before publishing. `make venv` reproduces a development environment from the hash-pinned requirements. |
| `build_common_tools` | SUGGESTED | **Met** | setuptools + `build`, driven by `make` and [`noxfile.py`](https://github.com/jonnyeclectic/boost/blob/main/noxfile.py). |
| `build_floss_tools` | SHOULD | **Met** | Every build and gate tool is FLOSS and runs on FLOSS platforms; CI runs on Ubuntu and macOS. |

### Automated test suite

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `test` | MUST | **Met** | Four tiers: `tests/unit`, `tests/functional` (drive the real CLI in-process), `tests/smoke.sh` (170 end-to-end checks through the `./boost` shim) and a Gherkin BDD suite (11 features, 47 scenarios). |
| `test_invocation` | SHOULD | **Met** | `make test` — or `nox`, which reproduces the exact CI gate in isolated venvs across every supported interpreter. |
| `test_most` | SUGGESTED | **Met** | An **80% line-coverage** gate (`fail_under = 80`), an **80% changed-line** gate on pull requests, and an **80% mutation** gate over `boost_cli/core` — the last of which means coverage cannot be satisfied by tests that merely execute the code without asserting on it. |
| `test_continuous_integration` | SUGGESTED | **Met** | GitHub Actions runs the full gate on every push and every pull request. |

### New functionality testing

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `test_policy` | MUST | **Met** | CONTRIBUTING states it outright: "Behavior changes need tests" and "Anything under `boost_cli/core/` is mutation-tested; expect to add unit tests that actually kill your mutants." |
| `tests_are_added` | MUST | **Met** | The policy is mechanically enforced, not merely stated: the changed-line coverage gate fails a pull request whose new lines are under 80% covered, and the mutation gate fails one whose new `core/` logic is untested — an unexercised branch counts as an unkilled mutant. Both are required checks. |
| `tests_documented_added` | SUGGESTED | **Met** | Documented in CONTRIBUTING ("The gates") and re-stated in the pull-request template checklist. |

### Warning flags

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `warnings` | MUST | **Met** | Python has no compiler warnings, so the criterion is met by linters: `ruff` (explicit rule set including the `S`/flake8-bandit, `B`/bugbear, `SIM`, `C4`, `PERF`, `RUF`, `UP` and `I` families), `mypy`, `pyright`, `vulture`, `xenon` and `refurb`. `pytest` additionally promotes `DeprecationWarning` raised inside `boost_cli` to an error. |
| `warnings_fixed` | MUST | **Met** | Not "mostly fixed" — **zero** findings are permitted. Each of those tools is a required check that fails the build on a single finding, so a warning cannot accumulate. `ruff`'s rule set is spelled out with `select`, not `extend-select`, so a tool upgrade can never silently switch families on or off. |
| `warnings_strict` | SUGGESTED | **Met** | The gates are already maximally strict — zero tolerance, plus a complexity ratchet (`xenon`) that fails on regression rather than on an absolute threshold. |

## Security

### Secure development knowledge

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `know_secure_design` | MUST | **Met** | [`docs/security-design.md`](https://github.com/jonnyeclectic/boost/blob/main/docs/security-design.md) names boost's trust boundaries and works through Saltzer and Schroeder's eight principles — economy of mechanism, fail-safe defaults, complete mediation, open design, separation of privilege, least privilege, least common mechanism, psychological acceptability — as concrete claims about this codebase, each pointing at the code that implements it. |
| `know_common_errors` | MUST | **Met** | The same document carries a table of the CWE/OWASP error classes that actually apply to a Python CLI that clones repositories and writes files — path traversal, OS command injection, zip-slip, link following, untrusted deserialization, supply-chain and CI-action compromise, leaked credentials, insecure download, improper input validation — each paired with the specific mitigation in this repository. Classes that do not apply are omitted rather than padded. |

### Use basic good cryptographic practices

boost implements no cryptographic protocol, stores no secret, and generates no
key. It **verifies** minisign/Ed25519 signatures over tap content. See
[the cryptography section](https://github.com/jonnyeclectic/boost/blob/main/docs/security-design.md#cryptography-boost-uses)
of the security-design document for the full account.

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `crypto_published` | MUST | **Met** | Ed25519 (RFC 8032), SHA-512 (FIPS 180-4), SHA-256 (FIPS 180-4) and BLAKE2b-512 (RFC 7693). All publicly published and expert-reviewed; no private or proprietary algorithm anywhere. |
| `crypto_call` | SHOULD | **Unmet — justified** | `boost_cli/core/ed25519.py` is a pure-standard-library implementation of Ed25519 rather than a call into `cryptography` or libsodium. It is a deliberate trade the stdlib-only runtime rule forces: CPython ships no Ed25519 primitive, so signature verification without a runtime dependency means implementing RFC 8032's verify half. The exposure is bounded — **verification only**, over public keys and public signatures, with no secret that a timing side channel could leak — and correctness is pinned to the published RFC 8032 §7.1 test vectors in the unit suite. Hashing is *not* reimplemented; it goes through `hashlib`. |
| `crypto_floss` | MUST | **Met** | Everything cryptographic is `hashlib` (Python standard library) plus boost's own GPL-3.0 code. No proprietary component, and every function is implementable with FLOSS. |
| `crypto_keylength` | MUST | **Met** | Ed25519 is a 255-bit curve — above the criterion's 224-bit elliptic-curve minimum — and the digests are 256- and 512-bit, above the 224-bit hash minimum. No shorter length is configurable, so there is nothing to disable. |
| `crypto_working` | MUST | **Met** | No MD4, MD5, SHA-1, single DES, RC4, Dual_EC_DRBG or ECB mode appears anywhere in the codebase; `ruff`'s `S` family fails the build on weak-hash use, so a regression is caught mechanically. |
| `crypto_weaknesses` | SHOULD | **Met** | Same evidence. Ed25519, SHA-2 and BLAKE2 have no known serious weakness. |
| `crypto_pfs` | SHOULD | **N/A** | boost implements no key-agreement protocol and no network cryptography. TLS is provided by `git` and by `pip`, not by boost. |
| `crypto_password_storage` | MUST | **N/A** | boost performs no inbound authentication of external users and stores no password. It is a local CLI with no accounts. |
| `crypto_random` | MUST | **N/A** | boost generates no cryptographic key and no nonce — signing is the publisher's job, boost only verifies. `random` is imported nowhere in `boost_cli/`, so there is no insecure generator to substitute. |

### Secured delivery against MITM attacks

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `delivery_mitm` | MUST | **Met** | Distribution is PyPI over HTTPS (`pipx install boost-skill-cli`) and GitHub over HTTPS. Publishing uses [PyPI Trusted Publishing](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/publish.yml) — a short-lived OIDC identity minted for that one workflow, with no long-lived token stored anywhere — and each release carries a **SLSA build-provenance attestation** tying the artifact to the commit and workflow that produced it. Taps clone over HTTPS or SSH. |
| `delivery_unsigned` | MUST | **Met** | boost consumes no hash fetched over HTTP. The only hashes in the build are the sha256 values committed in `requirements/*.txt`, which `pip --require-hashes` enforces over an HTTPS connection; the tool downloads in CI are HTTPS with a pinned version. |

### Publicly known vulnerabilities fixed

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `vulnerabilities_fixed_60_days` | MUST | **Met** | There are no unpatched vulnerabilities of medium or higher severity, publicly known or otherwise — none has been reported against boost. Dependency exposure is watched continuously by `osv-scanner`, `pip-audit` and Dependabot, all of which run in CI, and the runtime has no third-party dependency to inherit one from. |
| `vulnerabilities_critical_fixed` | SHOULD | **Met** | Same position, and the release cadence — one release per merge — means a fix reaches users within minutes of landing rather than waiting for a release train. |

### Other security issues

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `no_leaked_credentials` | MUST | **Met** | `gitleaks` runs in CI on every push over the repository, and fails the build on a hit (the allowlist in `.gitleaks.toml` covers only boost's own synthetic secret-scanner test fixtures). Structurally there is little to leak in the first place: publishing uses a short-lived OIDC identity rather than a stored PyPI token, and the two optional dashboard secrets are absent by default with their jobs skipping themselves. Confirm GitHub's own secret scanning and push protection are enabled in **Settings → Code security** while registering — that setting is not readable without repository-admin credentials, so it is not asserted here. |

## Analysis

### Static code analysis

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `static_analysis` | MUST | **Met** | Several tools, all required checks, all run before every release — which is *every* merge to `main`. [CodeQL](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/codeql.yml) does semantic analysis on push, on pull request and weekly; `ruff`'s `S` family is Python SAST (`shell=True`, `tempfile.mktemp`, unsafe YAML loading, weak hashing); `mypy` and `pyright` are two independent type checkers, the second adding None-flow and narrowing analysis over `core/`; `zizmor` audits the GitHub Actions workflows for excessive permissions and unpinned refs; `import-linter` enforces the architectural layering. SonarCloud is wired up as an optional non-blocking dashboard. |
| `static_analysis_common_vulnerabilities` | SUGGESTED | **Met** | CodeQL's Python security queries and `ruff`'s flake8-bandit family are both vulnerability-focused rather than generic-defect tools. `osv-scanner` and `pip-audit` cover known-vulnerable dependencies. |
| `static_analysis_fixed` | MUST | **Met** | Findings are fixed, or dismissed with a written proof of why they are false positives — never dismissed for convenience. The [Scorecard triage roadmap card](https://jonnyeclectic.github.io/boost/docs/roadmap.html#scorecard-findings-triage) records that discipline explicitly, including the rule that posture metrics must *not* be filed as false positives. One CodeQL alert is currently open and triaged as a false positive; see [Human actions](#human-actions). |
| `static_analysis_often` | SUGGESTED | **Met** | Every push and every pull request, plus a weekly scheduled CodeQL run to pick up new query releases against unchanged code. |

### Dynamic code analysis

| Criterion | Cat. | Answer | Evidence |
|---|---|---|---|
| `dynamic_analysis` | SUGGESTED | **Met** | [`fuzz.yml`](https://github.com/jonnyeclectic/boost/blob/main/.github/workflows/fuzz.yml) runs `atheris` (libFuzzer for Python) against the parsers over a target matrix, uploading any crashing input as an artifact. Beyond fuzzing, `tests/smoke.sh` drives the real binary end to end through 170 checks, and the functional suite executes the CLI against a throwaway `$HOME`. |
| `dynamic_analysis_unsafe` | SUGGESTED | **N/A** | Python is memory-safe; there is no buffer overflow or use-after-free class for a tool like ASan or Valgrind to find. The runtime has no C extension (the optional `[rag]` extra is not on the install path). |
| `dynamic_analysis_enable_assertions` | SUGGESTED | **Met** | The test suites are assertion-driven and run with assertions enabled (no `-O`), and `pytest` promotes `DeprecationWarning` raised inside `boost_cli` to a hard error, so a latent deprecation fails a run rather than scrolling past. |
| `dynamic_analysis_fixed` | MUST | **Met** | No medium-or-higher exploitable vulnerability has been found by dynamic analysis. A crashing input found by the fuzzer is uploaded as a workflow artifact and fixed; none is outstanding. |

---

## Human actions

Everything above is repository-side and done. These four steps need an account
or a repository setting, so they cannot be landed as a commit.

1. **Register the project** at <https://www.bestpractices.dev/en/projects/new>
   with the repository URL, signing in with the GitHub account that owns it.
   Transcribe the answers above — the criterion identifiers on the form match
   the identifiers in these tables one-for-one.
2. **Add the badge to the README** once the project has an id. The Scorecard
   `CIIBestPracticesID` check reads the same registration, so this also closes
   that Scorecard finding:

   ```markdown
   [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<ID>/badge)](https://www.bestpractices.dev/projects/<ID>)
   ```

   Do not add it before registering — an unknown id renders a broken badge.
3. **Set the repository `homepage` field** to
   `https://jonnyeclectic.github.io/boost/`. It is currently empty, which
   weakens the `description_good` and `interact` evidence for anyone reading the
   repository rather than the README.
4. **Dismiss CodeQL alert 54 as a false positive** ("clear-text logging of
   sensitive information", `cmd_trust` in `boost_cli/commands/quality.py`), and
   close its Copilot-Autofix issue
   [#562](https://github.com/jonnyeclectic/boost/issues/562) as won't-fix.
   Recorded reason: the values printed are a minisign **public** key's name and
   fingerprint. A public key fingerprint is meant to be published, and printing
   it is the entire point of the line — the user compares it by eye against the
   publisher's advertised fingerprint before trusting the key.

   An earlier version of this entry said the suggested autofix "must not be
   merged". It had already been merged, in `dc6e827`, two seconds before this
   document landed — which is why it is worth stating what actually went wrong.
   The autofix replaced the whole line with the constant `"trusted key added"`,
   deleting the only verification `trust add` offers, and it passed every gate
   because **no test asserted the fingerprint was printed**. The output is
   restored, the suppression now carries its reason inline, and
   `tests/functional/test_tap_signing.py` pins it so the line cannot be dropped
   silently a second time. The missing test was the real defect; the alert was
   only the trigger.

## Doing this on another project

[`openssf-playbook.md`](openssf-playbook.md) is the repeatable method behind
this document: where the authoritative criteria actually live, how to audit a
repository against them rather than assuming, the three buckets every criterion
sorts into, and the four documents Baseline Level 2 asks for.

## Keeping this document honest

Re-check it when any of these change, since each one moves an answer:

- a vulnerability is reported or fixed → `release_notes_vulns`,
  `vulnerability_report_response`, `vulnerabilities_fixed_60_days`
- a runtime dependency is added → `crypto_call`, `crypto_floss`,
  `dynamic_analysis_unsafe`
- a gate is removed or a threshold lowered → the Quality and Analysis sections
- the licence changes → `floss_license`, `floss_license_osi`, `crypto_floss`

The badge site re-asks for confirmation periodically; treat that prompt as the
cue to re-read this file rather than to click through.
