"""
Tests de la saisie des données brutes.

L'écriture est testée sur un classeur temporaire construit dans le test :
aucun test ne touche au fichier de production.
"""

import pandas as pd
import pytest
from openpyxl import Workbook

from backend.inflation import data_entry as saisie


COLONNES = ["Element_A", "Element_B", "Element_C"]


@pytest.fixture
def classeur(tmp_path):
    """Classeur d'essai : une feuille 'Grand_Alger', 24 mois d'historique."""
    chemin = tmp_path / "essai.xlsx"
    wb = Workbook()
    feuille = wb.active
    feuille.title = "Grand_Alger"

    feuille.append(["date"] + COLONNES)
    for rang, date in enumerate(pd.date_range("2023-01-01", periods=24, freq="MS")):
        feuille.append([date.to_pydatetime(), 100 + rang * 0.5, 200 + rang * 0.3, 50 + rang * 0.1])

    autre = wb.create_sheet("national")
    autre.append(["date"] + COLONNES)
    for rang, date in enumerate(pd.date_range("2023-01-01", periods=24, freq="MS")):
        autre.append([date.to_pydatetime(), 110 + rang * 0.4, 210 + rang * 0.2, 60 + rang * 0.1])

    wb.save(chemin)
    wb.close()
    return str(chemin)


# ---------------------------------------------------------------------------
# Complétude : la règle du tout ou rien
# ---------------------------------------------------------------------------


def test_completude_vide():
    assert saisie.valider_completude({}) == "vide"
    assert saisie.valider_completude({"a": None, "b": None}) == "vide"
    assert saisie.valider_completude({"a": float("nan")}) == "vide"


def test_completude_partielle():
    assert saisie.valider_completude({"a": 1.0, "b": None}) == "partiel"
    assert saisie.valider_completude({"a": 1.0, "b": 2.0, "c": None}) == "partiel"


def test_completude_complete():
    assert saisie.valider_completude({"a": 1.0, "b": 2.0}) == "complet"
    assert saisie.valider_completude({"a": 0.0}) == "complet", "zéro est une valeur"


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


def test_paniers_disponibles_et_manquants(classeur):
    disponibles = saisie.paniers_disponibles(classeur)
    assert "Grand_Alger" in disponibles and "national" in disponibles
    # 'core' n'est pas dans le classeur d'essai
    assert "core" in saisie.paniers_manquants(classeur)


def test_date_max_globale_retient_la_plus_ancienne(classeur):
    """Deux paniers synchronisés : la date max est celle des deux."""
    assert saisie.date_max_globale(classeur) == pd.Timestamp("2024-12-01")


def test_proposer_dates_insertion(classeur):
    dates = saisie.proposer_dates_insertion(classeur, nb_mois=3)
    assert [str(d) for d in dates] == ["2025-01", "2025-02", "2025-03"]


def test_lire_historique_colonne(classeur):
    serie = saisie.lire_historique_colonne(classeur, "Grand_Alger", "Element_A")
    assert serie.size == 24
    assert serie.iloc[0] == pytest.approx(100.0)


def test_lire_historique_colonne_absente(classeur):
    assert saisie.lire_historique_colonne(classeur, "Grand_Alger", "Inconnue").empty


def test_derniers_mois(classeur):
    assert saisie.derniers_mois(classeur, "Grand_Alger", 3).shape[0] == 3


def test_date_deja_presente(classeur):
    assert saisie.date_deja_presente(classeur, "Grand_Alger", "2024-06-01")
    assert not saisie.date_deja_presente(classeur, "Grand_Alger", "2025-01-01")


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


def test_inserer_nouvelle_ligne(classeur):
    valeurs = {"Element_A": 115.0, "Element_B": 208.0, "Element_C": 53.0}
    saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2025-01-01", valeurs)

    df = pd.read_excel(classeur, sheet_name="Grand_Alger")
    df["date"] = pd.to_datetime(df["date"])
    ligne = df[df["date"] == pd.Timestamp("2025-01-01")]
    assert len(ligne) == 1
    assert ligne.iloc[0]["Element_A"] == pytest.approx(115.0)
    assert ligne.iloc[0]["Element_C"] == pytest.approx(53.0)


def test_inserer_respecte_l_ordre_des_colonnes(classeur):
    """Les valeurs sont replacées par nom d'en-tête, jamais par position."""
    valeurs = {"Element_C": 53.0, "Element_A": 115.0, "Element_B": 208.0}
    saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2025-01-01", valeurs)

    df = pd.read_excel(classeur, sheet_name="Grand_Alger")
    df["date"] = pd.to_datetime(df["date"])
    ligne = df[df["date"] == pd.Timestamp("2025-01-01")].iloc[0]
    assert ligne["Element_A"] == pytest.approx(115.0)
    assert ligne["Element_B"] == pytest.approx(208.0)
    assert ligne["Element_C"] == pytest.approx(53.0)


def test_date_deja_presente_sans_ecraser_leve(classeur):
    valeurs = {"Element_A": 1.0, "Element_B": 2.0, "Element_C": 3.0}
    with pytest.raises(saisie.DateDejaPresente):
        saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2024-06-01", valeurs)


def test_ecrasement_explicite_met_a_jour(classeur):
    valeurs = {"Element_A": 999.0, "Element_B": 998.0, "Element_C": 997.0}
    saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2024-06-01", valeurs, ecraser=True)

    df = pd.read_excel(classeur, sheet_name="Grand_Alger")
    df["date"] = pd.to_datetime(df["date"])
    ligne = df[df["date"] == pd.Timestamp("2024-06-01")]
    assert len(ligne) == 1, "l'écrasement ne doit pas créer une ligne en double"
    assert ligne.iloc[0]["Element_A"] == pytest.approx(999.0)


def test_colonne_inconnue_refusee(classeur):
    with pytest.raises(ValueError, match="absentes"):
        saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2025-01-01", {"Element_Z": 1.0})


def test_feuille_inconnue_refusee(classeur):
    with pytest.raises(ValueError, match="absente"):
        saisie.inserer_ligne_panier(classeur, "panier_fantome", "2025-01-01", {"Element_A": 1.0})


def test_insertion_puis_relecture_alimente_la_detection(classeur):
    """La valeur écrite doit être visible par le module d'anomalies."""
    from backend.inflation import anomaly_detection as ad

    valeurs = {"Element_A": 115.0, "Element_B": 208.0, "Element_C": 53.0}
    saisie.inserer_ligne_panier(classeur, "Grand_Alger", "2025-01-01", valeurs)

    serie = saisie.lire_historique_colonne(classeur, "Grand_Alger", "Element_A")
    assert serie.size == 25
    verdict = ad.evaluer_valeur(serie, 1150.0, pd.Timestamp("2025-02-01"), "Element_A", "Grand_Alger")
    assert verdict["severite"] == "marque"


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_structure_panier_vient_de_categories_json():
    elements = saisie.structure_panier("Grand_Alger")
    assert len(elements) == 8
    assert all(isinstance(e, str) for e in elements)


def test_structure_panier_inconnu():
    with pytest.raises(ValueError):
        saisie.structure_panier("panier_fantome")
