"""Build a stratified evaluation sample of recommended URLs with HN context.

Usage: python -I eval_sample.py <hn.duckdb> <out.jsonl>
"""
import json
import sys

import duckdb

DB, OUT = sys.argv[1], sys.argv[2]
con = duckdb.connect(DB, read_only=True)

UNESC = ("replace(replace(replace(replace(replace(replace(replace(replace(replace({h},"
         "'&#x2F;','/'),'&#38;','&'),'&amp;','&'),'&#x27;',''''),'&quot;','\"'),'&#62;','>'),"
         "'&#60;','<'),'&gt;','>'),'&lt;','<')")
NORM = ("lower(regexp_replace(regexp_replace(regexp_replace(regexp_replace({u},'^https?://',''),"
        "'^www\\.',''),'[#?].*$',''),'/+$',''))")
SKIP = ("('news.ycombinator.com','en.wikipedia.org','en.m.wikipedia.org','youtube.com','youtu.be',"
        "'m.youtube.com','twitter.com','x.com','i.imgur.com','imgur.com','google.com','amazon.com',"
        "'amzn.to','amzn.com','amazon.co.uk','reddit.com','old.reddit.com','github.com','archive.org',"
        "'web.archive.org','webcache.googleusercontent.com','play.google.com','books.google.com',"
        "'hn.algolia.com','duckduckgo.com','scholar.google.com','groups.google.com',"
        "'citeseerx.ist.psu.edu','papers.ssrn.com','bugzilla.mozilla.org','goodreads.com',"
        "'wolframalpha.com','bing.com')")
NEWSY = ("('nytimes.com','techcrunch.com','arstechnica.com','theverge.com','bloomberg.com','wsj.com',"
         "'theguardian.com','bbc.com','bbc.co.uk','wired.com','economist.com','theatlantic.com',"
         "'newyorker.com','apple.com','microsoft.com','stripe.com','cloudflare.com','medium.com',"
         "'forbes.com','cnn.com','reuters.com','washingtonpost.com','ft.com','slate.com','vox.com',"
         "'businessinsider.com','venturebeat.com','engadget.com','gizmodo.com','zdnet.com')")
REC = (r"(?i)(highly recommend|strongly recommend|i recommend|i''d recommend|i would recommend|"
       r"can''t recommend .{0,20}enough|"
       r"great (resource|intro|introduction|tutorial|book|course|explanation|primer|starting point)|"
       r"excellent (resource|intro|introduction|tutorial|book|course|explanation|primer)|"
       r"best (intro|introduction|tutorial|resource|explanation|book|course|primer)|"
       r"worth (reading|a read|your time|checking out)|must[- ]read|start with|"
       r"good (place to start|starting point|intro|introduction|resource|tutorial)|"
       r"learn(ed|t)? (a lot|so much|a ton) from|taught me|changed (how|the way) i|"
       r"the (canonical|definitive|classic)|if you want to (learn|understand))")
STRIP = "regexp_replace(regexp_replace({t},'<[^>]+>',' ','g'),'\\s+',' ','g')"

con.execute(f"""CREATE TEMP TABLE mention AS
   SELECT c.id, c.author, c.time, {NORM.format(u=UNESC.format(h='h'))} AS nurl,
          left({UNESC.format(h=STRIP.format(t='c.text'))}, 700) AS excerpt
   FROM link_comments c, unnest(regexp_extract_all(c.text,'href="([^"]+)"',1)) t(h)
   WHERE c.dead=0 AND c.deleted=0 AND regexp_matches(c.text,'{REC}')""")
con.execute("""CREATE TEMP TABLE rec AS
   SELECT nurl, regexp_extract(nurl,'^([^/]+)',1) host, count(DISTINCT author) ppl,
          count(DISTINCT year(time)) yrs, min(year(time)) y0, max(year(time)) y1,
          list(excerpt ORDER BY length(excerpt) DESC)[1:3] excerpts
   FROM mention WHERE nurl <> '' GROUP BY 1""")
con.execute(f"""CREATE TEMP TABLE sub AS
   SELECT {NORM.format(u='url')} nurl, arg_max(title, score) title, max(score) best_score
   FROM stories WHERE url<>'' AND dead=0 GROUP BY 1""")

STRATA = {
    "A_strong": f"r.ppl>=5 AND r.host NOT IN {SKIP}",
    "B_weak": f"r.ppl=3 AND r.host NOT IN {SKIP}",
    "C_newsy": f"r.ppl>=3 AND r.host IN {NEWSY}",
}
SIZES = {"A_strong": 35, "B_weak": 35, "C_newsy": 30}
rows = []
for name, cond in STRATA.items():
    q = f"""SELECT r.nurl, r.host, r.ppl, r.yrs, r.y0, r.y1, r.excerpts, s.title, s.best_score
            FROM rec r LEFT JOIN sub s USING(nurl) WHERE {cond}
            ORDER BY hash(r.nurl || 'eval-seed-1') LIMIT {SIZES[name]}"""
    for rec in con.execute(q).fetchall():
        nurl, host, ppl, yrs, y0, y1, ex, title, score = rec
        rows.append({"stratum": name, "nurl": nurl, "host": host, "ppl": ppl, "yrs": yrs,
                     "y0": y0, "y1": y1, "excerpts": ex, "story_title": title,
                     "best_score": score})
with open(OUT, "w") as f:
    for i, r in enumerate(rows):
        f.write(json.dumps({"id": i, **r}, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} items to {OUT}")
