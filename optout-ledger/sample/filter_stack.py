#!/usr/bin/env python3
"""Remove opted-out repositories from your local copy of The Stack.

usage: filter_stack.py --input PATH --output DIR [--edition optouts.csv] [--repo-column NAME]
                       [--include-withdrawn]

PATH is a .parquet or .jsonl (optionally .gz) file, or a folder of them. Parquet needs pyarrow
(only imported if you have Parquet input). Your input is never modified: filtered copies are
written to DIR (which must not be the input folder) together with removal_report.csv.
Whole-account rows match every repository of that owner; repository rows match owner/repo.
Names are compared ignoring case. A trailing .git, a trailing slash, and a GitHub link
(with /tree/... or /blob/...) are treated as the same repository. Rows with withdrawn
yes (any capitalisation) are skipped unless you pass --include-withdrawn.
A JSONL line that is not one object is copied unchanged and counted; it is not deleted.
"""
import argparse, csv, errno, gzip, io, json, os, re, sys

CANDIDATE_COLUMNS = ("repo_path", "repo_name", "repository_name", "full_name", "repo")
# Third piece of a GitHub URL that still names one repository, not a file path.
_TAIL = {"tree", "blob", "commit", "commits", "issues", "issue", "pull", "pulls", "wiki",
         "releases", "release", "actions", "settings", "archive", "security", "graphs",
         "network", "tags", "tag", "branches", "branch", "raw", "blame", "compare",
         "stargazers", "watchers", "pulse", "community", "activity", "discussions",
         "projects", "packages", "deployments", "advisors", "forks", "stars"}
_OWNER = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,38}$")
_REPO = re.compile(r"^[a-z0-9_.-]{1,100}$")
_HOSTS = ("https://www.github.com/", "http://www.github.com/", "https://github.com/",
          "http://github.com/", "www.github.com/", "github.com/")


def _owner_key(name):
    return (name or "").strip().lower()


def _repo_key(name):
    return re.sub(r"(?i)\.git$", "", (name or "").strip()).lower()


def _norm_slug(slug):
    s = slug.strip().split("?")[0].split("#")[0].rstrip("/").lower()
    for host in _HOSTS:
        if s.startswith(host):
            s = s[len(host):]
            break
    parts = s.split("/")
    if len(parts) < 2 or not _OWNER.fullmatch(parts[0]):
        return ""
    repo = _repo_key(parts[1])
    if not _REPO.fullmatch(repo) or repo in (".", ".."):
        return ""
    if len(parts) > 2 and (parts[2] not in _TAIL or any(not p or p in (".", "..") for p in parts[2:])):
        return ""
    return parts[0] + "/" + repo


def load_rules(path, include_withdrawn=False):
    owners, repos = {}, {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"issue_number", "request_type", "owner", "repository", "withdrawn"}
        if not required.issubset(reader.fieldnames or []):
            sys.exit("edition is missing required columns")
        for r in reader:
            if None in r or any(r.get(k) is None for k in required):
                continue
            if r["withdrawn"].strip().lower() not in ("yes", "no", "unknown"):
                continue
            if (r.get("withdrawn") or "").strip().lower() == "yes" and not include_withdrawn:
                continue
            try:
                n = int(str(r.get("issue_number", "")).strip())
            except ValueError:
                continue
            owner = _owner_key(r.get("owner"))
            if n <= 0 or not _OWNER.fullmatch(owner):
                continue
            if r.get("request_type") == "whole_account" and not r["repository"].strip():
                if owner not in owners or n < owners[owner]:
                    owners[owner] = n
            elif r.get("request_type") == "repository":
                repo = _repo_key(r.get("repository"))
                if not _REPO.fullmatch(repo) or repo in (".", ".."):
                    continue
                k = owner + "/" + repo
                if k not in repos or n < repos[k]:
                    repos[k] = n
    return owners, repos


