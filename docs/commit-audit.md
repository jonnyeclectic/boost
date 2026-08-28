# Commit audit — message versus diff

Every commit claims something in its message. This is a record of an
independent pass checking whether the diff actually delivers it, produced while
adopting the [Developer Certificate of Origin](../CONTRIBUTING.md#sign-your-commits-dco).

It exists because the DCO itself could not be applied backwards. A
`Signed-off-by` is the *contributor* asserting they may submit the work, so a
trailer added later by a reviewer certifies nothing — and backfilling one across
569 commits would rewrite `main`, breaking 478 tags and invalidating the
build-provenance attestation on every published release. The review still had
value; the history rewrite did not. So the review happened and was written down
here instead.

Repo: `/private/tmp/claude-501/boost-osps` (worktree of github.com/jonnyeclectic/boost)
Range: 60 commits, `9ca72fd` through `c8c9075` inclusive (i.e. `git log -60 c8c9075`). NOTE: while this audit ran, a peer session
re-committed the tip to add a DCO sign-off, so `c8c9075` is now `0939f53` (identical
tree, message differs only by a `Signed-off-by:` trailer) and a 61st commit `b23b98f`
sits on top. The findings below are unaffected.
Method: read subject + full body, then the diff (generated payloads — `docs/roadmap.html`,
`registries.json`, `demo.gif` — checked at the stat level and judged against the
source-of-truth files and tests instead). Read-only: only `git log` / `git show`.

## Counts

| Verdict | Count |
|---|---|
| MATCHES | 57 |
| OVERSTATES | 1 |
| UNDERSTATES | 1 |
| SUPERSEDED | 1 |
| UNCLEAR | 0 |

## Needs a human look

- **`dc6e827` — UNDERSTATES.** "Potential fix for code scanning alert no. 54: Clear-text
  logging of sensitive information". The diff (`boost_cli/commands/quality.py`, `cmd_trust`)
  does not merely stop logging — it deletes the trusted-key **name and fingerprint** from
  `boost trust add`'s success line and replaces it with the constant `"trusted key added"`,
  discarding `rec` entirely. Nothing in the message says a user-facing verification output
  was removed. Two seconds later `560652b` shipped `docs/openssf-badge.md:231-240`, which
  states this exact autofix "would remove the only verification the command offers and make
  boost *less* secure, **so it must not be merged**" — and lists dismissing the alert as a
  pending human action. It was already merged, and it is still in `HEAD`.
- **`d82467a` — OVERSTATES.** Subject: "…and stop Dependabot auto-rebasing". The diff adds
  `rebase-strategy: disabled` to 3 of the 5 `package-ecosystem` blocks in
  `.github/dependabot.yml` (github-actions, npm `/`, npm `/tests/visual`); the two `pip`
  blocks are untouched. Those blocks carry `open-pull-requests-limit: 0`, but the file's own
  comment says "Security updates ignore the limit and keep firing" — so a live PR-producing
  path is still auto-rebased. Low severity, but the claim is unqualified.
- **`e4f2491` — SUPERSEDED by `838aa81`.** "fix(ci): give eval-stats credentials to push
  with" delivers the credentials (`git push origin HEAD:main` → an
  `x-access-token:${{ github.token }}@github.com/...` URL) plus a guard test, and the body
  implies the publisher now lands. It could not: `838aa81` establishes that `main` carries a
  ruleset with an empty bypass list so *no* token can push to it, and replaces the whole
  push-to-main with a PR flow off an `eval-metrics` branch.

## Cross-cutting note (not a verdict)

`560652b`'s `docs/openssf-badge.md` and the tree disagree about alert 54 — see `dc6e827`
above. `560652b`'s own subject claim ("all 67 passing criteria, with a threat model") is
delivered: 67 criteria rows (61 Met / 6 N/A / 1 Unmet-justified) plus
`docs/security-design.md` with trust boundaries, Saltzer–Schroeder principles, and CWE
classes.

## Per-commit table

