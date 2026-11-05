# Feasibility: a Hacker News learning-resource index

Date: 2026-11-03
Status: investigation complete, no application code written
Prepared with Claude Code

## 1. Verdict

Feasible, and cheaper than the two reference sites. The dataset is complete and local. Three independent signals in the data surface a few thousand high-quality, non-time-bound learning resources with measurable precision. Two data defects need workarounds, both tested. A static site generated a few times a year from a DuckDB pipeline is the recommended first version.

Everything in sections 2 to 4 is measured on the downloaded data unless marked as an assumption or recommendation.

## 2. Dataset (verified)

| Item | Value |
|---|---|
| Source | huggingface.co/datasets/open-index/hacker-news |
| Local copy | `dataset/data/YYYY/YYYY-MM.parquet` (239 files), plus `stats.csv`, `README.md` |
| Size on disk | 12 GB (12.42 GB of Parquet, Zstandard level 22) |
| Rows | 49,324,111; every non-empty month matches `stats.csv` (2006-11 and 2007-01 are empty upstream) |
| Coverage | 2006-10 to 2026-08-23 (monthly files). A separate `today/` config carries 5-minute live blocks; not downloaded |
| Item types | 43.1M comments, 6.24M stories, 18k jobs, 2k polls, 16k poll options |
| Licence | Open Data Commons Attribution (ODC-By) v1.0. Attribution to the dataset is required. Comment and story text remain the authors' |
| Text format | HTML, not Markdown. Code is HTML-escaped |
| Upstream source | ClickHouse public mirror of the HN Firebase API, exported month by month |

The download did not need authentication. Re-downloading a single new month later is one `hf download --include data/2026/2026-09.parquet` call.

## 3. Data quality findings (verified)

| Finding | Evidence | Impact | Workaround (tested) |
|---|---|---|---|
| Story `score` and `descendants` are stale snapshots for 2023 and 2026 | Story 36201593 (Apple Vision Pro, June 2023): dataset 329 points, live 2,608. 2023 has 634 stories with 100+ points; 2022 and 2024 have 15,198 and 14,096. 2022 points match live (comment counts differ slightly) | Cannot rank 2023 or 2026 content by points | Recompute comment counts from the parent chain (done: 43M comments resolved to root story in 16 s, max depth 40). Refetch points for the final candidate set only via the Algolia item API (tested, 12 calls) or the official Firebase API |
| Link hrefs inside comments are HTML-entity escaped from 2014 onward (`https:&#x2F;&#x2F;…`) | Entity frequency per month | Naive extraction returned garbage for 2014 to 2026 | Unescape `&#x2F; &#38; &amp; &#x27; &quot; &gt; &lt;` before URL normalisation |
| 2024 and 2025 files have an empty `words` column and `deleted` always 0 | Parquet footer column sizes; per-year counts | None for this project (tokenise ourselves). Deleted items may be absent rather than flagged | Ignore `words` |
| 103,320 comments do not resolve to a story | Root resolution | Negligible (orphans, poll and job replies) | Drop |
| Link rot | 29 of 40 sampled recommended URLs returned 2xx/3xx; several of the failures were 403 bot blocks, not dead pages. The sample came from the first analysis pass, which only parsed pre-2014 links correctly, so it over-represents old links | Some resources are gone; the modern candidate set is probably healthier | Store a Wayback Machine fallback link; run a liveness check at each rebuild |

## 4. Candidate signals (measured)

I defined "tutorial-like" as three measurable buckets and ran them over the whole archive. Precision figures come from my reading of 40 random items per bucket; treat them as rough.

| Signal | Definition | Count | Precision (40-item sample) |
|---|---|---|---|
| S1 Story titles | Title matches tutorial patterns (tutorial, introduction to, guide, from scratch, explained, learn X, primer, lecture notes, cheat sheet, interactive…) minus a news/product negative list; has a URL; 50+ points or 20+ comments | 9,527 (of 112,289 raw matches) | ~30/40 relevant |
| S2 Ask HN resource threads | Title starts "Ask HN:" and asks for resources, books, courses, how to learn, where to start, recommendations; 20+ comments | 1,176 threads, 92,403 comments | ~28/40 genuine resource requests |
| S3 URLs recommended inside S2 threads | hrefs in replies at any depth, normalised, counted by distinct commenters, noise hosts excluded | 27,273 hrefs, 21,386 URLs. 1,376 URLs with 2+ recommenders, 475 with 3+, 162 with 5+ | Top 50 are almost all learning resources. Long tail (2 to 4 people): ~24/40 |
| S4 Recommendation-phrase comments, whole corpus | Comment contains a link and phrasing such as "highly recommend", "great introduction", "best resource", "start with", "must read", "taught me" | 93,481 comments. 6,472 URLs with 2+ recommenders, 2,383 with 3+, 767 with 5+ | 3 to 6 recommenders: ~25/40 |
| Evergreen subset of S4 | 3+ distinct recommenders across 3+ distinct years | 1,845 URLs | High; see `docs/samples/top300_evergreen_urls.csv` |

