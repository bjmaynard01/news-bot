# NewsBot

Personal news aggregator agent. Fetches articles from RSS feeds, evaluates relevance using a local Ollama model, and emails a daily digest.

---

## Architecture

```
main.py
  └── fetcher.py     — poll RSS feeds, extract full text, store to DB
  └── evaluator.py   — send pending articles to Ollama, store relevance/summary/tags
  └── mailer.py      — compile and send digest email of today's relevant articles
```

Each script is independently runnable:

```bash
python fetcher.py      # fetch only
python evaluator.py    # evaluate pending articles only
python mailer.py       # send today's digest only
python main.py         # full pipeline (cron entry point)
python cleanup.py      # remove old / irrelevant articles per .env settings
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- MariaDB 10.6+
- [Ollama](https://ollama.com) running with your chosen model pulled
- Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) configured
- A "Send mail as" alias configured in Gmail if `GMAIL_FROM` differs from `GMAIL_LOGIN`

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# edit .env with your credentials
```

### 4. Initialize database

```bash
python setup_db.py
```

Creates the `news_bot` database, tables, and seeds all sources.

### 5. Run

```bash
python main.py
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DB_HOST` | MariaDB host | `localhost` |
| `DB_PORT` | MariaDB port | `3306` |
| `DB_NAME` | Database name | `newsbot` |
| `DB_USER` | Database user | — |
| `DB_PASSWORD` | Database password | — |
| `OLLAMA_HOST` | Ollama API base URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name to use | `mistral-small:24b` |
| `GMAIL_LOGIN` | Gmail account used to authenticate | — |
| `GMAIL_APP_PASSWORD` | Gmail App Password | — |
| `GMAIL_FROM` | From address on sent emails | — |
| `DIGEST_RECIPIENT` | Email address to send digest to | — |
| `ARTICLE_MAX_AGE_HOURS` | Mailer lookback window in hours | `24` |
| `ARTICLE_RETENTION_DAYS` | Age threshold for cleanup | `30` |
| `CLEANUP_NOT_RELEVANT` | Also delete `is_relevant=false` articles on cleanup | `false` |
| `CLEANUP_ERROR` | Also delete `status=error` articles on cleanup | `false` |

---

## Database Schema

### `sources`
| Column | Type | Notes |
|---|---|---|
| `id` | INT | PK |
| `name` | VARCHAR(255) | |
| `feed_url` | VARCHAR(512) | RSS feed URL |
| `site_url` | VARCHAR(512) | Canonical site URL |
| `active` | BOOLEAN | Set false to pause a source |
| `scrape_fallback` | BOOLEAN | Reserved for sources without RSS |

### `articles`
| Column | Type | Notes |
|---|---|---|
| `id` | INT | PK |
| `url` | VARCHAR(1024) | UNIQUE — deduplication key |
| `title` | VARCHAR(512) | |
| `source_name` | VARCHAR(255) | |
| `published_at` | DATETIME | From RSS entry |
| `fetched_at` | DATETIME | When the fetcher stored it |
| `full_text` | LONGTEXT | Extracted article body |
| `status` | ENUM | `pending` / `evaluated` / `error` |
| `is_relevant` | BOOLEAN | Set by evaluator |
| `summary` | TEXT | 2–3 sentence summary from Ollama |
| `tags` | JSON | Topic tags from Ollama |
| `emailed_at` | DATETIME | Set by mailer on send |

---

## Cron Example

```cron
0 7 * * * /path/to/venv/bin/python /path/to/news-bot/main.py
```
