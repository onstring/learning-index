import sys, duckdb

con = duckdb.connect(sys.argv[1])
con.execute("SELECT setseed(0.42)")
con.execute("SET preserve_insertion_order=false")

UNESC = ("replace(replace(replace(replace(replace(replace(replace(replace(replace({h},"
         "'&#x2F;','/'),'&#38;','&'),'&amp;','&'),'&#x27;',''''),'&quot;','\"'),'&#62;','>'),'&#60;','<'),'&gt;','>'),'&lt;','<')")
NORM = ("lower(regexp_replace(regexp_replace(regexp_replace(regexp_replace({u},'^https?://',''),"
        "'^www\\.',''),'[#?].*$',''),'/+$',''))")
HOST = "regexp_extract({n},'^([^/]+)',1)"
SKIP = "('news.ycombinator.com','en.wikipedia.org','youtube.com','youtu.be','twitter.com','x.com','i.imgur.com','imgur.com','google.com','amazon.com','amzn.to','amzn.com','amazon.co.uk','reddit.com','github.com','archive.org','web.archive.org','webcache.googleusercontent.com')"

TUT = (r"(?i)(^|[^a-z])(tutorial|introduction to|intro to|a guide to|guide to|beginners?|from scratch|"
       r"explained|how [a-z ]{1,30} works?|learn(ing)? [a-z+#]{1,20}|teach yourself|crash course|"
       r"lecture notes|lectures?|textbook|cheat ?sheet|primer|handbook|in plain english|step[- ]by[- ]step|"
       r"walkthrough|roadmap|curriculum|free (online )?(course|book)|101|the (little|missing) book|"
       r"for beginners|a (gentle|visual|practical|complete) (introduction|guide)|understanding [a-z]|"
       r"what every [a-z ]+ should know|the art of|illustrated|interactive|explorable)([^a-z]|$)")
TUT_NEG = (r"(?i)(^|[^a-z])(ceo|lawsuit|stock|shares|ipo|acqui|funding|raises|billion|million|trump|biden|"
           r"congress|senate|lays? off|layoffs|outage|breach|hack(ed|s)?|arrest|court|ban(s|ned)?|dies|dead|"
           r"obituary|election|war|strike|covid|vaccine|iphone|android|tesla|musk|zuckerberg|apple|google|microsoft|amazon|meta|openai)([^a-z]|$)")
ASK = (r"(?i)^ask hn:.*(resources?|books?|courses?|tutorials?|guides?|how (do|did|can|should|would) (i|you|one) (learn|get started|start|study|teach)|"
       r"where (to|do i|should i|can i) (start|begin|learn)|best way to learn|recommend|reading list|curriculum|roadmap|"
       r"self[- ]?(study|taught|learn)|get(ting)? started (with|in)|(intro|introduction) to|learn(ing)? [a-z+#.]+\?)")
ASK_NEG = r"(?i)(bookmark|facebook|notebook|macbook|chromebook|bookkeeping|book(ing|ed) |stopped reading|audiobook)"
REC = (r"(?i)(highly recommend|strongly recommend|i recommend|i'd recommend|i would recommend|can't recommend .{0,20}enough|"
       r"great (resource|intro|introduction|tutorial|book|course|explanation|primer|starting point)|"
       r"excellent (resource|intro|introduction|tutorial|book|course|explanation|primer)|best (intro|introduction|tutorial|resource|explanation|book|course|primer)|"
       r"worth (reading|a read|your time|checking out)|must[- ]read|start with|good (place to start|starting point|intro|introduction|resource|tutorial)|"
       r"learn(ed|t)? (a lot|so much|a ton) from|taught me|changed (how|the way) i|the (canonical|definitive|classic)|"
       r"if you want to (learn|understand))")

def esc(s): return s.replace("'", "''")

def q(title, sql, w=100):
    print(f"\n### {title}")
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(x)[:w].replace("\n", " ") for x in r))

# stories with recomputed comment count
con.execute("""CREATE OR REPLACE TEMP VIEW st AS
   SELECT s.*, coalesce(d.n_comments,0) AS ncom FROM stories s LEFT JOIN story_desc d ON s.id=d.id""")
q("A. recomputed comment counts vs dataset descendants, per year",
  """SELECT year(time) y, count(*) n, round(avg(descendants),1) ds_desc, round(avg(ncom),1) recomputed,
            count(*) FILTER (WHERE ncom>=20) ge20com FROM st GROUP BY 1 ORDER BY 1""")

