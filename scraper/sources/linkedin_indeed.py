"""Robot chercheur pour LinkedIn et Indeed, via la librairie gratuite JobSpy.

JobSpy sait interroger les pages de recherche publiques de LinkedIn et
d'Indeed sans compte ni mot de passe. On appelle chaque site séparément
(plutôt qu'en un seul appel groupé) pour que, si un site tombe en panne ou
bloque temporairement, l'autre continue de fonctionner et qu'on sache
précisément lequel a un problème.
"""

from __future__ import annotations

import random
import time
from datetime import date

from .. import config

SITES = ["linkedin", "indeed"]


def _normalize_date(value) -> str:
    """JobSpy renvoie tantôt un objet date, tantôt une chaîne, tantôt NaN
    (pandas) quand la date n'est pas connue."""
    if value is None or isinstance(value, float):  # None, NaN
        return ""
    if isinstance(value, str):
        return value[:10]
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _clean(value) -> str:
    """Nettoie une cellule pandas : NaN (flottant) et None deviennent une
    chaîne vide plutôt que de faire planter .strip()."""
    if value is None or isinstance(value, float):
        return ""
    return str(value).strip()


def _rows_from_dataframe(df, site: str, keyword: str) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        url = _clean(row.get("job_url")) or _clean(row.get("job_url_direct"))
        if not url:
            continue
        records.append(
            {
                "source": site,
                "search_keyword": keyword,
                "title": _clean(row.get("title")),
                "company": _clean(row.get("company")),
                "location": _clean(row.get("location")),
                "date_posted": _normalize_date(row.get("date_posted")),
                "url": url,
            }
        )
    return records


def scrape() -> dict:
    """Lance la recherche sur LinkedIn + Indeed pour tous les mots-clés.

    Renvoie {"records": [...], "statuses": [{"source": ..., "ok": ..., "count": ..., "error": ...}, ...]}.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        error = f"python-jobspy n'est pas installé ({exc})"
        return {
            "records": [],
            "statuses": [
                {"source": site, "ok": False, "count": 0, "error": error} for site in SITES
            ],
        }

    all_records: list[dict] = []
    counts = {site: 0 for site in SITES}
    errors = {site: None for site in SITES}

    for site in SITES:
        for keyword in config.KEYWORDS:
            try:
                df = scrape_jobs(
                    site_name=[site],
                    search_term=keyword,
                    location=config.LOCATION_JOBSPY,
                    country_indeed=config.COUNTRY_INDEED,
                    hours_old=config.HOURS_OLD,
                    results_wanted=config.RESULTS_WANTED,
                    linkedin_fetch_description=False,
                )
            except Exception as exc:  # noqa: BLE001 - on isole la panne, on ne casse pas les autres sources
                errors[site] = f"{keyword!r}: {exc}"
                continue

            if df is None or df.empty:
                continue

            rows = _rows_from_dataframe(df, site, keyword)
            all_records.extend(rows)
            counts[site] += len(rows)

            # Petite pause aléatoire entre deux requêtes pour rester discret.
            time.sleep(random.uniform(5, 15))

    statuses = [
        {
            "source": site,
            "ok": errors[site] is None,
            "count": counts[site],
            "error": errors[site],
        }
        for site in SITES
    ]
    return {"records": all_records, "statuses": statuses}
