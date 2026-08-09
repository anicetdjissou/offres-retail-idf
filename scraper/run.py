"""Chef d'orchestre : fait travailler les 3 Robots, range tout dans le
Carnet, et écrit ce que la Vitrine (page web) affichera.

Lancement : `python -m scraper.run` depuis la racine du projet.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from . import config, dedup
from .sources import hellowork, linkedin_indeed

SOURCES = [linkedin_indeed, hellowork]


def main() -> None:
    today = date.today()
    all_fresh_records: list[dict] = []
    statuses: list[dict] = []

    for module in SOURCES:
        print(f"--- {module.__name__} ---")
        result = module.scrape()
        records = result["records"]
        statuses.extend(result["statuses"])
        print(f"  {len(records)} offres brutes récupérées")
        all_fresh_records.extend(records)

    fresh = dedup.filter_freshness(all_fresh_records, config.FRESHNESS_DAYS, today)
    print(f"Total après filtre '{config.FRESHNESS_DAYS} derniers jours' : {len(fresh)}")

    existing = dedup.load_existing(config.JOBS_CSV)
    merged = dedup.merge(existing, fresh, today)
    merged = dedup.prune(merged, config.RETENTION_DAYS, today)
    print(f"Carnet après fusion + nettoyage ({config.RETENTION_DAYS}j) : {len(merged)} offres")

    dedup.write_csv(merged, config.JOBS_CSV)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    jobs_sorted = sorted(merged, key=lambda r: r.get("date_posted", ""), reverse=True)
    for target in (config.JOBS_JSON, config.DOCS_JOBS_JSON):
        target.write_text(
            json.dumps(jobs_sorted, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    run_log = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "statuses": statuses,
        "total_jobs": len(merged),
        "fresh_jobs_today": len(fresh),
    }
    for target in (config.RUN_LOG_JSON, config.DOCS_RUN_LOG_JSON):
        target.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Terminé.")
    for status in statuses:
        state = "OK" if status["ok"] else "PROBLÈME"
        print(f"  [{state}] {status['source']}: {status['count']} offres — {status['error'] or ''}")


if __name__ == "__main__":
    main()
