# Security policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue for security reports. Instead, use
GitHub's private vulnerability reporting:

**[Report a vulnerability](https://github.com/jonnyeclectic/boost/security/advisories/new)**

You can expect an acknowledgement within a few days. Please include steps to
reproduce and the affected command(s).

## Scope notes

boost executes `git` against registry URLs you tap and symlinks skills into
agent directories. Reports about tap-supplied content escaping the store,
path traversal via `SKILL.md` frontmatter, or command injection through
skill/tap names are especially valuable.
