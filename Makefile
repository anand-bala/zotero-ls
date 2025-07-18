SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# Default: create the dev environment
dev: uv.lock | .venv
.PHONY: dev

fmt:
	uv run --frozen ruff format 
	uv run --frozen ruff check --fix .
.PHONY: fmt

typing:
	uv run --frozen mypy src
	uv run --frozen ty check
	uvx basedpyright
.PHONY: typing

lint: fmt typing
.PHONY: lint

test:
	uv run --dev --frozen pytest
.PHONY: test

uv.lock .venv &: pyproject.toml
	uv sync --frozen --dev

# Automatic make target for scripts with locking
%.py.lock: %.py
	uv lock --script $<
