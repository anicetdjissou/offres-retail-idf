"""Le Carnet : fusion et anti-doublons des offres d'une exécution à l'autre.

Une offre est identifiée par son URL (nettoyée des paramètres de tracking
comme ?trk=... ou ?utm_...) — c'est notre clé pour dire "c'est la même offre
qu'hier, on ne la re-note pas comme neuve".
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

FIELDNAMES = [
    "source",
    "search_keyword",
    "title",
    "company",
    "location",
    "date_posted",
    "url",
    "first_seen",
]

# Paramètres de query string à retirer avant de comparer deux URLs (ils ne
# changent pas l'offre elle-même, juste le "d'où vient le clic").
_TRACKING_PREFIXES = ("utm_", "trk", "trkInfo", "refId", "ref_")


def normalize_url(url: str) -> str:
    """Retire les paramètres de tracking pour que deux liens vers la même
    offre, récupérés à des moments différents, soient reconnus identiques."""
    if not url:
        return url
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [
        pair
        for pair in parts.query.split("&")
        if pair and not pair.split("=", 1)[0].startswith(_TRACKING_PREFIXES)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), ""))


def load_existing(csv_path: Path) -> dict[str, dict]:
    """Charge le Carnet existant, indexé par URL normalisée."""
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return {normalize_url(row["url"]): row for row in reader if row.get("url")}


def merge(
    existing: dict[str, dict],
    fresh_records: list[dict],
    today: date | None = None,
) -> list[dict]:
    """Fusionne les offres fraîchement récupérées avec le Carnet existant.

    - Une offre déjà connue garde sa date `first_seen` d'origine.
    - Une offre nouvelle est ajoutée avec `first_seen` = aujourd'hui.
    - Le Carnet existant n'est jamais perdu : les offres qu'on n'a pas
      re-vues aujourd'hui (ex: un site en panne) restent dans le résultat.
    """
    today = today or date.today()
    today_str = today.isoformat()
    merged = dict(existing)

    for record in fresh_records:
        key = normalize_url(record["url"])
        record = dict(record)
        record["url"] = key
        if key in merged:
            record["first_seen"] = merged[key].get("first_seen") or today_str
        else:
            record["first_seen"] = today_str
        merged[key] = record

    return list(merged.values())


def prune(records: list[dict], retention_days: int, today: date | None = None) -> list[dict]:
    """Retire les offres dont la date de publication est trop ancienne,
    pour que le Carnet ne grossisse pas indéfiniment."""
    return _filter_by_age(records, retention_days, today, keep_undated=True)


def filter_freshness(records: list[dict], max_age_days: int, today: date | None = None) -> list[dict]:
    """Filtre de sécurité appliqué aux offres fraîchement récupérées : quel
    que soit le filtre de date déjà appliqué côté site, on ne garde ici que
    ce qui est vraiment publié depuis moins de `max_age_days`."""
    return _filter_by_age(records, max_age_days, today, keep_undated=True)


def _filter_by_age(
    records: list[dict], max_age_days: int, today: date | None, keep_undated: bool
) -> list[dict]:
    today = today or date.today()
    cutoff = today - timedelta(days=max_age_days)
    kept = []
    for record in records:
        raw = record.get("date_posted")
        try:
            posted = datetime.strptime(raw, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            # Pas de date exploitable : on garde par prudence plutôt que
            # de perdre une offre par erreur de parsing.
            if keep_undated:
                kept.append(record)
            continue
        if posted >= cutoff:
            kept.append(record)
    return kept


def write_csv(records: list[dict], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    records_sorted = sorted(records, key=lambda r: r.get("date_posted", ""), reverse=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in records_sorted:
            writer.writerow({key: record.get(key, "") for key in FIELDNAMES})
