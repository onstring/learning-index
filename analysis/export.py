import sys, duckdb, os

dbpath, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
con = duckdb.connect(dbpath, read_only=True)
UNESC = ("replace(replace(replace(replace(replace(replace(replace(replace(replace({h},"
         "'&#x2F;','/'),'&#38;','&'),'&amp;','&'),'&#x27;',''''),'&quot;','\"'),'&#62;','>'),'&#60;','<'),'&gt;','>'),'&lt;','<')")
NORM = ("lower(regexp_replace(regexp_replace(regexp_replace(regexp_replace({u},'^https?://',''),"
        "'^www\\.',''),'[#?].*$',''),'/+$',''))")
SKIP = "('news.ycombinator.com','en.wikipedia.org','en.m.wikipedia.org','youtube.com','youtu.be','m.youtube.com','twitter.com','x.com','i.imgur.com','imgur.com','google.com','amazon.com','amzn.to','amzn.com','amazon.co.uk','reddit.com','old.reddit.com','github.com','archive.org','web.archive.org','webcache.googleusercontent.com','play.google.com','books.google.com','hn.algolia.com','duckduckgo.com','scholar.google.com','groups.google.com','citeseerx.ist.psu.edu','papers.ssrn.com','bugzilla.mozilla.org','goodreads.com','wolframalpha.com','bing.com')"
REC = (r"(?i)(highly recommend|strongly recommend|i recommend|i''d recommend|i would recommend|can''t recommend .{0,20}enough|"
       r"great (resource|intro|introduction|tutorial|book|course|explanation|primer|starting point)|"
       r"excellent (resource|intro|introduction|tutorial|book|course|explanation|primer)|best (intro|introduction|tutorial|resource|explanation|book|course|primer)|"
       r"worth (reading|a read|your time|checking out)|must[- ]read|start with|good (place to start|starting point|intro|introduction|resource|tutorial)|"
       r"learn(ed|t)? (a lot|so much|a ton) from|taught me|changed (how|the way) i|the (canonical|definitive|classic)|"
       r"if you want to (learn|understand))")

con.execute(f"""CREATE TEMP TABLE rec AS
   SELECT nurl, regexp_extract(nurl,'^([^/]+)',1) host, count(DISTINCT author) ppl, count(DISTINCT year(time)) yrs,
          min(year(time)) y0, max(year(time)) y1, count(*) mentions, any_value(id) example_comment_id
   FROM (SELECT c.id, c.author, c.time, {NORM.format(u=UNESC.format(h='h'))} AS nurl
         FROM link_comments c, unnest(regexp_extract_all(c.text,'href="([^"]+)"',1)) t(h)
         WHERE c.dead=0 AND c.deleted=0 AND regexp_matches(c.text,'{REC}'))
   GROUP BY 1""")
con.execute(f"""CREATE TEMP TABLE sub AS
   SELECT {NORM.format(u='url')} nurl, arg_max(title, score) title, max(score) best_score, arg_max(id, score) story_id, count(*) submissions
   FROM stories WHERE url<>'' AND dead=0 GROUP BY 1""")

print("### overlap: recommended URLs (>=3 ppl, excl noise hosts) that were also submitted as a story")
print(con.execute(f"""SELECT count(*) rec_urls, count(s.nurl) with_story, count(s.nurl) FILTER (WHERE s.best_score>=20) with_story_ge20
   FROM rec r LEFT JOIN sub s USING(nurl) WHERE r.ppl>=3 AND r.host NOT IN {SKIP}""").fetchone())
print("### top hosts among rec URLs >=3 ppl (noise-list candidates)")
for r in con.execute(f"SELECT host, count(*) FROM rec WHERE ppl>=3 GROUP BY 1 ORDER BY 2 DESC LIMIT 40").fetchall(): print("  ", r)

con.execute(f"""COPY (SELECT r.nurl, r.ppl, r.yrs, r.y0, r.y1, r.mentions, s.title AS hn_story_title, s.best_score, s.story_id, r.example_comment_id
   FROM rec r LEFT JOIN sub s USING(nurl) WHERE r.nurl <> '' AND r.host NOT IN {SKIP} ORDER BY r.ppl DESC, r.yrs DESC LIMIT 300)
   TO '{outdir}/top300_recommended_urls.csv' (HEADER)""")
con.execute(f"""COPY (SELECT r.nurl, r.ppl, r.yrs, r.y0, r.y1, s.title AS hn_story_title, s.best_score
   FROM rec r LEFT JOIN sub s USING(nurl) WHERE r.nurl <> '' AND r.host NOT IN {SKIP} AND r.ppl>=3 AND r.yrs>=3 ORDER BY r.yrs DESC, r.ppl DESC LIMIT 300)
   TO '{outdir}/top300_evergreen_urls.csv' (HEADER)""")
print("wrote CSVs")
