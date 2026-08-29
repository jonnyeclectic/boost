# Earning the OpenSSF badges: a playbook

boost went from unregistered to three badges — **passing**, **Baseline Level 1**
and **Baseline Level 2** — in one working session. This is the method, written
so another project can follow it, including the parts that cost time to
discover and the parts where the honest answer is "no".

It is not a checklist of criteria. The criteria live upstream and change; what
transfers is how to find them, how to decide an answer, and which kinds of
criterion are worth attacking in which order.

## What you are actually applying for

bestpractices.dev issues **four independent badges**, not one with tiers. This
is the first thing most people get wrong, including this project's own earlier
notes.

| Badge | Criteria | Nature |
|---|---|---|
| **Passing** | 67 | The classic CII set — process, quality, security basics |
| **Baseline Level 1** | 24 | OSPS Baseline: repository hygiene and CI safety |
| **Baseline Level 2** | 19 | OSPS Baseline: governance, supply chain, documented policy |
| **Baseline Level 3** | 21 | OSPS Baseline: review, VEX, SCA policy |

Passing also has **silver** (55 more criteria) and **gold** (20 more) above it,
which *are* tiers — silver requires passing, gold requires silver.

Each badge is a separate form at
`bestpractices.dev/en/projects/<id>/<level>/edit`, where `<level>` is `passing`,
`baseline-1`, `baseline-2`, `baseline-3`, `silver` or `gold`. They share a
project id and nothing else. Register once, then work them independently.

## Step 1 — get the real criteria, not a summary

Do not work from a blog post, and do not work from what an LLM recalls. Both
will be plausible and subtly wrong about which criteria allow N/A, which demand
a URL, and which are MUST versus SHOULD — and those three facts decide most of
your answers.

The authoritative source is the badge application's own repository, and it takes
**two files**, because they are split:

```bash
# Metadata: category (MUST/SHOULD/SUGGESTED), na_allowed, met_url_required,
# met_justification_required. Carries NO descriptions.
curl -sL https://raw.githubusercontent.com/coreinfrastructure/best-practices-badge/main/criteria/criteria.yml

# The actual description: and details: prose for each criterion.
curl -sL https://raw.githubusercontent.com/coreinfrastructure/best-practices-badge/main/config/locales/en.yml
```

`https://www.bestpractices.dev/criteria/0.json` looks like the obvious endpoint
and returns **HTTP 406**. Skip it.

`criteria.yml` is an ordered map keyed by level — `- '0':` is passing, `'1'` is
silver, `'2'` is gold. Indentation is 2 / 4 / 6 / 10 spaces for major group,
minor group, criterion name, and keys. A parser that does not stop at `- '1':`
will silently fold silver criteria into your passing set; passing is **exactly
67**, so check your count before trusting your parse.

The OSPS Baseline criteria are not in that file at all. The fastest way to read
them, and the one that guarantees you are looking at what the form will actually
ask, is to open the form and scrape it — each criterion's full text sits in an
element whose `id` is the criterion name (`osps_qa_05_02`). Collapsed panels
return empty `innerText`, so read `textContent`.

## Step 2 — audit, do not assume

**The single highest-value finding: most unanswered criteria are already
satisfied and merely unrecorded.**

Nine of Baseline Level 1's 24 criteria were open when boost started. Every one
was already true. Branch protection plus a ruleset already refused direct
commits to `main`. No workflow used `pull_request_target`, so a fork's code
already could not reach a secret. An audit of every tracked file for binary
content turned up three zero-byte marker files and a 10-byte fuzz seed. The work
was proving it, not building it — and the badge went from 63% to 100% without a
line of code.

So audit before you plan. Concretely, for each open criterion, find the evidence
or establish that it is missing:

```bash
# Branch protection and rulesets (rulesets are separate from classic protection,
# and a repo can have both — checking only one will mislead you)
curl -s https://api.github.com/repos/OWNER/REPO/branches/main
curl -s https://api.github.com/repos/OWNER/REPO/rules/branches/main

# Private vulnerability reporting — a yes/no you should never guess
curl -s https://api.github.com/repos/OWNER/REPO/private-vulnerability-reporting

# Untrusted code reaching secrets
grep -rl pull_request_target .github/workflows/

# Binary and executable artifacts in version control
git ls-files | while read -r f; do
  [ -x "$f" ] && echo "EXEC: $f"
  file -b --mime "$f" | grep -q charset=binary && echo "BINARY: $f"
done
```

Two traps in that last one. Files carrying the executable bit are usually
*source scripts*, not the "generated executable artifacts" the criterion means.
And `file` reports zero-byte files as binary, so `__init__.py` and `py.typed`
will show up; check sizes before you believe them.

## Step 3 — sort every criterion into three buckets

This is the whole planning step, and it is what stops the work sprawling.

**Bucket 1 — documentation you can write.** By far the largest, and the one an
agent can close. Nothing about the software changes; you are recording what is
already true. Attack these first.

**Bucket 2 — a repository setting.** A checkbox or a field. Fast, but you cannot
do it from a branch, so collect them into one list and hand it over. For boost:
the empty `homepage` field, a CodeQL alert dismissal, enabling private
vulnerability reporting.

**Bucket 3 — structurally blocked.** Requires something you do not have, usually
another person. **Say so and move on.** Do not stretch an answer to make a
number go up; a badge that misrepresents your posture is worse than a missing
one, and the criteria are written by people who have seen every stretch.

For boost, bucket 3 was one thing wearing four hats: `OSPS-QA-07.01` (Level 3),
`two_person_review`, `bus_factor` and `contributors_unassociated` (gold) all
require a **non-author human reviewer**. A single-maintainer project cannot
satisfy them, and no commit changes that.

## Step 4 — write the four documents Level 2 asks for

