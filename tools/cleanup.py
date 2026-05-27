#!/usr/bin/env python3
"""
Delete all non-Simpsons images from the repo, regenerate CATALOG.md,
and recount categories for the README.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict

REPO = Path("/root/git/simpsons-ops-archive")
PLAN = Path("/tmp/simpsonsops/all_classifications.tsv")
META = Path("/tmp/simpsonsops/metadata.tsv")
KEYWORD_DELETE = Path("/tmp/simpsonsops/delete.tsv")
RECHECK = Path("/tmp/simpsonsops/recheck/all.tsv")

# Step 1: build the set of twitter IDs to delete
delete_ids = set()
with KEYWORD_DELETE.open() as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if parts:
            img_id = parts[0].rsplit(".", 1)[0]
            delete_ids.add(img_id)

with RECHECK.open() as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2 and parts[1] == "NO":
            img_id = parts[0].rsplit(".", 1)[0]
            delete_ids.add(img_id)

print(f"images flagged for deletion: {len(delete_ids)}")

# Step 2: walk the repo to find renamed files; map twitter_id -> repo_path.
# We have all_classifications.tsv with (twitter_filename, category, summary).
# The renaming script renamed each to a slug based on summary, in the same
# category folder. To find the current name, look at all files in that category
# folder. We need a mapping. Best approach: scan classifications + summary
# slugger to reconstruct what the rename produced. But easier: scan repo and
# match by extension + look up by the summary slugging we already did.
# Actually simplest: use the SAME slugger to regenerate the new filename.

MAX_LEN = 70
STOPWORDS = set("a an the and or but with of in on at to for by from up "
                "is are was were be been being have has had do does did "
                "this that these those it its their there here".split())

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    parts = [p for p in text.split("-") if p and p not in STOPWORDS]
    text = "-".join(parts)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text: return "untitled"
    if len(text) > MAX_LEN:
        cut = text[:MAX_LEN].rsplit("-", 1)[0]
        text = cut or text[:MAX_LEN]
    return text

# Reconstruct the rename mapping with the same collision-suffixing as before
classifications = []
with PLAN.open() as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            classifications.append(parts[:3])

# Tweet text for catalog
img_tweet = {}
with META.open() as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        while len(parts) < 4: parts.append("")
        sid, text, _, img_ids = parts[:4]
        for img_id in img_ids.split(","):
            img_id = img_id.strip()
            if img_id and img_id not in img_tweet and text:
                img_tweet[img_id] = (sid, text.strip())

# Replay the rename: produce id -> (category, current_filename)
id_to_file = {}
by_cat_taken = defaultdict(set)
for fname, cat, summary in classifications:
    img_id = fname.rsplit(".", 1)[0]
    ext = fname.rsplit(".", 1)[-1].lower()
    slug = slugify(summary)
    candidate = slug
    n = 2
    while candidate in by_cat_taken[cat]:
        candidate = f"{slug}-{n}"
        n += 1
    by_cat_taken[cat].add(candidate)
    id_to_file[img_id] = (cat, f"{candidate}.{ext}", summary)

# Step 3: delete the flagged files via git rm
deleted = 0
missing = 0
for img_id in delete_ids:
    if img_id not in id_to_file:
        print(f"skip unmapped: {img_id}")
        missing += 1
        continue
    cat, fname, _ = id_to_file[img_id]
    path = REPO / cat / fname
    if not path.exists():
        print(f"skip missing on disk: {path.relative_to(REPO)}")
        missing += 1
        continue
    r = subprocess.run(["git", "-C", str(REPO), "rm", "-f", str(path.relative_to(REPO))],
                       capture_output=True, text=True)
    if r.returncode == 0:
        deleted += 1
    else:
        print(f"  rm failed: {path.name}: {r.stderr.strip()}")
print(f"deleted: {deleted}, missing/unmapped: {missing}")

# Step 4: remove empty category folders
for cat_dir in REPO.iterdir():
    if cat_dir.is_dir() and cat_dir.name not in (".git", "tools"):
        remaining = list(cat_dir.iterdir())
        if not remaining:
            cat_dir.rmdir()
            print(f"removed empty folder: {cat_dir.name}")

# Step 5: rebuild CATALOG.md with only kept items
kept_by_cat = defaultdict(list)
for img_id, (cat, fname, summary) in id_to_file.items():
    if img_id in delete_ids:
        continue
    sid, text = img_tweet.get(img_id, ("", ""))
    kept_by_cat[cat].append((fname, summary, img_id, sid))

# Drop categories with zero kept items
kept_by_cat = {k: v for k, v in kept_by_cat.items() if v}

catalog = REPO / "CATALOG.md"
with catalog.open("w") as f:
    f.write("# Catalog\n\n")
    f.write("Every image with its category, one-line summary, original Twitter\n")
    f.write("image ID, and a link to the Wayback snapshot of the source tweet.\n")
    f.write("Filenames are slugged from the summary; the Twitter ID below is\n")
    f.write("the original `pbs.twimg.com/media/<id>`.\n\n")
    for cat in sorted(kept_by_cat):
        f.write(f"## {cat} ({len(kept_by_cat[cat])})\n\n")
        for fname, summary, img_id, sid in sorted(kept_by_cat[cat]):
            if sid:
                link = f"https://web.archive.org/web/2022*/twitter.com/SimpsonsOps/status/{sid}"
                f.write(f"- `{fname}` — {summary} (id `{img_id}`, [tweet]({link}))\n")
            else:
                f.write(f"- `{fname}` — {summary} (id `{img_id}`)\n")
        f.write("\n")
print(f"rewrote {catalog}")

# Step 6: report new category counts for README update
print("\n=== new category counts ===")
for cat in sorted(kept_by_cat, key=lambda c: -len(kept_by_cat[c])):
    print(f"  {cat}: {len(kept_by_cat[cat])}")
total = sum(len(v) for v in kept_by_cat.values())
print(f"  TOTAL: {total}")
