"""
Inflation — Indices complémentaires (national).

Trois indices publiés au niveau national, déjà calculés à la source
(feuille 'FCI_REG' du fichier complémentaire) et simplement intégrés ici :
- Réglementés,
- Fort Contenu d'Import (FCI),
- Hors Réglementés et Hors Agricoles frais (inflation sous-jacente 2).

Ces indices n'existent qu'au niveau national : pour Grand Alger, la
décomposition core / non-core (page Vue d'ensemble) reste la référence.
"""

import pandas as pd
import streamlit as st

from backend.inflation.calculator import (
    extraire_inflation_mom,
    extraire_inflation_yoy,
    get_max_date,
)
from backend.inflation.visualizer import (
    tracer_indices_complementaires_yoy,
    tracer_indices_complementaires_mom,
)
from config.settings import (
    FICHIER_DONNEES_CALCULS,
    FEUILLE_NATIONAL,
    FEUILLE_NATIONAL_REGLEMENTES,
    FEUILLE_NATIONAL_FCI,
    FEUILLE_NATIONAL_CORE2,
)
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
)
from app.components.journal import signaler
from app.components.layout import demarrer_page, libelle_page
from app.components.kpi_card import carte_kpi
from app.components.charts import graphique_puis_tableau
from app.components.periode import selecteur_periode, format_mois

contenu = demarrer_page("inflation_complementaire")

FICHIER = str(FICHIER_DONNEES_CALCULS)


@st.cache_data(show_spinner=False)
def _bornes(feuille):
    df = pd.read_excel(FICHIER, sheet_name=feuille)
    dates = pd.to_datetime(df["date"])
    return dates.min().date(), dates.max().date()


with contenu:
    entete_page(
        libelle_page("inflation_complementaire"),
        "Réglementés, Fort Contenu d'Import et inflation sous-jacente 2 "
        "(hors réglementés, hors agricole frais) — panier national.",
    )
    separateur_dore()

    try:
        FEUILLES = [
            FEUILLE_NATIONAL,
            FEUILLE_NATIONAL_REGLEMENTES,
            FEUILLE_NATIONAL_FCI,
            FEUILLE_NATIONAL_CORE2,
        ]

        titre_section("Filtres")
        col_gliss, col_periode = st.columns([2, 7.4], vertical_alignment="top")
        with col_gliss:
            glissement = st.selectbox(
                "Type de glissement",
                options=["Annuel", "Mensuel"],
                key="glissement_complementaires",
            )
        annuel = glissement == "Annuel"

        date_min, date_max = _bornes(FEUILLE_NATIONAL)
        with col_periode:
            debut, fin = selecteur_periode(date_min, date_max, cle="complementaires", defaut="5 ans")

        date_debut = pd.to_datetime(debut).strftime("%Y-%m")
        date_fin = pd.to_datetime(fin).strftime("%Y-%m")

        # -------------------------------------------------------- indicateurs
        titre_section("Indicateurs clés")

        col_k1, col_k2, col_k3, col_k4 = st.columns(4, gap="medium")
        extraire = extraire_inflation_yoy if annuel else extraire_inflation_mom

        date_reference = get_max_date(FICHIER, FEUILLE_NATIONAL)
        reference = date_reference.strftime("%Y-%m-%d")
        note = "dernier point : " + format_mois(date_reference)

        mesures = [
            ("Indice global · National", FEUILLE_NATIONAL),
            ("Réglementés", FEUILLE_NATIONAL_REGLEMENTES),
            ("Fort contenu d'import", FEUILLE_NATIONAL_FCI),
            ("Sous-jacente 2", FEUILLE_NATIONAL_CORE2),
        ]
        for colonne, (libelle, feuille) in zip((col_k1, col_k2, col_k3, col_k4), mesures):
            taux, evolution = extraire(FICHIER, feuille, reference)
            with colonne:
                st.markdown(
                    carte_kpi(libelle, float(taux.replace("%", "")), float(evolution), note=note),
                    unsafe_allow_html=True,
                )

        # --------------------------------------------------------- graphique
        suffixe = " — glissement annuel" if annuel else " — glissement mensuel"
        titre_section("Évolution")
        tracer = tracer_indices_complementaires_yoy if annuel else tracer_indices_complementaires_mom
        graphique_puis_tableau(
            tracer(
                nom_fichier=FICHIER,
                feuille_national=FEUILLE_NATIONAL,
                feuille_reglementes=FEUILLE_NATIONAL_REGLEMENTES,
                feuille_fci=FEUILLE_NATIONAL_FCI,
                feuille_core2=FEUILLE_NATIONAL_CORE2,
                date_debut=date_debut,
                date_fin=date_fin,
                export_png=False,
            ),
            cle="indices_complementaires",
            nom_fichier="indices_complementaires_nationaux_" + ("yoy" if annuel else "mom"),
            hauteur=460,
            titre="Indices nationaux complémentaires" + suffixe,
        )
        st.caption(
            "Réglementés, FCI et sous-jacente 2 sont calculés à la source et "
            "intégrés tels quels ; ils ne sont publiés qu'au niveau national."
        )
    except Exception as err:
        signaler("04_Inflation_Indice_complementaire", err, "Données indisponibles.", "error")

    pied_de_page()
