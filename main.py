"""
Main pipeline — chains cleanup (errors) → fetcher → evaluator → mailer.
Cron entry point: python main.py
"""
import logging
import sys

import cleanup
import evaluator
import fetcher
import mailer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [main] %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    steps = [
        ("pre-cleanup (errors)", cleanup.run,    {"force_error": True}),
        ("fetcher",              fetcher.run,    {}),
        ("evaluator",            evaluator.run,  {}),
        ("mailer",               mailer.run,     {}),
    ]

    for name, step, kwargs in steps:
        log.info("--- starting %s ---", name)
        try:
            step(**kwargs)
        except Exception as exc:
            log.exception("pipeline halted: %s failed — %s", name, exc)
            sys.exit(1)
        log.info("--- %s complete ---", name)

    log.info("pipeline finished")


if __name__ == "__main__":
    main()
