#!/usr/bin/env python3
# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Build the hermetic eval corpus: a local git tap the harness grades against.

`make eval` (the other retrieval gate) taps real GitHub repos, so it needs the
network and drifts when upstream does. This harness needs the opposite: a corpus
that is byte-identical on every machine and every CI run, so a metric moving can
only mean the *ranker* moved.

The corpus is generated, not committed, for the same reason tests/make_fixture.py
is: the source of truth is this file's item table, which diffs far better than 57
scattered Markdown files (49 skills, 4 rules, 4 workflows — `boost count` reports
"available 57" over the built corpus). It deliberately packs topical near-neighbors
(tdd-workflow vs unit-test-authoring vs mutation-testing) so recall@k and nDCG@k
have something to discriminate — a corpus of 5 unrelated skills scores 1.000 on
everything and measures nothing.

The five skills from tests/make_fixture.py are imported verbatim rather than
retyped, so the fixture tap stays the single source of truth for them.

Usage:  python3 evals/make_corpus.py [dest_dir]     # prints the corpus path
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The corpus directory name becomes the tap name, and boost names a root-level
# `.cursorrules` after its directory — so this string shows up as an item id.
CORPUS_DIRNAME = "boost-eval-corpus"
# Outside the repo on purpose: the corpus is a *git repo*, and nesting one
# inside the project confuses `git status`, coverage discovery, and mutmut's
# tree copy. It is disposable — deleting it just costs one rebuild.
DEFAULT_DEST = Path(tempfile.gettempdir()) / "boost-evals-home" / CORPUS_DIRNAME

# Fixed timestamp so `git commit` produces the same SHA from the same content —
# the corpus is then reproducible down to the commit the RAG index keys on.
GIT_EPOCH = "2024-01-01T00:00:00+00:00"


# --------------------------------------------------------------- item table
# (name, description, tags, body). The body is the searchable text: BM25 indexes
# the whole thing, so the vocabulary here is what the golden queries have to hit.

Item = tuple[str, str, list[str], str]

