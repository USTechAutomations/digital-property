THIS IS AN EXCERPT: 100 of 62,584 rows, and 10 of 129 unreadable requests. The full edition is the paid product.
Rows are spread across request types, confidence levels and states. Counts in stats.json
describe the full edition, not this excerpt. optouts.jsonl is not part of the excerpt.

OPT-OUT LEDGER - edition 2026-10-01
================================

What this is
------------
Every opt-out request filed in the public repository bigcode-project/opt-out-v2 (open and closed),
read by a script and turned into one row per (request, thing to remove). Captured
2026-10-01T02:50:47Z UTC. 8259 issues were read.

Files
-----
optouts.csv / optouts.jsonl   One row per (request, scope). Same content in both.
UNKNOWN.csv                   Requests the reader could not turn into rows (issue number and link only).
filter_stack.py               Removes matching repositories from your local copy of The Stack.
README.txt                    This file.

Columns of optouts.csv
----------------------
issue_number            The issue number in bigcode-project/opt-out-v2.
request_type            whole_account = every repository under that owner; repository = one named repository.
owner                   GitHub user or organisation, as written in the request.
repository              Repository name (blank for whole_account).
filed_date              Date the issue was opened (UTC, YYYY-MM-DD).
state                   open or closed, as on the capture date.
state_reason            GitHub's close reason (completed, not_planned) or blank. It is GitHub's label, not a statement about whether the removal was done.
withdrawn               yes = the request text, or a comment by the same person who filed it, clearly says it is withdrawn / opt back in.
                        no = no such wording found.
                        UNKNOWN = wording like "if ... I would prefer to cancel" that we could not read as a clear withdrawal.
                        Only comments by the person who filed the request count; withdrawals by anyone else, or made elsewhere, are not seen.
source_url              Link to the public issue.
body_sha256             SHA-256 of the request text at capture time (a fingerprint; the text itself is not included).
parse_confidence        high = standard form or legacy template read cleanly.
                        medium = read, but something odd (extra words, a wildcard, an owner taken from the issue title or filer).
                        low = free-form text where only list items were read.
first_issue_for_scope   Lowest issue number that asked for the same owner (and repository). Equal to issue_number if it is the first.

Matching rules (filter_stack.py)
--------------------------------
Owner and repository names are compared ignoring upper/lower case. A whole_account row matches every
repository whose owner is that name. A repository row matches that exact owner/repository only.
Rows with withdrawn = yes are skipped unless you pass --include-withdrawn.

What we do not claim
--------------------
- That any request is valid, or that the person filing it owns what they listed.
- That any licence has been revoked, or that any person has any legal right.
- That a model trained on the data forgot anything.
- That the list is complete: requests we could not read are in UNKNOWN.csv, and requests filed
  anywhere other than bigcode-project/opt-out-v2 are not here.
- Not legal advice.

Free-text bodies, emails and personal stories are left out on purpose. Owner names are already
public in the issues.
