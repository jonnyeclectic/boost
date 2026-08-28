# Security policy

## Supported versions

Only the latest release receives security fixes. [SUPPORT.md](SUPPORT.md) sets
out the scope and duration of support in full, including when a version stops
receiving security updates.

## Reporting a vulnerability

Please **do not** open a public issue for security reports. Instead, use
GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/jonnyeclectic/boost/security/advisories/new)**

You can expect an acknowledgement within a few days. Please include steps to
reproduce and the affected command(s).

## Vulnerability fixes in release notes

Every merge to `main` cuts a release, so a fix reaches users within minutes of
landing. When a release fixes a publicly known vulnerability in boost itself —
one that already had a CVE or an equivalent identifier when the release was
cut — the [release notes](https://github.com/jonnyeclectic/boost/releases) will
name it and its identifier, so you can tell an upgrade that matters from one
that does not. No such vulnerability has been reported to date.

Vulnerabilities in boost's *dependencies* are handled separately: the runtime
has none, and the development toolchain is watched by `osv-scanner`, `pip-audit`
and Dependabot.

## Scope notes

boost executes `git` against registry URLs you tap and symlinks skills into
agent directories. Reports about tap-supplied content escaping the store,
path traversal via `SKILL.md` frontmatter, or command injection through
skill/tap names are especially valuable.

## Secrets and credentials

The policy in one line: **boost stores no credential it could leak.**

- **Releases use no stored token.** Publishing goes through PyPI Trusted
  Publishing — GitHub mints a short-lived OIDC identity for `publish.yml` at the
  moment of upload. There is no PyPI API token in a secret, on a laptop, or in a
  password manager, so there is nothing to rotate and nothing to steal.
- **Every secret that does exist is optional.** Only `CODECOV_TOKEN`,
  `SONAR_TOKEN` and the optional evaluation API keys are configured, all as
  GitHub Actions repository secrets. Every job reading one skips itself when it
  is absent, so none is required to build, test or release.
- **Secrets never reach untrusted code.** No workflow uses
  `pull_request_target`, so a fork's pull request runs with a read-only token
  and no secret access. Secrets are bound at job level, never interpolated into
  a `run:` block, and `zizmor` fails a pull request that breaks either rule.
- **Access follows the maintainer list.** Who holds what is recorded in
  [MAINTAINERS.md](MAINTAINERS.md), which also states the policy that escalated
  permissions are reviewed before they are granted. Access is removed promptly
  when someone steps down and immediately if an account is believed compromised.
- **Rotation.** An optional dashboard token is rotated on suspicion of exposure
  or when the holder's access is removed — revoked at the issuing service, then
  replaced or deleted in repository settings. Because none is required, deleting
  one is always a safe first move.
- **Committed secrets are caught.** `gitleaks` runs in CI on every push and
  fails the build on a hit; the allowlist covers only boost's own synthetic
  scanner test fixtures.

If you believe a boost credential has been exposed, report it through the
private channel above rather than opening an issue.

## How boost is designed to resist this

[`docs/security-design.md`](docs/security-design.md) is the threat model: what
boost trusts and what it does not, the design principles the code is held to,
and the table of error classes — path traversal, command injection, zip-slip,
untrusted deserialization, supply-chain compromise — each paired with the
mitigation that counters it. It also states the known limits plainly, including
the one that matters most: boost gives you a skill's provenance, integrity and
diff, but judging what the skill *tells your agent to do* is yours.

For how boost's badge-level security posture is assessed, see
[`docs/openssf-badge.md`](docs/openssf-badge.md). Two companion documents cover
the supply chain either side of a release:
[`docs/dependencies.md`](docs/dependencies.md) — how dependencies are chosen,
pinned by hash, tracked, and at what threshold a finding blocks a merge — and
[`docs/verifying-releases.md`](docs/verifying-releases.md) — how to verify for
yourself that an artifact you installed was built by this repository.
