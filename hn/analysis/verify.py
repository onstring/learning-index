import sys, csv, duckdb

root = sys.argv[1]
con = duckdb.connect()

print("== 1. local row counts vs stats.csv ==")
local = {}
for (fn, n) in con.execute(
    f"SELECT filename, count(*) FROM read_parquet('{root}/data/*/*.parquet', filename=true) GROUP BY 1"
).fetchall():
    key = fn.split("/")[-1].replace(".parquet", "")
    local[key] = n
mism = 0
for r in csv.DictReader(open(f"{root}/stats.csv")):
    key = f"{r['year']}-{int(r['month']):02d}"
    want = int(r["count"])
    got = local.get(key)
    if got != want:
        mism += 1
        print("MISMATCH", key, "stats=", want, "local=", got)
print("months checked:", len(local), "mismatches:", mism, "total rows:", sum(local.values()))

print("\n== 2. per-column compressed bytes (footer only) ==")
for m in ["2023/2023-06", "2024/2024-06", "2025/2025-06", "2026/2026-06"]:
    rows = con.execute(
        f"""SELECT path_in_schema[1] col, sum(total_compressed_size) c, sum(total_uncompressed_size) u
            FROM parquet_metadata('{root}/data/{m}.parquet') GROUP BY 1 ORDER BY 2 DESC"""
    ).fetchall()
    print(m, " ".join(f"{c}={cs/1e6:.1f}MB(u{us/1e6:.0f})" for c, cs, us in rows[:6]))

print("\n== 3. content stats ==")
for m in ["2023/2023-06", "2024/2024-06", "2025/2025-06", "2026/2026-06"]:
    r = con.execute(
        f"""SELECT count(*) n,
               count(*) FILTER (WHERE type=1) stories,
               count(*) FILTER (WHERE type=2) comments,
               round(avg(length(text)) FILTER (WHERE type=2),1) avg_comment_len,
               count(*) FILTER (WHERE type=2 AND (text IS NULL OR text='')) empty_comments,
               round(avg(len(words)),1) avg_words,
               count(*) FILTER (WHERE deleted=1) deleted,
               count(*) FILTER (WHERE dead=1) dead,
               max(score) max_score,
               count(*) FILTER (WHERE type=2 AND text LIKE '%href=%') comments_with_links
            FROM read_parquet('{root}/data/{m}.parquet')"""
    ).fetchone()
    print(m, r)
