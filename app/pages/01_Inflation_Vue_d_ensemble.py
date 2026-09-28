"""
Inflation — Vue d'ensemble.

Carte de la portée, indicateurs clés, évolution et contributions. La portée
pilote TOUT, d'une seule source (`scope_vue_ensemble`) :

  - Grand Alger : indice global, core et non-core (décomposition publiée
    pour Grand Alger uniquement), contributions core / non-core ;
  - National    : indice global national, sous-jacente 2 et produits
    réglementés (séries nationales), contributions des huit groupes du panier
    national. Aucune série Grand Alger n'est affichée dans cette portée.
"""

import pandas as pd
import streamlit as st

from backend.inflation.calculator import extraire_inflation_mom, extraire_inflation_yoy, get_max_date
from backend.inflation.visualizer import tracer_carte_scope
from backend.inflation.portee import scope_vue_ensemble
from config.settings import FICHIER_DONNEES_CALCULS
from config.textes import MESSAGES
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    appliquer_theme_graphique,
)
from app.components.layout import demarrer_page, libelle_page
from app.components.kpi_card import carte_kpi
from app.components.charts import graphique_puis_tableau
from app.components.periode import selecteur_periode, format_mois
from app.components.donnees_pib import note_technique

contenu = demarrer_page("inflation_vue")

FICHIER = str(FICHIER_DONNEES_CALCULS)


@st.cache_data(show_spinner=False)
def _bornes(feuille):
    df = pd.read_excel(FICHIER, sheet_name=feuille)
    dates = pd.to_datetime(df["date"])
    return dates.min().date(), dates.max().date()


with contenu:
    entete_page(
        libelle_page("inflation_vue"),
        "Indice des prix à la consommation : niveau, évolution et contributions, pour la portée choisie.",
    )
    separateur_dore()

    # ------------------------------------------------------------- filtres
    titre_section("Filtres")
    col_portee, col_gliss, col_periode = st.columns([2, 2, 5.4], vertical_alignment="top")
    with col_portee:
        portee = st.selectbox("Portée géographique", options=["Grand Alger", "National"], key="portee")
    with col_gliss:
        glissement = st.selectbox("Type de glissement", options=["Annuel", "Mensuel"], key="glissement")
    mode = "yoy" if glissement == "Annuel" else "mom"
    scope = scope_vue_ensemble(portee, mode)

    try:
        date_min, date_max = _bornes(scope["feuille_globale"])
    except Exception:
        st.error(MESSAGES["donnees_indisponibles"])
        pied_de_page()
        st.stop()
    with col_periode:
        debut, fin = selecteur_periode(date_min, date_max, cle="vue", defaut="5 ans")
    date_debut = pd.to_datetime(debut).strftime("%Y-%m")
    date_fin = pd.to_datetime(fin).strftime("%Y-%m")

    # -------------------------------------------------------- indicateurs
    # Les indicateurs suivent la fin de la période choisie.
    date_reference = min(pd.Timestamp(fin), get_max_date(FICHIER, scope["feuille_globale"]))
    reference = date_reference.strftime("%Y-%m-%d")
    extraire = extraire_inflation_yoy if mode == "yoy" else extraire_inflation_mom
    titre_section("Indicateurs clés · " + portee + " · " + format_mois(date_reference))

    colonnes = st.columns(len(scope["kpi"]), gap="medium")
    taux_global = evolution_global = None
    for rang, (colonne, (libelle, feuille)) in enumerate(zip(colonnes, scope["kpi"])):
        with colonne:
            try:
                taux, evolution = extraire(FICHIER, feuille, reference)
                taux, evolution = float(str(taux).replace("%", "")), float(evolution)
                if taux != taux:  # NaN : composantes non renseignées pour ce mois
                    raise ValueError("indicateur non calculable")
                if rang == 0:
                    taux_global, evolution_global = taux, evolution
                # Hausse de l'inflation = défavorable (rouge).
                note = "vs même mois de l'an dernier" if mode == "yoy" else "vs mois précédent"
                st.markdown(
                    carte_kpi(
                        libelle,
                        taux,
                        evolution,
                        favorable_si_hausse=False,
                        note=note + " · " + format_mois(date_reference),
                    ),
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(
                    carte_kpi(libelle, None, None, note=MESSAGES["donnees_indisponibles"]), unsafe_allow_html=True
                )

    # -------------------------------------------------------------- carte
    if taux_global is not None:
        titre_section("Repère géographique")
        carte = tracer_carte_scope(portee, taux_global, evolution_global, date_reference, mode=mode)
        st.plotly_chart(appliquer_theme_graphique(carte, hauteur=380), width="stretch", key="carte_" + scope["cle"])

    # --------------------------------------------------------- graphiques
    titre_section("Évolution")
    try:
        graphique_puis_tableau(
            scope["tracer_evolution"](date_debut, date_fin),
            cle="evolution_" + scope["cle"],
            nom_fichier="inflation_" + scope["cle"],
            hauteur=430,
            titre=scope["titre_evolution"],
        )
    except Exception:
        st.info(MESSAGES["graphique_indisponible"])

    titre_section("Contributions")
    try:
        graphique_puis_tableau(
            scope["tracer_contributions"](date_debut, date_fin),
            cle="contributions_" + scope["cle"],
            nom_fichier="contributions_" + scope["cle"],
            hauteur=430,
            titre=scope["titre_contributions"],
        )
    except Exception:
        st.info(MESSAGES["graphique_indisponible"])
    if scope["note"]:
        note_technique(scope["note"])

    pied_de_page()
