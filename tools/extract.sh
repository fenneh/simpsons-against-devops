#!/usr/bin/env bash
# Extract pbs.twimg.com image URLs from each Wayback snapshot of @SimpsonsOps tweets.
# Outputs: status_urls.tsv  (status_id\timage_url) -- one row per image
set -u
cd "$(dirname "$0")"

# Build a deduped list: status_id -> latest timestamp (prefer twitter.com snapshots, then x.com)
# Prefer snapshots with /photo/ in URL (those most reliably contain the canonical image)
# Otherwise take the highest byte-count snapshot per status (richer HTML).

python3 <<'PY'
import json, re, sys
from collections import defaultdict

best = {}   # status_id -> (priority, ts, original)
# priority: 3 = has /photo/, 2 = plain status (twitter.com), 1 = plain status (x.com)

for path in ('cdx_twitter.json', 'cdx_x.json'):
    try:
        rows = json.load(open(path))
    except Exception:
        continue
    if not rows: continue
    rows = rows[1:]  # drop header
    for r in rows:
        urlkey, ts, original, mt, sc, digest, length = r
        m = re.search(r'/status/(\d+)', original)
        if not m: continue
        sid = m.group(1)
        if '/photo/' in original:
            pri = 3
        elif 'x.com' in original:
            pri = 1
        else:
            pri = 2
        # Prefer higher priority; among same priority, prefer latest timestamp
        key = (pri, ts)
        prev = best.get(sid)
        if prev is None or key > prev[:2]:
            best[sid] = (pri, ts, original)

with open('targets.tsv', 'w') as f:
    for sid, (pri, ts, orig) in sorted(best.items()):
        f.write(f"{sid}\t{ts}\t{orig}\n")

print(f"unique status ids: {len(best)}")
PY

wc -l targets.tsv
