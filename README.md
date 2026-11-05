# Learning Index

Small data-exploration projects that mine online communities for material worth learning
from, published as one static site with a shared look.

| Section | Source | Code | Published at |
|---|---|---|---|
| HN Learning Index | Hacker News comments (open-index/hacker-news, ODC-By 1.0) | [`hn/`](hn/README.md) | `site/hn/` |
| Reddit Investing Reading List | Top posts of 10 investing subreddits | [`reddit/`](reddit/README.md) | `site/reddit/` |
| Hub page | Counts from both sections | [`hub/`](hub/build.py) | `site/index.html` |

## Build and preview

```sh
make site      # rebuild site/ from committed results (HN also needs hn/data/resources.json)
make serve     # http://localhost:8000/ (HN search needs http, not file://)
make test      # HN suite plus Reddit renderer and hub tests
```

`make site-reddit site-hub` rebuilds only the Reddit section and hub, from the committed
`reddit/results*/` CSVs, so it works on a fresh clone.

## Publishing

`site/` is committed. On every push to `main` that touches `site/`, the workflow in
`.github/workflows/pages.yml` uploads it to GitHub Pages as-is; there is no build step on
GitHub. Enable it once in the repository's Settings, Pages, Source: GitHub Actions.

When the shared stylesheet or HN script changes, every HN page's `?v=<hash>` cache-busting
query changes too, so expect a diff across about 1,200 files.

## Shared theme

The single source of the look is `hn/src/hnlearn/static/style.css`. The HN site copies it
in; `reddit/classify/render.py` and `hub/build.py` copy the same file into their output, and
the Reddit page adds only `reddit/classify/reddit.css` for its few extra rules.

## Data notes

- HN: large inputs (`hn/dataset/`, `hn/data/`) are not committed; see `hn/README.md`.
- Reddit: raw scrapes (`reddit/reddit_top*/`) and classifier inputs hold full post bodies and
  usernames, so they are git-ignored. Only labels, the curated result CSVs (titles, links,
  LLM takeaways) and the built page are committed. Reddit's RSS feeds, used by the scraper,
  end on 13 November 2026.
- Nothing here is financial advice.
