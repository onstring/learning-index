import sys, duckdb

dbpath = sys.argv[1]
con = duckdb.connect(dbpath)
con.execute("SELECT setseed(0.42)")

TUT = (r"(?i)(^|[^a-z])(tutorial|introduction to|intro to|a guide to|guide to|beginner'?s?|from scratch|"
       r"explained|how [a-z ]{1,30} works?|learn(ing)? [a-z+#]{1,20}|teach yourself|crash course|"
       r"lecture notes|lectures?|textbook|cheat ?sheet|primer|handbook|in plain english|step[- ]by[- ]step|"
       r"walkthrough|roadmap|curriculum|free (online )?(course|book)|101|the (little|missing) book|"
       r"for beginners|a (gentle|visual|practical|complete) (introduction|guide)|understanding [a-z]|"
       r"what every [a-z ]+ should know|the art of|illustrated|interactive|explorable)([^a-z]|$)")
ASK = (r"(?i)(learn|resource|recommend|book|course|tutorial|best way|where (to|do i|should i) start|"
       r"how (do|did|would) you learn|get(ting)? started|study|reading list|curriculum|roadmap|teach|"
       r"good (intro|introduction)|beginner)")
NEWS = ["nytimes.com","bloomberg.com","techcrunch.com","theverge.com","reuters.com","wsj.com","washingtonpost.com",
        "theguardian.com","bbc.com","bbc.co.uk","cnn.com","arstechnica.com","wired.com","cnbc.com","ft.com",
        "businessinsider.com","forbes.com","theatlantic.com","economist.com","apnews.com","npr.org","engadget.com",
        "zdnet.com","venturebeat.com","theinformation.com","axios.com","politico.com","vice.com","gizmodo.com",
        "mashable.com","theregister.com","9to5mac.com","macrumors.com","techmeme.com","thenextweb.com","cnet.com",
        "bleepingcomputer.com","404media.co","semafor.com","restofworld.org","twitter.com","x.com"]
news_sql = "(" + ",".join(f"'{d}'" for d in NEWS) + ")"
TUT = TUT.replace("'", "''")
ASK = ASK.replace("'", "''")

NORM = """lower(regexp_replace(regexp_replace(regexp_replace(regexp_replace({u},'^https?://',''),'^www\\.',''),'[#?].*$',''),'/+$',''))"""
HOST = """regexp_extract({n},'^([^/]+)',1)"""

def q(title, sql, w=None):
    print(f"\n### {title}")
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(x)[: (w or 110)].replace("\n", " ") for x in r))

# ---- A. score / descendants reliability per year
q("A. per-year story score reliability",
  """SELECT year(time) y, count(*) stories, max(score) max_score,
            count(*) FILTER (WHERE score>=100) ge100, count(*) FILTER (WHERE score>=500) ge500,
            round(avg(descendants),1) avg_desc, max(descendants) max_desc,
            count(*) FILTER (WHERE url<>'') with_url, count(*) FILTER (WHERE dead=1) dead
     FROM stories GROUP BY 1 ORDER BY 1""")

# ---- B. bucket 1: tutorial-like story titles
con.execute(f"""CREATE OR REPLACE TEMP VIEW b1 AS
   SELECT *, {NORM.format(u='url')} AS nurl, {HOST.format(n=NORM.format(u='url'))} AS host
   FROM stories WHERE dead=0 AND deleted=0 AND regexp_matches(title, '{TUT}')""")
q("B1. tutorial-title stories by score threshold",
  """SELECT count(*) all_matches, count(*) FILTER (WHERE score>=20) ge20,
            count(*) FILTER (WHERE score>=50) ge50, count(*) FILTER (WHERE score>=100) ge100,
            count(*) FILTER (WHERE score>=100 AND url<>'') ge100_with_url FROM b1""")
q("B2. tutorial-title stories score>=50 per year",
  "SELECT year(time) y, count(*) n FROM b1 WHERE score>=50 GROUP BY 1 ORDER BY 1")
