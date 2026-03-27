"""
One-time setup script. Creates the newsbot database, tables, and seeds sources.
Run once before first use: python setup_db.py
"""
import os
import sys
from dotenv import load_dotenv
import pymysql
from db import engine, Session, Base, Source

load_dotenv()


def create_database():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            db_name = os.getenv("DB_NAME", "newsbot")
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            print(f"Database '{db_name}' ready.")
    finally:
        conn.close()


SOURCES = [
    # Security
    {"name": "Krebs on Security",    "feed_url": "https://krebsonsecurity.com/feed",                       "site_url": "https://krebsonsecurity.com"},
    {"name": "Schneier on Security", "feed_url": "https://www.schneier.com/feed/atom",                     "site_url": "https://www.schneier.com"},
    {"name": "BleepingComputer",     "feed_url": "https://www.bleepingcomputer.com/feed",                  "site_url": "https://www.bleepingcomputer.com"},
    {"name": "The Hacker News",      "feed_url": "https://feeds.feedburner.com/TheHackersNews",            "site_url": "https://thehackernews.com"},
    {"name": "CISA Alerts",          "feed_url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",  "site_url": "https://www.cisa.gov"},
    # Docker / Containers / Cloud
    {"name": "Docker Blog",          "feed_url": "https://www.docker.com/blog/feed",                       "site_url": "https://www.docker.com/blog"},
    {"name": "The New Stack",        "feed_url": "https://thenewstack.io/feed",                            "site_url": "https://thenewstack.io"},
    {"name": "CNCF Blog",            "feed_url": "https://www.cncf.io/feed",                               "site_url": "https://www.cncf.io/blog"},
    # Virtualization / Infrastructure / Homelab
    {"name": "Scott Lowe Blog",      "feed_url": "https://blog.scottlowe.org/feed.xml",                     "site_url": "https://blog.scottlowe.org"},
    {"name": "Proxmox Announcements","feed_url": "https://my.proxmox.com/en/announcements/rss",             "site_url": "https://my.proxmox.com/en/announcements"},
    {"name": "ServeTheHome",         "feed_url": "https://www.servethehome.com/feed",                       "site_url": "https://www.servethehome.com"},
    # AI
    {"name": "Ars Technica Tech Lab","feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab","site_url": "https://arstechnica.com"},
    {"name": "MIT Tech Review",      "feed_url": "https://www.technologyreview.com/feed",                  "site_url": "https://www.technologyreview.com"},
    {"name": "The Gradient",         "feed_url": "https://thegradient.pub/rss",                            "site_url": "https://thegradient.pub"},
    # General
    {"name": "Hacker News",          "feed_url": "https://hnrss.org/frontpage",                            "site_url": "https://news.ycombinator.com"},
    {"name": "Ars Technica",         "feed_url": "https://feeds.arstechnica.com/arstechnica/index",        "site_url": "https://arstechnica.com"},
]


def seed_sources(session):
    existing = {s.name for s in session.query(Source).all()}
    new_sources = [Source(**s) for s in SOURCES if s["name"] not in existing]
    if not new_sources:
        print("Sources already seeded, skipping.")
        return
    session.add_all(new_sources)
    session.commit()
    print(f"Seeded {len(new_sources)} source(s).")


if __name__ == "__main__":
    create_database()
    Base.metadata.create_all(engine)
    print("Tables created.")
    with Session() as session:
        seed_sources(session)
    print("Setup complete.")
