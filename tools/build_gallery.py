#!/usr/bin/env python3
"""
Generate index.html for the simpsons-ops-archive GitHub Pages gallery.

Walks the repo for images grouped by category folder, joins each with the
vision summary + source tweet from metadata, and emits a single
self-contained HTML page with a responsive grid.
"""
import html
import os
import re
from pathlib import Path
from collections import defaultdict

REPO = Path("/root/git/simpsons-against-devops")
META = Path("/tmp/simpsonsops/metadata.tsv")
PLAN = Path("/tmp/simpsonsops/all_classifications.tsv")

# Reuse the slugger to map twitter id -> current filename
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

# Replay rename: id -> (category, current filename, summary)
classifications = []
with PLAN.open() as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 3:
            classifications.append(parts[:3])

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

# Walk the repo to find which files actually exist (post-cleanup)
existing = set()
for cat_dir in REPO.iterdir():
    if cat_dir.is_dir() and cat_dir.name not in (".git", "tools"):
        for f in cat_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                existing.add(f"{cat_dir.name}/{f.name}")

# Build per-category list of (filename, summary, img_id, tweet_link)
gallery = defaultdict(list)
for img_id, (cat, fname, summary) in id_to_file.items():
    rel = f"{cat}/{fname}"
    if rel not in existing:
        continue
    sid, _text = img_tweet.get(img_id, ("", ""))
    tweet_link = f"https://web.archive.org/web/2022*/twitter.com/SimpsonsOps/status/{sid}" if sid else ""
    gallery[cat].append((fname, summary, img_id, tweet_link))

# Order categories: meta last, otherwise by count desc
cats_ordered = sorted(gallery, key=lambda c: (c == "meta", -len(gallery[c]), c))
total = sum(len(v) for v in gallery.values())

CATEGORY_BLURB = {
    "kubernetes": "k8s, kubectl, Helm, service mesh, eBPF",
    "cloud": "AWS, GCP, Azure, Lambda, serverless, cloud cost",
    "ci-cd": "Pipelines, deploys, rollouts, build failures",
    "on-call": "Pagers, outages, incident response, postmortems",
    "observability": "Metrics, logs, tracing, SLOs",
    "security": "IAM, SSH, secrets, auth",
    "databases": "SQL, Mongo, schema migrations",
    "languages": "vim/emacs, TypeScript any, indentation",
    "config-iac": "Terraform, YAML, Helm charts",
    "microservices": "Monolith vs microservices, service mesh patterns",
    "dev-culture": "Devs vs ops, blame, code review, SRE life",
    "meetings-process": "Retros, agile, hack weeks",
    "hiring": "Recruiters, interviews, LinkedIn titles",
    "ai-ml": "Watson, ML hype",
    "open-source": "Maintainers, OSS politics",
    "legacy": "Legacy code, tech debt, systemd jokes",
    "devops-philosophy": "DevOps culture vs title, thought leaders, transformations",
    "general": "Clearly tech humour, doesn't fit a tighter bucket",
    "meta": "Account self-references, off-topic Simpsons frames, conference shoutouts",
}

