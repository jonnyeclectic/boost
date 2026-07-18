# boost — test & quality gates
# `make check` is the full production gate: unit + functional with >=80%
# coverage, the shell-level smoke suite, and >=80% mutation strength.

VENV    := .venv
PY      := $(VENV)/bin/python
PYTEST  := $(VENV)/bin/pytest

.PHONY: venv test unit functional smoke coverage mutation lint check demo clean-test

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip -q install pytest pytest-cov coverage mutmut ruff mypy

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
	$(PY) scripts/build_registries.py --check
	$(PY) scripts/build_roadmap.py --check

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