Top of S3 by distinct recommenders: teachyourselfcs.com (29), nand2tetris.org (29), Coursera "Learning How to Learn" (25), eloquentjavascript.net (22), the Coursera machine-learning course (21), khanacademy.org (20), craftinginterpreters.com (18), dataintensive.net (17), neuralnetworksanddeeplearning.com (16), OSTEP (15), deeplearningbook.org (14), projecteuler.net (14), aosabook.org (14), htdp.org (14), course.fast.ai (14), Feynman Lectures (12). This is the target content.

Two further measurements matter for the build:

- Of the 2,348 URLs with 3+ recommenders (noise hosts excluded), 1,987 (85%) were also submitted to HN as a story. The story gives a title, the best-scoring discussion link, and a points figure for free. Only the remaining 15% need a page fetch for a title.
- Noise concentrates in a short host list: Google search, cache, Play Store, Books and Scholar; Amazon and Goodreads (books); YouTube (videos); Wikipedia; GitHub root; HN itself; xkcd; Bugzilla; SSRN and CiteSeerX. A host exclusion list of about 30 entries removes most of it. Wikipedia, GitHub and YouTube are scope decisions, not noise (section 8).

Sample exports for your own judgement: `docs/samples/top300_recommended_urls.csv` and `docs/samples/top300_evergreen_urls.csv`.

## 5. How the reference sites work (verified where stated)

- hackerbooks.org (About page): starts from the public HN archive; finds candidate book references with regexes and light NLP (quoted titles, "by Author", Amazon, Goodreads, Open Library links, ISBNs); matches them to Open Library; counts every matched title across all comments; uses a small model to disambiguate ambiguous titles; labels each mention recommend, neutral, critical or not-about-the-book with Claude Sonnet 5.5 (85% agreement with Opus 5.5 on 400 mentions). Ranking weights distinct commenters over raw mentions. "Rising" compares recent mentions to history. Static regeneration a few times a year with an email list for refresh notices. Built with Claude Code.
- hackertube.org: client-side rendered app. Its About text is not in the served HTML and I could not retrieve it, so I cannot state its method. The navigation (Longs, Categories, Playlists, Watch later) indicates YouTube links mined from HN with a video-player front end.
- HN Hall of Fame (orangecrumbs.com, a recent Show HN): "links repeatedly rediscovered by the community over years", about 1,100 inducted links, methodology not published.
- Older related work: hacker-recommended-books.vercel.app (NLP over comments), learnawesome.org (hand-curated, not HN-derived), Tom Larkworthy's "most favourited" analysis (favourites are not in this dataset).

Gap: none of these targets learning resources specifically, ranks by distinct recommenders and year span, or groups by topic. S3 and S4 above give exactly that.

## 6. Build approaches

Approach A (recommended): static site from a DuckDB pipeline

- Pipeline (Python plus DuckDB, as in `analysis/`): load Parquet, resolve roots, extract and normalise links, score candidates, refetch points for the candidate set, write one JSON or SQLite file.
- Optional classification pass (section 7).
- Static generator (Astro, Eleventy, Hugo, or Python plus Jinja) renders topic pages, resource pages with quoted comment excerpts linking back to HN, and a client-side search index (Pagefind).
- Hosting on GitHub Pages or Cloudflare Pages. Running cost about zero. Refresh a few times a year by pulling new monthly files, matching the hackerbooks model.
- Trade-off: no per-user state. "For you" style features would use browser localStorage, as hackerbooks does.

Approach B: static front end over a browser-queried SQLite file (sql.js-httpvfs)

- Lets visitors query the full candidate table without a server. Useful if you want thousands of long-tail items browsable with filters.
- Trade-off: heavier first load, more front-end code, harder to index for search engines.

Approach C: dynamic application (FastAPI or Next.js plus Postgres)

- Needed only for accounts, votes, user submissions, or near-real-time updates from the 5-minute live blocks.
- Trade-off: hosting cost, security surface, operations. Not justified for version one.

Recommendation: A, with the pipeline written so B or C can reuse its output later.

## 7. Classification and ranking design (proposal)

Ranking signal, in priority order: distinct recommenders, distinct threads, span of years between first and last recommendation, then HN points of the matching story. No time decay, since the goal is evergreen material. A small boost for recent years would offset the fact that a 2025 resource has had less time to collect three recommenders (S4 coverage drops from about 450 URLs per first-seen year to 119 for 2024).

