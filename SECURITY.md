# Security policy

## Supported versions

Only the latest release receives security fixes.

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

## How boost is designed to resist this

[`docs/security-design.md`](docs/security-design.md) is the threat model: what
boost trusts and what it does not, the design principles the code is held to,
and the table of error classes — path traversal, command injection, zip-slip,
untrusted deserialization, supply-chain compromise — each paired with the
mitigation that counters it. It also states the known limits plainly, including
the one that matters most: boost gives you a skill's provenance, integrity and
diff, but judging what the skill *tells your agent to do* is yours.

For how boost's badge-level security posture is assessed, see
[`docs/openssf-badge.md`](docs/openssf-badge.md).
