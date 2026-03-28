# NewsBot — CLAUDE.md

## Project Overview

NewsBot is a personal news aggregator agent. It fetches articles from RSS feeds, evaluates
relevance using a local Ollama model, and emails a daily digest of relevant articles.
Three independent services are orchestrated by a single `main.py` entry point.

**V1 Scope: Personal prototype only. No UI, no multi-user, no auth.**
**V1 Status: Complete.**

---

## Architecture

### Services

| Script | Role |
|---|---|
| `fetcher.py` | Polls RSS feeds, extracts full article text, stores to DB |
| `evaluator.py` | Sends pending articles to Ollama, stores relevance + summary + tags |
| `mailer.py` | Compiles and sends daily digest of relevant unsent articles |
| `main.py` | Chains all services in sequence — called by cron |
| `cleanup.py` | Removes old / irrelevant / error articles per env var settings |
| `setup_db.py` | One-time DB init: creates database, tables, seeds sources |
| `db.py` | Shared SQLAlchemy engine, session factory, and ORM models |

Each service is independently runnable from the CLI:

```bash
python fetcher.py      # fetch only
python evaluator.py    # evaluate pending articles only
python mailer.py       # send today's digest only
python main.py         # full pipeline (cron entry point)
python cleanup.py      # housekeeping run
```

### Pipeline Flow

```
main.py
  └── cleanup.py (force_error=True)
        - purges status=error articles before pipeline runs
  └── fetcher.py
        - reads active sources from sources table
        - parses RSS via feedparser
        - skips entries older than 24h (published_at cutoff, hardcoded)
        - extracts full text via trafilatura
        - falls back to requests + bs4 if trafilatura returns nothing
        - deduplicates by URL (pre-insert query + UNIQUE constraint safety net)
        - stores articles with status: pending
        - on total text extraction failure: stores full_text=null, status=error
  └── evaluator.py
        - pulls all status=pending articles
        - sends each to Ollama /api/generate with system prompt + article text
        - strips markdown fences / preamble from response before JSON parse
        - stores: is_relevant, summary, tags, status=evaluated
        - on Ollama failure or non-JSON response: status=error, log, continue
        - if is_relevant key missing from JSON: treated as relevant=false
  └── mailer.py
        - pulls is_relevant=true, emailed_at IS NULL, fetched within ARTICLE_MAX_AGE_HOURS
        - groups articles by first tag (title-cased), untagged → "General"
        - sends HTML + plaintext multipart digest via Gmail SMTP (port 587, STARTTLS)
        - From: GMAIL_FROM (alias), authenticated as GMAIL_LOGIN
        - sets emailed_at on all sent articles only after successful send
        - if no relevant articles: log and exit cleanly, no email sent
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

Note: `full_text` must be `LONGTEXT` — `TEXT` (64KB) is too small for some articles.
If upgrading an existing install: `ALTER TABLE articles MODIFY full_text LONGTEXT;`

---

## Seeded Sources

Managed in `setup_db.py`. Seed is idempotent — skips sources that already exist by name.

| Category | Source |
|---|---|
| Security | Krebs on Security, Schneier on Security, BleepingComputer, The Hacker News, CISA Alerts |
| Docker / Cloud | Docker Blog, The New Stack, CNCF Blog |
| Infra / Homelab | Scott Lowe Blog, Proxmox Announcements, ServeTheHome |
| AI | Ars Technica Tech Lab, MIT Tech Review, The Gradient |
| General | Hacker News, Ars Technica |

To add or disable sources, edit the `sources` table directly.

---

## Tech Stack

| Concern | Library |
|---|---|
| RSS parsing | `feedparser` |
| Article text extraction | `trafilatura` |
| HTTP scraping fallback | `requests` + `beautifulsoup4` |
| Database ORM | `sqlalchemy` + `pymysql` |
| Ollama inference | `ollama` (official Python client) — uses `/api/generate` |
| Email | `smtplib` (stdlib) |
| Config / secrets | `python-dotenv` |

---

## Environment Variables (`.env`)

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=news_bot
DB_USER=newsbot
DB_PASSWORD=

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral-small:24b

GMAIL_LOGIN=                   # Gmail account used to authenticate
GMAIL_APP_PASSWORD=            # App Password for GMAIL_LOGIN
GMAIL_FROM=                    # From: address (can be a Send-As alias)
DIGEST_RECIPIENT=              # Address to deliver the digest to

ARTICLE_MAX_AGE_HOURS=24       # Mailer lookback window
ARTICLE_RETENTION_DAYS=30      # Cleanup age threshold
CLEANUP_NOT_RELEVANT=false     # If true: also delete is_relevant=false articles
CLEANUP_ERROR=false            # If true: also delete status=error articles
```

Note: `GMAIL_FROM` can differ from `GMAIL_LOGIN` if a "Send mail as" alias is configured
in Gmail settings. `ARTICLE_MAX_AGE_HOURS` is mailer-only — the fetcher uses a hardcoded
24h lookback on `published_at` when parsing feeds.

---

## Ollama Evaluator Prompt Design

Uses `/api/generate` with `temperature=0`. The system prompt encodes the interest profile.
The model must return valid JSON — the evaluator strips markdown fences and preamble before
parsing, so minor model non-compliance is handled gracefully.

**System prompt:**
```
You are a news relevance filter. Your job is to decide whether an article
is relevant to the following interest areas: cybersecurity, vulnerabilities, security
advisories, Docker, containers, cloud infrastructure, virtualization, Proxmox, homelab,
AI, machine learning, EVs, tech advances in general, AI and LLMs.

Respond ONLY with a valid JSON object in this exact format:
{"relevant": true/false, "summary": "2-3 sentence summary if relevant, empty string if not", "tags": ["tag1", "tag2"]}

Do not include any text outside the JSON object.
```

**User message format:**
```
Title: {article.title}

{article.full_text}
```

---

## Error Handling Rules

- Fetcher: if RSS parse fails for a source, log and continue to next source
- Fetcher: if `trafilatura` returns no text, attempt `requests` + `bs4` fallback; if still empty, store article with `full_text=null`, `status=error`
- Fetcher: `DataError` on insert (e.g. oversized field) is caught, logged, article skipped
- Evaluator: if Ollama call fails or returns non-JSON, mark `status=error`, log, continue
- Evaluator: if `is_relevant` key missing from JSON response, treat as `relevant=false`
- Mailer: if no relevant articles exist for today, log and exit cleanly — do not send empty email
- Main: if any pipeline step raises an unhandled exception, log and exit with code 1

---

## Out of Scope for V1

- Web UI of any kind
- Multi-user support or interest profiles
- Source management outside of direct DB edits
- Different cron schedules per service
- File-based logging
- Claude API — local Ollama only

## Known Issues (post-V1)

See `TODO.md` for the full list. High priority before production cron use:
- Ars Technica appears as two sources — duplicate articles possible in digest
