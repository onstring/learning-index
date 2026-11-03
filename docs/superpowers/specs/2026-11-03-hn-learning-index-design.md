# HN Learning Index: design

Date: 2026-11-03. Status: approved decisions from the user, design by Claude Code.

## 1. Goal

A static website that lists free online learning resources (whole sites or single
posts) that Hacker News commenters have recommended repeatedly over the years, with a
topic, a resource type, a difficulty level, a one-sentence description, and the HN
comments that recommended it. Audience: curious students. Model: hackerbooks.org, but
for free online material instead of books.

Decisions already made by the user:

| Decision | Choice |
|---|---|
| Scope | free online resources only; no books for sale, videos, code repositories, news |
| Classifier | hybrid: clef-flash (gate, topic, type, difficulty) then qwen3:30b-a3b, thinking off (blurb on kept items only) |
| Delivery | static site generated from a local pipeline |
| Cost | $0; everything runs locally on Ollama |

Decisions made here, changeable by editing `config.py`:

| Decision | Choice | Why |
|---|---|---|
| Working name | "HN Learning Index" | neutral; one constant to rename |
| Candidate threshold | 3 or more distinct recommenders | the evaluated population; 2 is a later experiment |
| Keep rule | clef composite question at or above 0.7, and `is_video` below 0.8 | as evaluated (accuracy 0.85, recall 0.95). Hard exclusions at 0.5 on `is_video`, `is_code_repo`, `is_paid_book` were scored on the same eval outputs and only lost recall (0.92), so they are not applied at that level. The full run showed 38 kept rows with `is_video` above 0.5; the six above 0.8 were all screencast or lecture-video sites, so that one exclusion is applied. 0.8 for the composite scored higher on the same 100 items but was not adopted, to avoid tuning on the evaluation set |
| Topics, types, difficulty | the 15 / 8 / 3 lists from `analysis/eval/eval_rubric.py` | evaluated |
| Dead links | 404, 410, DNS failure or timeout excluded; 403 and 429 kept and marked unverified | bot blocks are common on good sites |
| Ranking | distinct recommenders descending, then years spanned descending | explainable |
| Refresh | manual: re-download dataset, re-run pipeline; every stage resumes from its output file | few times a year is enough |

## 2. Pipeline

Seven stages, one module each, each writing one file under `data/`. Every stage is
idempotent and resumable: it skips rows already present in its output.

```
dataset/*.parquet
  -> build_db     data/hn.duckdb         stories, link_comments, comment_parents, comment_root
  -> candidates   data/candidates.jsonl  one row per normalised URL with 3+ recommenders
  -> fetch        data/fetch.jsonl       status, final URL, title, meta description, text snippet
  -> classify     data/clef.jsonl        clef-flash probabilities, topic, type, difficulty, keep
  -> describe     data/blurbs.jsonl      qwen3 title + blurb for kept rows
  -> assemble     data/resources.json    joined, scored, slugged site model
  -> site         site/                  HTML, CSS, JS, search index
```

CLI: `uv run python -I -m hnlearn <stage> [--limit N] [options]`. `--limit` lets a slice
run end to end before the full multi-hour run.

### build_db

Port of `analysis/build_db.py` and `analysis/resolve_roots.py`. Reads every monthly
parquet, materialises the four tables, resolves each comment to its root story. About
30 s on the full dataset.

### candidates

Port of the recommendation signal from `analysis/export.py`. For every comment that
contains a link and matches the recommendation-phrase regex: unescape HTML entities,
extract hrefs, normalise (strip scheme, `www.`, query, fragment, trailing slash,
lower-case). Group by normalised URL. Keep rows with 3 or more distinct authors, host
not in the noise list, host containing a dot. Per row: `nurl`, `host`, `ppl`, `yrs`,
`y0`, `y1`, `mentions`, up to three evidence comments (id, author, time, root story id
and title, text excerpt of 700 characters, HTML stripped), and the best matching story
submission (id, title, score) if any.

### fetch

One GET per candidate, 8 in parallel, 15 s timeout, a fixed user agent, redirects
followed. Records status (or an error class), final URL, `<title>`, meta description
and the first 1,500 characters of visible body text. The body snippet is new relative
to the evaluation: it gives clef something to tell a paid-book landing page from a free
book, the hardest error class in the eval.

### classify

