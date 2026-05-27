#!/usr/bin/env python3
"""
Fetch each Wayback snapshot of a @SimpsonsOps tweet, extract pbs.twimg.com image URLs,
then download the images directly from pbs.twimg.com (content-addressed, still served
even though the account is gone).

Resumable: skips status IDs already in extracted.tsv, skips images already on disk.
"""
import csv
import os
import re
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import random
import urllib.request
import urllib.error

ROOT = Path(__file__).parent
TARGETS = ROOT / "targets.tsv"
EXTRACTED = ROOT / "extracted.tsv"       # status_id \t image_url
METADATA = ROOT / "metadata.tsv"         # status_id \t tweet_text \t alt_text \t image_ids_csv
FAILED = ROOT / "failed.tsv"             # status_id \t reason
IMG_DIR = ROOT / "images"
IMG_DIR.mkdir(exist_ok=True)

UA = "Mozilla/5.0 (compatible; SimpsonsOpsArchive/1.0)"
WAYBACK_WORKERS = 2
IMG_WORKERS = 8
TIMEOUT = 60
MAX_RETRIES = 6

PBS_RE = re.compile(r'https://pbs\.twimg\.com/media/([A-Za-z0-9_-]+)\.(jpg|jpeg|png|gif|webp)', re.I)
OG_DESC_RE = re.compile(r'property="og:description"[^>]*content="([^"]*)"')
TWEET_TEXT_RE = re.compile(r'js-tweet-text-container">\s*<p[^>]*>(.*?)</p>', re.S)
ALT_RE = re.compile(r'<img[^>]+alt="([^"]+)"[^>]+src="[^"]*pbs\.twimg\.com/media/([A-Za-z0-9_-]+)\.', re.I)
TAG_RE = re.compile(r'<[^>]+>')


def html_to_text(s):
    s = TAG_RE.sub(' ', s)
    s = s.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', s).strip()


def http_get(url, timeout=TIMEOUT, retries=MAX_RETRIES):
    """Fetch with exponential backoff on connection refused / 429 / 503."""
    delay = 1.0
    last_exc = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code in (429, 503, 502, 504):
                time.sleep(delay + random.uniform(0, delay))
                delay = min(delay * 2, 60)
                continue
            raise
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
            last_exc = e
            time.sleep(delay + random.uniform(0, delay))
            delay = min(delay * 2, 60)
            continue
    raise last_exc if last_exc else RuntimeError("http_get retries exhausted")


def already_done():
    done = set()
    if EXTRACTED.exists():
        with EXTRACTED.open() as f:
            for line in f:
                sid = line.split("\t", 1)[0]
                done.add(sid)
    if FAILED.exists():
        with FAILED.open() as f:
            for line in f:
                sid = line.split("\t", 1)[0]
                done.add(sid)
    return done


def fetch_one(sid, ts, original):
    url = f"https://web.archive.org/web/{ts}id_/{original}"
    time.sleep(random.uniform(0.05, 0.25))  # jitter per request
    try:
        body = http_get(url).decode("utf-8", errors="replace")
    except Exception as e:
        return sid, None, None, None, f"wayback_err:{type(e).__name__}:{e}"
    # Find all pbs.twimg.com/media/<id>.<ext>
    seen = set()
    for m in PBS_RE.finditer(body):
        img_id, ext = m.group(1), m.group(2).lower()
        canon = f"https://pbs.twimg.com/media/{img_id}.{ext}"
        seen.add(canon)

    # Tweet text — prefer the in-body tweet text container, fall back to og:description
    tweet_text = ""
    m = TWEET_TEXT_RE.search(body)
    if m:
        tweet_text = html_to_text(m.group(1))
    if not tweet_text:
        m2 = OG_DESC_RE.search(body)
        if m2:
            tweet_text = html_to_text(m2.group(1)).strip('"').strip('“”')

    # Per-image alt text (Twitter alt-text-on-image accessibility feature)
    alts = {}
    for m in ALT_RE.finditer(body):
        alt, img_id = m.group(1), m.group(2)
        if 'profile_images' in alt:
            continue
        alts[img_id] = html_to_text(alt)

    if not seen:
        return sid, [], tweet_text, alts, "no_images"
    return sid, sorted(seen), tweet_text, alts, None