SKILLS: tuple[Item, ...] = (
    # ---- testing ----------------------------------------------------------
    ("unit-test-authoring",
     "Write focused unit tests with arrange-act-assert structure",
     ["testing", "quality"], """
Write unit tests that fail for exactly one reason.

1. Arrange the smallest fixture that reproduces the behavior.
2. Act once — a test that calls the subject twice is two tests.
3. Assert on observable output, never on internal call order.

- Name tests `test_<unit>_<condition>_<expected>` so a failure reads as a sentence.
- Prefer parametrized cases over loops inside a single test.
- Mock only at process boundaries: the network, the clock, the filesystem.
"""),
    ("flaky-test-triage",
     "Diagnose and quarantine intermittently failing tests",
     ["testing", "debugging"], """
A test that fails one run in twenty is worse than no test — it trains the team
to ignore red builds.

1. Re-run the suspect test 50 times in isolation to confirm intermittency.
2. Classify the cause: shared mutable state, wall-clock dependence, unordered
   collection iteration, or a genuine race in the code under test.
3. Quarantine the test with an owner and a deadline, never silently skip it.

- Seed every random source explicitly; unseeded randomness is the top cause.
- Freeze time rather than sleeping; a `sleep(0.1)` is a race with a timer.
"""),
    ("integration-test-harness",
     "Stand up realistic integration tests against ephemeral services",
     ["testing", "infrastructure"], """
Integration tests prove the wiring that unit tests mock out.

1. Boot dependencies as disposable containers, one fresh set per suite.
2. Migrate the schema from scratch — never reuse a developer's local database.
3. Tear everything down in a fixture finalizer so a crash cannot leak state.

- Assert across the seam: the HTTP status *and* the row that was written.
- Keep the suite under ten minutes or engineers will stop running it locally.
"""),
    ("mutation-testing",
     "Measure test strength by mutating source and rerunning the suite",
     ["testing", "quality"], """
Line coverage says a line ran. Mutation testing says a line was *checked*.

1. Generate mutants: flip comparison operators, swap constants, drop statements.
2. Rerun the test suite against each mutant.
3. A mutant the suite still passes is a survivor — an assertion you never wrote.

- Score = killed / (total - skipped); untested code counts as unkilled.
- Gate the score in CI; a coverage percentage alone is gameable.
"""),
    ("snapshot-testing",
     "Golden-file testing for rendered output and serialized structures",
     ["testing", "quality"], """
Snapshot tests pin output that is tedious to assert field by field.

1. Render the output deterministically — sort keys, strip timestamps.
2. Commit the snapshot and review it like source code.
3. Update snapshots deliberately; a blanket `--update-all` defeats the point.

- Never snapshot anything containing a UUID, an absolute path, or a clock read.
- Large snapshots hide regressions; split them by concern.
"""),
    ("property-based-testing",
     "Generate test inputs from properties instead of hand-picked examples",
     ["testing", "quality"], """
Example tests find the bugs you imagined. Property tests find the others.

1. State an invariant: round-tripping a parse and a render returns the input.
2. Let the generator produce thousands of inputs, including pathological ones.
3. Shrink a failure to its minimal reproducing case before debugging it.

- Good properties: idempotence, round-trip, commutativity, never-crashes.
- Record the failing seed in the bug report so the case is reproducible.
"""),
    ("test-coverage-gates",
     "Enforce line and branch coverage thresholds in continuous integration",
     ["testing", "ci"], """
A coverage gate stops slow erosion; it does not prove correctness.

1. Measure branch coverage, not just line coverage.
2. Fail the build below the agreed floor rather than reporting a trend.
3. Exclude generated files explicitly, in config, with a comment saying why.

- Raise the floor only when it has held for a release; never lower it silently.
"""),

    # ---- version control ---------------------------------------------------
    ("branch-naming",
     "Consistent, greppable branch names tied to tracker issues",
     ["git", "hygiene"], """
Branch names are the index into six months of history.

1. Prefix by intent: `feat/`, `fix/`, `chore/`, `spike/`.
2. Embed the tracker ID so tooling can link the branch to the ticket.
3. Keep the slug short and lowercase, words separated by hyphens.

- One topic per branch — a branch that touches two concerns cannot be reverted.
- Delete merged branches; a stale branch list hides the active work.
"""),
    ("rebase-vs-merge",
     "Choose between rebase and merge for a clean, bisectable history",
     ["git", "workflow"], """
Rebase to tidy work that has not been shared; merge to record work that has.

1. Rebase your local feature branch onto the updated trunk before review.
2. Never rebase a branch someone else has already pulled.
3. Merge into trunk with a commit that names the change, not "Merge branch".

- Every commit on trunk must build, or `git bisect` becomes useless.
- Squash noisy fixup commits before merging, keep meaningful ones separate.
"""),
    ("git-bisect-hunt",
     "Find the commit that introduced a regression by binary search",
     ["git", "debugging"], """
Bisect turns "somewhere in 400 commits" into eight builds.

1. Write a script that exits 0 on good and 1 on bad — automate the verdict.
2. Mark a known-good tag and the current bad commit.
3. Run `git bisect run ./check.sh` and let it converge.

- Skip commits that fail to build rather than marking them bad.
- The result is a commit, not a culprit — read the diff before blaming it.
"""),
    ("monorepo-workspaces",
     "Structure a monorepo so builds and ownership stay tractable",
     ["architecture", "tooling"], """
A monorepo is one repository, not one build.

1. Give every package an explicit dependency manifest; no implicit reaching in.
2. Derive the affected set from the diff so CI builds only what changed.
3. Encode ownership per directory so review routing is automatic.

- Shared code needs a real API and a real owner, or it becomes a dumping ground.
"""),

    # ---- code review -------------------------------------------------------
    ("code-review-checklist",
     "Structured pull request review covering correctness, tests, and risk",
     ["review", "quality"], """
Review in passes; a single read mixes typo-hunting with design critique.

1. Read the description and the tests first — they state the intent.
2. Check correctness at the boundaries: empty input, overflow, concurrency.
3. Check the blast radius: what breaks if this is wrong in production?

- Approve or request changes explicitly; a silent review blocks the author.
- Distinguish blocking defects from preferences, and say which is which.
"""),
    ("pr-description-writer",
     "Write pull request descriptions that make review fast",
     ["review", "docs"], """
The description is the reviewer's only context. Spend two minutes on it.

1. Lead with why, not what — the diff already says what.
2. List the risk and how it was verified, including what you did *not* test.
3. Link the issue, the design doc, and any follow-up work you are deferring.

- Screenshot or paste output for anything user-visible.
"""),
    ("review-comment-tone",
     "Give review feedback that lands without bruising the author",
     ["review", "collaboration"], """
Critique the code, address the person.

1. Ask rather than assert when you might be missing context.
2. Say what you would do differently and why, not just that it is wrong.
3. Praise the parts that are genuinely good — reviews are not only defect lists.

- Prefix optional suggestions with `nit:` so blocking issues stand out.
"""),

    # ---- CI/CD -------------------------------------------------------------
    ("github-actions-ci",
     "Build reliable GitHub Actions pipelines with caching and matrices",
     ["ci", "automation"], """
A pipeline that is slow or flaky is a pipeline people route around.

1. Split lint, test, and build into separate jobs so failures are legible.
2. Cache the dependency directory keyed on the lock file hash.
3. Use a matrix for the platforms and interpreter versions you actually support.

- Pin action versions to a tag; a floating `@main` is remote code execution.
- Set a job timeout so a hung step cannot burn an hour of runner minutes.
"""),
    ("release-automation",
     "Automate versioning, changelog, and publishing from tags",
     ["ci", "release"], """
Every manual release step is a step someone will skip at 6pm on a Friday.

1. Derive the version from the git tag — one source of truth, no constant to bump.
2. Generate the changelog from commit messages, then edit it for humans.
3. Publish from CI with a scoped token; no laptop should hold publish rights.

- Never release from a red build; gate the publish job on the full test suite.
"""),
    ("docker-build-optimization",
     "Shrink container images and speed up layer rebuilds",
     ["docker", "performance"], """
Most slow Docker builds are cache misses, not slow compilers.

1. Copy the dependency manifest and install *before* copying source.
2. Use a multi-stage build so compilers never ship in the runtime image.
3. Pin the base image by digest for reproducibility.

- Order layers from least to most frequently changed.
- A `.dockerignore` that excludes `.git` often halves the build context.
"""),
    ("deployment-rollback",
     "Safe rollout and rollback strategy for production deployments",
     ["deployment", "reliability"], """
You will deploy a bad change. Plan the way back before you need it.

1. Roll out progressively — one canary instance, then a percentage, then all.
2. Watch the error rate and latency against the previous version, not a fixed threshold.
3. Make rollback a single command, and rehearse it while nothing is on fire.

- Database migrations must be backward compatible or rollback is a lie.
"""),
    ("feature-flag-hygiene",
     "Manage feature flags so they do not outlive their rollout",
     ["deployment", "hygiene"], """
Every flag is a branch in production that someone must eventually delete.

1. Create the flag with an owner and a removal date in the same commit.
2. Default to off, roll forward deliberately, and record the decision.
3. Delete the flag and the dead branch once the rollout is complete.

- A flag older than one quarter is technical debt with a config file.
"""),

    # ---- security ----------------------------------------------------------
    ("secret-scanning",
     "Detect and rotate credentials committed to a repository",
     ["security", "ci"], """
A secret in git history is compromised even after you delete the file.

1. Scan the full history, not just the working tree.
2. Rotate the credential first — removal is cleanup, rotation is the fix.
3. Add a pre-commit hook so the next one never lands.

- High-entropy string detection catches what pattern rules miss.
- Never rewrite shared history without telling everyone who has a clone.
"""),
    ("dependency-audit",
     "Audit third-party dependencies for known vulnerabilities",
     ["security", "supply-chain"], """
Your dependency tree is the majority of your attack surface.

1. Resolve the full transitive closure; direct dependencies are the small part.
2. Check each version against an advisory database and fail the build on a match.
3. Triage by exploitability in *your* usage, not by the raw severity score.

- Pin with a lock file; a floating range is an unreviewed change on every install.
"""),
    ("threat-modeling",
     "Systematically enumerate attacks against a system design",
     ["security", "architecture"], """
Threat modeling is design review with an adversary in the room.

1. Draw the data flow and mark every trust boundary it crosses.
2. Per boundary, enumerate spoofing, tampering, repudiation, disclosure,
   denial of service, and elevation of privilege.
3. Rank by (likelihood x impact) and assign a mitigation or an accepted risk.

- Do it at design time; retrofitting a mitigation costs an order of magnitude more.
"""),
    ("sql-injection-review",
     "Review data-access code for injection and unsafe query construction",
     ["security", "review"], """
Every string-concatenated query is a vulnerability waiting for the right input.

1. Grep for query construction that interpolates a variable.
2. Replace it with a parameterized statement — the driver escapes, you do not.
3. Confirm the ORM escape hatch (`raw`, `execute`) is not being used casually.

- Least-privilege database roles limit the damage when a query does slip through.
"""),
    ("auth-token-handling",
     "Store, scope, and rotate authentication tokens safely",
     ["security", "backend"], """
A token is a bearer credential: whoever holds it is you.

1. Scope every token to the narrowest permission set that works.
2. Keep tokens out of URLs, logs, and error reports — all three get archived.
3. Give every token an expiry and an automated rotation path.

- Store refresh tokens server-side; a browser is not a secure vault.
"""),

    # ---- performance -------------------------------------------------------
    ("profiling-python",
     "Profile Python programs to find real hotspots before optimizing",
     ["performance", "python"], """
Measure first. Intuition about where the time goes is wrong more often than not.

1. Profile a representative workload, not a microbenchmark you invented.
2. Read cumulative time to find the expensive subtree, total time for the hot leaf.
3. Optimize the top entry, re-measure, and stop when the profile flattens.

- Algorithmic complexity beats micro-optimization; check the big-O first.
- A line profiler answers "which line", a sampling profiler answers "which call".
"""),
    ("database-index-tuning",
     "Diagnose slow queries and design the indexes that fix them",
     ["performance", "database"], """
Read the query plan before you add an index.

1. Capture the slow query log and rank by total time, not worst case.
2. Read the execution plan for sequential scans over large tables.
3. Add a composite index in the order the predicates are evaluated.

- Every index slows writes; delete the ones the planner never chooses.
- Selectivity decides usefulness: an index on a boolean rarely helps.
"""),
    ("frontend-bundle-size",
     "Reduce JavaScript bundle size and improve page load time",
     ["performance", "frontend"], """
Bytes shipped are the load-time budget you actually control.

1. Analyze the bundle and rank modules by parsed size.
2. Code-split on the route boundary so the first paint ships less.
3. Replace the heavy dependency; a date library is rarely worth 70 KB.

- Measure on a throttled connection and a mid-range phone, not a laptop.
"""),
    ("caching-strategy",
     "Choose cache layers, keys, and invalidation for read-heavy systems",
     ["performance", "architecture"], """
Caching is a correctness problem disguised as a performance one.

1. Decide what may be stale, and for how long, before choosing a layer.
2. Build the key from every input that changes the value — including the version.
3. Prefer expiry over explicit invalidation; expiry fails safe.

- Guard against the stampede: one miss should not become a thousand queries.
"""),
    ("memory-leak-hunt",
     "Track down growing memory usage in long-running processes",
     ["performance", "debugging"], """
A leak is retention you did not intend, not memory the allocator kept.

1. Confirm the growth is monotonic under steady load, not just fragmentation.
2. Take heap snapshots at intervals and diff the object counts.
3. Follow the retention path back to the root that will not let go.

- Unbounded caches and event listeners nobody unsubscribed are the usual causes.
"""),

    # ---- documentation -----------------------------------------------------
    ("readme-authoring",
     "Write a README that gets a new user to first success fast",
     ["docs", "onboarding"], """
The README answers three questions in the first screen: what, why, how do I start.

1. Open with one sentence a stranger understands.
2. Give an install command and a runnable example that actually works.
3. Link deeper docs rather than inlining them.

- Test the quickstart on a clean machine every release; it rots silently.
"""),
    ("api-reference-docs",
     "Document an API surface with accurate parameters and examples",
     ["docs", "api"], """
Reference docs are consulted, not read. Optimize for scanning.

1. One entry per endpoint or function, with a consistent field order.
2. Document errors and edge cases — that is why people open the reference.
3. Every example must be copy-pasteable and version-pinned.

- Generate from source where possible so signatures cannot drift from prose.
"""),
    ("changelog-discipline",
     "Maintain a human-readable changelog across releases",
     ["docs", "release"], """
A changelog is written for the person deciding whether to upgrade.

1. Group by release, newest first, with a date.
2. Group entries by Added / Changed / Fixed / Removed / Security.
3. Call out breaking changes at the top with the migration step.

- Write it for humans; a dump of commit subjects is not a changelog.
"""),
    ("adr-writing",
     "Record architecture decisions with context and consequences",
     ["docs", "architecture"], """
An ADR captures why, so the next team does not relitigate it blind.

1. State the context and the forces in tension.
2. State the decision in one sentence, in the active voice.
3. State the consequences — including the ones you dislike.

- Never edit a decided ADR; supersede it with a new one that links back.
"""),

    # ---- debugging & operations -------------------------------------------
    ("stack-trace-triage",
     "Read a stack trace and locate the true origin of an exception",
     ["debugging", "quality"], """
The top frame is where it surfaced, rarely where it went wrong.

1. Read the exception type and message before the frames.
2. Find the deepest frame in your own code — the boundary is usually the bug.
3. Follow the `caused by` chain to the original failure.

- Reproduce before fixing; a fix you cannot verify is a guess.
"""),
    ("logging-discipline",
     "Emit structured logs that are useful during an incident",
     ["observability", "backend"], """
Logs are written once and read at 3am. Optimize for the reader.

1. Log structured key-value pairs, not interpolated prose.
2. Include a correlation ID on every line so a request can be reassembled.
3. Reserve ERROR for things a human must act on; everything else is INFO or DEBUG.

- Never log credentials, tokens, or personal data — logs get shipped and retained.
"""),
    ("production-incident-response",
     "Run a production incident from detection to postmortem",
     ["reliability", "operations"], """
Mitigate first, diagnose second. Users do not care about the root cause.

1. Declare the incident and name one commander; ambiguity costs minutes.
2. Mitigate — roll back, flip the flag, shed load — before investigating.
3. Keep a running timeline; memory is unreliable and the postmortem needs it.

- Blameless postmortems within a week, with owned action items.
"""),
    ("observability-metrics",
     "Instrument services with metrics that answer operational questions",
     ["observability", "reliability"], """
Instrument for the question you will ask during an outage.

1. Track rate, errors, and duration for every entry point.
2. Use histograms for latency — an average hides the tail that hurts users.
3. Alert on user-visible symptoms, not on CPU.

- Every alert needs a runbook link, or it will be silenced.
"""),

    # ---- refactoring -------------------------------------------------------
    ("refactor-legacy-code",
     "Safely restructure legacy code without a test suite to lean on",
     ["refactoring", "quality"], """
Get a seam, then a test, then refactor. Never the other way round.

1. Pin current behavior with characterization tests — record what it does today.
2. Introduce a seam (parameter, interface) so the unit becomes reachable.
3. Refactor in small commits, keeping the suite green at every step.

- Do not mix a behavior change into a refactoring commit; separate the reverts.
"""),
    ("dead-code-removal",
     "Find and delete unreachable code with confidence",
     ["refactoring", "hygiene"], """
Deleted code is the cheapest code to maintain.

1. Prove unreachability statically, then confirm with production telemetry.
2. Delete the code, its tests, its config, and its documentation together.
3. Commit deletions separately so the revert is trivial.

- Commented-out code is dead code with extra steps; git already remembers.
"""),
    ("type-annotation-migration",
     "Incrementally add static types to an untyped codebase",
     ["refactoring", "types"], """
Type a codebase leaf-first; annotations flow upward for free.

1. Turn on the checker in permissive mode and record the current error count.
2. Annotate the leaf modules with the most callers first.
3. Ratchet the strictness setting per module, never repo-wide at once.

- Fail CI on *new* errors while the backlog burns down; a big-bang migration stalls.
"""),
    ("api-deprecation",
     "Deprecate and remove a public API without breaking consumers",
     ["api", "release"], """
A deprecation is a schedule with a migration path, not a warning in a docstring.

1. Ship the replacement first and document the mapping from old to new.
2. Emit a runtime deprecation warning naming the removal version.
3. Remove only on a major version, after the announced window.

- Measure real usage before removing; telemetry beats assumption.
"""),

    # ---- planning & collaboration -----------------------------------------
    ("estimation-poker",
     "Run relative estimation sessions that surface hidden complexity",
     ["planning", "collaboration"], """
The value of estimation is the disagreement it exposes.

1. Estimate relative size, not hours — velocity converts it later.
2. Reveal simultaneously so nobody anchors on the loudest voice.
3. When estimates diverge widely, discuss the difference, then re-estimate.

- Split anything too big to estimate; the size is the signal.
"""),
    ("standup-notes",
     "Run an async standup that is worth reading",
     ["planning", "collaboration"], """
Write the standup for someone catching up tomorrow.

1. What moved, what is blocked, what you need from a named person.
2. Link the ticket or PR for anything you mention.
3. Raise blockers explicitly; a blocker mentioned in passing is not raised.

- Status is not a to-do list; report change, not activity.
"""),
    ("onboarding-buddy",
     "Get a new engineer to their first merged pull request",
     ["onboarding", "collaboration"], """
Measure onboarding by time to first merged change, not by documents read.

1. Have them fix the setup docs while following them — the first contribution.
2. Pair on a small, real, scoped change in week one.
3. Introduce systems on demand, when a task needs them, not as a lecture.

- Assign one named buddy; "ask anyone" means asking no one.
"""),
)

