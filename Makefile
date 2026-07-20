# boost — test & quality gates
# `make check` is the full production gate: unit + functional with >=80%
# coverage, the shell-level smoke suite, and >=80% mutation strength.

VENV    := .venv
PY      := $(VENV)/bin/python
PYTEST  := $(VENV)/bin/pytest

.PHONY: venv test unit functional smoke coverage mutation lint check demo clean-test eval eval-ai eval-rec audit

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip -q install pytest pytest-cov coverage mutmut ruff mypy codespell

unit:
	$(PYTEST) tests/unit -q

functional:
	$(PYTEST) tests/functional -q

# pytest suites with the 80% line-coverage gate (fail_under in pyproject.toml)
test:
	$(PYTEST) tests/unit tests/functional --cov=boost_cli --cov-report=term-missing -q

coverage: test

# shell-level functional suite: drives the real shim end-to-end in a sandbox
smoke:
	bash tests/smoke.sh

# mutation testing over boost_cli/core with the unit suite; 80% kill gate
mutation:
	$(PY) scripts/mutation_gate.py --run --min 80

lint:
	$(VENV)/bin/ruff check boost_cli tests
	$(VENV)/bin/mypy
	$(VENV)/bin/codespell boost_cli docs README.md
	@command -v actionlint >/dev/null 2>&1 && actionlint || echo "actionlint not on PATH — skipping (CI enforces it)"
	$(PY) scripts/build_registries.py --check
	$(PY) scripts/build_roadmap.py --check

# Supply-chain CVE gate: fail on a known OSV/PyPI advisory in the project's
# dependency closure. Mirrors the pip-audit CI workflow; run before releasing.
audit:
	$(VENV)/bin/pip-audit --strict --progress-spinner off .

# Tier 1 retrieval quality gate: golden-set recall@k over the tapped catalog.
# Deterministic + offline; a release-quality gate, kept separate from `check`.
eval:
	$(PY) scripts/eval_retrieval.py --build -k 10 --fail-under 0.85

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

# regenerate generated artifacts from their source (registries + roadmap boards)
generate:
	$(PY) scripts/build_registries.py
	$(PY) scripts/build_roadmap.py

# regenerate docs/demo.gif (brew install vhs)
demo:
	vhs docs/demo.tape

check: lint test smoke mutation
	@echo "== all gates passed =="

clean-test:
	rm -rf mutants .coverage htmlcov .pytest_cache
