"""Robot chercheur sur mesure pour HelloWork.

HelloWork n'a pas de librairie gratuite toute prête (contrairement à
LinkedIn/Indeed avec JobSpy), donc on lit directement les pages de
résultats de recherche publiques avec `requests` + `BeautifulSoup`.

Deux choix pour rester robuste face aux changements de design du site :
- on cible les attributs `data-cy="..."` (utilisés par HelloWork pour ses
  propres tests automatisés) plutôt que des classes CSS, qui changent bien
  plus souvent ;
- HelloWork ne propose pas de filtre "4 derniers jours" tout fait (juste
  24h / 3 jours / 1 semaine / 1 mois), donc on demande "1 semaine" triée
  par date, et on filtre nous-mêmes les offres à moins de 4 jours — avec
  arrêt anticipé de la pagination dès qu'une offre plus vieille apparaît,
  puisque les résultats sont triés du plus récent au plus ancien.
"""

from __future__ import annotations

import random
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .. import config

SOURCE_NAME = "hellowork"
BASE_URL = "https://www.hellowork.com"
SEARCH_URL = f"{BASE_URL}/fr-fr/emploi/recherche.html"
MAX_PAGES = 6  # filet de sécurité pour ne jamais boucler indéfiniment
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_RELATIVE_DATE_RE = re.compile(
    r"il y a\s+(\d+)\s*(minute|heure|jour|semaine|mois)", re.IGNORECASE
)
_UNIT_TO_DAYS = {
    "minute": 0,
    "heure": 0,
    "jour": 1,
    "semaine": 7,
    "mois": 30,
}


def _parse_relative_date(text: str, today: date) -> str | None:
    """Convertit 'il y a 3 jours' en une date AAAA-MM-JJ. Renvoie None si le
    texte ne correspond à aucun format connu."""
    text = (text or "").strip().lower()
    if not text:
        return None
    if "aujourd'hui" in text or "instant" in text:
        return today.isoformat()
    if "hier" in text:
        return (today - timedelta(days=1)).isoformat()
    match = _RELATIVE_DATE_RE.search(text)
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    days = amount * _UNIT_TO_DAYS.get(unit, 0) if unit in ("jour", "semaine", "mois") else 0
    return (today - timedelta(days=days)).isoformat()


def _parse_cards(html: str, keyword: str, today: date) -> tuple[list[dict], bool]:
    """Renvoie (offres_de_la_page, faut_il_continuer_la_pagination)."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all(attrs={"data-cy": "serpCard"})
    if not cards:
        return [], False

    records = []
    keep_going = True
    cutoff = today - timedelta(days=config.FRESHNESS_DAYS)

    for card in cards:
        link = card.find("a", attrs={"data-cy": "offerTitle"})
        if link is None or not link.get("href"):
            continue

        paragraphs = link.find_all("p")
        title = paragraphs[0].get_text(strip=True) if paragraphs else link.get("title", "")
        company = paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else ""

        location_el = card.find(attrs={"data-cy": "localisationCard"})
        location = location_el.get_text(strip=True) if location_el else ""

        date_el = card.find("div", class_="text-grey-500")
        date_posted = _parse_relative_date(date_el.get_text() if date_el else "", today)

        if date_posted is None:
            # Pas de date reconnue : on garde l'offre par prudence, mais on
            # ne s'en sert pas pour décider d'arrêter la pagination.
            records.append(
                {
                    "source": SOURCE_NAME,
                    "search_keyword": keyword,
                    "title": title,
                    "company": company,
                    "location": location,
                    "date_posted": "",
                    "url": urljoin(BASE_URL, link["href"]),
                }
            )
            continue

        if date_posted < cutoff.isoformat():
            # Résultats triés du plus récent au plus ancien : dès qu'on
            # tombe sur une offre trop vieille, la suite le sera aussi.
            keep_going = False
            continue

        records.append(
            {
                "source": SOURCE_NAME,
                "search_keyword": keyword,
                "title": title,
                "company": company,
                "location": location,
                "date_posted": date_posted,
                "url": urljoin(BASE_URL, link["href"]),
            }
        )

    return records, keep_going


def _scrape_keyword(session: requests.Session, keyword: str, today: date) -> list[dict]:
    records: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        response = session.get(
            SEARCH_URL,
            params={
                "k": keyword,
                "l": config.LOCATION_HELLOWORK,
                "d": "w",  # "depuis 1 semaine" : la plage native la plus proche de 4 jours
                "st": "date",  # trié du plus récent au plus ancien
                "p": page,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()

        page_records, keep_going = _parse_cards(response.text, keyword, today)
        records.extend(page_records)

        if not keep_going:
            break

        time.sleep(random.uniform(3, 8))

    return records


def scrape() -> dict:
    """Lance la recherche HelloWork pour tous les mots-clés.

    Renvoie {"records": [...], "statuses": [{"source": "hellowork", "ok": ..., "count": ..., "error": ...}]}.
    """
    today = date.today()
    all_records: list[dict] = []
    error = None

    with requests.Session() as session:
        for keyword in config.KEYWORDS:
            try:
                all_records.extend(_scrape_keyword(session, keyword, today))
            except Exception as exc:  # noqa: BLE001 - on isole la panne par mot-clé
                error = f"{keyword!r}: {exc}"
                continue
            time.sleep(random.uniform(3, 8))

    status = {
        "source": SOURCE_NAME,
        "ok": error is None,
        "count": len(all_records),
        "error": error,
    }
    return {"records": all_records, "statuses": [status]}