# Rules (.mdc / .cursorrules) and workflows (commands/, agents/) — boost indexes
# all three kinds out of one tap, so the corpus carries the other two as ranking
# pressure. The golden set grades skills only.
RULES: tuple[tuple[str, str], ...] = (
    ("rules/python-style.mdc", """---
description: Python formatting and idiom rules
globs: ["**/*.py"]
---
- Format with the project formatter; never hand-align.
- Prefer comprehensions over map/filter for readability.
- Type every public function signature.
"""),
    ("rules/typescript-style.mdc", """---
description: TypeScript strictness and import conventions
globs: ["**/*.ts", "**/*.tsx"]
---
- `strict` stays on; no implicit any, ever.
- Prefer `unknown` over `any` at boundaries, then narrow.
- Absolute imports from the package root, no deep relative chains.
"""),
    ("rules/react-conventions.mdc", """---
description: React component structure and hook rules
globs: ["**/*.tsx"]
---
- One component per file, named the same as the file.
- Derive state; do not mirror props into state.
- Every effect declares its full dependency array.
"""),
    (".cursorrules", """Project conventions for AI assistants.

- Match the surrounding code style before introducing a new one.
- Never commit generated files without regenerating them from source.
- Run the full gate before claiming a change is done.
"""),
)

WORKFLOWS: tuple[tuple[str, str], ...] = (
    ("commands/ship-it.md", """---
description: Run the full gate and open a pull request
---
Run lint, tests, and the smoke suite. If all pass, push the branch and open a
pull request with a generated description summarizing the diff and its risk.
"""),
    ("commands/triage-bug.md", """---
description: Reproduce, localize, and file a bug report
---
Reproduce the reported behavior, bisect to the introducing commit, and file an
issue containing the reproduction steps, the expected result, and the actual one.
"""),
    ("agents/security-auditor.md", """---
name: security-auditor
description: Reviews a diff for injection, secret exposure, and unsafe defaults
---
Audit the changed files for injection sinks, credentials in source, permissive
defaults, and missing authorization checks. Report findings ranked by severity.
"""),
    ("workflows/onboard-repo.md", """---
description: Orient in an unfamiliar repository
---
Map the entry points, the build and test commands, and the deployment path.
Produce a short orientation note a new engineer can follow to a first change.
"""),
)


