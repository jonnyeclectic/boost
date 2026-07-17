# boost — test & quality gates
# `make check` is the full production gate: unit + functional with >=80%
# coverage, the shell-level smoke suite, and >=80% mutation strength.

VENV    := .venv
PY      := $(VENV)/bin/python
PYTEST  := $(VENV)/bin/pytest

.PHONY: venv test unit functional smoke coverage mutation check clean-test

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip -q install pytest pytest-cov coverage mutmut

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

check: test smoke mutation
	@echo "== all gates passed =="

clean-test:
	rm -rf mutants .coverage htmlcov .pytest_cache
