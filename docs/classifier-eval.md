# Classifier evaluation: clef-flash vs qwen3:30b-a3b

Date: 2026-11-03. Prepared with Claude Code. No app code written.

Question from the user: can the local `clef-flash` model replace the planned Haiku pass
for classifying candidate URLs, and is its accuracy good enough?

## 1. Verdict

Yes, with one gap. On a 100-URL labelled sample, clef-flash tied the generative
local alternative (`qwen3:30b-a3b`, thinking off) on the keep/drop decision and
clearly beat it on topic labelling (0.79 versus 0.64), at the same speed (about
2.8 s per URL on this Mac). On keep/drop the two trade off differently: clef keeps
more of the good resources (recall 0.85 versus 0.64), qwen3 lets fewer bad ones
through (precision 0.92 versus 0.79 on confident items). Differences of that size
are inside the noise band for n=100 (see section 7).

The gap: clef-flash is a decision model. It scores typed questions and cannot write
text, so it cannot produce the one-line description each resource needs. Only 13 of
the 39 gold-keep URLs had a meta description at all, so descriptions need a
generative pass. Recommended split:

| Step | Model | Over | Why |
|---|---|---|---|
| keep/drop, topic, type, difficulty | clef-flash | all candidates | deterministic probabilities per criterion, tunable threshold, no JSON parsing, auditable |
| one-sentence blurb | qwen3:30b-a3b, thinking off | kept URLs only (roughly 40 percent) | reads well in the sample, 2.5 s per URL |

The simpler alternative, qwen3 alone in one call with the blurb included, was
rejected because it drops about a third of the good resources (recall 0.64) and
mislabels about a third of topics (0.64). Thinking mode fixes the topics but not the
recall, at 20 times the latency.

Which clef framing to carry: both the six-boolean rule and the single composite
question are recorded per URL. They reach the same accuracy with opposite
trade-offs (rule at 0.5: precision 0.79, recall 0.85; composite at 0.7: precision
0.74, recall 0.95). The thresholds were not chosen on a held-out set, so the build
should start with the composite at 0.7, keep the six booleans for audit and
explanation, and re-set the threshold on a fresh labelled batch of 100 URLs.

Both models cannot be loaded together on this 32 GB machine (12 GB + 19 GB), so the
pipeline runs them as two sequential phases. Estimated wall time for the current
candidate set (about 2,300 URLs with 3 or more recommenders): under 3 hours. No API
key, no cost.

## 2. What clef-flash is (verified)

| Fact | Value | Source |
|---|---|---|
| Maker | Cloudflare | Ollama library page |
| Base | fine-tuned from Qwen3.5-9B, 9.5B parameters | Ollama library page, `ollama show` |
| Type | decision model: takes a "state" plus typed questions, scores every option in one non-autoregressive pass | Ollama library page |
| Question types | `noul` (probability of true), `choice` (2 to 255 options with probabilities), `score` (2 to 10 ordered levels, weighted average) | Ollama API reference |
| Endpoint | `POST /v1/systemone`; not in the Ollama CLI or Python/JS libraries yet | Ollama docs |
| Capabilities | `decision`, `vision`; no `completion`, so it cannot generate text | `ollama show clef-flash` |
| Local runner here | MLX, mxfp8 quantisation, Ollama 0.40.2, model requires 0.40.0 | `ollama show` |
| Licence | Apache 2.0 | `ollama show` |
| Vendor benchmarks | mixed versus the 27B `clef` (for example CLINC150+OOS 66.8 vs 97.4, ANLI 59.1 vs 69.8); vendor-reported, not independently verified | Ollama library page |
| Known issue | GitHub issue 18769 reports failures on CUDA and CPU runners; did not reproduce here on MLX (100 of 100 calls succeeded) | GitHub |
| Determinism | identical probabilities on repeated identical requests (3 URLs, 2 calls each); qwen3 was run at temperature 0 but offers no such guarantee | measured here |

