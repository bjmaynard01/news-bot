"""
Add a new source to the database.
Usage: python add_source.py "Source Name" "https://example.com/feed.xml" "https://example.com"
       python add_source.py "Source Name" "https://example.com/feed.xml" "https://example.com" --inactive
"""
import argparse
import sys

from db import Session, Source


def main():
    parser = argparse.ArgumentParser(description="Add a news source to NewsBot.")
    parser.add_argument("name",     help="Display name for the source")
    parser.add_argument("feed_url", help="RSS/Atom feed URL")
    parser.add_argument("site_url", help="Canonical site URL")
    parser.add_argument("--inactive", action="store_true", help="Add as inactive (won't be fetched)")
    args = parser.parse_args()

    with Session() as session:
        existing = session.query(Source).filter_by(name=args.name).first()
        if existing:
            print(f"A source named '{args.name}' already exists (id={existing.id}). Aborting.")
            sys.exit(1)

        source = Source(
            name=args.name,
            feed_url=args.feed_url,
            site_url=args.site_url,
            active=not args.inactive,
        )
        session.add(source)
        session.commit()
        print(f"Added source '{source.name}' (id={source.id}, active={source.active})")


if __name__ == "__main__":
    main()
