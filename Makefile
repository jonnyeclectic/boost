# boost — test & quality gates
# `make check` is the full production gate: unit + functional with >=80%
# coverage, the shell-level smoke suite, >=80% mutation strength, and the
# Tier 1 retrieval-quality gate (golden-set recall@k).

VENV      := .venv
PY        := $(VENV)/bin/python
PYTEST    := $(VENV)/bin/pytest
# Sandboxed boost home for the Tier 1 eval corpus (gitignored) — keeps the
# pinned taps out of the developer's real ~/.boost.
EVAL_HOME := $(CURDIR)/.eval-home

.PHONY: venv test unit functional smoke coverage patch-coverage mutation lint check demo carousel clean-test eval eval-ai eval-rec eval-stats eval-explain evals evals-baseline evals-golden evals-online audit dist-check bdd bench bench-cli fuzz post-deploy

# Every tool comes from a hash-pinned requirements/*.txt — the same files CI
# installs (see scripts/lock_toolchain.py). pip enforces the hashes, so a dev
# venv and a CI runner resolve to identical bytes. mutation-tools.txt is a
# superset of test-tools.txt, so installing it alone covers both; the two are
# never layered because pip enforces hashes across the whole resolution.
venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip -q install -r requirements/mutation-tools.txt
	$(VENV)/bin/pip -q install -r requirements/coverage-tools.txt
	$(VENV)/bin/pip -q install -r requirements/lint-tools.txt
	$(VENV)/bin/pip -q install -r requirements/release-tools.txt
	$(VENV)/bin/pip -q install uv     # regenerates the locks; not itself locked

unit:
	$(PYTEST) tests/unit -q

functional:
	$(PYTEST) tests/functional -q

# pytest suites with the 80% line-coverage gate (fail_under in pyproject.toml)
test:
	$(PYTEST) tests/unit tests/functional --cov=boost_cli --cov-report=term-missing -q

coverage: test

# patch-coverage: gate coverage on the lines THIS branch changed vs main — the
# same check CI runs on every PR. Needs a diff base, so run it on a branch.
patch-coverage:
	$(PYTEST) tests/unit tests/functional --cov=boost_cli --cov-report=xml --cov-fail-under=0 -q
	$(VENV)/bin/diff-cover coverage.xml --compare-branch=origin/main --fail-under=80

# shell-level functional suite: drives the real shim end-to-end in a sandbox
smoke:
	bash tests/smoke.sh

# mutation testing over boost_cli/core with the unit suite; 80% kill gate
mutation:
	$(PY) scripts/mutation_gate.py --run --min 80

lint:
	$(VENV)/bin/ruff check boost_cli tests evals scripts
	$(VENV)/bin/mypy
	$(VENV)/bin/pyright
	$(VENV)/bin/lint-imports
	$(VENV)/bin/vulture boost_cli --min-confidence 80
	$(VENV)/bin/xenon --max-absolute F --max-modules E --max-average B boost_cli
	$(VENV)/bin/interrogate boost_cli/core
	$(VENV)/bin/refurb boost_cli
	$(VENV)/bin/codespell boost_cli docs README.md
	@# actionlint does not lint `run:` blocks itself — it shells out to
	@# shellcheck, and if shellcheck is not on PATH it skips them silently and
	@# still exits 0. So `make lint` could report a clean workflow lint having
	@# never looked inside a single script. shellcheck is pinned in
	@# requirements/lint-tools.in for exactly this; put $(VENV)/bin on PATH so
	@# actionlint finds it, and fail loudly rather than run a hollow check.
	@if command -v actionlint >/dev/null 2>&1; then \
	  if [ ! -x $(VENV)/bin/shellcheck ]; then \
	    echo "shellcheck missing from $(VENV) — actionlint would skip every run: block. Re-run 'make venv'."; exit 1; \
	  fi; \
	  PATH="$(CURDIR)/$(VENV)/bin:$$PATH" actionlint; \
	else echo "actionlint not on PATH — skipping (CI enforces it)"; fi
	$(PY) scripts/build_registries.py --check
	$(PY) scripts/build_roadmap.py --check
	$(PY) scripts/build_command_reference.py --check
	$(PY) scripts/lock_toolchain.py --check
	$(PY) scripts/a11y_check.py
	$(PY) scripts/page_budget.py
	$(PY) scripts/import_budget.py
	$(PY) scripts/perf_gate.py
	$(PY) scripts/check_anchors.py
	$(PY) scripts/check_required_checks.py
	$(PY) evals/make_golden.py --check

