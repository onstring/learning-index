# Reddit Investing Reading List

Finds top Reddit investing posts worth learning from: posts that share investing knowledge,
skills or analysis, not news, current affairs, jokes or brags. Run commands from this
folder unless noted. Standard library only (Python 3.9+).

## Pipeline

1. **Scrape** top posts via Reddit RSS (ends 13 November 2026):
   ```sh
   python3 reddit_top.py                                          # top 200, all time
   python3 reddit_top.py --time year --limit 30 --out reddit_top_year
   ```
   Writes one CSV per subreddit with the post text (`body`) and an `is_image` flag.
   These files hold post bodies and usernames and are git-ignored.
2. **Bucket and chunk**: image posts with short captions are dropped by rule; the rest are
   split into JSONL chunks for the classifier.
   ```sh
   python3 classify/prep.py --data reddit_top --out classify/work --chunk 180
   python3 classify/prep.py --data reddit_top_year --subs LETFs --out classify/work_letfs_year
   ```
3. **Classify** with LLM subagents (Claude Code), one per chunk, following
   `classify/prompt.md` and the stricter `classify/prompt_pass2.md`. Each writes
   `labels_*.jsonl` (strict pass: `labels_pass2*.jsonl`) beside its chunk.
   - All time: lenient Haiku pass, then a strict Sonnet pass over the shortlist.
   - Past year and r/LETFs: strict Sonnet pass directly.
   - `classify/calib.py` compares labels with 30 hand labels (`calib_mine.jsonl`).
4. **Merge** labels into ranked lists (strict-pass labels override the first pass):
   ```sh
   python3 classify/merge.py                                   # -> results/
   python3 classify/merge.py --data reddit_top_year --work classify/work_year --out results_year
   ```
   `reading_list.*` = score 4 or 5, `worth_a_look.csv` = score 3 from the strict pass,
   `all_labelled.csv` = every post with its label.
5. **Render** the page into the shared site: from the repo root, `make site-reddit site-hub`.

## Tests

From the repo root: `uv run --no-project --with pytest pytest reddit/tests hub/tests`.

## Known limits

- Only the post is assessed, not its comments.
- Scores come from separate LLM runs; the same post can differ by 1 between periods.
- r/LETFs was scored in its own batch, so it has proportionally more 5/5 posts.
