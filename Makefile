VENV := venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/python -m pytest

.PHONY: test test-verbose test-file lint setup

## Run all tests
test:
	$(PYTEST) tests/ -q

## Run all tests with verbose output
test-verbose:
	$(PYTEST) tests/ -v

## Run a specific test file: make test-file FILE=tests/test_config_flow.py
test-file:
	$(PYTEST) $(FILE) -v

## Install/update test dependencies
setup:
	$(PYTHON) -m pip install -r requirements_test.txt -q

## Run a quick import check
lint:
	$(PYTHON) -c "import custom_components.taiga"
