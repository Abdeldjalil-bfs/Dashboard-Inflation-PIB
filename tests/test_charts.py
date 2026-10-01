"""Export Excel au format tidy, partagé par graphique_puis_tableau() et
l'explorateur de séries (app/components/charts.py, explorateur_series.py)."""

import io

import pandas as pd

from app.components.charts import tableau_vers_excel_tidy


def test_tableau_vers_excel_tidy_une_ligne_par_observation():
    tableau = pd.DataFrame(
        {"Inflation IPC": [1.2, 2.3], "Core": [0.5, None]},
        index=pd.Index(["juil. 2026", "juin 2026"], name="Date"),
    )
    donnees = tableau_vers_excel_tidy(tableau)
    long = pd.read_excel(io.BytesIO(donnees), engine="openpyxl")

    assert list(long.columns) == ["Date", "serie", "valeur"]
    # Une ligne par observation non vide : 2 + 1 (la case manquante de Core
    # n'est pas exportée), jamais une colonne par série.
    assert len(long) == 3
    assert set(long["serie"]) == {"Inflation IPC", "Core"}
    ligne = long[(long["Date"] == "juil. 2026") & (long["serie"] == "Inflation IPC")]
    assert ligne["valeur"].iloc[0] == 1.2


def test_tableau_vers_excel_tidy_nom_colonne_valeur():
    tableau = pd.DataFrame({"A": [10.0]}, index=pd.Index(["T1 2025"], name="Date"))
    long = pd.read_excel(io.BytesIO(tableau_vers_excel_tidy(tableau, nom_valeur="pp")), engine="openpyxl")
    assert "pp" in long.columns