# --------------------------------------------------------------- generation

def _fixture_skills() -> dict[str, str]:
    """The five skills from tests/make_fixture.py, as full SKILL.md text.

    Imported rather than retyped so the fixture tap remains the single source of
    truth for them — if a fixture skill's wording changes, this corpus follows.
    """
    path = ROOT / "tests" / "make_fixture.py"
    spec = importlib.util.spec_from_file_location("boost_make_fixture", path)
    if spec is None or spec.loader is None:      # pragma: no cover - defensive
        raise SystemExit("cannot import %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {name: spec_d["frontmatter"] + "\n\n" + spec_d["body"]
            for name, spec_d in mod.SKILLS.items()}


def skill_md(name: str, description: str, tags: list[str], body: str) -> str:
    return ("---\nname: %s\ndescription: %s\nversion: 1.0.0\ntags: [%s]\n---\n\n"
            "# %s\n%s" % (name, description, ", ".join(tags),
                          name.replace("-", " ").title(), body))


def skill_names() -> list[str]:
    """Every skill id in the corpus — what the golden set is allowed to cite."""
    return sorted(list(_fixture_skills()) + [s[0] for s in SKILLS])


def build(dest: Path) -> Path:
    """Write the corpus to ``dest`` as a committed git repo. Idempotent."""
    skills_root = dest / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)

    for name, text in _fixture_skills().items():
        d = skills_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
    for name, description, tags, body in SKILLS:
        d = skills_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(skill_md(name, description, tags, body),
                                    encoding="utf-8")
    for rel, text in RULES + WORKFLOWS:
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (dest / "README.md").write_text(
        "# boost eval corpus\n\nGenerated by evals/make_corpus.py — do not edit "
        "by hand.\n", encoding="utf-8")

    env = dict(os.environ,
               GIT_AUTHOR_DATE=GIT_EPOCH, GIT_COMMITTER_DATE=GIT_EPOCH,
               GIT_AUTHOR_NAME="Boost Evals", GIT_AUTHOR_EMAIL="evals@boost.test",
               GIT_COMMITTER_NAME="Boost Evals",
               GIT_COMMITTER_EMAIL="evals@boost.test")

    def run(*a: str) -> None:
        subprocess.run(a, cwd=dest, check=True, capture_output=True, env=env)

    if not (dest / ".git").exists():
        run("git", "init", "-q")
    run("git", "add", "-A")
    if subprocess.run(("git", "diff", "--cached", "--quiet"), cwd=dest,
                      env=env, check=False).returncode != 0:
        run("git", "commit", "-qm", "eval corpus")
    return dest


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DEST
    print(build(dest.resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