def download_image(img_url):
    """Download from pbs.twimg.com directly, save as images/<id>.<ext>."""
    m = PBS_RE.search(img_url)
    if not m:
        return img_url, None, "bad_url"
    img_id, ext = m.group(1), m.group(2).lower()
    dest = IMG_DIR / f"{img_id}.{ext}"
    if dest.exists() and dest.stat().st_size > 1024:
        return img_url, dest, "exists"
    # Request original resolution
    orig_url = f"https://pbs.twimg.com/media/{img_id}?format={ext}&name=orig"
    try:
        data = http_get(orig_url, timeout=60)
        if len(data) < 200:
            return img_url, None, f"tiny:{len(data)}"
        dest.write_bytes(data)
        return img_url, dest, "ok"
    except urllib.error.HTTPError as e:
        # Fallback to the plain canonical url
        try:
            data = http_get(img_url, timeout=60)
            if len(data) < 200:
                return img_url, None, f"tiny_fallback:{len(data)}"
            dest.write_bytes(data)
            return img_url, dest, "ok_fallback"
        except Exception as e2:
            return img_url, None, f"http_err:{e}/{e2}"
    except Exception as e:
        return img_url, None, f"err:{type(e).__name__}:{e}"


def phase1_extract():
    done = already_done()
    targets = []
    with TARGETS.open() as f:
        for line in f:
            sid, ts, orig = line.rstrip("\n").split("\t")
            if sid in done:
                continue
            targets.append((sid, ts, orig))
    print(f"phase1: {len(targets)} status pages to fetch (already done: {len(done)})", flush=True)

    if not targets:
        return

    ex_f = EXTRACTED.open("a")
    meta_f = METADATA.open("a")
    fail_f = FAILED.open("a")
    n_ok = n_noimg = n_fail = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WAYBACK_WORKERS) as pool:
        futs = {pool.submit(fetch_one, sid, ts, orig): sid for sid, ts, orig in targets}
        for i, fut in enumerate(as_completed(futs), 1):
            sid, images, tweet_text, alts, err = fut.result()
            if err and err != "no_images":
                fail_f.write(f"{sid}\t{err}\n")
                fail_f.flush()
                n_fail += 1
                continue
            if err == "no_images":
                ex_f.write(f"{sid}\t\n")
                ex_f.flush()
                n_noimg += 1
            else:
                for u in images:
                    ex_f.write(f"{sid}\t{u}\n")
                ex_f.flush()
                n_ok += 1
            # Always record metadata when we have any tweet text or alts
            img_ids = []
            for u in (images or []):
                m = PBS_RE.search(u)
                if m: img_ids.append(m.group(1))
            alts_str = "; ".join(f"{k}={v}" for k, v in (alts or {}).items())
            meta_f.write(f"{sid}\t{(tweet_text or '').replace(chr(9),' ').replace(chr(10),' ')}\t{alts_str.replace(chr(9),' ').replace(chr(10),' ')}\t{','.join(img_ids)}\n")
            meta_f.flush()
            if i % 25 == 0:
                rate = i / (time.time() - t0)
                eta = (len(targets) - i) / max(rate, 0.01)
                print(f"  [{i}/{len(targets)}] ok={n_ok} no_img={n_noimg} fail={n_fail} "
                      f"rate={rate:.1f}/s eta={eta/60:.1f}m", flush=True)
    ex_f.close()
    meta_f.close()
    fail_f.close()
    print(f"phase1 done: ok={n_ok} no_img={n_noimg} fail={n_fail} in {(time.time()-t0)/60:.1f}m", flush=True)


def phase2_download():
    if not EXTRACTED.exists():
        print("no extracted.tsv — run phase 1 first")
        return
    urls = set()
    with EXTRACTED.open() as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[1]:
                urls.add(parts[1])
    print(f"phase2: {len(urls)} unique image urls", flush=True)

    n_ok = n_skip = n_fail = 0
    t0 = time.time()
    fail_f = open(ROOT / "img_failed.tsv", "a")
    with ThreadPoolExecutor(max_workers=IMG_WORKERS) as pool:
        futs = {pool.submit(download_image, u): u for u in urls}
        for i, fut in enumerate(as_completed(futs), 1):
            url, dest, status = fut.result()
            if status in ("ok", "ok_fallback"):
                n_ok += 1
            elif status == "exists":
                n_skip += 1
            else:
                n_fail += 1
                fail_f.write(f"{url}\t{status}\n")
                fail_f.flush()
            if i % 50 == 0:
                rate = i / (time.time() - t0)
                eta = (len(urls) - i) / max(rate, 0.01)
                print(f"  [{i}/{len(urls)}] ok={n_ok} skip={n_skip} fail={n_fail} "
                      f"rate={rate:.1f}/s eta={eta/60:.1f}m", flush=True)
    fail_f.close()
    print(f"phase2 done: ok={n_ok} skip={n_skip} fail={n_fail} in {(time.time()-t0)/60:.1f}m", flush=True)


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    if phase in ("1", "extract", "all"):
        phase1_extract()
    if phase in ("2", "download", "all"):
        phase2_download()