HTML = []
HTML.append("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simpsons Against DevOps — image archive</title>
<meta name="description" content="{total} Simpsons memes from the deleted @SimpsonsOps Twitter account, sorted into folders.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='50' fill='%23ffd900'/%3E%3Ctext x='50' y='75' text-anchor='middle' font-family='Helvetica,Arial,sans-serif' font-weight='900' font-size='78' fill='%23000'%3ES%3C/text%3E%3C/svg%3E">
<style>
  :root {{
    color-scheme: light dark;
    --bg: #fafaf7;
    --fg: #1a1a1a;
    --muted: #666;
    --card-bg: #fff;
    --card-border: #e4e4dc;
    --accent: #ffd900;
    --link: #2563eb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #14140f;
      --fg: #e9e9e3;
      --muted: #9a9a92;
      --card-bg: #1f1f19;
      --card-border: #2d2d24;
      --link: #7aa3ff;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.5;
  }}
  header {{
    padding: 2.5rem 1.5rem 1rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: clamp(1.8rem, 4vw, 2.6rem);
    margin: 0 0 0.5rem;
    letter-spacing: -0.02em;
  }}
  h1 .yellow {{ color: #ffd900; }}
  .lede {{
    font-size: 1.05rem;
    color: var(--muted);
    max-width: 720px;
    margin: 0 0 1rem;
  }}
  .lede a {{ color: var(--link); }}
  .quote {{
    background: var(--card-bg);
    border-left: 3px solid var(--accent);
    padding: 0.75rem 1rem;
    margin: 1rem 0 1.5rem;
    max-width: 720px;
    font-size: 0.95rem;
    color: var(--muted);
  }}
  .quote strong {{ color: var(--fg); }}
  nav {{
    padding: 0.75rem 1.5rem;
    max-width: 1400px;
    margin: 0 auto;
    border-top: 1px solid var(--card-border);
    border-bottom: 1px solid var(--card-border);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 10;
  }}
  nav ul {{
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    font-size: 0.9rem;
  }}
  nav a {{ color: var(--fg); text-decoration: none; }}
  nav a:hover {{ color: var(--link); }}
  nav .count {{ color: var(--muted); font-size: 0.8em; }}
  section.cat {{
    padding: 2rem 1.5rem 1rem;
    max-width: 1400px;
    margin: 0 auto;
    scroll-margin-top: 60px;
  }}
  section.cat h2 {{
    font-size: 1.3rem;
    margin: 0 0 0.25rem;
    letter-spacing: -0.01em;
  }}
  section.cat .blurb {{
    color: var(--muted);
    font-size: 0.9rem;
    margin: 0 0 1rem;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 1rem;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 80ms ease, box-shadow 80ms ease;
  }}
  .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
  }}
  .card .img-link {{ display: block; }}
  .card img {{
    width: 100%;
    height: auto;
    display: block;
    background: #ddd;
  }}
  .card .cap {{
    padding: 0.6rem 0.75rem 0.75rem;
    font-size: 0.83rem;
    color: var(--muted);
    line-height: 1.35;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }}
  .card .cap .text {{ color: var(--muted); }}
  .card .cap .tweet {{
    color: var(--link);
    text-decoration: none;
    font-size: 0.78rem;
    align-self: flex-start;
  }}
  .card .cap .tweet:hover {{ text-decoration: underline; }}
  .lightbox {{
    border: none;
    padding: 0;
    background: transparent;
    max-width: none;
    max-height: none;
    margin: auto;
    color: #fff;
    overflow: visible;
  }}
  .lightbox::backdrop {{
    background: rgba(0, 0, 0, 0.92);
    backdrop-filter: blur(4px);
  }}
  .lightbox img {{
    display: block;
    max-width: 92vw;
    max-height: 82vh;
    margin: 0 auto;
    border-radius: 4px;
    background: #222;
  }}
  .lightbox .lb-cap {{
    margin: 0.85rem auto 0;
    text-align: center;
    font-size: 0.9rem;
    max-width: 80ch;
    color: rgba(255, 255, 255, 0.85);
    line-height: 1.4;
  }}
  .lightbox .lb-cap a {{
    display: inline-block;
    margin-top: 0.4rem;
    color: #ffd900;
    text-decoration: none;
    font-size: 0.85rem;
  }}
  .lightbox .lb-cap a:hover {{ text-decoration: underline; }}
  .lightbox .close {{
    position: fixed;
    top: 0.75rem;
    right: 1rem;
    background: transparent;
    border: none;
    color: #fff;
    font-size: 2.2rem;
    cursor: pointer;
    line-height: 1;
    padding: 0.25rem 0.6rem;
    opacity: 0.7;
  }}
  .lightbox .close:hover {{ opacity: 1; }}
  footer {{
    padding: 2rem 1.5rem;
    max-width: 1400px;
    margin: 0 auto;
    color: var(--muted);
    font-size: 0.85rem;
    border-top: 1px solid var(--card-border);
  }}
  footer a {{ color: var(--link); }}
</style>
</head>
<body>
<header>
  <h1>Simpsons Against <span class="yellow">DevOps</span></h1>
  <p class="lede">
    <strong>{total}</strong> Simpsons memes by
    <a href="https://bsky.app/profile/simpsonsops.dev">@simpsonsops.dev</a>.
    The original
    <a href="https://web.archive.org/web/2022*/twitter.com/SimpsonsOps">@SimpsonsOps</a>
    Twitter account got nuked post-Musk, so these came out of the Wayback
    Machine and got sorted into folders by topic.
  </p>
  <div class="quote">
    From a DM with the creator, May 2021:<br>
    <strong>Me:</strong> Would you object to a github repo containing all the images within themed folders?<br>
    <strong>Them:</strong> Definitely feel free to set up a GitHub repo though. I'd only ask that the images also link back to any relevant tweets if it's not too much of a hassle.
  </div>
</header>
<nav><ul>
""".format(total=total))

for cat in cats_ordered:
    HTML.append(f'<li><a href="#{cat}">{cat} <span class="count">{len(gallery[cat])}</span></a></li>\n')

HTML.append("</ul></nav>\n")

for cat in cats_ordered:
    blurb = CATEGORY_BLURB.get(cat, "")
    HTML.append(f'<section class="cat" id="{cat}">\n')
    HTML.append(f'  <h2>{cat} <span style="color:var(--muted);font-weight:400;">({len(gallery[cat])})</span></h2>\n')
    if blurb:
        HTML.append(f'  <p class="blurb">{html.escape(blurb)}</p>\n')
    HTML.append('  <div class="grid">\n')
    for fname, summary, img_id, tweet_link in sorted(gallery[cat]):
        src = f"{cat}/{fname}"
        cap = html.escape(summary)
        HTML.append('    <div class="card">\n')
        HTML.append(f'      <a class="img-link" href="{src}"><img src="{src}" loading="lazy" alt="{cap}"></a>\n')
        HTML.append('      <div class="cap">\n')
        HTML.append(f'        <span class="text">{cap}</span>\n')
        if tweet_link:
            HTML.append(f'        <a class="tweet" href="{tweet_link}" target="_blank" rel="noopener">→ source tweet</a>\n')
        HTML.append('      </div>\n')
        HTML.append('    </div>\n')
    HTML.append('  </div>\n')
    HTML.append('</section>\n')

HTML.append(f"""<footer>
  {total} images across {len(cats_ordered)} folders. Images by
  <a href="https://bsky.app/profile/simpsonsops.dev">@simpsonsops.dev</a>.
  Repo: <a href="https://github.com/fenneh/simpsons-against-devops">github.com/fenneh/simpsons-against-devops</a>.
</footer>
<dialog id="lb" class="lightbox" aria-label="Image viewer">
  <button class="close" type="button" aria-label="Close">&times;</button>
  <img id="lb-img" alt="">
  <div class="lb-cap">
    <span id="lb-text"></span><br>
    <a id="lb-tweet" target="_blank" rel="noopener">&rarr; source tweet</a>
  </div>
</dialog>
<script>
(function() {{
  var dlg = document.getElementById('lb');
  if (!dlg || !dlg.showModal) return;
  var img = document.getElementById('lb-img');
  var text = document.getElementById('lb-text');
  var tweet = document.getElementById('lb-tweet');
  document.querySelectorAll('.card').forEach(function(card) {{
    var link = card.querySelector('.img-link');
    if (!link) return;
    link.addEventListener('click', function(e) {{
      e.preventDefault();
      img.src = link.getAttribute('href');
      var txt = card.querySelector('.text').textContent;
      img.alt = txt;
      text.textContent = txt;
      var t = card.querySelector('.tweet');
      if (t) {{
        tweet.href = t.href;
        tweet.style.display = '';
      }} else {{
        tweet.style.display = 'none';
      }}
      dlg.showModal();
    }});
  }});
  dlg.addEventListener('click', function(e) {{
    if (e.target === dlg) dlg.close();
  }});
  document.querySelector('.lightbox .close').addEventListener('click', function() {{
    dlg.close();
  }});
}})();
</script>
</body>
</html>
""")

out = REPO / "index.html"
out.write_text("".join(HTML))
print(f"wrote {out} — {total} images across {len(cats_ordered)} categories")

# .nojekyll so Pages serves folders starting with anything (including ai-ml etc.)
nojekyll = REPO / ".nojekyll"
nojekyll.write_text("")
print(f"wrote {nojekyll}")
