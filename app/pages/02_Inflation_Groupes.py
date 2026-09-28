"""
Inflation — Groupes.

Évolution et contribution des huit groupes du panier. Chaque graphique est suivi du tableau de ses valeurs.
"""

import pandas as pd
import streamlit as st

from backend.inflation.visualizer import (
    tracer_inflation_grand_alger_mom,
    tracer_inflation_grand_alger_yoy,
    tracer_inflation_national_mom,
    tracer_inflation_national_yoy,
    tracer_inflation_contributions_grand_alger_mom,
    tracer_inflation_contributions_grand_alger_yoy,
    tracer_inflation_contributions_national_mom,
    tracer_inflation_contributions_national_yoy,
)
from config.settings import (
    FICHIER_DONNEES_CALCULS,
    FEUILLE_GRAND_ALGER,
    FEUILLE_NATIONAL,
)
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
)
from app.components.journal import signaler
from app.components.layout import demarrer_page, libelle_page
from app.components.charts import graphique_puis_tableau
from app.components.periode import selecteur_periode

contenu = demarrer_page("inflation_groupes")

FICHIER = str(FICHIER_DONNEES_CALCULS)

_EVOLUTION = {
    (True, True): tracer_inflation_grand_alger_yoy,
    (True, False): tracer_inflation_grand_alger_mom,
    (False, True): tracer_inflation_national_yoy,
    (False, False): tracer_inflation_national_mom,
}
_CONTRIBUTIONS = {
    (True, True): tracer_inflation_contributions_grand_alger_yoy,
    (True, False): tracer_inflation_contributions_grand_alger_mom,
    (False, True): tracer_inflation_contributions_national_yoy,
    (False, False): tracer_inflation_contributions_national_mom,
}


@st.cache_data(show_spinner=False)
def _bornes(feuille):
    df = pd.read_excel(FICHIER, sheet_name=feuille)
    dates = pd.to_datetime(df["date"])
    return dates.min().date(), dates.max().date()


with contenu:
    entete_page(
        libelle_page("inflation_groupes"),
        "Évolution et contribution en points de pourcentage des huit groupes de produits composant le panier.",
    )
    separateur_dore()

    # ------------------------------------------------------------- filtres
    titre_section("Filtres")

    col_portee, col_gliss, col_periode = st.columns([2, 2, 5.4], vertical_alignment="top")
    with col_portee:
        portee = st.selectbox(
            "Portée géographique",
            options=["Grand Alger", "National"],
            key="portee",
        )
    with col_gliss:
        glissement = st.selectbox(
            "Type de glissement",
            options=["Annuel", "Mensuel"],
            key="glissement",
        )

    grand_alger = portee == "Grand Alger"
    annuel = glissement == "Annuel"
    feuille = FEUILLE_GRAND_ALGER if grand_alger else FEUILLE_NATIONAL

    date_min, date_max = _bornes(feuille)
    with col_periode:
        debut, fin = selecteur_periode(date_min, date_max, cle="groupes", defaut="5 ans")

    date_debut = pd.to_datetime(debut).strftime("%Y-%m")
    date_fin = pd.to_datetime(fin).strftime("%Y-%m")

    # ------------------------------------- structure du panier, en tête de
    # --------------------------------------------------------- graphiques
    suffixe = " — glissement annuel" if annuel else " — glissement mensuel"
    nom_base = ("yoy" if annuel else "mom") + "_" + ("grand_alger" if grand_alger else "national")

    titre_section("Évolution des groupes")
    try:
        graphique_puis_tableau(
            _EVOLUTION[(grand_alger, annuel)](FICHIER, date_debut, date_fin, export_png=False),
            cle="evolution_groupes",
            nom_fichier="groupes_evolution_" + nom_base,
            hauteur=470,
            titre="Évolution des huit groupes · " + portee + suffixe,
        )
    except Exception as err:
        signaler("02_Inflation_Groupes", err, "Graphique indisponible.", "error")

    titre_section("Contributions des groupes")
    try:
        graphique_puis_tableau(
            _CONTRIBUTIONS[(grand_alger, annuel)](FICHIER, date_debut, date_fin, export_png=False),
            cle="contributions_groupes",
            nom_fichier="groupes_contributions_" + nom_base,
            hauteur=470,
            titre="Contribution des groupes à l'indice global · " + portee + suffixe,
        )
    except Exception as err:
        signaler("02_Inflation_Groupes", err, "Graphique indisponible.", "error")

    pied_de_page()
