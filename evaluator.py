"""
Evaluator service — sends pending articles to Ollama, stores relevance + summary + tags.
Run standalone: python evaluator.py
"""
import json
import logging
import os
import re

from dotenv import load_dotenv
import ollama

from db import Session, Article

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [evaluator] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODEL = os.getenv("OLLAMA_MODEL", "mistral-small:24b")
HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")

SYSTEM_PROMPT = """\
You are a news relevance filter. Your job is to decide whether an article
is relevant to the following interest areas: cybersecurity, vulnerabilities, security
advisories, Docker, containers, cloud infrastructure, virtualization, Proxmox, homelab,
AI, machine learning, EVs, tech advances in general, AI and LLMs.

Respond ONLY with a valid JSON object in this exact format:
{"relevant": true/false, "summary": "2-3 sentence summary if relevant, empty string if not", "tags": ["tag1", "tag2"]}

Do not include any text outside the JSON object.\
"""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(raw: str) -> dict | None:
    """
    Parse JSON from model output. Handles markdown code fences and preamble.
    Returns None if no valid JSON object can be extracted.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = _JSON_RE.search(raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _evaluate(client: ollama.Client, article: Article) -> dict | None:
    prompt = f"Title: {article.title}\n\n{article.full_text or ''}"
    response = client.generate(
        model=MODEL,
        system=SYSTEM_PROMPT,
        prompt=prompt,
        options={"temperature": 0},
    )
    return _parse_response(response.response)


def run():
    client = ollama.Client(host=HOST)

    with Session() as session:
        pending = (
            session.query(Article)
            .filter_by(status="pending")
            .all()
        )

        if not pending:
            log.info("no pending articles to evaluate")
            return

        log.info("evaluating %d pending article(s) via %s [%s]", len(pending), HOST, MODEL)

        evaluated = errors = 0
        for article in pending:
            try:
                result = _evaluate(client, article)
            except Exception as exc:
                log.error("ollama call failed for article %d ('%s'): %s", article.id, article.title, exc)
                article.status = "error"
                session.commit()
                errors += 1
                continue

            if result is None:
                log.error("unparseable response for article %d ('%s')", article.id, article.title)
                article.status = "error"
                session.commit()
                errors += 1
                continue

            article.is_relevant = bool(result.get("relevant", False))
            article.summary     = result.get("summary") or None
            article.tags        = result.get("tags") or []
            article.status      = "evaluated"
            session.commit()

            log.info(
                "[%s] article %d — relevant=%s tags=%s",
                "YES" if article.is_relevant else "no ",
                article.id,
                article.is_relevant,
                article.tags,
            )
            evaluated += 1

    log.info("evaluation complete — %d evaluated, %d error(s)", evaluated, errors)


if __name__ == "__main__":
    run()
