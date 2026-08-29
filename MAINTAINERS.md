# Maintainers

Who has access to what, what each role is expected to do, and what has to
happen before anyone is granted more. This file is the authoritative list; if it
disagrees with someone's memory, this file is right and the memory is stale.

## Current maintainers

| Name | GitHub | Role | Since |
|---|---|---|---|
| Jonathan Reyes | [@jonnyeclectic](https://github.com/jonnyeclectic) | Lead maintainer | 2026-07 |

boost is a **single-maintainer project today**. That is stated plainly rather
than glossed, because it is the single largest risk to the project and it
changes what you should expect: review latency depends on one person, and the
bus factor is one. See [Continuity](#continuity) for what happens if that
person becomes unavailable, and [Becoming a maintainer](#becoming-a-maintainer)
for how that changes.

## Access to sensitive resources

Every credential and privileged surface the project depends on, and who holds
it. Nothing not listed here grants access to anything.

| Resource | Who has access | How access works |
|---|---|---|
| GitHub repository (admin) | Lead maintainer | GitHub account with 2FA |
| `main` branch | **No one directly.** | A ruleset requires a pull request and the full required-check gate; `non_fast_forward` blocks history rewrites. Admin included. |
| PyPI project `boost-skill-cli` | **No stored credential exists.** | Publishing is a [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/): GitHub mints a short-lived OIDC token for `publish.yml` on `main` only. There is no API token to leak, share, or rotate. |
| GitHub Actions secrets | Lead maintainer | Only optional dashboard tokens (`CODECOV_TOKEN`, `SONAR_TOKEN`) and optional evaluation API keys. Every job reading one skips itself when it is absent, so none is required to build, test, or release. |
| Security advisories / private vulnerability reports | Lead maintainer | GitHub private vulnerability reporting |
| GitHub Pages docs site | Lead maintainer | Published from `main` by CI; no separate credential |

## Roles and responsibilities

**Lead maintainer.** Sets direction; reviews and merges pull requests; owns the
release process; is the recipient of private vulnerability reports and owns the
response; administers repository settings, branch rulesets and the required-check
list; maintains this file.

**Maintainer** (none appointed yet). Reviews and merges pull requests within an
agreed area; may not change repository settings, rulesets, or the release path.
A maintainer is expected to keep the quality gates green rather than route
around them, and to say so publicly when a gate is wrong instead of disabling it
quietly.

**Contributor.** Anyone who opens a pull request. No standing permissions; a
contribution is merged by a maintainer after the gates pass. See
[CONTRIBUTING.md](CONTRIBUTING.md).

**Security reporter.** Anyone who reports a vulnerability through the process in
[SECURITY.md](SECURITY.md). Reporters are credited by name in the advisory and
the release notes unless they ask not to be.

## Becoming a maintainer

Escalated permission is granted deliberately and never by default. The policy:

1. **A track record first.** A sustained series of merged, non-trivial
   contributions — enough that their judgement on this codebase is a known
   quantity, not an assumption.
2. **Review before the grant.** The lead maintainer reviews that history and
   proposes the change in a public issue, naming the scope of access being
   granted and why. Existing maintainers may object there.
3. **Least privilege at the grant.** New collaborators receive the lowest
   permission that lets them do the job. Write access is a separate, later
   decision from repository administration, which is a separate decision again
   from anything touching the release path.
4. **This file is updated in the same change** that grants the permission. An
   access grant that is not recorded here has not happened.

The same review applies when an existing maintainer is given more access, not
only to a first grant.

## Removing access

Access is removed promptly when a maintainer steps down, becomes unreachable for
an extended period, or at their own request — and immediately if an account is
believed compromised. Removal does not require agreement from the person losing
access. Because publishing uses a short-lived OIDC identity rather than a stored
token, removing someone's GitHub access removes their ability to release; there
is no separate credential left behind to revoke.

## Continuity

If the lead maintainer becomes unavailable:

- **The code is safe regardless.** It is Apache-2.0, the full history is public,
  and every release is reproducible from a public tag. Anyone may fork.
- **The published artifacts stay published.** PyPI releases and GitHub releases
  remain available; nothing expires if no one logs in.
- **Recovery of the canonical repository** would go through
  [GitHub's account-recovery and inactive-repository processes](https://docs.github.com/en/site-policy).
  Because the release path is a GitHub OIDC identity bound to this repository,
  whoever legitimately controls the repository controls releases — there is no
  personal token that has to be handed over.
- **The practical answer is to fork.** Until a second maintainer exists, that
  is the honest continuity plan, and the project would rather say so than
  imply a succession process it does not have.

Reducing this risk is open work: if you have been contributing and want to help
carry it, say so in an issue.
