"""Réglages centraux du Robot chercheur d'offres.

C'est le seul fichier que quelqu'un de non-technique aurait besoin de
regarder pour changer les métiers recherchés, la zone géographique ou
la fenêtre de fraîcheur des offres.
"""

from pathlib import Path

# Les 4 métiers recherchés (un appel de recherche par mot-clé et par site).
KEYWORDS = [
    "Data Analyst Retail",
    "Prévision des ventes",
    "Demand Planner",
    "Contrôleur de gestion retail",
]

# Zone géographique.
# Testé en vrai : demander "Île-de-France, France" à LinkedIn (accentué,
# avec ", France") fait planter la résolution de zone quand on combine ça
# avec le filtre de fraîcheur (0 résultat, ou pire : des offres à Lyon !).
# "Paris, France" est correctement compris par LinkedIn ET Indeed comme
# "la région parisienne" (Paris + petite/grande couronne), donc c'est ce
# qu'on utilise pour ces deux sites.
LOCATION_JOBSPY = "Paris, France"          # utilisé pour LinkedIn/Indeed via JobSpy
LOCATION_HELLOWORK = "Île-de-France"       # utilisé pour la recherche HelloWork (testé OK)
COUNTRY_INDEED = "France"

# On ne garde que les offres publiées il y a moins de 4 jours.
FRESHNESS_DAYS = 4
HOURS_OLD = FRESHNESS_DAYS * 24  # paramètre attendu par JobSpy

# Nombre max de résultats par mot-clé et par site — volontairement bas pour
# rester discret vis-à-vis des sites (moins de requêtes = moins de risque de blocage).
RESULTS_WANTED = 40

# On garde un historique de 14 jours dans le Carnet, même si seules les
# offres <= FRESHNESS_DAYS intéressent la Vitrine — ça donne un peu de
# contexte "encore ouverte" sans faire grossir le fichier indéfiniment.
RETENTION_DAYS = 14

# Dossiers.
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DOCS_DATA_DIR = ROOT_DIR / "docs" / "data"

JOBS_CSV = DATA_DIR / "jobs.csv"
JOBS_JSON = DATA_DIR / "jobs.json"
RUN_LOG_JSON = DATA_DIR / "run_log.json"
DOCS_JOBS_JSON = DOCS_DATA_DIR / "jobs.json"
DOCS_RUN_LOG_JSON = DOCS_DATA_DIR / "run_log.json"
