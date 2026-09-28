"""
Séries temporelles.

Explorateur : on choisit un périmètre, une mesure, les séries à comparer, un
mode de représentation et une période. Le graphique, la synthèse chiffrée et
le tableau exportable se mettent à jour ensemble.
"""

import streamlit as st

import backend.inflation.series as S
from app.components.theme import entete_page, separateur_dore, titre_section, pied_de_page
from app.components.explorateur_series import afficher_series, modes_representation
from app.components.layout import demarrer_page, libelle_page
from app.components.periode import selecteur_periode, format_mois

contenu = demarrer_page("inflation_series")


@st.cache_data(show_spinner=False)
def _perimetres():
    return S.perimetres_disponibles()


@st.cache_data(show_spinner=False)
def _familles(feuille):
    return S.familles_disponibles(feuille)


@st.cache_data(show_spinner=False)
def _agregats(feuille):
    return S.agregats_disponibles(feuille)


@st.cache_data(show_spinner=False)
def _bornes(feuille):
    df = S.charger(feuille, S.familles_disponibles(feuille)[0]["colonnes"][:1])
    return df.index.min().date(), df.index.max().date()


@st.cache_data(show_spinner=False)
def _donnees(feuille, colonnes, debut, fin):
    return S.charger(feuille, list(colonnes), debut, fin)


with contenu:
    entete_page(
        libelle_page("inflation_series"),
        "Comparez les séries du panier sur la mesure, la période et la représentation de votre choix.",
    )
    separateur_dore()

    titre_section("Sélection")

    perimetres = _perimetres()
    libelles_perimetres = [lib for _f, lib in perimetres]
    feuille_par_libelle = {lib: f for f, lib in perimetres}

    col_p, col_m, col_mode = st.columns([2.4, 2.4, 3.2])

    with col_p:
        libelle_perimetre = st.selectbox(
            "Périmètre",
            options=libelles_perimetres,
            key="serie_perimetre",
        )
    feuille = feuille_par_libelle[libelle_perimetre]

    familles = _familles(feuille)
    with col_m:
        nom_famille = st.selectbox(
            "Mesure",
            options=[f["nom"] for f in familles],
            key="serie_mesure",
        )

    famille = next(f for f in familles if f["nom"] == nom_famille)
    unite = S.UNITES.get(nom_famille, "")

    modes = modes_representation(
        "niveau" if nom_famille == "Indice" else "contribution" if nom_famille.startswith("Contribution") else "taux"
    )

    with col_mode:
        mode = (
            st.segmented_control(
                "Représentation",
                options=modes,
                default=modes[0],
                key="serie_mode",
            )
            or modes[0]
        )

    libelle_vers_colonne = dict(zip(famille["libelles"], famille["colonnes"]))
    disponibles = famille["libelles"]

    series_choisies = st.multiselect(
        "Séries comparées",
        options=disponibles,
        default=disponibles[: min(4, len(disponibles))],
        key="serie_choix_" + feuille + "_" + nom_famille,
    )

    agregats = _agregats(feuille)
    col_ag, _reste = st.columns([2.4, 5.6])
    agregat_choisi = None
    with col_ag:
        if agregats:
            agregat_choisi = st.selectbox(
                "Superposer un agrégat",
                options=["Aucun"] + agregats,
                key="serie_agregat",
            )
            if agregat_choisi == "Aucun":
                agregat_choisi = None

    date_min, date_max = _bornes(feuille)
    debut, fin = selecteur_periode(date_min, date_max, cle="series", defaut="5 ans")

    if not series_choisies:
        st.info("Sélectionnez au moins une série à afficher.")
        pied_de_page()
        st.stop()

    colonnes = [libelle_vers_colonne[l] for l in series_choisies]
    donnees = _donnees(feuille, tuple(colonnes), debut, fin)

    if donnees.empty:
        st.warning("Aucune donnée sur cette période.")
        pied_de_page()
        st.stop()

    donnees = donnees.copy()
    donnees.columns = series_choisies[: len(donnees.columns)]
    agregat = None
    if agregat_choisi:
        serie_agregat = _donnees(feuille, (agregat_choisi,), debut, fin)
        if not serie_agregat.empty:
            agregat = (agregat_choisi, serie_agregat[agregat_choisi])
    afficher_series(
        donnees,
        mode,
        unite,
        titre=nom_famille + " · " + libelle_perimetre,
        titre_axe=nom_famille,
        format_date=format_mois,
        periode_txt=format_mois(debut) + " &rarr; " + format_mois(fin),
        nom_csv="series_" + feuille + "_" + nom_famille.replace(" ", "_").lower(),
        cle="series",
        agregat=agregat,
    )

    pied_de_page()
