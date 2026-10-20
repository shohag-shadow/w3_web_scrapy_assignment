# Books to Scrape — Random Book Sampler

A Scrapy spider that samples 5–10 random categories from
[books.toscrape.com](https://books.toscrape.com/), takes up to 5 books
from each, and exports the results as JSON, CSV, XML, and SQLite. Runs
locally or as a containerised Scrapyd service.

---

## Project Overview

The site is a public scraping sandbox: a homepage with 50 category
links, each category paginated across 1–4 listing pages, each listing
page linking to book detail pages carrying title, price, availability
and cover image.

The spider deliberately samples rather than exhausts: **5–10 random
categories**, **up to 5 books per category**. A full run is ~1–2
minutes. .

---

## Features

- Three-stage spider: `parse` → `parse_category` → `parse_book`
- Optional `seed` for reproducible sampling
- Three pipelines: clean → validate → store
- Four output formats: `books.json`, `books.csv`, `books.xml`, `books.db`
- Same `settings.py` works locally and in Docker via `DATA_DIR`
- Containerised Scrapyd daemon with the egg baked in
- `scrapyd-deploy` support for redeploying without rebuilding
- `test.sh` schedules a crawl, waits, and copies the results

---

## Tech Stack

| Layer | Tool | Version |
|---|---|---|
| Language | Python | 3.12 |
| Crawl framework | Scrapy | 2.19 |
| Job server | Scrapyd | latest |
| Packaging | scrapyd-client | latest |
| Containers | Docker Compose | v2 |
| Storage | SQLite (stdlib) | bundled |

---

## Installation Guide

```bash
git clone https://github.com/shohag-shadow/w3_web_scrapy_assignment.git
cd w3_web_scrapy_assignment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Verify:

```bash
scrapy list      # -> books
```

Empty output means `SPIDER_MODULES` in `settings.py` doesn't match the
package folder. `ModuleNotFoundError: tutorial` means a leftover import
still references the scaffold name.

---

## Environment Setup

Two optional environment variables, both with safe defaults:

| Variable | Default | Purpose |
|---|---|---|
| `DATA_DIR` | `.` | Where the four output files go. Compose sets it to `/var/lib/scrapyd` (the mounted volume). |
| `TZ` | `UTC` | Log timestamp timezone. |

No `.env` file is used. `settings.py` resolves paths from `DATA_DIR`:

```python
DATA_DIR = os.environ.get("DATA_DIR", ".")
DATABASE_PATH = os.path.join(DATA_DIR, "books.db")
FEEDS = {
    os.path.join(DATA_DIR, "books.json"): {...},
    os.path.join(DATA_DIR, "books.csv"):  {...},
    os.path.join(DATA_DIR, "books.xml"):  {...},
}
```

---

## Running the Spider

```bash
scrapy crawl books 
```

| Argument | Effect |
|---|---|
| `-a seed=42` | Reproducible random choices |
| `-a start_url=…` | Different starting page |
| `-s LOG_LEVEL=DEBUG` | Verbose logging |

Output lands in the current directory (`DATA_DIR="."`): `books.json`,
`books.csv`, `books.xml`, `books.db`. Runtime: ~1–2 min with the default
`DOWNLOAD_DELAY = 1` and `CONCURRENT_REQUESTS_PER_DOMAIN = 1`.

Verify all four agree:

```bash
python -c "import json; print(len(json.load(open('books.json'))))"
tail -n +2 books.csv | wc -l
grep -c "<item>" books.xml
sqlite3 books.db "SELECT COUNT(*) FROM books;"
```

---

## Docker Setup Guide

Files: `Dockerfile` (build egg + install Scrapyd), `docker-compose.yml`
(daemon, volume, `DATA_DIR`), `scrapyd.conf` (bind address, ports,
directories), `.dockerignore` (keeps `.venv/` and outputs out of the
image).

```bash
docker compose up -d --build
docker compose ps                                  # wait for (healthy)
curl http://localhost:6800/daemonstatus.json       # {"status":"ok",...}
```

The egg is baked into the image, so the spider is ready immediately:

```bash
curl "http://localhost:6800/listspiders.json?project=w3_web_scrapy_assignment"
# {"status": "ok", "spiders": ["books"]}
```

Schedule a crawl:

```bash
curl http://localhost:6800/schedule.json \
     -d project=w3_web_scrapy_assignment -d spider=books -d seed=42
```

Results appear in `./scrapyd-data/books.*` (the volume mount) once the
job finishes. `./test.sh` automates the whole schedule → wait → copy
cycle and drops the files into `./results-YYYY-MM-DD_HH-MM-SS/`
alongside the job log.

Shut down: `docker compose down`.

---

## Scrapyd Deployment Guide

Two deployment paths exist:

**1. Baked-in egg (automatic).** The `Dockerfile` builds the egg at
image-build time and installs it into `/src/eggs/`. `docker compose up
-d --build` is enough — no extra step.

**2. `scrapyd-deploy` (for code changes without a rebuild).** Push a
new egg to the running container:

```bash
pip install scrapyd-client     # once
scrapyd-deploy                 # from the project root
```

Requires `setup.py` (present) and the `[deploy:default]` section in
`scrapy.cfg`:

```ini
[deploy:default]
url = http://localhost:6800/
project = w3_web_scrapy_assignment
```

Note the `:default` suffix on the section name — bare `[deploy]` fails
on recent `scrapyd-client` versions with `Unknown target: default`.

Confirm both eggs exist:

```bash
curl "http://localhost:6800/listversions.json?project=w3_web_scrapy_assignment"
# {"status": "ok", "versions": ["1", "1.0"]}
```

`"1"` is the baked-in egg; `"1.0"` is the one just pushed. Scrapyd
picks the highest version on the next `schedule.json` call.

**API endpoints.**

| Endpoint | Purpose |
|---|---|
| `GET /daemonstatus.json` | Liveness |
| `GET /listprojects.json` | Registered projects |
| `GET /listspiders.json?project=…` | Spiders in a project |
| `POST /schedule.json` | Start a crawl |
| `GET /listjobs.json?project=…` | `pending` / `running` / `finished` |
| `GET /status.json?project=…&jobid=…` | One job's state |
| `POST /cancel.json` | Cancel a job |

Logs: `/var/lib/scrapyd/logs/{project}/{spider}/{jobid}.log`
(host: `./scrapyd-data/logs/…`).

---

## Output Format Description

All four formats share six fields:

| Field | Type | Example |
|---|---|---|
| `title` | string | `A Light in the Attic` |
| `price` | float | `51.77` |
| `availability` | boolean | `true` |
| `product_url` | absolute URL | `https://books.toscrape.com/catalogue/…` |
| `image_url` | absolute URL | `https://books.toscrape.com/media/…` |
| `category` | string | `Poetry` |

```json
[{"title":"A Light in the Attic","price":51.77,"availability":true,
  "product_url":"https://books.toscrape.com/…","image_url":"https://books.toscrape.com/…",
  "category":"Poetry"}]
```

```csv
title,price,availability,product_url,image_url,category
A Light in the Attic,51.77,True,https://…,https://…,Poetry
```

```xml
<items><item><title>A Light in the Attic</title><price>51.77</price>
<availability>True</availability><product_url>…</product_url>
<image_url>…</image_url><category>Poetry</category></item></items>
```

CSV column order follows the field declaration order in `items.py`.

---

## Database Configuration

| Setting | Location | Value |
|---|---|---|
| `DATABASE_PATH` | `settings.py` | `os.path.join(DATA_DIR, "books.db")` |
| Backend | — | SQLite (stdlib) |
| Reset mode | `SQLitePipeline.open_spider` | Creates the table if missing, **empties it** each run |
| Constraint | schema | `product_url` is `UNIQUE`; duplicates become `DropItem` |

```sql
CREATE TABLE books (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    price        REAL    NOT NULL,
    availability INTEGER NOT NULL,
    product_url  TEXT    NOT NULL UNIQUE,
    image_url    TEXT    NOT NULL,
    category     TEXT    NOT NULL
);
```

Emptied on `open_spider` so the database and the three feed files always
describe **the same single run**. For history, remove the
`DELETE FROM books` line and add a `run_id` column.

---

## Architecture Diagram

```
books.toscrape.com
       │
       ▼
   parse()                      discover all 50 categories,
       │                        shuffle, pick 5–10
       ▼
   parse_category()             accumulate book links page by page,
       │                        follow "next", then sample ≤5 URLs
       ▼
   parse_book()                 extract 6 fields → BookItem
       │
       ▼
   ┌─── Pipelines (100 → 200 → 300) ─────────────────────────┐
   │ 100 CleaningPipeline     trim, "£51.77" → 51.77, bool    │
   │ 200 ValidationPipeline   drop empty / negative / relative│
   │ 300 SQLitePipeline       INSERT INTO books …             │
   └────────────────────────────┬────────────────────────────┘
                                ▼
             FEEDS → books.json, books.csv, books.xml
```

---

## Folder Structure

```
w3_web_scrapy_assignment/
├── scrapy.cfg                     # project marker + [deploy:default]
├── setup.py                       # required by scrapyd-deploy
├── Dockerfile                     # multi-stage: egg, then Scrapyd
├── docker-compose.yml             # port 6800, volume, DATA_DIR
├── scrapyd.conf                   # bind address, ports, directories
├── .dockerignore                  # keep .venv/, outputs out of image
├── requirements.txt
├── test.sh                        # schedule + wait + copy
├── README.md
│
├── w3_web_scrapy_assignment/      # Python package
│   ├── items.py                   # BookItem
│   ├── pipelines.py               # Cleaning, Validation, SQLite
│   ├── settings.py                # settings + DATA_DIR logic
│   └── spiders/books.py           # BooksSpider
│
└── (generated)
    ├── books.{json,csv,xml,db}
    ├── scrapyd-data/              # volume mount
    └── results-*/                 # snapshots from test.sh
```

---

## Design Decisions

1. **Three parse methods, not many helpers.** They mirror the site's
   homepage → listing → detail structure. Folding helpers in trades one
   duplicated "skip bad category" branch for a top-to-bottom reading
   flow.
2. **`cb_kwargs` for state.** Each request carries `category` and
   `book_urls` via `cb_kwargs`, keeping callback signatures explicit
   and avoiding collisions with Scrapy's own `response.meta` keys.
   `book_urls` is copied per request, so concurrent jobs can't corrupt
   each other.
3. **Absolute paths via `DATA_DIR`.** Scrapyd runs each job in a temp
   directory that's deleted on finish, so relative paths vanish.
   `DATA_DIR=/var/lib/scrapyd` in Docker, `"."` locally. Chosen over
   auto-detecting with `os.path.isdir` because explicit beats implicit.
4. **Pipeline order 100 → 200 → 300.** Clean must precede validate
   (`"£51.77" < 0` fails); SQLite runs last so dirty rows never reach
   the database. Feed exporters run **after** all pipelines, so a
   `DropItem` also excludes the item from JSON/CSV/XML — the four
   outputs stay identical.
5. **`FEEDS` handles file export, not a pipeline.** Scrapy's built-in
   exporters already cover JSON/CSV/XML with `overwrite`, `encoding`,
   and `indent`. Writing those formats from a pipeline duplicates work.
6. **Egg baked into the image, with `scrapyd-deploy` as an escape
   hatch.** Baking the egg makes the spider runnable right after
   `docker compose up -d --build`, no deploy step. `setup.py` and
   `[deploy:default]` in `scrapy.cfg` keep the standard
   `scrapyd-deploy` path working too, so post-build code changes
   don't require a full image rebuild.
7. **"Take what's available", not "replace what's short".** Categories
   with fewer than 5 books yield all of them; failed categories are
   skipped. An earlier design kept spare categories and swapped them
   in, which promised "exactly 5" but made output volume depend on
   retries. Removing it made "5" an honest *cap*, not a target.

---

## Known Limitations

1. **`seed` does not guarantee identical output.** `parse_category`
   runs in network-completion order, so categories consume the shared
   RNG in different orders across runs. Per-category seeding
   (`random.Random(hash(name))`) would fix it.

2. **Variable output volume.** ~15–50 items, depending on how many
   categories were chosen and how many books each had.

3. **Feed files only written on clean termination.** JSON/XML close
   their tags on `finish_reason == 'finished'`; a cancelled or crashed
   job may leave them missing or truncated while `books.db` still has
   partial data. A surviving database doesn't imply the feeds succeeded.
4. **Scrapyd runs as root.** Files in `scrapyd-data/` are root-owned.
   Delete with `docker compose exec scrapyd rm …` (no `sudo` needed).
5. **`scrapyd.conf` changes require a rebuild.** It's copied into the
   image at build time; no runtime reload.
6. **Locale-dependent price parsing.** `clean_price` assumes
   dot-decimals. A `1.234,56` (comma-decimal) price would be misparsed.
   Fine for this site; breaks if ported.
7. **Single-domain assumption.** `allowed_domains` is derived from
   `start_url`; pointing at a different host yields empty results
   (OffsiteMiddleware blocks it). Remove or update `allowed_domains`.
8. **Docker build cache can hide egg staleness.** If a rebuild seems
   to have no effect, `docker compose build --no-cache` forces a clean
   build before concluding the code is wrong.