"""
Non-régression du bug de portée : en « National », aucune série ni aucun
titre ne doit provenir du panier Grand Alger (et inversement).
"""

import os

import pandas as pd
import pytest

from config.settings import FICHIER_DONNEES_CALCULS, FEUILLE_GRAND_ALGER, FEUILLE_NATIONAL
from backend.inflation.portee import scope_vue_ensemble, PORTEES

pytestmark = pytest.mark.skipif(
    not os.path.exists(FICHIER_DONNEES_CALCULS), reason="fichier de calculs absent (lancer pipeline_global)"
)

DEBUT, FIN = "2023-01", "2024-12"


@pytest.mark.parametrize("mode", ["yoy", "mom"])
def test_les_deux_portees_different(mode):
    ga, nat = (scope_vue_ensemble(p, mode) for p in PORTEES)
    assert ga["feuille_globale"] == FEUILLE_GRAND_ALGER
    assert nat["feuille_globale"] == FEUILLE_NATIONAL
    assert ga["cle"] != nat["cle"]
    for cle in ("titre_evolution", "titre_contributions"):
        assert ga[cle] != nat[cle]
        assert "Grand Alger" not in nat[cle]
    assert all("Grand Alger" not in libelle for libelle, _f in nat["kpi"])
    assert all(f != FEUILLE_GRAND_ALGER for _l, f in nat["kpi"])


@pytest.mark.parametrize("mode", ["yoy", "mom"])
def test_series_tracees_viennent_de_la_bonne_feuille(mode):
    colonne = "Inflation (%, yoy)" if mode == "yoy" else "Inflation (%, mom)"
    for portee in PORTEES:
        scope = scope_vue_ensemble(portee, mode)
        attendu = (
            pd.read_excel(FICHIER_DONNEES_CALCULS, sheet_name=scope["feuille_globale"])
            .set_index("date")[colonne]
            .loc[DEBUT:FIN]
            .dropna()
        )
        attendu.index = pd.to_datetime(attendu.index).to_period("M")
        fig = scope["tracer_evolution"](DEBUT, FIN)
        premiere = fig.data[0]
        trace = pd.Series(list(premiere.y), index=pd.to_datetime(list(premiere.x)).to_period("M")).dropna()
        commun = attendu.index.intersection(trace.index)
        assert len(commun) >= 12
        assert (attendu.loc[commun] - trace.loc[commun]).abs().max() < 0.006, (
            portee
        )  # valeurs tracées arrondies à 2 décimales


def test_contributions_nationales_ne_sont_pas_core_noncore():
    fig = scope_vue_ensemble("National", "yoy")["tracer_contributions"](DEBUT, FIN)
    noms = [t.name for t in fig.data]
    assert not any("Core" in (n or "") for n in noms)
    assert len(noms) >= 8  # les huit groupes (plus la courbe d'ensemble)
