"""
Inflation — Catégories.

Répartition du panier entre les trois grandes masses (biens alimentaires,
biens manufacturés, services), puis leur évolution et leur contribution.
Chaque graphique est suivi du tableau de ses valeurs.
"""

import pandas as pd
import streamlit as st

from backend.inflation.visualizer import (
    tracer_inflation_categories_mom,
    tracer_inflation_categories_yoy,
    tracer_inflation_contributions_categories_mom,
    tracer_inflation_contributions_categories_yoy,
)
from config.settings import FICHIER_DONNEES_CALCULS, FEUILLE_CATEGORIES
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

contenu = demarrer_page("inflation_categories")

FICHIER = str(FICHIER_DONNEES_CALCULS)


@st.cache_data(show_spinner=False)
def _bornes():
    df = pd.read_excel(FICHIER, sheet_name=FEUILLE_CATEGORIES)
    dates = pd.to_datetime(df["date"])
    return dates.min().date(), dates.max().date()


with contenu:
    entete_page(
        libelle_page("inflation_categories"),
        "Évolution et contribution en points de pourcentage des biens "
        "alimentaires, des biens manufacturés et des services.",
    )
    separateur_dore()

    # ------------------------------------------------------------- filtres
    # Même bandeau que les autres pages. La portée n'a pas de sens ici : les
    # trois catégories ne sont pas déclinées par territoire.
    titre_section("Filtres")

    col_gliss, col_periode = st.columns([2, 7.4], vertical_alignment="top")

    with col_gliss:
        glissement = st.selectbox(
            "Type de glissement",
            options=["Annuel", "Mensuel"],
            key="glissement",
        )
    annuel = glissement == "Annuel"

    date_min, date_max = _bornes()
    with col_periode:
        debut, fin = selecteur_periode(date_min, date_max, cle="categories", defaut="5 ans")

    date_debut = pd.to_datetime(debut).strftime("%Y-%m")
    date_fin = pd.to_datetime(fin).strftime("%Y-%m")

    # --------------------------------------------------------- graphiques
    suffixe = " — glissement annuel" if annuel else " — glissement mensuel"
    nom_base = "yoy" if annuel else "mom"

    titre_section("Évolution des catégories")
    try:
        tracer = tracer_inflation_categories_yoy if annuel else tracer_inflation_categories_mom
        graphique_puis_tableau(
            tracer(nom_fichier=FICHIER, date_debut=date_debut, date_fin=date_fin, export_png=False),
            cle="evolution_categories",
            nom_fichier="categories_evolution_" + nom_base,
            hauteur=470,
            titre="Évolution des trois catégories · Grand Alger" + suffixe,
        )
    except Exception as err:
        signaler("03_Inflation_Categories", err, "Graphique indisponible.", "error")

    titre_section("Contributions des catégories")
    try:
        tracer = (
            tracer_inflation_contributions_categories_yoy if annuel else tracer_inflation_contributions_categories_mom
        )
        graphique_puis_tableau(
            tracer(nom_fichier=FICHIER, date_debut=date_debut, date_fin=date_fin, export_png=False),
            cle="contributions_categories",
            nom_fichier="categories_contributions_" + nom_base,
            hauteur=470,
            titre="Contribution des catégories à l'indice global · Grand Alger" + suffixe,
        )
    except Exception as err:
        signaler("03_Inflation_Categories", err, "Graphique indisponible.", "error")

    pied_de_page()