# ---- B. tutorial-title stories, with negative filter
con.execute(f"""CREATE OR REPLACE TEMP VIEW b1 AS
   SELECT *, {NORM.format(u='url')} AS nurl, {HOST.format(n=NORM.format(u='url'))} AS host
   FROM st WHERE dead=0 AND deleted=0 AND url<>'' AND regexp_matches(title,'{esc(TUT)}') AND NOT regexp_matches(title,'{esc(TUT_NEG)}')""")
q("B1. tutorial-title stories (url, neg filter) by threshold; score unreliable for 2023/2026 so also by comments",
  """SELECT count(*) all_, count(*) FILTER (WHERE score>=50) ge50, count(*) FILTER (WHERE score>=100) ge100,
            count(*) FILTER (WHERE score>=50 OR ncom>=20) ge50_or_20com,
            count(*) FILTER (WHERE (score>=50 OR ncom>=20) AND year(time) IN (2023,2026)) of_which_2023_2026 FROM b1""")
q("B2. SAMPLE 40 b1 (score>=100 or ncom>=40)",
  "SELECT id, year(time) y, score, ncom, title, host FROM b1 WHERE score>=100 OR ncom>=40 ORDER BY random() LIMIT 40", 85)

# ---- C. Ask HN resource threads (tight)
con.execute(f"""CREATE OR REPLACE TEMP VIEW b2 AS
   SELECT * FROM st WHERE dead=0 AND deleted=0 AND regexp_matches(title,'{esc(ASK)}') AND NOT regexp_matches(title,'{esc(ASK_NEG)}')""")
q("C1. tight Ask HN resource threads by recomputed comments",
  """SELECT count(*) all_, count(*) FILTER (WHERE ncom>=10) ge10, count(*) FILTER (WHERE ncom>=20) ge20,
            count(*) FILTER (WHERE ncom>=50) ge50, count(*) FILTER (WHERE ncom>=100) ge100,
            sum(ncom) FILTER (WHERE ncom>=20) total_comments_in_ge20 FROM b2""")
q("C2. per year ncom>=20", "SELECT year(time) y, count(*) n FROM b2 WHERE ncom>=20 GROUP BY 1 ORDER BY 1")
q("C3. SAMPLE 40 tight Ask HN threads ncom>=20",
  "SELECT id, year(time) y, score, ncom, title FROM b2 WHERE ncom>=20 ORDER BY random() LIMIT 40", 100)

# ---- D. links in ALL-depth replies to b2 (ncom>=20)
con.execute(f"""CREATE OR REPLACE TEMP TABLE b2_links AS
   SELECT c.id cid, c.author, r.root AS story_id, r.depth, year(c.time) y,
          {NORM.format(u=UNESC.format(h='h'))} AS nurl
   FROM link_comments c JOIN comment_root r ON c.id=r.id JOIN b2 s ON r.root=s.id AND s.ncom>=20,
        unnest(regexp_extract_all(c.text, 'href="([^"]+)"', 1)) AS t(h)
   WHERE c.dead=0 AND c.deleted=0""")
con.execute(f"ALTER TABLE b2_links ADD COLUMN host VARCHAR; UPDATE b2_links SET host={HOST.format(n='nurl')}")
q("D1. link stats, all-depth replies of tight Ask HN threads",
  """SELECT count(*) hrefs, count(DISTINCT nurl) urls, count(DISTINCT host) hosts, count(DISTINCT cid) comments,
            count(DISTINCT story_id) threads, count(*) FILTER (WHERE depth=1) top_level_hrefs, min(y) y0, max(y) y1 FROM b2_links""")
q("D2. URLs by >=N distinct commenters (excluding skip hosts)",
  f"""SELECT count(*) FILTER (WHERE ppl>=2) ge2, count(*) FILTER (WHERE ppl>=3) ge3, count(*) FILTER (WHERE ppl>=5) ge5,
             count(*) FILTER (WHERE ppl>=10) ge10
      FROM (SELECT nurl, count(DISTINCT author) ppl FROM b2_links WHERE host NOT IN {SKIP} GROUP BY 1)""")