For each fetched candidate, one `POST /v1/systemone` to clef-flash with the state text
(URL, host, page title, description, body snippet, HN story title, recommender count
and years, evidence excerpts) and the rubric questions: six booleans, the composite
question, topic choice, type choice, difficulty score. Writes all probabilities. `keep`
is derived by the rule in section 1 and recomputed by `assemble`, so changing the
threshold never needs a re-run. Before the full run, the 100 evaluation URLs are
re-scored with the production state text (which now includes a body snippet) and
checked against `analysis/eval/eval_gold.csv`; if accuracy drops, the snippet is
removed, not the model.

### describe

For each kept row, one `POST /api/chat` to qwen3:30b-a3b, thinking off, temperature 0,
JSON schema `{title, blurb}`. Title: a clean short title when the page title is
missing or noisy. Blurb: one neutral sentence, at most 25 words, no mention of HN.

### assemble

Joins the four JSONL files, applies the keep rule, drops dead links, computes rank,
builds a URL slug (host plus path, limited length, hash suffix on collision), picks the
display title (qwen title, else page title, else HN story title, else URL) and the
link target (final URL when the fetch succeeded, else `https://` plus the normalised
URL). Writes `resources.json`, the single input of the site stage.

### site

Jinja2 templates with autoescape on, one CSS file, one small JS file for client-side
search over `search.json`. Pages: home (top 100 and topic navigation), one page per
topic, one page per resource, about (method, data source, licences, attribution).
Resource page shows title, link, blurb, topic, type, difficulty, recommender count and
year span, up to three HN excerpts each linking to the comment and naming the author,
and the HN story link with points when one exists.

## 3. Code layout

```
pyproject.toml            uv project; deps duckdb, jinja2; dev pytest, pytest-cov, ruff
src/hnlearn/
  __main__.py             argparse dispatch to stages
  config.py               paths, thresholds, noise hosts, site name
  sql.py                  UNESC, NORM, HOST fragments and the recommendation regex
  text.py                 strip_html, unescape, truncate, slugify, normalise_url
  jsonl.py                read, append, done-key set for resume
  rubric.py               questions, topics, types, difficulty, keep rule, state text
  ollama.py               systemone(), chat_json(); explicit errors; no retries hidden
  build_db.py  candidates.py  fetch.py  classify.py  describe.py  assemble.py  site.py
  templates/              base, home, topic, resource, about
  static/                 style.css, search.js
tests/                    one file per module, fixtures built in-test
data/                     pipeline outputs (git-ignored)
site/                     generated site (git-ignored for now)
```

Each module stays under 400 lines, functions under 50 lines. No mutation of shared
state: stages read files and write new files.

## 4. Error handling and trust boundaries

- Dataset and fetched pages are untrusted. Scripts run with `python -I`; no code is
  loaded from `dataset/` or `data/`. All page content is rendered through Jinja2
  autoescape; no `|safe` on data. Link targets must start with `http://` or `https://`.
- Fetch targets and every redirect must be http or https to a public address (loopback,
  private, link-local and `localhost` names are refused after DNS resolution), with no
  credentials in the URL. This stops a crafted href in the dataset from reaching the local
  Ollama server or anything else on the network.
- Fetch failures are recorded per row, never raised; a failed fetch is a data point. Rows
  with no HTTP answer or a 5xx are fetched again on the next run; later rows for the same
  URL supersede earlier ones.
- Ollama failures (connection refused, HTTP error, invalid JSON from qwen) are
  recorded per row with the error text and the row is retried on the next run.
- Every stage validates its input rows (required keys, types) and stops with a clear
  message on a malformed file rather than producing a partial site.

## 5. Testing

pytest, 80 percent coverage target. Unit tests for text, sql (DuckDB on an in-test
fixture), rubric, jsonl, assemble. Integration tests for build_db and candidates on a
tiny parquet built in the test, for fetch against a local `http.server` thread, for
classify and describe with a fake Ollama transport, and for site by rendering a
two-resource fixture and checking the HTML. Rendering tests assert that an excerpt
containing `<script>` is escaped.

## 6. Run plan

1. Slice: `--limit 50` through every stage; inspect `resources.json` and the site.
2. Full run in the background: fetch (about 10 min), classify (about 2 to 3 h at
   3 to 4 s per URL), describe (about 1 h). Both models cannot be loaded at once on
   this 32 GB machine; classify finishes before describe starts.
3. Site build from the full outputs; spot-check 30 resources against the eval rubric.

## 7. Out of scope for this version

Ask HN resource-thread signal (85 percent overlap with the phrase signal in the
feasibility study), refetching live HN points, archive.org fallback for dead links,
a dynamic search backend, user submissions, and the 27B `clef` model.