Every project that reaches Baseline Level 2 writes approximately these four.
They are worth having irrespective of any badge, which is the test of whether a
compliance exercise was worth doing.

| Document | The question it answers | Where it usually goes wrong |
|---|---|---|
| `MAINTAINERS.md` | Who holds which credential, what each role may do, how someone gets more access, what happens if you vanish | Listing people but not *credentials*. The criterion asks about access to sensitive resources. If you publish with OIDC/Trusted Publishing, the honest entry is "nobody holds it — there is no token", which is a stronger answer than a name |
| `SUPPORT.md` | What is supported, on what platforms, for how long, and when a version stops getting security fixes | Implying a supported older line you do not actually maintain. If you only support latest, say only latest |
| `docs/dependencies.md` | How a dependency is chosen, obtained, tracked — and **the severity threshold at which a finding blocks a release** | Describing your scanners and calling it a policy. "We run osv-scanner" is not a policy; "critical and high block the merge, medium blocks if reachable, suppression requires a written argument" is |
| `docs/verifying-releases.md` | The exact commands a consumer runs to verify an artifact came from you | Omitting the identity check. `gh attestation verify FILE --repo O/R` proves *someone* built it; adding `--signer-workflow O/R/.github/workflows/publish.yml` proves **which workflow** did |

And a threat model — `docs/security-design.md` — which passing needs for
`know_secure_design` and `know_common_errors`, and Baseline Level 2 reuses for
`osps_sa_01_01` and `osps_sa_03_01`. One document, four criteria. Write it early.

Make it specific or it satisfies nobody. Work through Saltzer and Schroeder's
eight principles as **claims about your code**, each pointing at the file that
implements it. Table your CWE classes with the mitigation that counters each,
and **omit the ones that do not apply** rather than padding — a threat model
listing SQL injection for a project with no database advertises that nobody
thought about it.

## Step 5 — answer honestly, including when the answer is "no"

A `SHOULD` may be answered **Unmet with a justification** and the badge still
passes. Use that. It is there precisely so you do not have to lie.

boost answered `crypto_call` Unmet: it reimplements Ed25519 verification in pure
Python because its stdlib-only rule leaves no alternative. The justification
states the trade, bounds the exposure (verify-only, public keys, no secret for a
timing channel), and cites the RFC test vectors that pin correctness. That is a
better answer than a stretched "Met", and it is the kind of thing a reviewer
reads and trusts the rest of your form because of.

Three specific honesty traps worth naming, all of which caught this project:

- **Do not claim a setting you cannot read.** `no_leaked_credentials` was
  drafted asserting "GitHub secret scanning is on". That setting needs
  repo-admin credentials to read. The answer became what *was* checkable —
  gitleaks failing the build, OIDC publishing leaving no stored token — plus a
  note asking the registrant to confirm the setting themselves.
- **Do not restate a claim your own repo refuses to make.** A draft said `main`
  "takes changes only through reviewed pull requests". The ruleset deliberately
  requires status checks and *not* human approval, and this repo's Scorecard
  triage keeps that finding open rather than dismissing it, because the score is
  accurate. The badge form nearly contradicted the repo's own honesty.
- **Re-verify anything you inherited.** A note said the licence was MIT. It is
  GPL-3.0 at the time, and is Apache-2.0 now. That single check changed
  three answers.

## Step 6 — filling the forms

Each form is one radio group per criterion (`project[<name>_status]`, values
`Met` / `Unmet` / `N/A` / `?`) and one textarea
(`project[<name>_justification]`). Filling 67 by hand is a bad use of a
session; drive it, then audit that nothing is left at `?` before submitting:

```javascript
// Set a status + justification, dispatching the events the app listens for
const r = document.querySelector(
  `input[type=radio][name="project[${key}_status]"][value="${status}"]`);
r.click();
const ta = document.querySelector(`textarea[name="project[${key}_justification]"]`);
ta.value = justification;
ta.dispatchEvent(new Event('input',  {bubbles: true}));
ta.dispatchEvent(new Event('change', {bubbles: true}));
```

Two operational notes. Prefer the **"Submit (and exit)"** button over "Save (and
continue) 🤖" — the latter runs automation that fills unknown values, which you
do not want once you have answered everything deliberately. And the form's
progress percentage is the fastest correctness check you have: if you answered
every criterion and it does not read 100%, something did not take.

## Step 7 — keep the answer sheet in the repository

Write your answers into a tracked document — boost's is
[`openssf-badge.md`](openssf-badge.md) — with each answer's evidence beside it.
This matters more than it sounds:

- The badge site periodically asks you to reconfirm. Re-reading your own
  reasoning beats re-deriving it.
- Answers go stale in predictable ways. Note them: a vulnerability being
  reported moves three answers; adding a runtime dependency moves three more; a
  licence change moves three.
- It makes the claims reviewable by people who do not have a badge account,
  which is most of your users.

## What this cost, and what it found

Three badges, six new documents, and — the part worth the whole exercise — a
**live regression on `main`**. Auditing commits against their messages surfaced
a merged Copilot autofix that had replaced `boost trust add`'s printed key
fingerprint with a constant string, deleting the only verification the command
offered. It passed every gate because no test asserted that line.

That is the honest argument for doing this. The badges are a forcing function;
what you get is the audit.

## Related

- [`openssf-badge.md`](openssf-badge.md) — boost's worked answers, all 67
  passing criteria with evidence
- [`security-design.md`](security-design.md) — the threat model the knowledge
  criteria require
- [`dependencies.md`](dependencies.md) · [`verifying-releases.md`](verifying-releases.md)
  · [`../MAINTAINERS.md`](../MAINTAINERS.md) · [`../SUPPORT.md`](../SUPPORT.md)
  — the Level 2 four
