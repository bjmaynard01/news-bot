"""
Cleanup script — removes articles older than ARTICLE_RETENTION_DAYS.
If CLEANUP_NOT_RELEVANT=true, also removes articles with no summary (irrelevant or errored).
Run standalone or add to cron after main.py: python cleanup.py
"""
import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from sqlalchemy import or_

from db import Session, Article

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [cleanup] %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(force_error: bool = False):
    """
    force_error=True purges status=error articles unconditionally.
    Used by main.py before the pipeline regardless of env var settings.
    """
    retention_days       = int(os.getenv("ARTICLE_RETENTION_DAYS", 30))
    cleanup_not_relevant = os.getenv("CLEANUP_NOT_RELEVANT", "false").lower() == "true"
    cleanup_error        = force_error or os.getenv("CLEANUP_ERROR", "false").lower() == "true"

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_naive = cutoff.replace(tzinfo=None)

    age_filter        = Article.fetched_at < cutoff_naive
    irrelevant_filter = Article.is_relevant == False  # noqa: E712
    status_filter     = Article.status == "error"

    with Session() as session:
        query = session.query(Article)

        if cleanup_not_relevant:
            query = query.filter(or_(age_filter, irrelevant_filter, status_filter))
            log.info("cleanup mode: age (>%dd) OR is_relevant=false OR status=error", retention_days)
        elif cleanup_error:
            query = query.filter(status_filter)
            log.info("cleanup mode: status=error")
        else:
            query = query.filter(age_filter)
            log.info("cleanup mode: age only (>%dd)", retention_days)

        deleted = query.delete(synchronize_session=False)
        session.commit()

    log.info("deleted %d article(s)", deleted)


if __name__ == "__main__":
    run()
