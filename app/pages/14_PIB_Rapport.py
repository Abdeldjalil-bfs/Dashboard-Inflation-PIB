"""
Rapport trimestriel PIB.

Aucune logique de génération ici : choix du trimestre, appel à
backend.inflation.reporting.generer_rapport_pib_pdf(), téléchargement.
"""

import os

import pandas as pd
import streamlit as st

from backend.inflation.reporting import generer_rapport_pib_pdf
from config.settings import RAPPORTS_DIR
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    TEXTE_ATTENUE,
)
from app.components.journal import journaliser, journaliser_erreur
from app.components.layout import demarrer_page, libelle_page
from app.components.periode import format_trimestre
from app.components.donnees_pib import charger_ou_arreter

contenu = demarrer_page("pib_rapport")

with contenu:
    entete_page(
        libelle_page("pib_rapport"),
        "Document éditorial généré à partir des comptes nationaux : synthèse, "
        "optique offre, optique demande et annexe méthodologique.",
    )
    separateur_dore()

    r = charger_ou_arreter()
    # Le rapport s'appuie sur le détail sectoriel : trimestres où il est publié.
    trimestres = sorted(r["croissance"]["yoy"]["HH_reel"].dropna().index, reverse=True)

    titre_section("Trimestre de référence")
    col_t, col_bouton, _reste = st.columns([2.6, 2, 3.4], vertical_alignment="bottom")
    with col_t:
        i = st.selectbox(
            "Trimestre du rapport",
            options=range(len(trimestres)),
            format_func=lambda k: format_trimestre(trimestres[k]),
            key="pib_rapport_trimestre",
        )
    date = pd.Timestamp(trimestres[i])
    nom = "rapport_pib_%s" % format_trimestre(date).replace(" ", "_")
    chemin_sortie = os.path.join(str(RAPPORTS_DIR), nom + ".pdf")

    with col_bouton:
        lancer = st.button("Générer le rapport", key="btn_rapport_pib")

    if lancer:
        with st.spinner("Génération du rapport…"):
            try:
                st.session_state["pib_rapport_chemin"] = generer_rapport_pib_pdf(date, chemin_sortie)
                journaliser("rapport", "rapport PIB généré : " + os.path.basename(chemin_sortie))
                st.session_state["pib_rapport_format"] = "pdf"
            except Exception as err:
                journaliser_erreur("rapport", err)
                st.error(
                    "La génération du rapport a échoué. Réessayez ; si le problème persiste, "
                    "consultez le journal de l'application."
                )
                st.session_state.pop("pib_rapport_chemin", None)

    chemin = st.session_state.get("pib_rapport_chemin")
    if chemin and os.path.exists(chemin):
        format_rapport = st.session_state.get("pib_rapport_format", "pdf")
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
                key="dl_rapport_pib",
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
        "Le texte d'analyse est produit par un moteur de règles déterministe paramétré dans "
        "<code>config/narrative_rules.json</code> (bloc « pib ») : aucun modèle de langage "
        "n'intervient. La méthode de calcul des contributions, détectée à partir des données, "
        "figure en dernière page.</div>",
        unsafe_allow_html=True,
    )

    pied_de_page()
