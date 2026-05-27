#!/usr/bin/env python3
"""
Sort each image into KEEP (Simpsons content) / DELETE (clearly not Simpsons)
/ AMBIGUOUS (needs vision re-check), based on the existing vision summary.
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

PLAN = Path("/tmp/simpsonsops/all_classifications.tsv")

# Tokens that mean "this is Simpsons content" — most Simpsons memes mention
# a character by name in the summary.
KEEP_TOKENS = [
    r"\bsimpsons?\b", r"\bhomer\b", r"\bmarge\b", r"\bbart\b", r"\blisa\b",
    r"\bmaggie\b", r"\bmr\.?\s*burns\b", r"\bsmithers\b", r"\bned\b",
    r"\bflanders\b", r"\btodd\b", r"\brod\b", r"\bkrusty\b", r"\bralph\b",
    r"\bmilhouse\b", r"\bnelson\b", r"\bapu\b", r"\bsideshow\b",
    r"\bfrink\b", r"\bmoleman\b", r"\bwiggum\b", r"\blenny\b", r"\bcarl\b",
    r"\bmoe\b", r"\bskinner\b", r"\bedna\b", r"\bkrabappel\b",
    r"\bwillie\b", r"\bgroundskeeper\b", r"\bkearney\b", r"\bjimbo\b",
    r"\bdolph\b", r"\bhutz\b", r"\bcomic\s*book\s*guy\b",
    r"\bdisco\s*stu\b", r"\bjohnny\s*tightlips\b", r"\bfat\s*tony\b",
    r"\bhibbert\b", r"\bkent\s*brockman\b", r"\bms?\s*hoover\b",
    r"\bsnake\b", r"\bgil\b", r"\bagnes\b", r"\bchalmers\b",
    r"\blyle\s*lanley\b", r"\btroy\s*mcclure\b", r"\blard\s*lad\b",
    r"\bkwik[- ]?e[- ]?mart\b", r"\bsquishee\b", r"\bduff\b",
    r"\bgrampa\b", r"\babe\s*simpson\b", r"\bevergreen\s*terrace\b",
    r"\bspringfield\b", r"\bitchy\b", r"\bscratchy\b",
    r"\bplopper\b", r"\bsea\s*captain\b", r"\bjub[- ]?jub\b",
    r"\bblinky\b", r"\bkearney\b", r"\botto\b", r"\bnahasapeemapetilon\b",
    r"\bmoe\s*szyslak\b", r"\bjasper\b", r"\bhans\s*moleman\b",
    r"\bkrustyland\b", r"\bquimby\b", r"\blenny\s*leonard\b",
    r"\bnelson\s*muntz\b", r"\bmilhouse\s*van\s*houten\b",
    r"\bhomer\s*simpson\b", r"\bbart\s*simpson\b", r"\blisa\s*simpson\b",
]

# Tokens that mean "this is NOT Simpsons" — fast trigger for deletion.
# Order matters: more specific patterns first.
DELETE_TOKENS = [
    r"\bjojo\b", r"\banime\b", r"\bweeb\b", r"\bpepe\b",
    r"\bspider[- ]?man\b", r"\bthomas the tank\b", r"\bsailor moon\b",
    r"\buno reverse\b", r"\buno card\b", r"\broll safe\b",
    r"\bmonty python\b", r"\bdoge\b", r"\bcheems\b",
    r"\bselfie\b", r"\bheadshot\b",
    r"\b(?:dog|cat|kitten|puppy|husky|poodle|terrier|bulldog|spaniel|retriever|labrador|tabby|scottie|corgi|frenchie|lab)\b",
    r"\baurora borealis\b", r"\bribeye\b", r"\bpasta\b",
    r"\bcocktail\b", r"\bwhisky\b", r"\bbabybel\b",
    r"\bcrypto\b", r"\btvot\b", r"\bandy jassy\b", r"\bfoo fighters\b",
    r"\bwinamp\b",
    r"\bphoto of\b", r"\bphotograph\b", r"\bmirror selfie\b",
    r"\bdumpster fire\b.*\bvinyl\b", r"\bvinyl figure\b",
    r"\bketchup bottle\b",
    r"\btwitter profile\b", r"\btwitter follower\b",
    r"\btwitter verif", r"\bverified checkmark\b",
    r"\bemoji\b", r"\bemoji reaction\b",
    r"\bbiden\b", r"\btrump\b", r"\bdr nicole\b", r"\bcharity majors\b",
    r"\bian coldwater\b", r"\bnora\b", r"\bquinnypig\b", r"\bcorey quinn\b",
    r"\bstallman\b", r"\bsteve yegge\b", r"\bbernie\b",
    r"\bplank\b.*ed.?edd",  # Plank from Ed Edd Eddy
    r"\bdark souls\b",
    r"\bsailor moon\b",
    r"\bwooden case\b", r"\bbeer can\b", r"\bbottle of\b",
    r"\bvans\b.*shoe", r"\bvans sneakers\b", r"\bvans shoe\b",
    r"\bevergreen ship\b", r"\bsuez canal\b",
    r"\bsign meme\b",
    r"\bspongebob\b", r"\bkrusty krab\b",  # SpongeBob, not Krusty the Clown
    r"\btoblerone\b", r"\bplane mascot\b", r"\bfan art\b",
    r"\bgraffiti\b",
    r"\bblack and white retro\b", r"\bold computer room\b",
    r"\bdocker whale\b.*sinking\b",  # generic docker imagery
    r"\bclassified picture\b",  # Lisa pointing meme might count
    r"\barchitecture diagram\b",
    r"\baws status page\b", r"\baws console\b", r"\bgrafana\b.*\bgraph\b",
    r"\bsoftbank\b",
    r"\bfacebook report dialog\b",
    r"\bgithub video\b",
    r"\bgoose illustration\b", r"\bcaped goose\b",
    r"\bjpkg\b", r"\bjudas priest\b",
    r"\bcursed simpsons fanart\b",  # fanart isn't a screenshot
    r"\bchur (brewing|squishee)\b",  # beer photo despite squishee
    r"\bnix(zusehen)?\b",
    r"\bhanging duck\b", r"\bturkeys?\b",
    r"\bguy posing\b", r"\bman hugging\b", r"\bcurly grey\b",
    r"\bdr hibbert\b.*\bsimpsons style\b",  # wait keep
    r"\bdatadog team\b", r"\bjp.?ke\b",
    r"\bnewspaper clipping\b", r"\binkblot\b",
    r"\bphoto of a pan\b", r"\bphoto of a\b", r"\btwitter status\b",
    r"\bdiagram of\b", r"\bventure capital\b",
    r"\bopen-source elasticsearch\b.*banner\b",
    r"\bcastle iron pan\b", r"\bdishwasher\b",
    r"\bfacebook\b", r"\bdomino guy\b",
    r"\bdumpster\b",
    r"\bfan recreation\b",
    r"\b(reddit|hacker news)\b",
    r"\bgift photo\b",
    r"\binkblots\b",
    r"\bswift welcoming\b",  # plane mascot
    r"\bmascot\b",
    r"\bsoftball sign-up\b",
    r"\bspider.man pointing\b",
    r"\bphoto\b.*\b(beer|pasta|food|raw|cooked|fries|sneakers|shoes|bottle|whisky|ribeye|steak|drink|cocktail|car|park|fish|chip|kangaroo)\b",
    r"\bjk simmons\b",
    r"\bblack scott\b",  # dogs photo
    r"\bthinkpad\b",  # corgi at thinkpad
    r"\bduckbill\b",  # duckbill merch photo, not simpsons
    r"\bblue check\b",  # twitter verification UI screenshot
    r"\boauth\b.*\bauth\b",  # raw IAM diagrams
    r"\biam policy\b.*\bchart\b",
    r"\boriginal tweet\b",  # screenshot of tweet
    r"\bscreenshot\b",  # generic screenshots
    r"\baudience research\b.*\bstrip\b",  # XKCD-like comic
    r"\bbart v lisa\b",  # OK these are simpsons but listed as standoff variants
]
# Note: bart v lisa IS simpsons. Don't blacklist. Remove that rule.
DELETE_TOKENS = [r for r in DELETE_TOKENS if "bart v lisa" not in r]


keep_re = re.compile("|".join(KEEP_TOKENS), re.I)
del_re = re.compile("|".join(DELETE_TOKENS), re.I)


def classify(summary):
    has_keep = bool(keep_re.search(summary))
    has_del = bool(del_re.search(summary))
    if has_keep and not has_del:
        return "KEEP"
    if has_del and not has_keep:
        return "DELETE"
    if has_keep and has_del:
        return "AMBIGUOUS_CONFLICT"
    return "AMBIGUOUS_NONE"


def main():
    rows = []
    with PLAN.open() as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                rows.append(parts[:3])

    buckets = defaultdict(list)
    for fname, cat, summary in rows:
        verdict = classify(summary)
        buckets[verdict].append((fname, cat, summary))

    for v in ("KEEP", "DELETE", "AMBIGUOUS_CONFLICT", "AMBIGUOUS_NONE"):
        print(f"\n=== {v}: {len(buckets[v])} ===")
        for fname, cat, summary in buckets[v][:15]:
            print(f"  [{cat:20s}] {summary[:80]}   ({fname})")
        if len(buckets[v]) > 15:
            print(f"  ... and {len(buckets[v]) - 15} more")

    print(f"\ntotal: {sum(len(v) for v in buckets.values())}")
    print(f"KEEP: {len(buckets['KEEP'])}  DELETE: {len(buckets['DELETE'])}  "
          f"AMBIGUOUS: {len(buckets['AMBIGUOUS_CONFLICT']) + len(buckets['AMBIGUOUS_NONE'])}")

    # Write the lists
    with open("/tmp/simpsonsops/keep.tsv", "w") as f:
        for fname, cat, summary in buckets["KEEP"]:
            f.write(f"{fname}\t{cat}\t{summary}\n")
    with open("/tmp/simpsonsops/delete.tsv", "w") as f:
        for fname, cat, summary in buckets["DELETE"]:
            f.write(f"{fname}\t{cat}\t{summary}\n")
    with open("/tmp/simpsonsops/ambiguous.tsv", "w") as f:
        for fname, cat, summary in buckets["AMBIGUOUS_CONFLICT"] + buckets["AMBIGUOUS_NONE"]:
            f.write(f"{fname}\t{cat}\t{summary}\n")


if __name__ == "__main__":
    main()
