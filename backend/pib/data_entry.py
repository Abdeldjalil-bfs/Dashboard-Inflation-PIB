"""
Saisie des données PIB : insertion, modification, suppression d'une valeur.

Les classeurs ONS (PIB_TR_S.xlsx, PIB_TR_D.xlsx) sont pilotés par formules
(dates en =EDATE, volumes recalculés depuis les taux). Les réenregistrer
avec openpyxl effacerait leurs valeurs en cache et les rendrait illisibles
jusqu'à leur réouverture dans Excel. Ce module ne les modifie donc JAMAIS :
chaque saisie est consignée dans un journal (config.settings.
FICHIER_PIB_SAISIES), rejoué à la lecture par backend.pib.lecture_ons.

Conséquence à connaître : une valeur saisie n'est pas propagée par les
formules ONS (modifier le nominal ne recalcule pas le volume). Chaque onglet
se corrige séparément.
"""

import json
import os
from datetime import datetime

import pandas as pd

from backend.pib import lecture_ons as L

ACTIONS = ("insertion", "modification", "suppression")


def _chemins():
    from config.settings import FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE, FICHIER_PIB_SAISIES

    return {"offre": str(FICHIER_PIB_OFFRE), "demande": str(FICHIER_PIB_DEMANDE)}, str(FICHIER_PIB_SAISIES)


def fichiers_disponibles() -> dict:
    """{'offre': libellé, 'demande': libellé} pour les fichiers présents."""
    chemins, _ = _chemins()
    libelles = {"offre": "Offre — PIB_TR_S", "demande": "Demande — PIB_TR_D"}
    return {cle: libelles[cle] for cle, chemin in chemins.items() if os.path.exists(chemin)}


def feuilles_disponibles() -> dict:
    """{nom d'onglet: libellé} — nominal et réel, depuis pib_config.json."""
    feuilles = L.config_pib()["feuilles"]
    return {
        feuilles["nominal"]: "Prix courants (" + feuilles["nominal"] + ")",
        feuilles["reel"]: "Volumes (" + feuilles["reel"] + ")",
    }


def lire_feuille(fichier_cle: str, feuille: str, journal=None, fichier=None) -> pd.DataFrame:
    """Onglet ONS après application du journal."""
    chemins, _ = _chemins()
    return L.lire_feuille_corrigee(fichier or chemins[fichier_cle], fichier_cle, feuille, journal)


def colonnes_saisissables(fichier_cle: str) -> list:
    return L.colonnes_saisissables(fichier_cle)


def trimestres_disponibles(df: pd.DataFrame, colonne: str) -> list:
    """Trimestres où `colonne` porte une valeur, du plus récent au plus ancien."""
    serie = L.colonne(df, colonne).dropna()
    return sorted(serie.index, reverse=True)


def proposer_trimestres_insertion(df: pd.DataFrame, colonne: str, nb: int = 4) -> list:
    """
    Trimestres saisissables pour une insertion : les trimestres vides de la
    colonne après sa dernière valeur connue, puis les suivants.
    """
    serie = L.colonne(df, colonne)
    connus = serie.dropna()
    depart = connus.index.max() if not connus.empty else df.index.min() - pd.DateOffset(months=3)
    return [depart + pd.DateOffset(months=3 * i) for i in range(1, nb + 1)]


def lire_valeur(df: pd.DataFrame, colonne: str, date):
    serie = L.colonne(df, colonne)
    date = pd.Timestamp(date)
    if date not in serie.index or pd.isna(serie.loc[date]):
        return None
    return float(serie.loc[date])


def evaluer_saisie(df: pd.DataFrame, colonne: str, date, valeur: float, libelle_source: str) -> dict:
    """
    Détection d'anomalies adaptée au trimestriel : historique ANTÉRIEUR à la
    date visée, fenêtre récente en trimestres (anomaly_rules.json), et
    comparaison au même trimestre des années précédentes.
    """
    from config.settings import ANOMALY_RULES_PATH
    from backend.inflation.anomaly_detection import evaluer_valeur

    with open(ANOMALY_RULES_PATH, "r", encoding="utf-8") as flux:
        n_fenetre = json.load(flux).get("fenetre_glissante_trimestres", 20)
    historique = L.colonne(df, colonne).loc[: pd.Timestamp(date) - pd.Timedelta(days=1)]
    return evaluer_valeur(historique, float(valeur), date, colonne, libelle_source, n_fenetre=n_fenetre)


def enregistrer_saisie(
    fichier_cle: str, feuille: str, colonne: str, date, action: str, valeur=None, utilisateur: str = "", journal=None
) -> None:
    """
    Consigne une saisie dans le journal. Contrôles : action connue, colonne
    lue par le tableau de bord, valeur fournie sauf pour une suppression.
    """
    if action not in ACTIONS:
        raise ValueError("Action inconnue : %s" % action)
    if fichier_cle not in ("offre", "demande"):
        raise ValueError("Fichier inconnu : %s" % fichier_cle)
    if L.normaliser(colonne) not in {L.normaliser(c) for c in colonnes_saisissables(fichier_cle)}:
        raise ValueError("Colonne non saisissable : %s" % colonne)
    if action != "suppression" and (valeur is None or pd.isna(valeur)):
        raise ValueError("Une valeur est requise pour une %s." % action)

    if journal is None:
        _, journal = _chemins()
    journal = str(journal)
    existant = L.lire_journal(journal)
    entree = pd.DataFrame(
        [
            {
                "horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                "utilisateur": utilisateur,
                "fichier": fichier_cle,
                "feuille": feuille,
                "date": pd.Timestamp(date),
                "colonne": colonne,
                "action": action,
                "valeur": None if action == "suppression" else float(valeur),
            }
        ]
    )
    tout = entree if existant.empty else pd.concat([existant, entree], ignore_index=True)
    os.makedirs(os.path.dirname(os.path.abspath(journal)), exist_ok=True)
    tout.to_excel(journal, index=False)


def historique_saisies(journal=None) -> pd.DataFrame:
    """Journal complet, saisies les plus récentes en tête."""
    return L.lire_journal(journal).iloc[::-1].reset_index(drop=True)