q("D3. top 50 URLs by distinct commenters (excluding skip hosts)",
  f"""SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT story_id) thr, min(y) y0, max(y) y1
      FROM b2_links WHERE host NOT IN {SKIP} GROUP BY 1 ORDER BY 2 DESC LIMIT 50""", 75)
q("D4. top 30 hosts", "SELECT host, count(DISTINCT author) ppl, count(DISTINCT nurl) urls FROM b2_links GROUP BY 1 ORDER BY 2 DESC LIMIT 30")
q("D5. SAMPLE 40 URLs with 2-4 commenters (precision eyeball of the long tail)",
  f"""SELECT nurl, ppl, y0 FROM (SELECT nurl, count(DISTINCT author) ppl, min(y) y0 FROM b2_links WHERE host NOT IN {SKIP} GROUP BY 1)
      WHERE ppl BETWEEN 2 AND 4 ORDER BY random() LIMIT 40""", 90)

# ---- E. corpus-wide recommendation-phrase comments with links
con.execute(f"""CREATE OR REPLACE TEMP TABLE rec_links AS
   SELECT c.id cid, c.author, year(c.time) y, {NORM.format(u=UNESC.format(h='h'))} AS nurl
   FROM link_comments c, unnest(regexp_extract_all(c.text, 'href="([^"]+)"', 1)) AS t(h)
   WHERE c.dead=0 AND c.deleted=0 AND regexp_matches(c.text,'{esc(REC)}')""")
con.execute(f"ALTER TABLE rec_links ADD COLUMN host VARCHAR; UPDATE rec_links SET host={HOST.format(n='nurl')}")
q("E1. recommendation-phrase comments with links: stats",
  f"""SELECT count(DISTINCT cid) comments, count(*) hrefs, count(DISTINCT nurl) urls,
             count(DISTINCT nurl) FILTER (WHERE host NOT IN {SKIP}) urls_excl_skip FROM rec_links""")
q("E2. URLs by >=N distinct recommenders (excl skip hosts)",
  f"""SELECT count(*) FILTER (WHERE ppl>=2) ge2, count(*) FILTER (WHERE ppl>=3) ge3, count(*) FILTER (WHERE ppl>=5) ge5,
             count(*) FILTER (WHERE ppl>=10) ge10, count(*) FILTER (WHERE ppl>=3 AND yrs>=3) ge3_and_3yrs
      FROM (SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs FROM rec_links WHERE host NOT IN {SKIP} GROUP BY 1)""")
q("E3. top 50 recommended URLs corpus-wide (excl skip hosts)",
  f"""SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs, min(y) y0, max(y) y1
      FROM rec_links WHERE host NOT IN {SKIP} GROUP BY 1 ORDER BY 2 DESC LIMIT 50""", 75)
q("E4. SAMPLE 40 recommended URLs with 3-6 recommenders (precision eyeball)",
  f"""SELECT nurl, ppl, yrs FROM (SELECT nurl, count(DISTINCT author) ppl, count(DISTINCT y) yrs FROM rec_links WHERE host NOT IN {SKIP} GROUP BY 1)
      WHERE ppl BETWEEN 3 AND 6 ORDER BY random() LIMIT 40""", 90)
q("E5. recommended URLs per first-seen year (coverage check post-2015)",
  f"""SELECT y0, count(*) n FROM (SELECT nurl, min(y) y0, count(DISTINCT author) ppl FROM rec_links WHERE host NOT IN {SKIP} GROUP BY 1 HAVING ppl>=2) GROUP BY 1 ORDER BY 1""")

# ---- F. sizing for LLM classification
q("F. candidate set sizes for LLM pass",
  f"""SELECT (SELECT count(*) FROM b1 WHERE score>=50 OR ncom>=20) tutorial_title_stories,
             (SELECT count(*) FROM b2 WHERE ncom>=20) ask_threads,
             (SELECT count(DISTINCT cid) FROM b2_links WHERE host NOT IN {SKIP}) ask_link_comments,
             (SELECT count(*) FROM (SELECT nurl FROM rec_links WHERE host NOT IN {SKIP} GROUP BY 1 HAVING count(DISTINCT author)>=2)) rec_urls_ge2,
             (SELECT count(DISTINCT cid) FROM rec_links WHERE host NOT IN {SKIP}) rec_comments,
             (SELECT round(avg(length(text))) FROM link_comments USING SAMPLE 100000) avg_link_comment_chars""")
