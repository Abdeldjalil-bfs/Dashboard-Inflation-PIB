"""
Catalogue et chargement des séries PIB de la base (vue cnt_pib_derniere),
pour la page Séries du module PIB — pendant de backend/inflation/series.py.

Lecture pure : aucune dépendance Streamlit. Les niveaux sont convertis en
milliards de dinars (diviseur de pib_config.json) ; les mesures dérivées
(glissement nominal, part du PIB) sont calculées ici, jamais dans la page.
"""

import pandas as pd

from backend.pib import base_cnt


def _config():
    from backend.pib.calculator import _config_pib

    return _config_pib()


def perimetres():
    """[(bloc, libellé, type)] dans l'ordre de pib_config.json."""
    return [(b["bloc"], b["libelle"], b["type"]) for b in _config()["blocs_cnt"]]


def mesures(type_bloc):
    return _config()["mesures_series"][type_bloc]


def libelles_postes():
    """Clé ou libellé ONS -> libellé affiché."""
    from backend.pib.calculator import libelles_offre, libelles_demande

    libelles = dict(libelles_offre())
    libelles.update(libelles_demande())
    libelles[base_cnt.POSTE_PIB] = _config()["libelles_agregats"]["PIB"]
    return libelles


def tableau_bloc(bloc, conn=None) -> pd.DataFrame:
    """Bloc en format large : index trimestre, une colonne par poste (libellé affiché)."""
    df = base_cnt.lire_derniere(conn, bloc)
    if df.empty:
        return pd.DataFrame()
    df = df.assign(date=[base_cnt.date_trimestre(a, t) for a, t in zip(df["annee"], df["trimestre"])])
    large = df.pivot_table(index="date", columns="poste", values="valeur", aggfunc="first").sort_index()
    ordre = [p for p in libelles_postes() if p in large.columns] + [
        p for p in large.columns if p not in libelles_postes()
    ]
    large = large[ordre]
    large.columns = [libelles_postes().get(c, c) for c in large.columns]
    return large


def mesure(bloc, cle_mesure, conn=None) -> pd.DataFrame:
    """Valeurs de la mesure demandée pour toutes les séries du bloc."""
    large = tableau_bloc(bloc, conn)
    if large.empty or cle_mesure == "brut":
        return large
    libelle_pib = libelles_postes()[base_cnt.POSTE_PIB]
    if cle_mesure == "niveau":
        return large / float(_config()["diviseur_affichage"])
    if cle_mesure == "glissement":
        return (large / large.shift(4) - 1) * 100
    if cle_mesure == "part":
        if libelle_pib not in large.columns:
            return pd.DataFrame()
        return large.div(large[libelle_pib], axis=0).drop(columns=libelle_pib) * 100
    raise ValueError("Mesure inconnue : %s" % cle_mesure)
