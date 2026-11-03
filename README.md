# HN Learning Index

Static website listing free online learning resources that Hacker News commenters
have recommended repeatedly over the years. Built from the
[open-index/hacker-news](https://huggingface.co/datasets/open-index/hacker-news)
dataset (ODC-By 1.0) with a local DuckDB pipeline and two local Ollama models.

Design: `docs/superpowers/specs/2026-11-03-hn-learning-index-design.md`.
Feasibility study: `docs/feasibility.md`. Classifier evaluation: `docs/classifier-eval.md`.

## Setup

```sh
uv sync
uvx --from huggingface_hub hf download open-index/hacker-news --repo-type dataset \
    --include 'data/*' stats.csv README.md --local-dir dataset
ollama pull clef-flash
ollama pull qwen3:30b-a3b
```

## Pipeline

Every stage reads the previous stage's file under `data/` and resumes where it left off.

```sh
uv run python -I -m hnlearn build_db      # dataset/*.parquet -> data/hn.duckdb
uv run python -I -m hnlearn candidates    # -> data/candidates.jsonl
uv run python -I -m hnlearn fetch         # -> data/fetch.jsonl
uv run python -I -m hnlearn classify      # clef-flash -> data/clef.jsonl
uv run python -I -m hnlearn describe      # qwen3 -> data/blurbs.jsonl
uv run python -I -m hnlearn assemble      # -> data/resources.json
uv run python -I -m hnlearn site          # -> site/
```

`--limit N` on any stage processes the first N rows, for a quick end-to-end slice.
`make all` runs every stage in order and unloads clef-flash before the describe stage
(the two models do not fit in memory together on a 32 GB machine).

## Tests

```sh
uv run pytest --cov
uv run ruff check src tests
```
