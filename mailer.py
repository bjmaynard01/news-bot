"""
Mailer service — compiles and sends daily digest of relevant unsent articles.
Run standalone: python mailer.py
"""
import logging
import os
import smtplib
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from db import Session, Article

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [mailer] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

GMAIL_LOGIN   = os.getenv("GMAIL_LOGIN")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GMAIL_FROM    = os.getenv("GMAIL_FROM")
RECIPIENT     = os.getenv("DIGEST_RECIPIENT")
MAX_AGE_HOURS = int(os.getenv("ARTICLE_MAX_AGE_HOURS", 24))


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def _fetch_articles(session) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    cutoff_naive = cutoff.replace(tzinfo=None)
    return (
        session.query(Article)
        .filter(
            Article.is_relevant == True,       # noqa: E712
            Article.emailed_at.is_(None),
            Article.fetched_at >= cutoff_naive,
        )
        .order_by(Article.published_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Email composition
# ---------------------------------------------------------------------------

def _group_by_tag(articles: list[Article]) -> dict[str, list[Article]]:
    """Group articles by their first tag. Untagged go to 'General'."""
    groups: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        tag = (article.tags[0].title() if article.tags else "General")
        groups[tag].append(article)
    return dict(sorted(groups.items()))


def _render_html(articles: list[Article], date_str: str) -> str:
    groups = _group_by_tag(articles)

    sections = []
    for tag, items in groups.items():
        rows = []
        for a in items:
            pub = a.published_at.strftime("%b %d, %H:%M") if a.published_at else ""
            rows.append(f"""
            <div style="margin-bottom:18px;">
              <a href="{a.url}" style="font-size:15px;font-weight:600;color:#1a0dab;text-decoration:none;">{a.title or a.url}</a>
              <div style="font-size:12px;color:#666;margin:2px 0 6px;">{a.source_name or ''}{' &mdash; ' + pub if pub else ''}</div>
              <div style="font-size:14px;color:#333;line-height:1.5;">{a.summary or ''}</div>
            </div>""")

        sections.append(f"""
        <div style="margin-bottom:32px;">
          <h2 style="font-size:16px;font-weight:700;color:#fff;background:#333;padding:6px 12px;margin:0 0 12px;border-radius:4px;">{tag}</h2>
          {''.join(rows)}
        </div>""")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;padding:24px;background:#f9f9f9;">
  <div style="background:#fff;border-radius:8px;padding:28px;box-shadow:0 1px 4px rgba(0,0,0,.08);">
    <h1 style="font-size:20px;margin:0 0 4px;color:#111;">NewsBot Digest</h1>
    <div style="font-size:13px;color:#888;margin-bottom:28px;">{date_str} &mdash; {len(articles)} article{'s' if len(articles) != 1 else ''}</div>
    {''.join(sections)}
    <div style="font-size:11px;color:#bbb;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
      Delivered by NewsBot &mdash; local Ollama digest
    </div>
  </div>
</body>
</html>"""


def _render_plaintext(articles: list[Article], date_str: str) -> str:
    groups = _group_by_tag(articles)
    lines = [f"NewsBot Digest — {date_str} ({len(articles)} articles)\n"]
    for tag, items in groups.items():
        lines.append(f"\n== {tag.upper()} ==\n")
        for a in items:
            pub = a.published_at.strftime("%b %d, %H:%M") if a.published_at else ""
            lines.append(f"{a.title or a.url}")
            if a.source_name or pub:
                lines.append(f"  {a.source_name or ''}{' — ' + pub if pub else ''}")
            if a.summary:
                lines.append(f"  {a.summary}")
            lines.append(f"  {a.url}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def _send(subject: str, html: str, plaintext: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_FROM
    msg["To"]      = RECIPIENT

    msg.attach(MIMEText(plaintext, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(GMAIL_LOGIN, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_FROM, RECIPIENT, msg.as_string())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    with Session() as session:
        articles = _fetch_articles(session)

        if not articles:
            log.info("no relevant unsent articles in the last %dh — skipping email", MAX_AGE_HOURS)
            return

        log.info("composing digest: %d article(s)", len(articles))

        date_str = datetime.now().strftime("%B %d, %Y")
        subject  = f"NewsBot Digest — {date_str}"
        html     = _render_html(articles, date_str)
        plain    = _render_plaintext(articles, date_str)

        _send(subject, html, plain)

        now = datetime.utcnow()
        for a in articles:
            a.emailed_at = now
        session.commit()

    log.info("digest sent to %s", RECIPIENT)


if __name__ == "__main__":
    run()