q("B3. news-domain exclusion effect on b1 score>=50",
  f"""SELECT count(*) before_excl, count(*) FILTER (WHERE host NOT IN {news_sql}) after_excl,
             count(*) FILTER (WHERE regexp_matches(title,'(19|20)[0-9][0-9]|v[0-9]+\\.[0-9]|[0-9]+\\.[0-9]+\\.[0-9]')) dated_or_versioned
      FROM b1 WHERE score>=50""")
q("B4. top hosts in b1 score>=50",
  "SELECT host, count(*) n FROM b1 WHERE score>=50 AND host<>'' GROUP BY 1 ORDER BY 2 DESC LIMIT 30")
q("B5. SAMPLE 40 random b1 stories score>=100 (precision eyeball)",
  "SELECT id, year(time) y, score, descendants d, title, host FROM b1 WHERE score>=100 ORDER BY random() LIMIT 40", 90)

# ---- C. bucket 2: Ask HN resource threads
con.execute(f"""CREATE OR REPLACE TEMP VIEW b2 AS
   SELECT * FROM stories WHERE dead=0 AND deleted=0 AND title ILIKE 'Ask HN:%' AND regexp_matches(title,'{ASK}')""")
q("C1. Ask HN resource threads by descendants threshold",
  """SELECT count(*) all_matches, count(*) FILTER (WHERE descendants>=10) ge10,
            count(*) FILTER (WHERE descendants>=20) ge20, count(*) FILTER (WHERE descendants>=50) ge50,
            count(*) FILTER (WHERE descendants>=100) ge100 FROM b2""")
q("C2. per year (descendants>=20)",
  "SELECT year(time) y, count(*) n FROM b2 WHERE descendants>=20 GROUP BY 1 ORDER BY 1")
q("C3. SAMPLE 40 random Ask HN resource threads descendants>=20",
  "SELECT id, year(time) y, score, descendants d, title FROM b2 WHERE descendants>=20 ORDER BY random() LIMIT 40", 100)
q("C4. top 15 Ask HN resource threads by descendants",
  "SELECT id, year(time) y, score, descendants d, title FROM b2 ORDER BY descendants DESC LIMIT 15", 100)

# ---- D. bucket 3: URLs in top-level replies to b2 threads (descendants>=20)
con.execute(f"""CREATE OR REPLACE TEMP TABLE b2_links AS
   SELECT c.id cid, c.author, c.parent AS story_id, year(c.time) y,
          {NORM.format(u='h')} AS nurl, {HOST.format(n=NORM.format(u='h'))} AS host
   FROM link_comments c JOIN b2 s ON c.parent=s.id AND s.descendants>=20,
        unnest(regexp_extract_all(c.text, 'href="([^"]+)"', 1)) AS t(h)
   WHERE c.dead=0 AND c.deleted=0""")
q("D1. link stats in top-level replies of Ask HN resource threads",
  """SELECT count(*) hrefs, count(DISTINCT nurl) distinct_urls, count(DISTINCT host) distinct_hosts,
            count(DISTINCT cid) comments, count(DISTINCT story_id) threads FROM b2_links""")
q("D2. top 40 URLs by distinct commenters (threads, year span)",
  """SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT story_id) threads, min(y) y0, max(y) y1
     FROM b2_links WHERE host NOT IN ('news.ycombinator.com') GROUP BY 1 ORDER BY 2 DESC LIMIT 40""", 80)
q("D3. top 30 hosts by distinct commenters",
  "SELECT host, count(DISTINCT author) ppl, count(DISTINCT nurl) urls FROM b2_links GROUP BY 1 ORDER BY 2 DESC LIMIT 30")
q("D4. URL distribution: how many URLs have >=N distinct commenters",
  """SELECT count(*) FILTER (WHERE ppl>=2) ge2, count(*) FILTER (WHERE ppl>=3) ge3,
            count(*) FILTER (WHERE ppl>=5) ge5, count(*) FILTER (WHERE ppl>=10) ge10
     FROM (SELECT nurl, count(DISTINCT author) ppl FROM b2_links GROUP BY 1)""")