Sources: [Ollama library: clef-flash](https://ollama.com/library/clef-flash),
[Ollama docs: decision models](https://docs.ollama.com/capabilities/decision),
[Ollama API: systemone](https://docs.ollama.com/api/systemone.md),
[Ollama announcement on X](https://x.com/ollama/status/2106186667543666841),
[GitHub issue 18769](https://github.com/ollama/ollama/issues/18769).

## 3. Method

**Sample.** 100 URLs drawn deterministically from the recommendation table built in
the feasibility study (comments matching a recommendation phrase, hrefs unescaped and
normalised, noise hosts excluded). Three strata:

| Stratum | Rule | n | Purpose |
|---|---|---|---|
| A_strong | 5 or more distinct recommenders | 35 | likely positives |
| B_weak | exactly 3 recommenders | 35 | the marginal cases the pipeline will mostly see |
| C_newsy | 3 or more recommenders, host in a list of 30 news and product domains | 30 | likely negatives |

The sample covers only URLs with 3 or more recommenders. It says nothing about
URLs with 2 recommenders.

**Context given to both models (identical text).** URL, host, fetched page title and
meta description where the fetch succeeded (67 of 100 returned HTTP 200, 62 had a
title, 39 a description), HTTP status otherwise, best HN story title, number of
recommenders and year span, and up to three recommending comment excerpts (700
characters each, HTML stripped).

**Rubric.** One file (`analysis/eval/eval_rubric.py`, rendered as `rubric.md`) drives
the gold labels, the clef question schema and the qwen prompt, so wording is not a
confound. Keep is decomposed into six booleans:

    keep = free_to_access AND is_learning_material AND is_evergreen
           AND NOT is_video AND NOT is_code_repo AND NOT is_paid_book

plus a single composite question for clef only, 15 topics, 8 resource types and a
3-level difficulty.

**Gold labels.** Written by Claude Code from the same context plus general knowledge
of the sites, not by the user. 39 keep, 61 drop. 27 items are flagged borderline
(for example classic essays, journalism with teaching value, a freemium practice
site, an unauthorised book PDF). Metrics are reported on all 100 and on the 73
confident items.

**Models.**

| Run | Call | Settings |
|---|---|---|
| clef-flash | `/v1/systemone`, 10 questions per URL | defaults; no generation controls exist |
| qwen3:30b-a3b | `/api/chat`, JSON schema output | `think: false`, temperature 0, `num_ctx` 8192 |
| qwen3:30b-a3b, thinking | same | `think: true` |

Latency excludes model load (one warm-up call).

## 4. Results: keep/drop

Precision = share of model keeps that are gold keeps. Recall = share of gold keeps
the model kept.

| Run | n | Accuracy | Precision | Recall | Confident-only acc / P / R |
|---|---|---|---|---|---|
| no model: keep everything the heuristics pass | 100 | 0.39 | 0.39 | 1.00 | 0.41 / 0.41 / 1.00 |
| clef rule, threshold 0.5 | 100 | 0.85 | 0.79 | 0.85 | 0.85 / 0.79 / 0.87 |
| clef composite, threshold 0.7 | 100 | 0.85 | 0.74 | 0.95 | 0.89 / 0.81 / 0.97 |
| clef rule, threshold 0.7 | 100 | 0.81 | 0.88 | 0.59 | 0.81 / 0.86 / 0.63 |
| clef rule, threshold 0.3 | 100 | 0.75 | 0.62 | 0.95 | 0.84 / 0.74 / 0.93 |
| qwen3 no-think | 100 | 0.79 | 0.78 | 0.64 | 0.88 / 0.92 / 0.77 |
| clef rule AND qwen3 | 100 | 0.81 | 0.88 | 0.59 | 0.86 / 0.92 / 0.73 |
| clef rule OR qwen3 | 100 | 0.83 | 0.73 | 0.90 | 0.86 / 0.79 / 0.90 |
| qwen3 thinking | 100 | 0.78 | 0.71 | 0.74 | 0.85 / 0.85 / 0.77 |

The no-model row is the baseline the user would get from the heuristic pipeline
alone. Gold keep rate by stratum: A_strong 20 of 35, B_weak 16 of 35, C_newsy 3 of
30. The C stratum oversamples negatives, so the realistic baseline precision for
the candidate population is the A plus B figure, 36 of 70 (0.51). A classifier lifts
that to 0.79 (clef rule) or 0.92 (qwen3, confident items) while keeping most of the
good resources.

Per stratum (accuracy, clef rule at 0.5): A_strong 0.74, B_weak 0.86, C_newsy 0.97.
Qwen3 no-think: 0.74, 0.74, 0.90. Qwen3 thinking: 0.69, 0.77, 0.90. Clef and qwen3
no-think agreed on 78 of 100 URLs.

Latency per URL, warm:

| Run | Mean | Median | Max |
|---|---|---|---|
| clef-flash (2,200 input tokens, 10 questions) | 2.81 s | 2.86 s | 3.21 s |
| qwen3 no-think | 2.54 s | 2.57 s | 3.09 s |
| qwen3 thinking (about 2,400 output tokens per URL) | 53.5 s | 52.6 s | 108 s |

Thinking did not improve qwen3's keep decision (0.78 versus 0.79) and cost 20 times
the latency. It did lift qwen3's topic accuracy to clef's level (section 5).

### 4b. Re-score with the production pipeline

The production fetch stage adds the first 1,500 characters of visible page text to
the context, which the evaluation above did not have. The 100 URLs were re-run through
the production `fetch` and `classify` stages; 13 URLs were skipped as dead by the
production rule and the comparison below covers the 87 in common.

| Run (n=87) | Accuracy | Precision | Recall | Confident-only acc / P / R | Topic acc | s/URL |
|---|---|---|---|---|---|---|
| eval context, composite 0.7 | 0.87 | 0.79 | 0.94 | 0.89 / 0.81 / 0.96 | 0.77 | 2.81 |
| production context, composite 0.7 | 0.89 | 0.80 | 0.94 | 0.92 / 0.87 / 0.96 | 0.77 | 3.13 |

The snippet helps slightly and costs 0.3 s per URL. Five URLs flipped at 0.7, three
of them in the right direction. The production run keeps the snippet.

### 4c. Full production run

Run on 2026-11-03 over every candidate with 3 or more recommenders.

| Measure | Value |
|---|---|
| candidates | 2,522 |
| classified (live pages only) | 2,179 in 1 h 55 min, 0 failures, 3.2 s and 2,460 input tokens per URL |
| kept at composite 0.7 | 1,193 (55 percent); 1,010 would pass at 0.8 |
| kept rows with `is_video` above 0.5 | 38, mostly MOOCs with lecture video; the 6 above 0.8 were screencast or lecture-video sites and are excluded |
| kept rows with `is_paid_book` above 0.5 | 17, about 10 of them real paid-book pages; no exclusion applied because a 0.6 cut would also drop free books such as the Google SRE book |
| blurbs (qwen3, thinking off) | 1,193 in 37 min, 0 failures, 1.6 s per URL |
| final resources on the site | 1,186 |

Spot check: 30 resources drawn at random from the built site (`analysis/spot_check.py`,
seed 7) were judged against the rubric by Claude Code. 23 were clear keeps, 4 were
borderline (an experience report, an essay series, an audio talk series, a business
blog), 3 were clear misses (the MongoDB product site, the paid Garbage Collection
Handbook homepage, the NHS website). That is a precision of about 0.77 to 0.90
depending on how the borderline items are counted, in line with the evaluation.

## 5. Results: topic

Accuracy on the 39 gold-keep URLs, counting a hit when the model's topic is in the
gold set of acceptable topics (some URLs accept two):

| Run | Topic accuracy |
|---|---|
| clef-flash | 0.79 |
| qwen3 no-think | 0.64 |
| qwen3 thinking | 0.79 |

## 6. Error analysis

Clef rule at 0.5, 15 errors in 100:

- **Missed keeps (6).** Coursera "Learning How to Learn" and Startup School scored
  `is_video` 0.77 and 0.84 (both sites do contain video). Apple documentation archive
  and Advent of Code scored `is_evergreen` below 0.5. LeetCode and the Dan Abramov
  Redux post scored `is_learning_material` below 0.5.
- **False keeps (9).** The TAPL book page (`is_paid_book` 0.03) and Land of Lisp
  (0.38): with no meta description the model cannot tell a book landing page from a
  free book. The Theoretical Minimum video lectures (`is_video` 0.10). Bullet Journal,
  Google Books home, xkcd, IPFS, a Joel Spolsky anecdote and the Wirth essay PDF all
  passed `is_learning_material` narrowly (0.54 to 0.73).

Qwen3 no-think errs the other way: it dropped 14 gold keeps, including the
All About Circuits textbook, Divio documentation guide, CS231n syllabus, Intel
manuals and the Agile Manifesto, and kept the TAPL page, Theoretical Minimum,
nim-lang.org and oilshell.org.

Both models share the hardest failure: a paid-book landing page with a bare title.
Fetching page body text (not only the meta tags) or adding a "known publisher" host
list would fix most of these.

## 7. Caveats

- n=100. A difference under about 10 points between runs is noise. The two models
  are tied on this evidence; the choice rests on the pipeline properties in section 1.
- The clef thresholds in the table were not chosen on a separate set. Treat 0.5 for
  the rule and 0.7 for the composite as the two framings tried, not as tuned values.
  Rule at 0.5 and composite at 0.7 reach the same accuracy by different trade-offs
  (precision versus recall).
- Gold labels are one labeller's judgement. The 27 borderline items are where a
  second labeller would most likely disagree.
- Vendor benchmark numbers for clef-flash are not independently verified and do not
  cover this task.
- The larger `clef` (27B) is reported by the vendor as more accurate. The Ollama
  library lists its download at 18 to 20 GB, the same as `qwen3:30b-a3b`, so it
  should fit this 32 GB machine. It was not tried; it is the first thing to test if
  precision needs lifting.
- The feasibility report estimated heuristic precision at 60 to 75 percent for the
  broader original scope (books and videos included). Under the narrowed scope
  (free online resources only) the no-model precision measured here on the A plus B
  strata is 0.51, so the earlier figure is optimistic for the new scope.
- Page fetches ran once from this network on 2026-11-03. Sites that blocked the
  fetch (403, 429) gave the models less context than a pipeline with a browser-like
  fetcher would have.

## 8. Blurb source

Three options for the one-line description each resource needs:

| Source | Coverage on gold keeps | Quality |
|---|---|---|
| meta description | 13 of 39 | variable, often marketing |
| best HN comment excerpt | 39 of 39 | authentic but rambling; needs attribution either way |
| qwen3 blurb | 39 of 39 | one neutral sentence, read well in a 10-item spot check |

Sample qwen3 blurbs: "Learn formal methods and proof techniques using Coq, a proof
assistant for verifying software correctness." (Software Foundations); "An interactive
tutorial teaching Go programming basics through hands-on exercises." (Tour of Go).

## 9. Reproduction

All files in `analysis/eval/`. Scripts read the dataset only through the DuckDB file
built by `analysis/build_db.py`; run with `python -I`.

| Step | Command | Time |
|---|---|---|
| sample | `uv run --python 3.12 --with duckdb python -I eval_sample.py hn.duckdb eval_items.jsonl` | 6 s |
| fetch titles | `python3 -I eval_fetch.py eval_items.jsonl eval_items_fetched.jsonl` | 21 s |
| clef run | `python3 -I eval_run.py eval_items_fetched.jsonl clef clef-flash eval_clef.jsonl` | 4 min 49 s |
| qwen run | `python3 -I eval_run.py eval_items_fetched.jsonl qwen qwen3:30b-a3b eval_qwen.jsonl` | not timed end to end; 2.5 s per URL plus 7.6 s warm-up |
| qwen thinking run | `python3 -I eval_run.py eval_items_fetched.jsonl qwen_think qwen3:30b-a3b eval_qwen_think.jsonl` | about 90 min |
| score | `python3 -I eval_score.py eval_items_fetched.jsonl eval_gold.csv eval_clef.jsonl eval_qwen.jsonl` | 1 s |

Raw model outputs (`eval_clef.jsonl`, `eval_qwen.jsonl`) and the gold file
(`eval_gold.csv`) are included so the disagreement list can be spot-checked.

Re-running the sample step returns the same 100 URLs in the same order. The
excerpt order and the chosen story title can differ on ties (33 of 100 items on a
second run), so model outputs can shift slightly on a rerun. The committed
`eval_items_fetched.jsonl` is the exact input the reported numbers came from.
