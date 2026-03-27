# NewsBot — TODO

## Remaining V1 Implementation

- [ ] `mailer.py` — compile relevant articles grouped by tag, send digest via Gmail SMTP
- [ ] `main.py` — chain fetcher → evaluator → mailer, top-level error handling, exit codes

---

## Known Issues / Polish

- [ ] `cleanup.py` docstring still references old `CLEANUP_NULL` variable name — update to match current env vars
- [ ] Scott Lowe Blog feed URL was corrected in setup_db.py but the old record in the DB still has the broken URL — update via SQL or re-seed
- [ ] Proxmox source was renamed to "Proxmox Announcements" in setup_db.py — same issue if already seeded with old name
- [ ] Fetcher logs trafilatura redirect noise at INFO level (e.g. Nature.com auth redirects) — consider suppressing trafilatura's internal logger

---

## Features to Add

- [ ] **Retry queue** — re-attempt `status=error` articles on next fetcher run instead of leaving them stranded
- [ ] **Scrape fallback** — implement `scrape_fallback=true` path in fetcher for sources without RSS
- [ ] **Per-source fetch limits** — cap max articles pulled per source per run to avoid hammering feeds with large backlogs
- [ ] **Digest deduplication** — Ars Technica appears as two sources (Tech Lab + general); articles could appear twice in the digest
- [ ] **File-based logging** — write logs to a rotating file in addition to stdout for easier cron debugging
- [ ] **Dry-run mode** — `--dry-run` flag for mailer that prints the digest without sending
- [ ] **Source health tracking** — track consecutive fetch failures per source, alert or auto-disable after N failures
- [ ] **Tag normalization** — Ollama returns freeform tags; consider normalizing to a fixed taxonomy for cleaner grouping in the digest
- [ ] **User Accounts** - Individual user accounts, allow for custom categories, run frequencies, distribution lists, etc.
- [ ] **Sort Order** - maybe allow user to sort order of importance on categories
