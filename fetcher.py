"""
Fetcher service — polls RSS feeds, extracts full article text, stores to DB.
Run standalone: python fetcher.py
"""
import logging
from datetime import datetime, timezone, timedelta

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError, DataError

from db import Session, Source, Article

logging.basicConfig(level=logging.INFO, format="%(asctime)s [fetcher] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FETCH_TIMEOUT = 15  # seconds for HTTP requests
LOOKBACK_HOURS = 24


def _now_utc():
    return datetime.now(timezone.utc)


def _entry_published(entry) -> datetime | None:
    """Return a tz-aware datetime from a feedparser entry, or None."""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t is None:
        return None
    return datetime(*t[:6], tzinfo=timezone.utc)


def _extract_text_trafilatura(url: str) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            return trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    except Exception as exc:
        log.debug("trafilatura failed for %s: %s", url, exc)
    return None


def _extract_text_bs4(url: str) -> str | None:
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": "newsbot/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(separator=" ", strip=True) for p in paragraphs)
        return text if text.strip() else None
    except Exception as exc:
        log.debug("bs4 fallback failed for %s: %s", url, exc)
    return None


def _fetch_text(url: str) -> tuple[str | None, str]:
    """
    Returns (full_text, status).
    status is 'pending' on success, 'error' if both extraction methods failed.
    """
    text = _extract_text_trafilatura(url)
    if text:
        return text, "pending"
    log.warning("trafilatura returned nothing for %s — trying bs4 fallback", url)
    text = _extract_text_bs4(url)
    if text:
        return text, "pending"
    log.warning("both extraction methods failed for %s", url)
    return None, "error"


def _process_feed(session, source: Source, cutoff: datetime) -> tuple[int, int]:
    """Parse one RSS feed. Returns (inserted, skipped)."""
    inserted = skipped = 0
    try:
        feed = feedparser.parse(source.feed_url)
    except Exception as exc:
        log.error("feedparser failed for source '%s': %s", source.name, exc)
        return 0, 0

    if feed.bozo and not feed.entries:
        log.error("feed parse error for source '%s': %s", source.name, feed.bozo_exception)
        return 0, 0

    for entry in feed.entries:
        url = entry.get("link")
        if not url:
            continue

        published = _entry_published(entry)
        if published and published < cutoff:
            skipped += 1
            continue

        # deduplicate
        if session.query(Article.id).filter_by(url=url).scalar():
            skipped += 1
            continue

        title = entry.get("title", "")[:512]
        full_text, status = _fetch_text(url)

        article = Article(
            url=url,
            title=title,
            source_name=source.name,
            published_at=published.replace(tzinfo=None) if published else None,
            full_text=full_text,
            status=status,
        )
        try:
            session.add(article)
            session.commit()
            inserted += 1
            log.info("stored [%s] %s", source.name, title[:80])
        except IntegrityError:
            session.rollback()
            skipped += 1
        except DataError as exc:
            session.rollback()
            log.error("data error storing '%s': %s", url, exc)
            skipped += 1

    return inserted, skipped


def run():
    cutoff = _now_utc() - timedelta(hours=LOOKBACK_HOURS)
    log.info("fetching articles published after %s UTC", cutoff.strftime("%Y-%m-%d %H:%M"))

    with Session() as session:
        sources = session.query(Source).filter_by(active=True).all()
        log.info("processing %d active source(s)", len(sources))

        total_inserted = total_skipped = 0
        for source in sources:
            if not source.feed_url:
                log.warning("source '%s' has no feed_url and scrape_fallback is not implemented — skipping", source.name)
                continue
            ins, skp = _process_feed(session, source, cutoff)
            total_inserted += ins
            total_skipped += skp
            log.info("source '%s': %d inserted, %d skipped", source.name, ins, skp)

    log.info("fetch complete — %d new article(s), %d skipped", total_inserted, total_skipped)


if __name__ == "__main__":
    run()
