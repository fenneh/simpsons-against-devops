#!/usr/bin/env python3
"""
Categorize @SimpsonsOps images into themed folders using tweet text + alt text.

Reads metadata.tsv (status_id\ttweet_text\talt_text\timage_ids_csv), maps each
image to one folder via keyword rules. Anything that doesn't match goes to
uncategorized/ for manual review.

Outputs: a plan TSV (image_id\tcategory\tmatched_rule\ttweet_text_excerpt)
which we then execute to copy images into final layout.
"""
import re
import sys
import csv
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).parent
META = ROOT / "metadata.tsv"
IMG_DIR = ROOT / "images"
PLAN = ROOT / "plan.tsv"

# Categories with ordered keyword rules. First match wins (so put narrow rules
# before broad ones). Word-boundary matched, case-insensitive.
# Keep folder names short, lowercase, hyphenated.
CATEGORIES = [
    ("kubernetes", [
        r"\bk8s\b", r"\bkubernetes?\b", r"\bkubectl\b", r"\bhelm\b", r"\bistio\b",
        r"\boperator pattern\b", r"\bcrd\b", r"\bcustom resource\b", r"\bservice mesh\b",
        r"\bingress\b", r"\bpod[s]?\b", r"\bdeployment\b", r"\bkubecon\b", r"\bcncf\b",
        r"\beks\b", r"\bgke\b", r"\baks\b", r"\bkube ", r"\bmemenetes\b",
    ]),
    ("aws", [
        r"\baws\b", r"\bamazon web services\b", r"\bec2\b", r"\bs3\b", r"\blambda\b",
        r"\bcloudformation\b", r"\biam\b", r"\bdynamodb\b", r"\brds\b", r"\beventbridge\b",
        r"\bcloudfront\b", r"\bcloudwatch\b", r"\bsqs\b", r"\bsns\b", r"\bfargate\b",
        r"\breinvent\b",
    ]),
    ("gcp", [
        r"\bgcp\b", r"\bgoogle cloud\b", r"\bbigquery\b", r"\bcloud run\b", r"\bgke\b",
    ]),
    ("azure", [
        r"\bazure\b", r"\bmicrosoft cloud\b", r"\bcosmos db\b",
    ]),
    ("ci-cd", [
        r"\bci/?cd\b", r"\bcontinuous (integration|deployment|delivery)\b", r"\bjenkins\b",
        r"\bcircleci\b", r"\btravis ?ci\b", r"\bgithub actions?\b", r"\bargocd\b",
        r"\bspinnaker\b", r"\bgitlab\b", r"\bbuildkite\b", r"\bpipeline\b", r"\bbuild fail",
        r"\bdeploy(s|ing|ment)?\b", r"\brollback\b", r"\bcanary\b", r"\bblue/?green\b",
    ]),
    ("on-call-incidents", [
        r"\bon[- ]?call\b", r"\bpager\b", r"\bpagerduty\b", r"\bopsgenie\b",
        r"\bvictorops\b", r"\bincident\b", r"\boutage\b", r"\bpostmortem\b",
        r"\bblameless\b", r"\bSEV[- ]?\d\b", r"\bSLA\b", r"\b3 ?am\b",
        r"\b2 ?am\b", r"\b4 ?am\b", r"\bweekend\b.*\b(page|deploy)",
    ]),
    ("observability", [
        r"\bdatadog\b", r"\bgrafana\b", r"\bprometheus\b", r"\belastic( stack|search)?\b",
        r"\bsplunk\b", r"\bsentry\b", r"\bopentelemetry\b", r"\botel\b",
        r"\btrac(e|ing)\b", r"\bmetric[s]?\b", r"\blog(ging|s)?\b", r"\bdashboard\b",
        r"\balert[s]?\b", r"\bnew ?relic\b", r"\bobservability\b", r"\bSLO\b", r"\bSLI\b",
    ]),
    ("config-yaml", [
        r"\byaml\b", r"\bhelm chart\b", r"\bansible\b", r"\bterraform\b", r"\bhcl\b",
        r"\bcloudformation template\b", r"\bjson schema\b", r"\btoml\b", r"\bdotenv\b",
        r"\bconfig file\b",
    ]),
    ("security", [
        r"\bsecurity\b", r"\bvuln(erab(le|ility))?\b", r"\bzero[- ]?day\b", r"\bcve\b",
        r"\bpentest\b", r"\boauth\b", r"\bcred(ential)?[s]?\b", r"\bsecret[s]?\b",
        r"\b\.env\b", r"\bencrypt(ion|ed)?\b", r"\bSSO\b", r"\bauth0\b", r"\bokta\b",
        r"\bSOC2\b", r"\bcompliance\b", r"\bGDPR\b", r"\blog4j\b",
    ]),
    ("databases", [
        r"\bpostgres(ql)?\b", r"\bmysql\b", r"\bmongo(db)?\b", r"\bredis\b", r"\bcassandra\b",
        r"\belasticsearch\b", r"\bschema migration\b", r"\bORM\b", r"\bSQL\b",
        r"\bdatabase\b",
    ]),
    ("languages-frameworks", [
        r"\btypescript\b", r"\bjavascript\b", r"\bgolang\b", r"\bgo lang\b", r"\bpython\b",
        r"\brust\b", r"\bjava\b", r"\bruby\b", r"\bnode(\.?js)?\b", r"\breact\b",
        r"\bnext\.?js\b", r"\bdjango\b", r"\brails\b", r"\bspring boot\b", r"\bdotnet\b",
        r"\bphp\b", r"\bperl\b", r"\bhaskell\b", r"\bbash\b", r"\bzsh\b",
    ]),
    ("microservices-architecture", [
        r"\bmicroservice[s]?\b", r"\bmonolith\b", r"\bsoa\b", r"\bservice mesh\b",
        r"\bevent[- ]driven\b", r"\bsaga pattern\b", r"\bcqrs\b", r"\bDDD\b",
        r"\bdistributed system\b",
    ]),
    ("agile-scrum-process", [
        r"\bagile\b", r"\bscrum\b", r"\bstand[- ]?up\b", r"\bretro(spective)?\b",
        r"\bsprint\b", r"\bjira\b", r"\bplanning poker\b", r"\bstory point\b",
        r"\bbacklog\b", r"\bkanban\b", r"\bOKR[s]?\b", r"\bKPI[s]?\b",
    ]),
    ("legacy-tech-debt", [
        r"\blegacy\b", r"\btech(nical)? debt\b", r"\brefactor\b", r"\bspaghetti\b",
        r"\bbig ball of mud\b", r"\bcobol\b", r"\bSOAP\b",
    ]),
    ("devs-vs-ops", [
        r"\bdev(eloper)?s? vs ops\b", r"\bworks on my machine\b", r"\bthrow it over the wall\b",
        r"\bblame\b", r"\bDevOps engineer\b", r"\bSRE\b", r"\bplatform team\b",
        r"\bdeveloper experience\b", r"\bDX\b",
    ]),
    ("hiring-jobs", [
        r"\bhiring\b", r"\binterview\b", r"\bresume\b", r"\bC[Vv]\b", r"\bleetcode\b",
        r"\bjob (search|hunt)\b", r"\bsalary\b", r"\bcomp(ensation)?\b", r"\boffer letter\b",
        r"\bquit(ting)?\b", r"\bresign\b", r"\blayoff[s]?\b", r"\bperformance review\b",
    ]),
    ("meetings-management", [
        r"\bmeeting[s]?\b", r"\bmanager\b", r"\bmiddle manag(er|ement)\b",
        r"\bone[- ]on[- ]one\b", r"\b1:1\b", r"\bskip level\b", r"\bdirector\b",
        r"\bCTO\b", r"\bVP of\b",
    ]),
    ("ai-ml", [
        r"\bAI\b", r"\bartificial intelligence\b", r"\bML\b", r"\bmachine learning\b",
        r"\bLLM\b", r"\bChatGPT\b", r"\bcopilot\b", r"\btensor(flow)?\b", r"\bpytorch\b",
        r"\bGPT-?\d\b",
    ]),
    ("open-source", [
        r"\bopen[- ]?source\b", r"\bOSS\b", r"\bmaintainer[s]?\b", r"\bcontributor[s]?\b",
        r"\bgithub issue\b", r"\bpull request\b", r"\bPR\b.*\bmerge\b", r"\blicense\b",
    ]),
    # Meta last — many tech tweets mention "meme" or "twitter" in passing;
    # only bucket here when nothing more specific matched.
    ("meta-twitter", [
        r"\bMusk\b", r"\bElon\b", r"\bblue check\b", r"\bverif",
        r"\bfollower[s]?\b", r"\bshitpost(ing)?\b",
        r"\btwitter\b", r"\bmeme[s]?\b",
    ]),
]


