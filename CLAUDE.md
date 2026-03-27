# NewsBot — CLAUDE.md

## Project Overview

NewsBot is a personal news aggregator agent. It fetches articles from RSS feeds, evaluates
relevance using a local Ollama model, and emails a daily digest of relevant articles.
Three independent services are orchestrated by a single `main.py` entry point.

**V1 Scope: Personal prototype only. No UI, no multi-user, no auth.**

---

## Architecture

### Services

| Script | Role |
|---|---|
| `fetcher.py` | Polls RSS feeds, extracts full article text, stores to DB |
| `evaluator.py` | Sends pending articles to Ollama, stores relevance + summary + tags |
| `mailer.py` | Compiles and sends daily digest of relevant unsent articles |
| `main.py` | Chains all three in sequence — called by cron |

Each service is independently runnable from the CLI:

```bash
python fetcher.py      # fetch only
python evaluator.py    # evaluate pending articles only
python mailer.py       # send today's digest only
python main.py         # full pipeline (cron entry point)
```

### Flow

```
main.py
  └── fetcher.py
        - reads sources table
        - parses RSS via feedparser
        - falls back to requests scrape if no RSS
        - extracts full text via trafilatura
        - deduplicates by URL
        - stores articles with status: pending
  └── evaluator.py
        - pulls all status: pending articles
        - loops through as batch, sends each to Ollama
        - stores: is_relevant, summary, tags, status: evaluated
        - on Ollama failure: status: error, continue
  └── mailer.py
        - pulls is_relevant=true, emailed_at IS NULL, fetched today
        - groups by tags
        - sends digest email via Gmail SMTP
        - sets emailed_at on sent articles
```

---

## Database Schema (MariaDB)

### `sources` table

```sql
CREATE TABLE sources (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    feed_url        VARCHAR(512),
    site_url        VARCHAR(512) NOT NULL,
    active          BOOLEAN DEFAULT TRUE,
    scrape_fallback BOOLEAN DEFAULT FALSE
);
```

### `articles` table

```sql
CREATE TABLE articles (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    url          VARCHAR(1024) NOT NULL UNIQUE,
    title        VARCHAR(512),
    source_name  VARCHAR(255),
    published_at DATETIME,
    fetched_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    full_text    LONGTEXT,
    status       ENUM('pending', 'evaluated', 'error') DEFAULT 'pending',
    is_relevant  BOOLEAN,
    summary      TEXT,
    tags         JSON,
    emailed_at   DATETIME
);
```

---

## Initial Source Seed Data

Insert these into the `sources` table on first run. All are RSS-native.

```sql
-- Security
INSERT INTO sources (name, feed_url, site_url) VALUES
('Krebs on Security',   'https://krebsonsecurity.com/feed',                      'https://krebsonsecurity.com'),
('Schneier on Security','https://www.schneier.com/feed/atom',                    'https://www.schneier.com'),
('BleepingComputer',    'https://www.bleepingcomputer.com/feed',                 'https://www.bleepingcomputer.com'),
('The Hacker News',     'https://feeds.feedburner.com/TheHackersNews',           'https://thehackernews.com'),
('CISA Alerts',         'https://www.cisa.gov/cybersecurity-advisories/all.xml', 'https://www.cisa.gov');

-- Docker / Containers / Cloud
INSERT INTO sources (name, feed_url, site_url) VALUES
('Docker Blog',         'https://www.docker.com/blog/feed',   'https://www.docker.com/blog'),
('The New Stack',       'https://thenewstack.io/feed',        'https://thenewstack.io'),
('CNCF Blog',           'https://www.cncf.io/feed',           'https://www.cncf.io/blog');

-- Virtualization / Infrastructure / Homelab
INSERT INTO sources (name, feed_url, site_url) VALUES
('Scott Lowe Blog',     'https://feeds.scottlowe.org/slowe/content/feed', 'https://blog.scottlowe.org'),
('Proxmox Blog',        'https://www.proxmox.com/en/news/feed',           'https://www.proxmox.com/en/news'),
('ServeTheHome',        'https://www.servethehome.com/feed',              'https://www.servethehome.com');

-- AI
INSERT INTO sources (name, feed_url, site_url) VALUES
('Ars Technica Tech Lab','https://feeds.arstechnica.com/arstechnica/technology-lab', 'https://arstechnica.com'),
('MIT Tech Review',      'https://www.technologyreview.com/feed',                    'https://www.technologyreview.com'),
('The Gradient',         'https://thegradient.pub/rss',                              'https://thegradient.pub');

-- General / Catch-all
INSERT INTO sources (name, feed_url, site_url) VALUES
('Hacker News',         'https://hnrss.org/frontpage',                          'https://news.ycombinator.com'),
('Ars Technica',        'https://feeds.arstechnica.com/arstechnica/index',      'https://arstechnica.com');
```

---

## Tech Stack

| Concern | Library |
|---|---|
| RSS parsing | `feedparser` |
| Article text extraction | `trafilatura` |
| HTTP scraping fallback | `requests` + `beautifulsoup4` |
| Database ORM | `sqlalchemy` + `pymysql` |
| Ollama inference | `ollama` (official Python client) |
| Email | `smtplib` (stdlib) |
| Config / secrets | `python-dotenv` |

---

## Environment Variables (`.env`)

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=newsbot
DB_USER=newsbot
DB_PASSWORD=

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral-small:24b

GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
DIGEST_RECIPIENT=

ARTICLE_MAX_AGE_HOURS=24
```

---

## Ollama Evaluator Prompt Design

The evaluator sends each article as a single user message. The system prompt encodes
the interest profile. The model must return valid JSON only — no preamble, no markdown.

**System prompt:**
```
You are a technical news relevance filter. Your job is to decide whether an article
is relevant to the following interest areas: cybersecurity, vulnerabilities, security
advisories, Docker, containers, cloud infrastructure, virtualization, Proxmox, homelab,
AI, machine learning, and LLMs.

Respond ONLY with a valid JSON object in this exact format:
{"relevant": true/false, "summary": "2-3 sentence summary if relevant, empty string if not", "tags": ["tag1", "tag2"]}

Do not include any text outside the JSON object.
```

**User message:**
```
Title: {article.title}

{article.full_text}
```

---

## Error Handling Rules

- Fetcher: if RSS parse fails for a source, log and continue to next source
- Fetcher: if `trafilatura` returns no text, attempt `requests` + `bs4` fallback; if still empty, store article with `full_text: null` and `status: error`
- Evaluator: if Ollama call fails or returns non-JSON, mark article `status: error`, log, continue
- Evaluator: if `is_relevant` key missing from JSON response, treat as `relevant: false`
- Mailer: if no relevant articles exist for today, log and exit cleanly — do not send empty email

---

## Development Order

Build and verify in this order. Do not proceed to the next service until the current
one is working end-to-end.

1. **Database setup** — create DB, tables, seed sources
2. **`fetcher.py`** — RSS parsing, text extraction, DB insert, deduplication
3. **`evaluator.py`** — Ollama integration, batch loop, DB update
4. **`mailer.py`** — digest composition, email send, emailed_at update
5. **`main.py`** — chain all three, top-level error handling

---

## Out of Scope for V1

- Web UI of any kind
- Multi-user support or interest profiles
- Source management outside of direct DB edits
- Different cron schedules per service
- File-based logging
- Claude API — local Ollama only