| SHA | Subject (60 chars) | Verdict | Evidence |
|---|---|---|---|
| c8c9075 (now 0939f53) | docs: the four documents OSPS Baseline Level 2 asks for | MATCHES | Exactly four new docs (MAINTAINERS.md, SUPPORT.md, docs/dependencies.md, docs/verifying-releases.md) + roadmap item; all four added to the vale list in prose-lint.yml; SECURITY.md gains a Secrets section. |
| 560652b | docs(security): answer all 67 OpenSSF passing criteria, wit | MATCHES | 67 criteria rows in docs/openssf-badge.md; docs/security-design.md is the threat model. See cross-cutting note re: alert 54. |
| dc6e827 | Potential fix for code scanning alert no. 54: Clear-text lo | UNDERSTATES | quality.py `cmd_trust` drops `rec["name"]`/`rec["fingerprint"]` for a constant string, removing the key-verification output; undisclosed, and contradicted by docs/openssf-badge.md:231. |
| b0b1c6e | chore: drop permission entries for paths that no longer exi | MATCHES | Exactly 5 `Bash(...)` entries removed from .claude/settings.local.json, all naming `~/vibe`/`vibe_cli`. |
| 8658e8f | fix(ci): exempt cramjam from the licence gate, with the ups | MATCHES | `"cramjam": "MIT upstream; wheel metadata omits it"` in UNDECLARED_OK + `test_cramjam_is_exempt`. |
| 714e879 | chore(deps-dev): bump eslint from 10.8.1 to 10.9.1 | MATCHES | Routine bot bump (batched with the other dependabot rows below). |
| 61d6097 | chore(deps): bump the codeql-action group with 3 updates | MATCHES | Routine bot bump; all three sub-action pins move together, as 731a598's grouping intends. |
| d82467a | docs(style): display-face traps, an AI-tells prose rule, an | OVERSTATES | `rebase-strategy: disabled` on 3 of 5 `package-ecosystem` blocks in .github/dependabot.yml; both pip blocks untouched. |
| f75d85d | chore(deps): bump step-security/harden-runner 2.20.1→2.21.0 | MATCHES | Routine bot bump across 18 workflows. |
| e6e1d31 | chore(eval): refresh published metrics | MATCHES | docs/eval-latest.json: `generated`/`commit` re-stamped; no metric value moved (nothing claimed one would). |
| 7819053 | chore(deps): bump google/osv-scanner-action reusable workfl | MATCHES | Routine bot bump. |
| e3d1ccd | chore(deps): bump puppeteer-core 25.6.0→25.8.0 in /tests/vi | MATCHES | Routine bot bump, lockfile + manifest only. |
| d6f6e80 | chore(deps): bump the codeql-action group with 3 updates | MATCHES | Routine bot bump, grouped. |
| 351f558 | fix(cli): fold long hints to the pane without splitting the | MATCHES | `out.wrap()` + `wrap=` kwarg on warn/info/dim/kv in core/output.py; 5 command modules converted; test_cli_pane_width.py (137 lines) + test_output.py (+217). |
| fc70c8a | fix(search): a term with no postings falls back to the comm | MATCHES | `rag.stem_expansions()` range-scan + `_note_stem_expansions` in discovery.py so the substitution is reported; 14 unit + 3 functional tests added. |
| 7a5816f | fix(cli): fit the boxes and the help screen to the terminal | MATCHES | Both literal `%%` strings removed from commands/team.py; `panel()` clamps to `term_width() - 4`; `print_help` measures via `out.term_width()`. |
| 8687c40 | feat(catalog): curate a marketing / CRM / email / outreach d | MATCHES | 16 new `marketing` rows + 4 recategorised = 20, in scripts/build_registries.py (the source of truth); registries.json + taps-scale.txt regenerated; test_registry_categories.py +94. |
| 1167bcd | docs(demo): re-record demo.gif against the current CLI | MATCHES | Bot; docs/demo.gif binary only. |
| 3387607 | perf(dense): rank on one bit per dimension, rescore the sur | MATCHES | `vec_chunks_bin` + `vec_raw` + `quantize()`/`quantized()` in core/dense.py; `reindex --dense` calls quantize and doctor reports `quantized`; test_dense_quantized.py (376) incl. `test_the_rescore_is_load_bearing`; test_dense_status_cheap.py (281) covers the COUNT(*) removal. |
| 7db0477 | perf(search): cache the LLM rerank order, keyed on exactly | MATCHES | `rerank_cache_path()` + FIFO get/put in core/rag.py; `"rerank_cache.json"` added to paths.INTERNAL_CACHE_FILES; MCP cost wording updated + test_rerank_cache.py. |
| 45a6dfa | perf(search): rank from the index, materialise only the sur | MATCHES | `_retrieve_from_index` + `_windowed` in core/rag.py; dense.ready() stats before importing; test_rag_fastpath.py (279) + test_dense_ready_order.py. |
| d53354e | docs(demo): re-record demo.gif against the current CLI | MATCHES | Bot; binary only. |
| f54b72b | chore(eval): refresh published metrics | MATCHES | Timestamp/commit re-stamp only. |
| 7f1a9a8 | feat(ui): one design system across search and browse | MATCHES | `search_layout`, `format_search_row`, `meter_hue`, `kind_label` in core/output.py; `rule_segments`, `scrollbar`, `empty_lines`, `badge_positions`, `state_glyph`, `session_summary`, `install_target`, `count_tail` in core/browse.py (12 helpers, as claimed); `_aurora_theme`/`_subseq`/`_match_positions` removed. |
| 3a28b3f | test(eval): re-pin the Tier 1b scale corpus | MATCHES | Bot; exactly 165/165 lines in taps-scale.txt — the distractors gain SHAs, the 20 required rows are byte-identical. Confirms 007f1dd's fix held. |
| 007f1dd | fix(eval): the scale re-pin moved the twenty rows it does n | MATCHES | `frozen_rows()` + `frozen=` in `relock_text` (scripts/eval_corpus.py); eval-scale.yml gains a post-refresh `build_scale_corpus.py --check`; test_eval_corpus.py +153, test_scale_corpus.py +34. |
| 422570f | chore(eval): refresh published metrics | MATCHES | Timestamp/commit re-stamp only. |
| a3a751a | docs(shards): replace the scale estimate with what the job | MATCHES | shards.yml comment-only rewrite carrying the measured 77,423→24,246 / 2 h 07 m / 129 MB figures; no timeout or logic changed, as the `docs(` prefix implies. |
| 838aa81 | fix(ci): a publisher that could not publish, and an alert t | MATCHES | eval-stats.yml: push-to-main replaced by a branch + PR, `contents`/`pull-requests: write`; ci-failure-issue.yml gains the `close-issue` job keyed on the per-workflow marker and moves `issues: write` from workflow to job level; two guard tests. |
| ec87983 | fix(registry): a tap spec too long for the filesystem is an | MATCHES | `MAX_NAME_BYTES = 255` + total `_looks_like_a_directory()` in core/registry.py; both reproducers added as fuzz corpus seeds; test_registry_control_chars.py +120. |
| 3f7bd86 | fix(deps): bump two transitive npm advisories out of the th | MATCHES | package-lock.json only: brace-expansion 5.0.8→5.0.9 and nanoid 3.3.16→3.3.18, exactly the two named. |
| 06b6246 | fix(registries): stop advertising two repos that no longer | MATCHES | `RETIRED = {...}` + `verify_live()` + `--verify-live` in scripts/build_registries.py; 28 lines removed from registries.json; 3 new tests in test_registry_categories.py. |
| 709eb05 | feat(catalog): give an entry an identity for what it is, no | MATCHES | `catalog._content_digest` + `CACHE_FORMAT = 1` with rescan-on-stale; browse.dedupe and `resolve_one` key on the digest; dense chunk-dedupe; test_content_identity.py (437) + test_dense_embed_dedupe.py (216). |
| 0861e7f | chore(deps-dev): bump eslint from 10.8.0 to 10.8.1 | MATCHES | Routine bot bump. |
| c289c88 | chore(deps): bump puppeteer-core 25.5.0→25.6.0 in /tests/vi | MATCHES | Routine bot bump. |
| 0fd70ba | docs(demo): re-record demo.gif against the current CLI | MATCHES | Bot; binary only. |
| 717b8c8 | feat(browse): let space reach the query, and rebuild the br | MATCHES | Printable-range fix with the keymap move (Enter/Tab/Esc/^T) in commands/discovery.py; new core/browse.py (470) holding the pure logic; scripts/build_roadmap.py gains the raw-`<` guard the second sub-commit describes; test_browse.py (687) + test_roadmap_fresh.py. |
| 3e6b494 | fix(completions): stop --install deleting the config betwee | MATCHES | `_spans`/`_outside` single-scan rewrite of `_merge_rc`/`_strip_rc` plus `RcPlan`/`plan_install`/`plan_uninstall`/`apply` and `--dry-run`; test_complete_rc_block.py (367) incl. the 672-arrangement property test. |
| 35eb03f | fix(visual): stop handing --single-process to a full Chrome | MATCHES | `needsSingleProcess` predicate gates both `--single-process`/`--in-process-gpu` and `headless: "shell"` in visual_check.mjs; test_visual_harness_flags.py pins parity with a11y_check.mjs. |
| 4be314c | perf(taps): stop checking out the 84% of a repo boost never | MATCHES | `SPARSE_PATTERNS` + `--filter=blob:none --sparse` + memoized `materialize`/`narrow` in core/gitutil.py; `cmd_compact`; `paths.INTERNAL_CACHE_FILES` guard for `boost clean`; command counters corrected; 5 new test modules incl. test_gitutil_sparse.py (293). |
| 15b129e | fix: four defects found by reading a real machine's crash r | MATCHES | All four present: `logs._redact` (name + value-shape), `PermissionError` handling in store `_copy_skill`, `IncompleteRead` in embed `_post`, and `blocked_links` in sync_plan/sync_apply + doctor; four dedicated test modules. |
| bf85de1 | feat(catalog): share the catalogue instead of making everyo | MATCHES | New core/catalogbundle.py (265) with `export_bundle`/`import_bundle`/`_safe_members` (traversal, symlink, member-count and size caps); `cmd_catalog` + COMMANDS row; test_catalogbundle.py (405) + test_cli_catalog.py (190); the pinned command-count literals updated across README/CLAUDE/docs/tests. |
| 5b27b41 | fix(self-update): stop claiming "already up to date" withou | MATCHES | `PYPI_JSON` + `latest_version()` + `is_behind()` in core/selfupdate.py; per-manager index-refresh flags (`--refresh` / `--no-cache-dir`); test_selfupdate.py +272. |
| c4a8584 | chore(deps): bump step-security/harden-runner 2.20.0→2.20.1 | MATCHES | Routine bot bump to the peeled SHA, as the body states. |
| aba4e27 | fix(shards): make the shard pipeline able to produce a shar | MATCHES | `--list-repos` in scripts/eval_corpus.py and shards.yml switched to it; `_tap_chunk_count`/`_unreadable_vectors` separate the two states in core/dense.py; three new test modules incl. one that runs without sqlite-vec. |
| 14ba426 | chore(deps): bump puppeteer-core 25.4.0→25.5.0 in /tests/vi | MATCHES | Human-authored regeneration, but touches only tests/visual/package{,-lock}.json; puppeteer-core 25.4.0→25.5.0, @puppeteer/browsers 3.0.6→3.1.0, axe-core held at 4.13.0 — exactly as the body states. |
| f5ecc54 | fix(store): let `boost sync` repair a skill whose SKILL.md | MATCHES | One-condition change `if not sdir.is_dir()` → `or not (sdir / "SKILL.md").is_file()`; test_sync_repairs_gutted_skill.py (96) pins both directions. |
| 0b5b317 | docs: correct five measurably-wrong claims, and stop the sm | MATCHES | All five: recall floor 0.85→0.78, the UP006/UP035/UP045 sweep note, UP031 ~860→1,005/1,800 with the reproducing command, index.html 5→7 pre-tapped (both places), smoke 170→174; plus 5 commands added to smoke.sh and test_smoke_covers_every_command.py mirroring COMMANDS. |
| 470b9de | fix(registry): reject control characters in a tap spec, and | MATCHES | Control-char rejection at `parse_spec`; the watched list goes from 2 to exactly 26 workflows; Makefile `lint` now runs `zizmor --offline`; test_failure_alerting_covers_unattended.py + test_zizmor_ignores_still_anchor.py. |
| 13891fa | docs(demo): re-record demo.gif against the current CLI | MATCHES | Bot; binary only. |
| 93f16d9 | test(langsmith): cover the golden-set publisher, which had | MATCHES | Single new file tests/unit/test_publish_golden_dataset.py (226); no production change, as the `test(` prefix implies. |
| e4f2491 | fix(ci): give eval-stats credentials to push with | SUPERSEDED | Credentials added as claimed, but the push to `main` still could not succeed; `838aa81` replaces `git push … HEAD:main` with an `eval-metrics` branch + PR because main's ruleset has an empty bypass list. |
| 3ebccb0 | chore(deps): bump google/osv-scanner-action/... | MATCHES | Routine bot bump. |
| 844675e | chore(deps): bump actions/attest-build-provenance 4.1.1→4.2 | MATCHES | Routine bot bump. |
| 08a7744 | fix(ci): stop one PR's demo run from cancelling another PR' | MATCHES | demo.yml `group: demo` → `demo-${{ pull_request.number \|\| sha }}` with `cancel-in-progress` gated on `pull_request`; sonarcloud.yml given the same shape; test_workflow_concurrency_groups.py (144). |
| 8a4a211 | chore(deps): bump axe-core from 4.12.1 to 4.13.0 in /tests/ | MATCHES | Routine bot bump. |
| 731a598 | fix(ci): move every sub-action of one action repo in lockst | MATCHES | `groups:` for `github/codeql-action*` and `actions/cache*` in dependabot.yml; all three codeql pins moved to the same peeled SHA; test_action_pin_lockstep.py (290) parametrised over both families. |
| ff969c8 | fix(gitutil): never download Git LFS payloads when cloning | MATCHES | `env=os.environ \| {"GIT_LFS_SKIP_SMUDGE": "1"}` passed per-call in core/gitutil.py; test_gitutil_lfs.py (67). |
| 3827fea | docs(demo): re-record demo.gif against the current CLI | MATCHES | Bot; binary only. |
| 9ca72fd | feat(serve): a searchable, faceted catalogue and a graph of | MATCHES | core/serve.py +793: `catalog_rows`, `search_rows` (reusing catalog.search), `entry_tags` namespaced facets, `_label_propagate` graph, fingerprint-keyed `cached_view`/`cached_graph`, `public_row` \u-escaping; test_serve.py +571 incl. the reflection payload tests. |
