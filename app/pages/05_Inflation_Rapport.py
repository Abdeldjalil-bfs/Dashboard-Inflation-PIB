"""
Rapport mensuel d'inflation.

Cette page ne contient aucune logique de génération : elle choisit un mois de
référence, appelle backend.inflation.reporting.generer_rapport_pdf() et
propose le fichier au téléchargement.
"""

import os

import pandas as pd
import streamlit as st

from backend.inflation.reporting import (
    generer_rapport_pdf,
    libelle_mois,
)
from config.settings import (
    FICHIER_DONNEES_CALCULS,
    RAPPORTS_DIR,
    FEUILLE_GRAND_ALGER,
)
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    TEXTE_ATTENUE,
)
from app.components.journal import journaliser, journaliser_erreur
from app.components.layout import demarrer_page, libelle_page

contenu = demarrer_page("inflation_rapport")


@st.cache_data(show_spinner=False)
def _mois_disponibles():
    """Mois couverts par le fichier de calculs, du plus récent au plus ancien."""
    df = pd.read_excel(str(FICHIER_DONNEES_CALCULS), sheet_name=FEUILLE_GRAND_ALGER)
    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce").dropna().sort_values()
    # Une ligne par mois : on garde la dernière date connue de chaque mois.
    par_mois = {}
    for date in dates:
        par_mois[(date.year, date.month)] = date
    return sorted(par_mois.values(), reverse=True)


with contenu:
    entete_page(
        libelle_page("inflation_rapport"),
        "Document éditorial généré à partir des séries calculées : couverture, "
        "synthèse exécutive, décomposition core / non-core, groupes, catégories "
        "et annexe méthodologique.",
    )
    separateur_dore()

    titre_section("Mois de référence")

    mois = _mois_disponibles()
    if not mois:
        st.error("Aucune donnée disponible dans le fichier de calculs.")
        pied_de_page()
        st.stop()

    col_mois, col_bouton, _reste = st.columns([2.6, 2, 3.4], vertical_alignment="bottom")

    with col_mois:
        index = st.selectbox(
            "Mois du rapport",
            options=range(len(mois)),
            format_func=lambda i: libelle_mois(mois[i]),
            index=0,
            key="rapport_mois",
        )
    date_reference = pd.Timestamp(mois[index])

    nom_fichier = "rapport_inflation_%04d_%02d" % (date_reference.year, date_reference.month)
    chemin_sortie = os.path.join(str(RAPPORTS_DIR), nom_fichier + ".pdf")

    with col_bouton:
        lancer = st.button("Générer le rapport", key="btn_rapport")

    if lancer:
        with st.spinner("Génération du rapport…"):
            try:
                chemin = generer_rapport_pdf(date_reference.strftime("%Y-%m-%d"), chemin_sortie)
                st.session_state["rapport_chemin"] = chemin
                journaliser("rapport", "rapport d'inflation généré : " + os.path.basename(chemin))
                st.session_state["rapport_format"] = "pdf"
            except Exception as err:
                journaliser_erreur("rapport", err)
                st.error(
                    "La génération du rapport a échoué. Réessayez ; si le problème persiste, "
                    "consultez le journal de l'application."
                )
                st.session_state.pop("rapport_chemin", None)

    chemin = st.session_state.get("rapport_chemin")
    if chemin and os.path.exists(chemin):
        format_rapport = st.session_state.get("rapport_format", "pdf")
        with open(chemin, "rb") as flux:
            donnees = flux.read()

        titre_section("Document")
        col_dl, col_info = st.columns([2, 6], vertical_alignment="center")
        with col_dl:
            st.download_button(
                "Télécharger le rapport",
                data=donnees,
                file_name=os.path.basename(chemin),
                mime="application/pdf",
                key="dl_rapport",
            )
        with col_info:
            st.markdown(
                "<div style='font-size:0.78rem;color:"
                + TEXTE_ATTENUE
                + ";'>"
                + os.path.basename(chemin)
                + " — "
                + ("%.0f" % (len(donnees) / 1024))
                + " Ko · format "
                + format_rapport.upper()
                + "</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div style='font-size:0.74rem;color:" + TEXTE_ATTENUE + ";margin-top:1.4rem;'>"
        "Le texte d'analyse est produit par un moteur de règles déterministe "
        "paramétré dans <code>config/narrative_rules.json</code> : aucun modèle "
        "de langage n'intervient. Chaque rapport porte en dernière page la date "
        "de génération, la dernière donnée disponible et l'empreinte des "
        "pondérations utilisées.</div>",
        unsafe_allow_html=True,
    )

    pied_de_page()
