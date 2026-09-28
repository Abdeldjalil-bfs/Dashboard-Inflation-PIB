"""
Statistiques d'appui au rapport, communes aux modules Inflation et PIB.

Fonctions pures sur des séries pandas : aucune lecture de fichier, aucune
dépendance au module appelant. Le module Inflation les appelle après lecture
de ses feuilles ; le module PIB directement sur ses séries trimestrielles.
"""

import pandas as pd


def statistiques_serie(serie: pd.Series, date_debut=None, date_fin=None) -> dict:
    """
    Moyenne, écart-type, min, max et nombre d'observations de `serie` sur la
    fenêtre demandée (bornes incluses, None = pas de borne).
    """
    serie = pd.Series(serie).dropna().sort_index()
    if date_debut is not None:
        serie = serie.loc[pd.Timestamp(date_debut) :]
    if date_fin is not None:
        serie = serie.loc[: pd.Timestamp(date_fin)]
    if serie.empty:
        return {"moyenne": None, "ecart_type": None, "min": None, "max": None, "nb_observations": 0}
    return {
        "moyenne": round(float(serie.mean()), 3),
        "ecart_type": round(float(serie.std()), 3) if serie.size > 1 else None,
        "min": round(float(serie.min()), 3),
        "max": round(float(serie.max()), 3),
        "nb_observations": int(serie.size),
    }


def moyenne_depuis_debut_annee(serie: pd.Series, date_reference) -> dict:
    """
    Moyenne de `serie` du début de l'année de `date_reference` (janvier ou T1)
    jusqu'à `date_reference` inclus, et la même fenêtre l'année précédente.

    Retour : {"actuelle", "precedente", "nb_periodes"} — None si non couvert.
    """
    serie = pd.Series(serie).dropna().sort_index()
    date_reference = pd.Timestamp(date_reference)

    def _moyenne(annee):
        fenetre = serie[(serie.index.year == annee) & (serie.index.month <= date_reference.month)]
        return (round(float(fenetre.mean()), 3), int(fenetre.size)) if not fenetre.empty else (None, 0)

    actuelle, nb = _moyenne(date_reference.year)
    precedente, _ = _moyenne(date_reference.year - 1)
    return {"actuelle": actuelle, "precedente": precedente, "nb_periodes": nb}


def classer_contributeurs(valeurs: dict, n: int = 3):
    """
    Plus forts contributeurs positifs et négatifs parmi `valeurs` : un dict
    {libellé: valeur} ou une liste de couples (libellé, valeur).

    Retour : (positifs, negatifs), deux listes de dicts {"nom",
    "contribution", "part"}, triées par valeur absolue décroissante.

    `part` est rapportée à la MASSE des contributions (somme des valeurs
    absolues), non à leur somme algébrique : quand hausses et baisses se
    compensent, la somme tend vers zéro et le ratio explose. La masse donne
    une part bornée entre 0 et 100 %, « part du mouvement d'ensemble ».
    """
    couples = valeurs.items() if isinstance(valeurs, dict) else valeurs
    propres = [(nom, float(v)) for nom, v in couples if v is not None and not pd.isna(v)]
    masse = sum(abs(v) for _n, v in propres)

    def _fiche(nom, valeur):
        return {
            "nom": nom,
            "contribution": round(valeur, 3),
            "part": round(abs(valeur) / masse * 100, 1) if masse > 0 else None,
        }

    positifs = sorted([v for v in propres if v[1] > 0], key=lambda v: -v[1])
    negatifs = sorted([v for v in propres if v[1] < 0], key=lambda v: v[1])
    return ([_fiche(nom, val) for nom, val in positifs[:n]], [_fiche(nom, val) for nom, val in negatifs[:n]])
