# simpsons-against-devops

239 Simpsons memes posted by the **Simpsons Against DevOps** Twitter account
([@SimpsonsOps](https://web.archive.org/web/2022*/twitter.com/SimpsonsOps)),
pulled out of the Wayback Machine after the account got nuked from Twitter
post-Musk.

The creator is on Bluesky now: https://bsky.app/profile/simpsonsops.dev

**Gallery:** https://fenneh.github.io/simpsons-against-devops/

## Permission

Posted with explicit permission. From a DM exchange on 14 May 2021:

> **Me:** Hey, big fan of your work. Would you object to a github repo
> containing all the images within themed folders e.g. k8s?
>
> **Them:** Hey, thanks! I started a little side project to get a static
> site hosted with a bunch of taxonomy and whatnot but I've been lazy
> lately. Definitely feel free to set up a GitHub repo though. I'd only
> ask that the images also link back to any relevant tweets if it's not
> too much of a hassle.

Every image in the gallery links back to the Wayback snapshot of the
original tweet.

## What's in here

239 Simpsons images sorted by topic. Each filename is slugged from a one-line
vision summary so you can read what's in the image without opening it.

| Folder | Count | What's in it |
| --- | --- | --- |
| `meta/` | 69 | Account self-references, Simpsons frames with no specific tech bucket, off-topic Simpsons references |
| `on-call/` | 24 | Pagers, outages, incident response, postmortems |
| `dev-culture/` | 21 | Devs vs ops, blame, code review, SRE life |
| `devops-philosophy/` | 21 | "Is DevOps a culture or a title", thought leaders, transformations |
| `kubernetes/` | 12 | k8s, kubectl, Helm, service mesh, eBPF |
| `cloud/` | 12 | AWS, GCP, Azure, Lambda, serverless, cost economics |
| `ci-cd/` | 11 | Pipelines, deploys, rollouts, build failures |
| `general/` | 10 | Clearly tech humour that didn't fit a tighter bucket |
| `languages/` | 8 | vim/emacs, TypeScript any, indentation jokes |
| `config-iac/` | 8 | Terraform, YAML, Helm charts |
| `security/` | 8 | IAM, SSH, secrets, auth |
| `observability/` | 7 | Metrics, logs, tracing, SLOs |
| `legacy/` | 6 | Legacy code, tech debt, systemd jokes |
| `microservices/` | 6 | Monolith vs microservices, service mesh patterns |
| `meetings-process/` | 5 | Retros, agile, hack weeks |
| `hiring/` | 4 | Recruiters, interviews, LinkedIn titles |
| `open-source/` | 3 | Maintainers, OSS politics, CentOS drama |
| `databases/` | 2 | SQL, Mongo |
| `ai-ml/` | 2 | Watson, ML hype |

`CATALOG.md` has the full per-image summary and a link to the Wayback snapshot
of the original tweet.

## How it was rebuilt

1. Queried the Wayback CDX API for snapshots of `twitter.com/SimpsonsOps/*`
   and `x.com/SimpsonsOps/*`, about 1267 unique tweet IDs
2. Fetched each archived tweet page, pulled out `pbs.twimg.com/media/...` URLs
   and the tweet text
3. Downloaded the original-resolution image straight from `pbs.twimg.com`.
   Twitter's media CDN is content-addressed so the images still serve even
   when the account is gone. For the ~9% that 404'd on pbs, grabbed the
   archived copy from Wayback instead
4. Ran every image through Claude vision twice: once to summarise and bucket
   into a topic, then a second pass with a yellow-skin / Simpsons-frame yes/no
   filter to drop non-Simpsons content (other meme formats, real photos,
   product shots, conference promos)

417 of 422 unique image URLs recovered; 239 of those turned out to be actual
Simpsons content and stayed.

Scripts in `tools/`. The TSV intermediates aren't in git but are reproducible.

## License

Images are by [@simpsonsops.dev](https://bsky.app/profile/simpsonsops.dev) and
aren't relicensed. Scripts in `tools/` are MIT.