def compile_rules():
    compiled = []
    for cat, patterns in CATEGORIES:
        compiled.append((cat, [(p, re.compile(p, re.I)) for p in patterns]))
    return compiled


def classify(text):
    rules = compile_rules()
    for cat, patterns in rules:
        for raw, pat in patterns:
            if pat.search(text):
                return cat, raw
    return "uncategorized", ""


def main():
    if not META.exists():
        print(f"missing {META}")
        sys.exit(1)
    rows = []
    with META.open() as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            while len(parts) < 4:
                parts.append("")
            sid, text, alts, img_ids = parts[:4]
            text_blob = (text + " " + alts).strip()
            for img_id in [x for x in img_ids.split(",") if x]:
                cat, rule = classify(text_blob)
                rows.append((img_id, cat, rule, text[:140], sid))

    # Dedupe by image_id (some images appear in multiple tweets — keep first)
    seen = set()
    deduped = []
    for r in rows:
        if r[0] in seen: continue
        seen.add(r[0])
        deduped.append(r)

    with PLAN.open("w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["image_id", "category", "rule", "tweet_excerpt", "status_id"])
        for r in deduped:
            w.writerow(r)

    # Report
    counts = Counter(r[1] for r in deduped)
    print(f"total images planned: {len(deduped)}")
    for cat, n in counts.most_common():
        print(f"  {n:5d}  {cat}")


if __name__ == "__main__":
    main()
