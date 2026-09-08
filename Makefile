VENV := venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/python -m pytest
NODE := node

.PHONY: test test-py test-js test-verbose test-file lint setup

## Run all tests — the integration (Python) and the Lovelace card (JavaScript)
test: test-py test-js

## Run the integration's Python tests
test-py:
	$(PYTEST) tests/ -q

## Run the Lovelace card's tests (Node's built-in runner; no dependencies)
test-js:
	@command -v $(NODE) >/dev/null 2>&1 || \
		{ echo "make test-js: '$(NODE)' not found — the card tests need Node 18 or later"; exit 1; }
	$(NODE) --test tests/js/*.test.mjs

## Run all tests with verbose output
test-verbose:
	$(PYTEST) tests/ -v
	$(NODE) --test tests/js/*.test.mjs

## Run a specific test file: make test-file FILE=tests/test_config_flow.py
test-file:
	$(PYTEST) $(FILE) -v

## Install/update test dependencies
setup:
	$(PYTHON) -m pip install -r requirements_test.txt -q

## Run a quick import check
lint:
	$(PYTHON) -c "import custom_components.taiga"
