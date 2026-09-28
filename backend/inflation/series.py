"""
Catalogue et chargement des séries temporelles du fichier de calculs.

Module de lecture pur : aucune dépendance Streamlit, aucun calcul. Il se
contente d'inventorier ce que le fichier de travail contient et d'en extraire
des sous-ensembles propres, prêts à tracer.
"""

import pandas as pd

from config.settings import FICHIER_DONNEES_CALCULS

# Nom de feuille -> libelle affiche
PERIMETRES = [
    ("Grand_Alger", "Grand Alger"),
    ("national", "National"),
    ("categories", "Catégories"),
    ("core", "Core"),
    ("Produits_agricoles_frais", "Non-core (produits agricoles frais)"),
    ("Alimentations_Boissons_non_alco", "Alimentation et boissons"),
]

LIBELLE_PERIMETRE = dict(PERIMETRES)

# Famille de mesure -> (prefixe de colonne, suffixe, unite)
# L'ordre fixe l'ordre d'affichage.
FAMILLES = [
    ("Indice", None, None, "indice"),
    ("Inflation MoM", "Inflation_MoM (%)_", None, "%"),
    ("Inflation YoY", "Inflation_YoY (%)_", None, "%"),
    ("Contribution MoM", "Contrib_MoM_", " (pp)", "pp"),
    ("Contribution YoY", "Contrib_YoY_", " (pp)", "pp"),
]

UNITES = {nom: unite for nom, _p, _s, unite in FAMILLES}

# Colonnes agregees : ce sont des totaux, pas des elements du panier.
AGREGATS = {
    "IPC (%)",
    "IPC Core (%)",
    "IPC Non Core (%)",
    "Inflation (%, mom)",
    "Inflation (%, yoy)",
    "Contrib_Core_MoM (pp)",
    "Contrib_Non_Core_MoM (pp)",
    "Contrib_Core_YoY (pp)",
    "Contrib_Non_Core_YoY (pp)",
}


def _lire(feuille, fichier=None):
    """Lit une feuille, indexee par date, colonnes vides ecartees."""
    chemin = str(fichier or FICHIER_DONNEES_CALCULS)
    df = pd.read_excel(chemin, sheet_name=feuille)
    df.rename(columns={df.columns[0]: "date"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    # Les colonnes "Unnamed: n" entierement vides polluent le fichier source.
    utiles = [c for c in df.columns if not str(c).startswith("Unnamed") and df[c].notna().any()]
    return df[utiles]


def perimetres_disponibles(fichier=None):
    """Feuilles reellement presentes, dans l'ordre de PERIMETRES."""
    chemin = str(fichier or FICHIER_DONNEES_CALCULS)
    presentes = set(pd.ExcelFile(chemin).sheet_names)
    return [(f, lib) for f, lib in PERIMETRES if f in presentes]


def familles_disponibles(feuille, fichier=None):
    """Familles de mesure presentes dans la feuille, avec leurs series."""
    df = _lire(feuille, fichier)
    colonnes = [str(c) for c in df.columns]

    resultat = []
    for nom, prefixe, suffixe, _unite in FAMILLES:
        if prefixe is None:
            # Indice : series brutes (elements du panier), agregats exclus
            series = [
                c
                for c in colonnes
                if c not in AGREGATS
                and not c.startswith("Inflation")
                and not c.startswith("Contrib")
                and not c.startswith("IPC")
            ]
        else:
            series = [c for c in colonnes if c.startswith(prefixe)]

        if series:
            resultat.append(
                {
                    "nom": nom,
                    "colonnes": series,
                    "libelles": [nettoyer_libelle(c, prefixe, suffixe) for c in series],
                }
            )
    return resultat


def agregats_disponibles(feuille, fichier=None):
    """Series agregees de la feuille (IPC, inflation globale, contributions core)."""
    df = _lire(feuille, fichier)
    return [str(c) for c in df.columns if str(c) in AGREGATS]


def nettoyer_libelle(colonne, prefixe=None, suffixe=None):
    """'Contrib_YoY_Pain_Cereales (pp)' -> 'Pain Cereales'."""
    libelle = str(colonne)
    if prefixe and libelle.startswith(prefixe):
        libelle = libelle[len(prefixe) :]
    if suffixe and libelle.endswith(suffixe):
        libelle = libelle[: -len(suffixe)]
    return libelle.replace("_", " ").strip()


def charger(feuille, colonnes, date_debut=None, date_fin=None, fichier=None):
    """
    Renvoie un DataFrame indexe par date, restreint aux colonnes et a la
    periode demandees. Les colonnes absentes sont ignorees silencieusement.
    """
    df = _lire(feuille, fichier)
    presentes = [c for c in colonnes if c in df.columns]
    if not presentes:
        return pd.DataFrame(index=df.index[:0])

    df = df[presentes]
    if date_debut is not None:
        df = df.loc[pd.Timestamp(date_debut) :]
    if date_fin is not None:
        df = df.loc[: pd.Timestamp(date_fin) + pd.offsets.MonthEnd(1)]
    return df
