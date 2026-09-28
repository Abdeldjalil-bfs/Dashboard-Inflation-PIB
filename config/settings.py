from pathlib import Path

# Racine du projet (dossier qui contient app/, backend/, config/, data/...)
BASE_DIR = Path(__file__).resolve().parent.parent

# Dossiers
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CONFIG_DIR = BASE_DIR / "config"
OUTPUTS_DIR = BASE_DIR / "outputs"
GRAPHES_DIR = OUTPUTS_DIR / "graphes"
ASSETS_DIR = BASE_DIR / "assets"
GEO_DIR = ASSETS_DIR / "geo"
SAUVEGARDES_DIR = DATA_DIR / "sauvegardes"

# Fichiers - Inflation
INFLATION_RAW_DIR = RAW_DIR / "inflation"
FICHIER_DONNEES = INFLATION_RAW_DIR / "Fichier_de_donnes.xlsx"
FICHIER_DONNEES_SECOURS = SAUVEGARDES_DIR / "Fichier_de_donnes_secours.xlsx"
FICHIER_DONNEES_CALCULS = PROCESSED_DIR / "Fichier_de_donnes_et_calculs.xlsx"

# Fichier complementaire (feuille 'FCI_REG') : indices nationaux Reglementes /
# Fort Contenu d'Import / Hors Reglementes-Hors Agricoles frais (inflation
# sous-jacente 2). Deja calcules a la source, simplement integres tels quels.
FICHIER_DONNEES_COMPLEMENTAIRES = INFLATION_RAW_DIR / "Data_inflation.xlsx"

# Config
WEIGHTS_PATH = CONFIG_DIR / "weights.json"
CATEGORIES_PATH = CONFIG_DIR / "categories.json"
NARRATIVE_RULES_PATH = CONFIG_DIR / "narrative_rules.json"
ANOMALY_RULES_PATH = CONFIG_DIR / "anomaly_rules.json"

# Les cinq paniers, dans l'ordre d'affichage.
# Attention : le fichier BRUT ne porte pas la feuille 'core', qui n'existe
# que dans le fichier de calculs. Les fonctions de saisie ne proposent donc
# que les paniers réellement présents dans le classeur visé.
PANIERS = ["Grand_Alger", "national", "categories", "core", "Produits_agricoles_frais"]

# Rapports PDF générés
RAPPORTS_DIR = OUTPUTS_DIR / "rapports"

# Auth
USERS_FILE = DATA_DIR / "users.xlsx"

# Assets
# Le fichier d'origine est un trace noir sur fond BLANC OPAQUE : il apparait en
# rectangle blanc sur le degrade navy. Les deux variantes ci-dessous sont
# detourees (fond transparent) et recolorees pour la charte.
LOGO_SOURCE_PATH = ASSETS_DIR / "bankofalgerialogo.png"
LOGO_OR_PATH = ASSETS_DIR / "logo_or.png"
LOGO_CLAIR_PATH = ASSETS_DIR / "logo_clair.png"

# Logo utilise par l'interface
LOGO_PATH = LOGO_OR_PATH

# Feuilles Excel (inflation)
FEUILLE_GRAND_ALGER = "Grand_Alger"
FEUILLE_NATIONAL = "national"
FEUILLE_CORE = "core"
FEUILLE_NON_CORE = "Produits_agricoles_frais"
FEUILLE_CATEGORIES = "categories"

# Feuilles Excel (indices complementaires nationaux, depuis FICHIER_DONNEES_COMPLEMENTAIRES)
FEUILLE_NATIONAL_REGLEMENTES = "national_reglementes"
FEUILLE_NATIONAL_FCI = "national_fci"
FEUILLE_NATIONAL_CORE2 = "national_core2"

# Fichiers - PIB (comptes nationaux trimestriels, ONS)
PIB_RAW_DIR = RAW_DIR / "pib"
PIB_CONFIG_PATH = CONFIG_DIR / "pib_config.json"
FICHIER_PIB_OFFRE = PIB_RAW_DIR / "PIB_TR_S.xlsx"
FICHIER_PIB_DEMANDE = PIB_RAW_DIR / "PIB_TR_D.xlsx"
FICHIER_PIB_CALCULS = PROCESSED_DIR / "Fichier_PIB_et_calculs.xlsx"

# Journal des saisies PIB. Les classeurs ONS sont pilotés par formules : les
# réenregistrer avec openpyxl effacerait leurs valeurs en cache. Les saisies
# (insertion, modification, suppression) sont donc consignées ici et
# appliquées à la lecture, sans jamais toucher aux fichiers ONS.
FICHIER_PIB_SAISIES = PIB_RAW_DIR / "PIB_saisies.xlsx"
# ---------------------------------------------------------------------------
# Ingestion des Comptes Nationaux Trimestriels (CNT) publiés par l'ONS
# ---------------------------------------------------------------------------
# Base SQLite des millésimes CNT (table cnt_pib, vue cnt_pib_derniere).
CNT_DB_PATH = DATA_DIR / "dashboard.db"

# Modèle d'URL des rapports PDF publiés sur ons.dz.
ONS_CNT_URL_TEMPLATE = "https://www.ons.dz/IMG/pdf/CNT{trimestre}T{annee}.pdf"

# Vérification du certificat TLS d'ons.dz. False reprend le comportement du
# script d'origine (chaîne de certificats du site historiquement incomplète).
# À repasser à True dès qu'un téléchargement réel réussit avec True : non
# testé à ce jour, ons.dz étant injoignable depuis l'environnement de
# développement (voir docs/AUDIT_INGESTION_CNT.md).
ONS_CNT_VERIFY_SSL = False

# Délai maximal de téléchargement d'un rapport, en secondes.
ONS_CNT_TIMEOUT = 120


# Journal de l application
LOGS_DIR = BASE_DIR / "logs"
FICHIER_JOURNAL = LOGS_DIR / "dashboard.log"
