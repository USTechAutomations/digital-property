#!/usr/bin/env python3
"""Remove opted-out repositories from your local copy of The Stack.

usage: filter_stack.py --input PATH --output DIR [--edition optouts.csv] [--repo-column NAME]
                       [--include-withdrawn]

PATH is a .parquet or .jsonl (optionally .gz) file, or a folder of them. Parquet needs pyarrow
(only imported if you have Parquet input). Your input is never modified: filtered copies are
written to DIR (which must not be the input folder) together with removal_report.csv.
Whole-account rows match every repository of that owner; repository rows match owner/repo exactly.
Names are compared ignoring case.
"""
import argparse, csv, gzip, json, os, sys

CANDIDATE_COLUMNS = ("repo_path", "repo_name", "repository_name", "full_name", "repo")


def load_rules(path, include_withdrawn=False):
    owners, repos = {}, {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["withdrawn"] == "yes" and not include_withdrawn:
                continue
            n = int(r["issue_number"])
            if r["request_type"] == "whole_account":
                k = r["owner"].lower()
                if k not in owners or n < owners[k]:
                    owners[k] = n
            else:
                k = (r["owner"] + "/" + r["repository"]).lower()
                if k not in repos or n < repos[k]:
                    repos[k] = n
    return owners, repos


def match(slug, owners, repos):
    """Issue number of the earliest matching request, or None."""
    if not isinstance(slug, str) or not slug:
        return None
    s = slug.strip().lower()
    hits = []
    if s in repos:
        hits.append(repos[s])
    o = s.split("/", 1)[0]
    if o in owners:
        hits.append(owners[o])
    return min(hits) if hits else None


def pick_column(names, wanted):
    if wanted:
        if wanted not in names:
            sys.exit(f"column {wanted!r} not found; columns are: {sorted(names)}")
        return wanted
    for c in CANDIDATE_COLUMNS:
        if c in names:
            return c
    sys.exit("no repository column found; pass --repo-column. Columns: " + ", ".join(sorted(names)))


def _open(path, mode):
    return gzip.open(path, mode + "t", encoding="utf-8") if path.endswith(".gz") else open(path, mode, encoding="utf-8")


def filter_jsonl(src, dst, owners, repos, col, counts):
    scanned = removed = 0
    with _open(src, "r") as fi, _open(dst, "w") as fo:
        for line in fi:
            if not line.strip():
                continue
            row = json.loads(line)
            if col is None:
                col = pick_column(set(row), None)
            scanned += 1
            hit = match(row.get(col), owners, repos)
            if hit is None:
                fo.write(line if line.endswith("\n") else line + "\n")
            else:
                removed += 1
                counts[hit] = counts.get(hit, 0) + 1
    return scanned, removed


def filter_parquet(src, dst, owners, repos, wanted, counts):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        sys.exit("pyarrow is needed for Parquet input (pip install pyarrow), or convert to JSONL")
    pf = pq.ParquetFile(src)
    col = pick_column(set(pf.schema_arrow.names), wanted)
    scanned = removed = 0
    writer = pq.ParquetWriter(dst, pf.schema_arrow)
    try:
        for batch in pf.iter_batches(batch_size=1000):
            slugs = batch.column(col).to_pylist()
            keep = []
            for i, s in enumerate(slugs):
                hit = match(s, owners, repos)
                if hit is None:
                    keep.append(i)
                else:
                    removed += 1
                    counts[hit] = counts.get(hit, 0) + 1
            scanned += len(slugs)
            if keep:
                writer.write_table(pa.Table.from_batches([batch]).take(keep))
    finally:
        writer.close()
    return scanned, removed


def inputs(path):
    if os.path.isdir(path):
        for n in sorted(os.listdir(path)):
            if n.endswith((".parquet", ".jsonl", ".jsonl.gz")):
                yield os.path.join(path, n)
    else:
        yield path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--edition", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "optouts.csv"))
    ap.add_argument("--repo-column")
    ap.add_argument("--include-withdrawn", action="store_true")
    a = ap.parse_args(argv)
    in_abs = os.path.abspath(a.input)
    out_abs = os.path.abspath(a.output)
    in_dir = in_abs if os.path.isdir(in_abs) else os.path.dirname(in_abs)
    if out_abs == in_dir:
        sys.exit("refusing: output folder is the input folder (inputs are never modified in place)")
    os.makedirs(out_abs, exist_ok=True)
    owners, repos = load_rules(a.edition, a.include_withdrawn)
    meta = {}
    with open(a.edition, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meta[int(r["issue_number"])] = r
    counts, total_scanned, total_removed, files = {}, 0, 0, 0
    for src in inputs(a.input):
        dst = os.path.join(out_abs, os.path.basename(src))
        if os.path.abspath(dst) == os.path.abspath(src):
            sys.exit("refusing to overwrite input")
        if src.endswith(".parquet"):
            s, r = filter_parquet(src, dst, owners, repos, a.repo_column, counts)
        else:
            s, r = filter_jsonl(src, dst, owners, repos, a.repo_column, counts)
        total_scanned += s
        total_removed += r
        files += 1
    with open(os.path.join(out_abs, "removal_report.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["issue_number", "request_type", "owner", "repository", "rows_removed", "source_url"])
        for n in sorted(counts):
            m = meta.get(n, {})
            w.writerow([n, m.get("request_type", ""), m.get("owner", ""), m.get("repository", ""), counts[n],
                        m.get("source_url", "")])
    print(json.dumps({"files": files, "rows_scanned": total_scanned, "rows_removed": total_removed,
                      "rows_kept": total_scanned - total_removed, "requests_matched": len(counts)}))


if __name__ == "__main__":
    main()