def match(slug, owners, repos):
    """Issue number of the earliest matching request, or None."""
    if not isinstance(slug, str) or not slug.strip():
        return None
    s = _norm_slug(slug)
    if not s:
        return None
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


def _open_write(path):
    """Write a normal file. Following a link would overwrite the file it points at."""
    if os.path.islink(path):
        sys.exit("refusing to follow an output link")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o644)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EEXIST):
            sys.exit("refusing to follow an output link")
        raise
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.GzipFile(fileobj=os.fdopen(fd, "wb"), mode="wb"), encoding="utf-8", newline="")
    return os.fdopen(fd, "w", encoding="utf-8", newline="")


def _emit(fo, line):
    fo.write(line if line.endswith("\n") else line + "\n")


def filter_jsonl(src, dst, owners, repos, col, counts):
    """Stream one line at a time. A line that is not one JSON object is copied, not dropped."""
    scanned = removed = malformed = 0
    chosen = col
    try:
        with _open(src, "r") as fi, _open_write(dst) as fo:
            checked = False
            for line in fi:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    _emit(fo, line)
                    continue
                if not isinstance(row, dict):
                    malformed += 1
                    _emit(fo, line)
                    continue
                if not checked:
                    if chosen is None:
                        chosen = pick_column(set(row), None)
                    elif chosen not in row:
                        sys.exit("column %r not found; columns are: %s" % (chosen, sorted(row)))
                    checked = True
                scanned += 1
                hit = match(row.get(chosen), owners, repos)
                if hit is None:
                    _emit(fo, line)
                else:
                    removed += 1
                    counts[hit] = counts.get(hit, 0) + 1
    except SystemExit:
        # a partial file would look like a finished filter and drop the unread tail
        if os.path.lexists(dst) and not os.path.islink(dst):
            os.remove(dst)
        raise
    return scanned, removed, malformed


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
    return scanned, removed, 0


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
    in_abs = os.path.realpath(a.input)
    out_abs = os.path.realpath(a.output)
    in_dir = in_abs if os.path.isdir(in_abs) else os.path.dirname(in_abs)
    if out_abs == in_dir:
        sys.exit("refusing: output folder is the input folder (inputs are never modified in place)")
    os.makedirs(out_abs, exist_ok=True)
    owners, repos = load_rules(a.edition, a.include_withdrawn)
    meta = {}
    with open(a.edition, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                meta[int(str(r.get("issue_number", "")).strip())] = r
            except ValueError:
                continue
    counts, total_scanned, total_removed, total_bad, files = {}, 0, 0, 0, 0
    for src in inputs(a.input):
        dst = os.path.join(out_abs, os.path.basename(src))
        if os.path.islink(dst):
            sys.exit("refusing to follow an output link")
        if os.path.realpath(dst) == os.path.realpath(src):
            sys.exit("refusing to overwrite input")
        if src.endswith(".parquet"):
            s, r, b = filter_parquet(src, dst, owners, repos, a.repo_column, counts)
        else:
            s, r, b = filter_jsonl(src, dst, owners, repos, a.repo_column, counts)
        total_scanned += s
        total_removed += r
        total_bad += b
        files += 1
    report_path = os.path.join(out_abs, "removal_report.csv")
    if os.path.islink(report_path):
        sys.exit("refusing to follow an output link")
    with _open_write(report_path) as f:
        w = csv.writer(f)
        w.writerow(["issue_number", "request_type", "owner", "repository", "rows_removed", "source_url"])
        for n in sorted(counts):
            m = meta.get(n, {})
            w.writerow([n, m.get("request_type", ""), m.get("owner", ""), m.get("repository", ""), counts[n],
                        m.get("source_url", "")])
    print(json.dumps({"files": files, "rows_scanned": total_scanned, "rows_removed": total_removed,
                      "rows_kept": total_scanned - total_removed, "rows_malformed": total_bad,
                      "requests_matched": len(counts)}))


if __name__ == "__main__":
    main()
