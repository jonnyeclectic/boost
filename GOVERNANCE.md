# Governance

How boost makes decisions, who makes them, and what happens when people
disagree. [MAINTAINERS.md](MAINTAINERS.md) is the companion: it lists who holds
which role and which credential. This file is about the *process*.

## The short version

boost is a **single-maintainer project** run in the open. The lead maintainer
decides; everything that shapes a decision — the roadmap, the quality gates, the
reasoning behind a change — is public and arguable before it lands. That is a
benevolent-dictator model, and naming it plainly is better than implying a
committee that does not exist.

This is stated as the current state, not an aspiration. It changes when a second
maintainer is appointed under
[MAINTAINERS.md](MAINTAINERS.md#becoming-a-maintainer), and this file changes
with it.

## How a decision gets made

**1. Anyone may propose.** Open an issue, or open a pull request. There is no
membership requirement and no form to fill in.

**2. The argument happens in public, on the artifact.** Issues, pull requests,
and the roadmap boards. A decision made in a private channel is not a decision
this project recognises; if something was settled elsewhere, it gets written
down in the open before it is acted on.

**3. The gates decide what they can.** A large class of decisions is not a
matter of opinion here — the change either passes the required checks or it does
not. Coverage, mutation score, retrieval quality, the lint and type gates, the
generated-file freshness checks: these are stated thresholds, and a maintainer
does not get to wave one through. Changing a *threshold* is itself a decision
that goes through this process, in its own pull request, with the measurement
that justifies it.

**4. The lead maintainer decides what the gates cannot.** Scope, design,
priority, and whether a proposal fits the project at all. The decision is
recorded where the work is: in the pull request, or as a roadmap card.

**5. A "no" is recorded, not dropped.** The roadmap has a `declined` status
precisely so a rejected proposal stops reading as backlog. Without it the same
refuted question gets re-opened by the next person — or the next agent — who
scans the board for work. If your proposal is declined you get the reason in
writing, and it stays there.

## Disagreements

**With a decision.** Say so on the issue or pull request. Bring the thing that
would change the answer: a measurement, a failing case, a constraint that was
missed. This project changes its mind on evidence and says so when it does —
several roadmap cards exist specifically to record that an earlier claim was
wrong.

**With the process, or with a person.** Conduct concerns go through the private
reporting route in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), never a public
issue.

**When you cannot reach agreement.** With a single maintainer there is no appeal
body, and pretending otherwise would be dishonest. The real backstop is the
licence: boost is GPL-3.0 with full public history, so anyone who thinks the
project is being run badly can fork it and prove it. That is a genuine check on
the maintainer, not a consolation prize.

## What is deliberately not decided by discussion

Some things are settled by rule, and a pull request arguing the opposite gets
declined on sight unless it changes the rule first:

- **The runtime imports no third-party package.** Enforced by `import-linter`.
- **Generated files are never hand-edited.** `registries.json`, both roadmap
  boards, `commands.html`. Edit the source and regenerate.
- **A suppressed finding needs a written argument**, naming what would have to
  change for the suppression to stop being true. See
  [`docs/dependencies.md`](docs/dependencies.md).
- **A badge answer or a security claim must be checkable.** If the evidence
  needs credentials nobody reading has, the claim gets softened to what *is*
  checkable rather than asserted.

## Roadmap and priority

Priority is public and data-driven. Both boards are generated from one file per
item under `docs/roadmap/items/`, so proposing work is a pull request adding a
card, and claiming work is a pull request setting `status` and `owner` on one.
Two people claiming different items touch different files and merge cleanly; two
claiming the *same* item conflict on that one small file, which is the intended
"already claimed" signal — first to merge wins.

There is no private backlog. What is on the boards is what is planned.

## Releases

Every merge to `main` cuts a release. There is no release manager, no release
meeting, and no window: the decision to release *is* the decision to merge.
Consequences of that are set out in [SUPPORT.md](SUPPORT.md) — only the latest
release is supported — and in
[`docs/verifying-releases.md`](docs/verifying-releases.md), which is how you
check that a release came from this repository.

## Changing this document

Like anything else: a pull request, argued in public, merged through the gates.
