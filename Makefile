# Pipeline orchestration. Every stage resumes from its output file, so `make all` is safe
# to re-run after an interruption. clef-flash is unloaded before the describe stage because
# the two Ollama models do not fit in memory together on a 32 GB machine.

PY := uv run python -I -m hnlearn

.PHONY: all build_db candidates fetch classify describe assemble site test lint clean-site

all: build_db candidates fetch classify describe assemble site

build_db:
	$(PY) build_db -v

candidates:
	$(PY) candidates

fetch:
	$(PY) fetch -v

classify:
	$(PY) classify -v

describe:
	-ollama stop clef-flash
	$(PY) describe -v
	-ollama stop qwen3:30b-a3b

assemble:
	$(PY) assemble

site:
	$(PY) site

test:
	uv run pytest --cov

lint:
	uv run ruff check src tests

clean-site:
	rm -rf site
