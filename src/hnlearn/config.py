"""Paths, thresholds, model names and noise lists. Edit here, not in the stages."""

from pathlib import Path

SITE_NAME = "HN Learning Index"
SITE_TAGLINE = "Free online learning resources that Hacker News keeps recommending"

DATASET_DIR = Path("dataset")
DATA_DIR = Path("data")
SITE_DIR = Path("site")

DB_PATH = DATA_DIR / "hn.duckdb"
CANDIDATES_PATH = DATA_DIR / "candidates.jsonl"
FETCH_PATH = DATA_DIR / "fetch.jsonl"
CLEF_PATH = DATA_DIR / "clef.jsonl"
BLURBS_PATH = DATA_DIR / "blurbs.jsonl"
RESOURCES_PATH = DATA_DIR / "resources.json"

# candidates
MIN_PEOPLE = 3
MAX_EXCERPTS = 3
EXCERPT_CHARS = 700

# fetch
FETCH_TIMEOUT_S = 15
FETCH_WORKERS = 8
FETCH_MAX_BYTES = 300_000
FETCH_USER_AGENT = "Mozilla/5.0 (compatible; hn-learning-index/0.1; +https://news.ycombinator.com)"
SNIPPET_CHARS = 1500
# a page that answers with one of these is still eligible; anything else is dead
ELIGIBLE_STATUSES = frozenset({200, 403, 429})

# models
OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_S = 600
CLEF_MODEL = "clef-flash"
BLURB_MODEL = "qwen3:30b-a3b"
KEEP_THRESHOLD = 0.7
BLURB_MAX_WORDS = 25

# site
HOME_LIMIT = 100

# hosts that are never a learning resource in their own right
NOISE_HOSTS = (
    "news.ycombinator.com", "hn.algolia.com",
    "en.wikipedia.org", "en.m.wikipedia.org",
    "youtube.com", "youtu.be", "m.youtube.com", "vimeo.com",
    "twitter.com", "x.com", "mobile.twitter.com", "facebook.com", "linkedin.com",
    "instagram.com", "tiktok.com", "mastodon.social", "bsky.app",
    "i.imgur.com", "imgur.com",
    "google.com", "duckduckgo.com", "bing.com", "scholar.google.com", "groups.google.com",
    "play.google.com", "books.google.com", "books.google.co.uk", "news.google.com",
    "amazon.com", "amzn.to", "amzn.com", "amazon.co.uk", "goodreads.com",
    "reddit.com", "old.reddit.com",
    "github.com", "gist.github.com", "gitlab.com", "bitbucket.org",
    "npmjs.com", "pypi.org", "crates.io",
    "archive.org", "web.archive.org", "webcache.googleusercontent.com",
    "citeseerx.ist.psu.edu", "papers.ssrn.com", "bugzilla.mozilla.org",
    "wolframalpha.com", "apps.apple.com", "itunes.apple.com", "open.spotify.com",
    "podcasts.apple.com", "soundcloud.com",
)
# suffix matches, for language editions and country domains
NOISE_HOST_SUFFIXES = (".wikipedia.org", ".wikimedia.org", ".amazon.com", ".amazon.de",
                       ".amazon.co.uk", ".youtube.com")
