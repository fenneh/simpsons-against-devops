#!/usr/bin/env python3
"""Wayback fallback: for each image_url in img_failed.tsv, try the wayback machine."""
import re
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

ROOT = Path(__file__).parent
FAILED = ROOT / "img_failed.tsv"
IMG_DIR = ROOT / "images"
RECOVERED = ROOT / "img_recovered.tsv"
STILL_DEAD = ROOT / "img_still_dead.tsv"

PBS_RE = re.compile(r'https://pbs\.twimg\.com/media/([A-Za-z0-9_-]+)\.(jpg|jpeg|png|gif|webp)', re.I)
UA = "Mozilla/5.0 (compatible; SimpsonsOpsArchive/1.0)"

def http_get(url, timeout=60, retries=4):
    delay = 1.0
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last = e
            time.sleep(delay + random.uniform(0, delay))
            delay = min(delay * 2, 30)
            continue
        except urllib.error.HTTPError as e:
            if e.code in (429, 503, 502, 504):
                time.sleep(delay + random.uniform(0, delay))
                delay = min(delay * 2, 30)
                continue
            return None
    return None


def cdx_lookup(pbs_url):
    """Return earliest available wayback timestamp for this pbs.twimg URL, or None."""
    api = f"https://web.archive.org/cdx/search/cdx?url={pbs_url}&output=json&filter=statuscode:200&limit=1"
    try:
        data = http_get(api, timeout=30)
        if not data: return None
        import json
        rows = json.loads(data)
        if len(rows) < 2: return None
        return rows[1][1]  # timestamp
    except Exception:
        return None


def recover(img_url):
    m = PBS_RE.search(img_url)
    if not m: return img_url, None, "bad_url"
    img_id, ext = m.group(1), m.group(2).lower()
    dest = IMG_DIR / f"{img_id}.{ext}"
    if dest.exists() and dest.stat().st_size > 1024:
        return img_url, dest, "already"

    ts = cdx_lookup(img_url)
    if not ts:
        return img_url, None, "not_in_wayback"
    wb_url = f"https://web.archive.org/web/{ts}id_/{img_url}"
    time.sleep(random.uniform(0.2, 0.8))
    data = http_get(wb_url, timeout=60)
    if not data or len(data) < 500:
        return img_url, None, f"empty_or_tiny:{len(data) if data else 0}"
    dest.write_bytes(data)
    return img_url, dest, "ok"


def main():
    urls = []
    with FAILED.open() as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                urls.append(parts[0])
    urls = list(set(urls))
    print(f"trying wayback fallback for {len(urls)} urls", flush=True)

    n_ok = n_fail = n_already = 0
    rec_f = RECOVERED.open("a")
    dead_f = STILL_DEAD.open("a")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {pool.submit(recover, u): u for u in urls}
        for i, fut in enumerate(as_completed(futs), 1):
            url, dest, status = fut.result()
            if status in ("ok", "already"):
                n_ok += 1
                rec_f.write(f"{url}\t{status}\n"); rec_f.flush()
            else:
                n_fail += 1
                dead_f.write(f"{url}\t{status}\n"); dead_f.flush()
            if i % 10 == 0:
                rate = i / (time.time() - t0)
                eta = (len(urls) - i) / max(rate, 0.01)
                print(f"  [{i}/{len(urls)}] ok={n_ok} fail={n_fail} eta={eta/60:.1f}m", flush=True)
    rec_f.close(); dead_f.close()
    print(f"wayback fallback done: ok={n_ok} fail={n_fail} in {(time.time()-t0)/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
