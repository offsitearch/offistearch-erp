# StudioERP v2 — Makefile (Windows-friendly; uses `python -m`).
PYTHON ?= python
VENV   ?= .venv

.PHONY: venv install install-dev lint test test-kernel build check

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(PYTHON) -m pip install -e .
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest

test-kernel:
	pytest tests

build:
	ruff check src tests
	pytest

check: build
