# Build the published static site in site/ (committed; GitHub Pages serves it as-is).
#   site/index.html   hub page             <- hub/build.py
#   site/hn/          HN learning index    <- hn/ pipeline (needs hn/data/resources.json)
#   site/reddit/      Reddit reading list  <- reddit/results*/ CSVs (committed)
# Pipelines themselves: see hn/README.md and reddit/README.md.

PY3 := python3 -I

.PHONY: site site-hn site-reddit site-hub test serve

site: site-hn site-reddit site-hub

site-hn:
	$(MAKE) -C hn site OUT=../site/hn

site-reddit:
	$(PY3) reddit/classify/render.py --out site/reddit \
	  --set "All time" reddit/results/reading_list.csv reddit/results/worth_a_look.csv \
	  --set "Past year" reddit/results_year/reading_list.csv reddit/results_year/worth_a_look.csv

site-hub: site-reddit
	$(PY3) hub/build.py --site site

test:
	$(MAKE) -C hn test
	uv run --no-project -q --with pytest pytest -q reddit/tests hub/tests

serve:
	python3 -m http.server -d site 8000
