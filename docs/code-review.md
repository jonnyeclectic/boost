# Code review in boost

What review a change gets before it reaches `main`, what a reviewer checks, and
what "acceptable" means. This is the project's documented review requirement
(OpenSSF Best Practices `code_review_standards`); [CONTRIBUTING.md](../CONTRIBUTING.md)
covers how to open the pull request in the first place, and
[GOVERNANCE.md](../GOVERNANCE.md) covers who decides when reviewers disagree.

## The honest shape of it

boost has **one maintainer** ([MAINTAINERS.md](../MAINTAINERS.md)). That is the
single most important fact about review here, and stating it is more useful
than implying a committee:

- **A pull request from anyone else** is reviewed by the maintainer, who is not
  its author. That is ordinary two-person review.
- **A pull request from the maintainer** is not. It gets the full automated
  gate and a deliberate self-review pass, and that is all — there is no second
  human. Most changes on `main` are of this kind.

So boost does **not** claim `two_person_review`, `bus_factor` or
`contributors_unassociated`, and [docs/openssf-badge.md](openssf-badge.md)
records them as Unmet rather than dressed up. Adding a second maintainer is the
fix, and it is a recruiting problem, not an engineering one.

What the project does instead of pretending otherwise is push as much of review
as possible into checks that do not get tired: 21 required checks, a mutation
gate that fails tests which cover code without testing it, a retrieval-quality
gate with four floors, and a linter tier that includes a second type checker
and an import-layering check.

## How a review is conducted

1. **The gate runs first.** A reviewer does not read a red pull request. The
   required checks are listed in
   [`.github/required-checks.txt`](../.github/required-checks.txt) and
   `scripts/check_required_checks.py` fails the build if a name there stops
   matching a real job.
2. **Read the description as release notes.** It becomes them, via
   release-drafter. If it does not explain what changed and why, that is a
   review comment.
3. **Read the diff against the claim.** The recurring failure in this
   repository is not broken code; it is a true-sounding sentence. A comment,
   a docstring or a `docs/` line that asserts a number, a behaviour or a
   version must be traceable to something that was run. "Measured" and
   "predicted" are different words.
4. **Look for the test that would have caught it.** New behaviour under
   `boost_cli/core/` needs tests that kill mutants, not tests that import the
   module.
5. **Comment, do not silently fix.** A reviewer who edits the branch stops
   being a reviewer.

## What must be checked

A reviewer walks this list. It is short on purpose: everything mechanical is
already a check, so what is left is what a machine cannot see.

| Area | The question |
|---|---|
| Layering | Does `core/` stay free of `commands/` and `cli`? `import-linter` enforces it, but a new allowlisted edge needs a reason. |
| Runtime dependencies | Any third-party import under `boost_cli/`? The runtime is stdlib-only, and that constraint is load-bearing for `crypto_call` and for install size. |
| Blast radius on `$HOME` | Does the change write, link or delete under `~/.boost`, `~/.agents/skills` or an agent dotdir? Those paths hold the user's real configuration. Symlink handling, `copytree`, and anything that removes a path get read twice. |
| Sparse checkouts | Does it read a tap's real files? It must go through `store.source_dir_for`, or it will read the half of the directory the cone fetched and report success. |
| Generated files | Was the source edited and the artifact regenerated, in that order? |
| Claims | Every number, version and behaviour asserted in prose — is it measured? |
| Security surface | `subprocess`, path joins from catalog data, archive extraction, anything reading a tap. [docs/security-design.md](security-design.md) names the boundaries. |
| Tests | Do they fail before the change and pass after? Do they kill mutants? |
| Sign-off | Does each commit carry a `Signed-off-by` naming its own author? |

## What makes a change acceptable

All of these, with no exceptions granted quietly:

- **Every required check green** on the merge commit, not just on the branch.
  "Require branches to be up to date" is on, so a stale green does not count.
- **No unresolved review comment.** A comment answered with a reason rather
  than a change is resolved; a comment ignored is not.
- **Tests for behaviour changes**, and the mutation gate still at or above 80%.
- **DCO sign-off** on every commit the pull request adds.
- **Generated files regenerated** as the last step.
- **One approving review** from the maintainer, for a pull request the
  maintainer did not write.

A change that fails any of these is not merged, whoever wrote it. The one
latitude the maintainer has over an outside contributor is smaller than it
looks: they can merge their own work without a second approval, because there
is no second approver — not because the bar is lower.

## When review finds something after the merge

It happens, and the response is a follow-up pull request, never a force-push to
`main`: every merge to `main` cuts a PyPI release, so history there is
published. [docs/verifying-releases.md](verifying-releases.md) covers what a
consumer can check independently.