Heuristic filtering alone gives roughly 60 to 75% precision. (Update, 2026-11-03: after the scope narrowed to free online resources only, a 100-URL labelled evaluation measured heuristic-only precision at 0.51 on realistic candidates, so this figure is optimistic for the new scope. The LLM pass can run locally on Ollama at no API cost; see `docs/classifier-eval.md`.) An LLM pass would lift that and add what heuristics cannot: a yes/no "is this a learning resource", topic tags, difficulty, and a one-line description. Cost estimate (Anthropic list prices, batch API at half price), assuming about 83,000 candidate comments at an average 655 characters plus a short prompt, roughly 40M input and 2.5M output tokens:

| Model | Input $/M | Output $/M | Estimated batch cost |
|---|---|---|---|
| Claude Haiku 5.5 | 0.10 | 0.50 | about $3 |
| Claude Sonnet 5.5 | 2.00 | 10.00 | about $55 |
| Claude Opus 5.5 | 4.00 | 20.00 | about $110 |

Classifying per URL with its aggregated comment excerpts, rather than per comment, would cut this several-fold. Haiku 5.5 is adequate for binary filtering; Sonnet 5.5 for descriptions and tags, as hackerbooks found.

Topic taxonomy: derive about 25 topics (programming languages, systems, maths, ML, security, writing, finance, science, careers, design…) from S2 thread titles and confirm with the LLM pass.

URL canonicalisation: strip scheme, `www`, fragments and trailing slashes; merge m.youtube and youtube, en.m.wikipedia and en.wikipedia; treat amzn.to and amazon as one host. Query strings need care: the analysis stripped them wholesale, which merges distinct items whose identity lives in the query (YouTube `v=`, ACM `citation.cfm?id=`, Play Store `id=`, Google Books). The canonicaliser needs a per-host allowlist of identifying parameters. The analysis also produced a small number of empty URLs from malformed hrefs; filter those.

## 8. Risks and considerations

- Licence and attribution. ODC-By requires attribution to the dataset. HN comment text belongs to its authors. hackerbooks quotes excerpts with a link back to the comment; I recommend the same pattern and a takedown contact. This is not legal advice; confirm with whoever handles IP questions for the project.
- External API dependency for points refresh. Only the candidate set (low thousands) needs it, so a rebuild stays well within the limits of either HN API. I could not retrieve the Algolia rate-limit statement because that page is client-rendered; treat its limit as unverified.
- Precision ceiling without an LLM pass. Expect visible noise in the long tail unless you add the classification step or a manual review of the top few hundred.
- Link rot grows over time. Build in a liveness check and Wayback fallback from the start.
- Overlap with hackerbooks for book links and with hackertube for videos. Keep or exclude by host; see open questions.
- Recency bias against new resources, see section 7.

## 9. Open questions for you

1. Scope: free online text and interactive resources only, or also books (Amazon, Goodreads), videos (YouTube), papers (arXiv) and GitHub repositories?
2. LLM pass: run one, and if so which model and budget? The cheapest option is about $3.
3. Static site (approach A) or something dynamic? Any hosting preference?
4. Refresh cadence: a few times a year by hand, or a scheduled monthly job?
5. Topic taxonomy: fixed list you define, or derived from the data?
6. Name and domain.

## 10. Reproduction

All scripts live in `analysis/`. They were run with `uv run --python 3.12 --with duckdb python -I <script>` on an Apple Silicon Mac with the 12 GB of Parquet on the local SSD. Runtimes are wall-clock measurements from this session (second runs, so the operating system file cache was warm).

| Script | Purpose | Measured runtime |
|---|---|---|
| `verify.py <dataset_dir>` | Row counts against `stats.csv`, Parquet footer column sizes, content stats | 1 s |
| `build_db.py <dataset_dir> <db>` | Materialise stories, link-bearing comments, comment parent map into DuckDB (5.7 GB) | 12 s |
| `resolve_roots.py <db>` | Resolve every comment to its root story, recompute comment counts | 16 s |
| `analyze.py <db> <urls_out>` | First pass (contains the href escaping bug; kept for traceability) | not timed |
| `analyze2.py <db>` | Corrected pass behind sections 3 and 4 | 3 s |
| `export.py <db> <out_dir>` | Overlap with story submissions, noise hosts, sample CSVs | 2 s |

The whole pipeline from raw Parquet to ranked candidates therefore runs in well under a minute, which makes frequent rebuilds cheap.

Raw outputs: `analysis/analysis_v1_output.txt`, `analysis/analysis_v2_output.txt`, `analysis/linkrot_sample.txt`.

## Sources

- Dataset card and README: https://huggingface.co/datasets/open-index/hacker-news
- hackerbooks.org About: https://hackerbooks.org/about
- hackertube.org: https://hackertube.org/
- HN Hall of Fame Show HN (via Zeli mirror): https://zeli.app/story/49008406
- hacker-recommended-books: https://hacker-recommended-books.vercel.app
- HN Algolia API: https://hn.algolia.com/api
- Anthropic model pricing as loaded in this session's `claude-api` reference (cached 2026-10-06)