# Supply-chain CVE gate: fail on a known OSV/PyPI advisory in the project's
# dependency closure. Mirrors the pip-audit CI workflow; run before releasing.
audit:
	$(VENV)/bin/pip-audit --strict --progress-spinner off .

# Pre-publish package-metadata gate: build then validate the dist. Mirrors the
# package-metadata CI workflow; run before releasing.
dist-check:
	rm -rf dist
	$(PY) -m build
	$(VENV)/bin/twine check --strict dist/*
	$(VENV)/bin/check-wheel-contents dist/*.whl
	$(VENV)/bin/pyroma --min 8 dist/*.tar.gz

# Tier 1 retrieval quality gate over a pinned corpus (tests/eval/taps.txt).
# Part of `check` and required in CI (the lint job). Taps the pinned repos into
# a sandboxed $(EVAL_HOME) first (network on the first run; a sentinel skips
# re-tapping after), then floors FOUR metrics on BM25, not just recall.
#
# recall@k alone could not fail this build for a ranker that found the right
# answer every time and never ranked it first — recall@10 1.000 with hit@1
# 0.000 passed.
#
# The floors are calibrated against a TWENTY-tap corpus, not the six it used to
# be. Over six repos BM25 scored 1.000 / 0.791 / 0.854 / 0.882; over twenty it
# scores 0.863 / 0.473 / 0.607 / 0.662 on the same golden set. The second set is
# what a real user sees, so flooring against the first was measuring the corpus
# rather than the retrieval — three of the four old floors fail outright once
# the corpus is realistic. Each floor now sits ~10% below its measured value:
# loose enough that upstream repo drift cannot flake the build, tight enough
# that a collapse fails it. Regression-vs-baseline stays relaxed
# (--regression-eps 1) because the corpus tracks upstream HEAD rather than
# pinned commits; the absolute floors are the real gate.
eval:
	PYTHON=$(PY) BOOST_HOME=$(EVAL_HOME) bash scripts/ensure_eval_corpus.sh
	BOOST_HOME=$(EVAL_HOME) $(PY) scripts/eval_retrieval.py --build -k 10 \
	  --fail-under 0.78 --floor hit@1=0.40 --floor MRR=0.52 --floor nDCG@k=0.58 \
	  --regression-eps 1

# Tier 2a: LLM rerank lift over BM25 on the same golden set. Opt-in and
# key-gated — needs the `claude` CLI on PATH or ANTHROPIC_API_KEY; skips
# cleanly otherwise. Not part of `check` (network + cost).
eval-ai:
	$(PY) scripts/eval_retrieval.py --rerank -k 10

# Tier 2b: recommendation quality — heuristic vs `_ai_picks` over golden
# stacks, with a hard grounding gate (no off-shortlist / hallucinated picks).
# Same opt-in/key-gated contract as eval-ai; the heuristic arm always runs.
eval-rec:
	$(PY) scripts/eval_recommend.py --build -k 5 --fail-hallucination

# Tier 1b: statistical-significance testing between engines (ranx paired
# t-test). Opt-in — needs the [eval] extra (`pip install -e '.[eval]'`);
# degrades cleanly if ranx is absent. Runs over the pinned corpus like `eval`.
# Informational (no gate): tells you whether a metric gap is real or noise.
eval-stats:
	PYTHON=$(PY) BOOST_HOME=$(EVAL_HOME) bash scripts/ensure_eval_corpus.sh
	BOOST_HOME=$(EVAL_HOME) $(PY) scripts/eval_retrieval.py --build -k 10 --stats

# Tier 2c: explain-faithfulness (ragas, LLM-judged). Opt-in and key-gated —
# needs the [eval] extra plus a judge key (OPENAI_API_KEY, or ANTHROPIC_API_KEY
# with langchain-anthropic) and boost AI to generate the explanations. Skips
# cleanly when any piece is missing. Over the pinned corpus; out of `check`.
eval-explain:
	PYTHON=$(PY) BOOST_HOME=$(EVAL_HOME) bash scripts/ensure_eval_corpus.sh
	BOOST_HOME=$(EVAL_HOME) $(PY) scripts/eval_explain.py --fail-under 0.80

# Retrieval-quality gate over the HERMETIC golden set: recall@5/@10, MRR, and
# nDCG@5/@10 with graded (3/2/1) relevance, plus a paired-bootstrap regression
# test against the committed evals/baseline.json. Part of `check` and required
# in CI. Unlike `eval` above it needs no network and no API key: it generates
# its own corpus and taps it into a disposable BOOST_HOME under the system temp
# dir, so a metric moving can only mean the ranker moved.
evals:
	$(PY) scripts/eval_gate.py --run

# Re-pin evals/baseline.json to the current scores. Deliberate: it is how you
# accept a ranking change, so it must be a separate commit that says why.
evals-baseline:
	$(PY) evals/run_evals.py --save-baseline

# Regenerate evals/golden_set.json from evals/make_golden.py after editing the
# query table (`--check` runs in `lint` and fails on drift).
evals-golden:
	$(PY) evals/make_golden.py

# The same five metrics over the pinned REAL-registry corpus `eval` uses.
# Needs the network; reported, never gated — mirrors `tests/smoke.sh --online`.
evals-online:
	$(PY) evals/run_evals.py --online --faithfulness

# Opt-in Gherkin/BDD suite (tests/bdd) — additive to tests/functional, not a
# replacement. Needs the [bdd] extra (`pip install -e '.[bdd]'`); not part of
# `make check`.
bdd:
	$(VENV)/bin/behave tests/bdd/features

# Opt-in micro-benchmarks (tests/perf) for perf-sensitive core paths. Needs
# the [perf] extra (`pip install -e '.[perf]'`); not part of `make check` — a
# timing regression is informational, not a merge gate.
bench:
	$(PYTEST) tests/perf --benchmark-only -q

# Opt-in wall-clock benchmark of the real `boost` binary via hyperfine. Not
# part of `make check`; degrades cleanly (prints a skip message, exits 0) when
# hyperfine isn't installed (`brew install hyperfine`).
bench-cli:
	@if command -v hyperfine >/dev/null 2>&1; then bash scripts/bench_cli.sh; \
	else echo "hyperfine not on PATH — install via 'brew install hyperfine', skipping"; fi

# Opt-in coverage-guided fuzzing of the hand-rolled parsers (atheris/libFuzzer).
# Not part of `make check` — a fuzzer is a search, not a pass/fail gate; the
# scheduled `fuzz` workflow owns the long runs. Each target degrades cleanly to
# a seed-corpus pass when atheris is absent (it ships manylinux wheels only), and
# the seed pass also runs in the normal unit suite so the harnesses can't rot.
# FUZZ_SECONDS=60 make fuzz   to run longer.
FUZZ_SECONDS ?= 30
fuzz:
	@for t in fuzz_frontmatter fuzz_registry; do \
		echo "== $$t"; \
		$(PY) tests/fuzz/$$t.py tests/fuzz/corpus/$${t#fuzz_} \
			-max_total_time=$(FUZZ_SECONDS) -artifact_prefix=/tmp/ || exit 1; \
	done

# Health check for the PUBLISHED docs site: every page 200, every local asset and
# internal link resolves, and (with Chrome) no console errors or failed runtime
# requests. Not part of `make check` — it needs the network and the live deploy;
# the post-deploy workflow runs it after Pages republishes.
# BOOST_SITE=http://localhost:8000/ make post-deploy   to check a local serve.
BOOST_SITE ?= https://jonnyeclectic.github.io/boost/
post-deploy:
	$(PY) scripts/post_deploy_smoke.py --base-url "$(BOOST_SITE)" -v
	@if command -v node >/dev/null 2>&1; then BOOST_SITE="$(BOOST_SITE)" node tests/visual/console_check.mjs; \
	else echo "node not on PATH — skipping the console check (CI runs it)"; fi

# regenerate generated artifacts from their source (registries + roadmap boards)
generate:
	$(PY) scripts/build_registries.py
	$(PY) scripts/build_roadmap.py
	$(PY) scripts/build_command_reference.py

# regenerate docs/demo.gif (brew install vhs)
demo:
	vhs docs/demo.tape

# regenerate all 8 docs/carousel/gifs/*.gif, one flagship command per group
carousel:
	for t in docs/carousel/tapes/*.tape; do vhs "$$t"; done

check: lint eval evals test smoke mutation
	@echo "== all gates passed =="

clean-test:
	rm -rf mutants .coverage htmlcov .pytest_cache
