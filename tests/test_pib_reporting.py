"""Moteur de rédaction PIB : règles déterministes, gabarits de narrative_rules.json."""

import os

import pytest

from backend.inflation import reporting as R


def test_virgule_decimale():
    assert R.virgule_decimale("3.9 % et +0.45 pt, T2 2025.") == "3,9 % et +0,45 pt, T2 2025."


def test_niveau_croissance():
    niveaux = R.REGLES_PIB["niveaux"]
    assert R.qualificatif_niveau_croissance(-0.5) == niveaux["contraction"]
    assert R.qualificatif_niveau_croissance(1.0) == niveaux["faible"]
    assert R.qualificatif_niveau_croissance(3.0) == niveaux["moderee"]
    assert R.qualificatif_niveau_croissance(6.0) == niveaux["soutenue"]


def test_synthese_hausse_et_baisse():
    texte = R.texte_synthese_pib(3.9, 4.3, "deuxième trimestre 2025")
    assert "progresse de 3.9 %" in texte and R.QUALIFICATIFS["deceleration_moderee"] in texte
    assert "recule de 1.2 %" in R.texte_synthese_pib(-1.2, 0.5, "premier trimestre 2020")


def test_hydrocarbures_commente_un_ecart():
    texte = R.texte_hydrocarbures(5.4, -5.5, 3.9)
    assert R.GABARITS_PIB["sens_hydrocarbures_freinent"] in texte
    assert "s'écarte" not in R.texte_hydrocarbures(4.0, 3.5, 3.9)


def test_contributions_pluriel():
    positifs = [{"nom": "Services", "contribution": 1.77, "part": 40.0}]
    negatifs = [{"nom": "A", "contribution": -0.5, "part": 10.0}, {"nom": "B", "contribution": -0.2, "part": 5.0}]
    texte = R.texte_contributions_pib(positifs, negatifs, "offre")
    assert "Services (+1.77 pt)" in texte and R.GABARITS_PIB["verbe_pluriel"] in texte


def _fichiers_reels():
    from config.settings import FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE

    return os.path.exists(FICHIER_PIB_OFFRE) and os.path.exists(FICHIER_PIB_DEMANDE)


@pytest.mark.skipif(not _fichiers_reels(), reason="fichiers ONS absents")
def test_redaction_sur_donnees_reelles():
    contexte = R.construire_contexte_pib("2025-06-01")
    textes = R._rediger_pib(contexte)
    assert contexte["trimestre_court"] == "T2 2025"
    assert textes["synthese"] and textes["offre"] and textes["demande"]
    assert "." not in textes["synthese"].split("%")[0][-4:]  # virgule décimale
