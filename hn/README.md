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

Run these from this `hn/` folder; this project is one section of the Learning Index repo
(see the [top-level README](../README.md)). Every stage reads the previous stage's file under
`data/` and resumes where it left off. `make site` writes to `../site/hn/`, the published
location; `python -m hnlearn site` without `--out` still writes to `site/` here.

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

## Preview

```sh
python3 -m http.server -d ../site 8000   # then open http://localhost:8000/hn/
```

Opening `../site/hn/index.html` straight from disk works for browsing, but search needs the
http server because browsers refuse to load `search.json` over `file://`.

## First full run (2026-11-03, dataset through 2026-08, Apple Silicon 32 GB)

| Stage | Output | Time |
|---|---|---|
| build_db | 6.2M stories, 5.1M link comments, 43.1M comment-root rows | 33 s |
| candidates | 2,522 URLs with 3+ distinct recommenders | 3 s |
| fetch | 2,522 pages; 2,003 live (200/403/429), 344 dead, the rest retried | 9 min + 3 min |
| classify (clef-flash) | 2,179 scored, 0 failures, 3.2 s per URL | 1 h 46 min + 9 min |
| describe (qwen3:30b-a3b) | 1,193 blurbs, 0 failures, 1.6 s per URL | 37 min |
| assemble + site | 1,186 resources, 15 topics, 1,203 pages | seconds |

Of the scored URLs, 54 percent pass the keep rule. A 30-item random spot check of the
built site found 3 clear misses (a product homepage, a paid-book homepage, a health
information site) and 4 borderline items, consistent with the precision measured in
`docs/classifier-eval.md`.

## Tests

```sh
uv run pytest --cov
uv run ruff check src tests
```