# ---- E. corpus-wide: URLs mentioned in ANY comment, by distinct commenters and year span
con.execute(f"""CREATE OR REPLACE TEMP TABLE all_links AS
   SELECT c.author, year(c.time) y, c.id cid,
          {NORM.format(u='h')} AS nurl, {HOST.format(n=NORM.format(u='h'))} AS host
   FROM link_comments c, unnest(regexp_extract_all(c.text, 'href="([^"]+)"', 1)) AS t(h)
   WHERE c.dead=0 AND c.deleted=0""")
q("E1. corpus-wide link stats",
  "SELECT count(*) hrefs, count(DISTINCT nurl) urls, count(DISTINCT host) hosts FROM all_links")
q("E2. top 40 URLs corpus-wide by distinct commenters, excluding HN/wikipedia/youtube/twitter/github root",
  """SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs, min(y) y0, max(y) y1
     FROM all_links WHERE host NOT IN ('news.ycombinator.com','en.wikipedia.org','youtube.com','youtu.be','twitter.com','x.com','github.com','i.imgur.com','imgur.com','archive.org','web.archive.org','google.com')
     GROUP BY 1 HAVING count(DISTINCT author)>=5 ORDER BY 2 DESC LIMIT 40""", 80)
q("E3. evergreen: URLs with >=5 distinct commenters AND mentioned in >=3 distinct years (count by band)",
  """SELECT count(*) FILTER (WHERE yrs>=3) yrs3, count(*) FILTER (WHERE yrs>=5) yrs5, count(*) FILTER (WHERE yrs>=8) yrs8
     FROM (SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs FROM all_links
           WHERE host NOT IN ('news.ycombinator.com') GROUP BY 1 HAVING ppl>=5)""")
q("E4. SAMPLE 40 evergreen URLs (>=5 people, >=4 years), random",
  """SELECT nurl, ppl, yrs, y0, y1 FROM (SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs, min(y) y0, max(y) y1
     FROM all_links WHERE host NOT IN ('news.ycombinator.com','en.wikipedia.org','youtube.com','youtu.be','twitter.com','x.com','i.imgur.com','imgur.com')
     GROUP BY 1 HAVING ppl>=5 AND yrs>=4) ORDER BY random() LIMIT 40""", 80)
q("E5. story URLs resubmitted in >=2 distinct years with a score>=20 submission (count, top 25)",
  f"""WITH s AS (SELECT {NORM.format(u='url')} nurl, year(time) y, score, title FROM stories WHERE url<>'' AND dead=0)
      SELECT nurl, count(DISTINCT y) yrs, max(score) best, min(y) y0, max(y) y1, any_value(title) title
      FROM s GROUP BY 1 HAVING count(DISTINCT y)>=2 AND max(score)>=20 ORDER BY 2 DESC, 3 DESC LIMIT 25""", 70)
q("E6. count of resubmitted-story URLs by year-span band",
  f"""WITH s AS (SELECT {NORM.format(u='url')} nurl, year(time) y, score FROM stories WHERE url<>'' AND dead=0),
      g AS (SELECT nurl, count(DISTINCT y) yrs, max(score) best FROM s GROUP BY 1 HAVING max(score)>=20)
      SELECT count(*) FILTER (WHERE yrs>=2) yrs2, count(*) FILTER (WHERE yrs>=3) yrs3, count(*) FILTER (WHERE yrs>=5) yrs5 FROM g""")

# ---- F. link rot sample list (written for a separate HEAD pass)
rows = con.execute("""SELECT nurl FROM (SELECT nurl, count(DISTINCT author) ppl FROM b2_links
   WHERE host NOT IN ('news.ycombinator.com') GROUP BY 1 HAVING ppl>=3) ORDER BY random() LIMIT 40""").fetchall()
with open(sys.argv[2], "w") as f:
    for (u,) in rows:
        f.write(u + "\n")
print(f"\nwrote {len(rows)} urls for link-rot check to {sys.argv[2]}")
