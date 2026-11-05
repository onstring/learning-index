"""Resolve each comment to its root story id via iterative parent lookup.
Writes table comment_root(id, root, depth) and story_desc(id, n_comments) into the DuckDB file."""
import sys, time, duckdb

con = duckdb.connect(sys.argv[1])
con.execute("SET preserve_insertion_order=false")
t = time.time()
# story id set for termination test
con.execute("CREATE OR REPLACE TEMP TABLE sid AS SELECT id FROM stories")
# cur: (id, node, depth) where node is the current ancestor being examined
con.execute("""CREATE OR REPLACE TABLE comment_root AS
    SELECT id, parent AS root, 1 AS depth FROM comment_parents""")
for i in range(1, 40):
    # rows whose current root is not a story and has a known parent -> climb
    n = con.execute("""
        UPDATE comment_root cr SET root = cp.parent, depth = cr.depth + 1
        FROM comment_parents cp
        WHERE cr.root = cp.id""").fetchone()[0]
    print(f"iter {i}: climbed {n:,} rows ({time.time()-t:.0f}s)", flush=True)
    if n == 0:
        break
unres = con.execute("SELECT count(*) FROM comment_root WHERE root NOT IN (SELECT id FROM sid)").fetchone()[0]
print(f"comments not resolving to a story (orphan/poll/job/deleted parent): {unres:,}")
con.execute("""CREATE OR REPLACE TABLE story_desc AS
    SELECT root AS id, count(*) AS n_comments, max(depth) AS max_depth FROM comment_root GROUP BY 1""")
print(con.execute("SELECT count(*), sum(n_comments), max(max_depth) FROM story_desc").fetchone())
print(f"done in {time.time()-t:.0f}s")
