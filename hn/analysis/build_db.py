import sys, time, duckdb

root, dbpath = sys.argv[1], sys.argv[2]
src = f"read_parquet('{root}/data/*/*.parquet')"
con = duckdb.connect(dbpath)
con.execute("SET preserve_insertion_order=false")

steps = [
    ("stories",
     f"""CREATE OR REPLACE TABLE stories AS
         SELECT id, "by" AS author, time, title, url, score, descendants, text, dead, deleted
         FROM {src} WHERE type=1"""),
    ("link_comments",
     f"""CREATE OR REPLACE TABLE link_comments AS
         SELECT id, "by" AS author, time, parent, text, dead, deleted
         FROM {src} WHERE type=2 AND text LIKE '%href=%'"""),
    ("comment_parents",
     f"""CREATE OR REPLACE TABLE comment_parents AS
         SELECT id, parent FROM {src} WHERE type=2"""),
]
for name, sql in steps:
    t = time.time()
    con.execute(sql)
    n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    print(f"{name}: {n:,} rows in {time.time()-t:.0f}s", flush=True)
con.close()
