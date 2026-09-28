"""
PIB — Séries.

Explorateur des séries PIB de la base (dernière version publiée de chaque
observation) : même fonctionnement, même mise en page et mêmes exports que
la page Séries du module Inflation, en fréquence trimestrielle.
"""

import pandas as pd
import streamlit as st

from backend.pib import series as S
from config.textes import MESSAGES
from app.components.theme import entete_page, separateur_dore, titre_section, pied_de_page
from app.components.layout import demarrer_page, libelle_page
from app.components.explorateur_series import afficher_series, modes_representation
from app.components.periode import selecteur_periode_trimestres, format_trimestre

contenu = demarrer_page("pib_series")


@st.cache_data(show_spinner=False)
def _mesure(bloc, cle):
    return S.mesure(bloc, cle)


with contenu:
    entete_page(
        libelle_page("pib_series"),
        "Comparez les séries des comptes nationaux trimestriels sur la mesure, la "
        "période et la représentation de votre choix.",
    )
    separateur_dore()

    titre_section("Sélection")
    perimetres = S.perimetres()
    col_p, col_m, col_mode = st.columns([2.6, 2.4, 3.0])
    with col_p:
        choix = st.selectbox(
            "Périmètre",
            options=range(len(perimetres)),
            format_func=lambda i: perimetres[i][1],
            key="pib_serie_perimetre",
        )
    bloc, libelle_bloc, type_bloc = perimetres[choix]
    mesures = S.mesures(type_bloc)
    with col_m:
        rang = st.selectbox(
            "Mesure",
            options=range(len(mesures)),
            format_func=lambda i: mesures[i]["libelle"],
            key="pib_serie_mesure_" + type_bloc,
        )
    mesure = mesures[rang]
    modes = modes_representation(mesure["type"])
    with col_mode:
        mode = (
            st.segmented_control(
                "Représentation", options=modes, default=modes[0], key="pib_serie_mode_" + mesure["type"]
            )
            or modes[0]
        )

    try:
        donnees = _mesure(bloc, mesure["cle"])
    except Exception:
        donnees = pd.DataFrame()
    if donnees.empty:
        st.info(MESSAGES["base_vide"])
        pied_de_page()
        st.stop()

    libelle_pib = S.libelles_postes()[S.base_cnt.POSTE_PIB]
    disponibles = [c for c in donnees.columns if c != libelle_pib]
    choisies = st.multiselect(
        "Séries comparées",
        options=disponibles,
        default=disponibles[: min(4, len(disponibles))],
        key="pib_serie_choix_" + bloc + "_" + mesure["cle"],
    )
    superposer = False
    if libelle_pib in donnees.columns:
        col_ag, _reste = st.columns([2.6, 5.4])
        with col_ag:
            superposer = st.toggle("Superposer le PIB total", value=True, key="pib_serie_agregat")

    publies = donnees.dropna(how="all").index
    debut, fin = selecteur_periode_trimestres(
        publies.min().date(), publies.max().date(), cle="pib_series", defaut="5 ans"
    )
    if not choisies:
        st.info("Sélectionnez au moins une série à afficher.")
        pied_de_page()
        st.stop()

    fenetre = donnees.loc[pd.Timestamp(debut) : pd.Timestamp(fin)]
    agregat = (libelle_pib, fenetre[libelle_pib].dropna()) if superposer else None
    afficher_series(
        fenetre[choisies].dropna(how="all"),
        mode,
        mesure["unite"],
        titre=mesure["libelle"] + " · " + libelle_bloc,
        titre_axe=mesure["libelle"],
        format_date=format_trimestre,
        periode_txt=format_trimestre(debut) + " &rarr; " + format_trimestre(fin),
        nom_csv="pib_series_" + bloc.lower() + "_" + mesure["cle"],
        cle="pib_series",
        agregat=agregat,
    )

    pied_de_page()
