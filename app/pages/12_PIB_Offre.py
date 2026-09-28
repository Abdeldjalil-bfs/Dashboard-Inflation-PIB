"""
PIB — Optique offre (secteurs d'activité, PIB_TR_S.xlsx).

Contributions sectorielles à la croissance réelle sur la période
sélectionnée, structure du PIB nominal (100 % empilé) et tableau de
croissance QoQ / YoY par branche. Mise en page et filtres uniquement :
calculs dans backend.pib.calculator, tracés dans backend.pib.visualizer.
"""

import pandas as pd
import streamlit as st

from backend.pib.visualizer import tracer_contributions_offre, tracer_parts_sectorielles
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    POSITIF,
    NEGATIF,
)
from app.components.layout import demarrer_page, libelle_page
from app.components.charts import graphique_puis_tableau
from app.components.periode import selecteur_periode_trimestres, format_trimestre
from app.components.donnees_pib import charger_ou_arreter, libelles_pib, note_technique

contenu = demarrer_page("pib_offre")

with contenu:
    entete_page(
        libelle_page("pib_offre"),
        "Contributions des secteurs d'activité à la croissance réelle, structure du PIB et croissance par branche.",
    )
    separateur_dore()

    r = charger_ou_arreter()
    libelles, _lib_demande, agregats = libelles_pib()
    methode = r["methode"]

    # ------------------------------------------------------------- filtres
    titre_section("Filtres")
    col_gliss, col_periode = st.columns([2, 7.4], vertical_alignment="top")
    with col_gliss:
        glissement = st.selectbox(
            "Type de glissement",
            options=["Annuel (T/T−4)", "Trimestriel (T/T−1)"],
            key="pib_offre_glissement",
        )
    mode = "yoy" if glissement.startswith("Annuel") else "qoq"

    contributions = r["contributions_offre"][mode].dropna(how="all")
    publies = contributions.dropna().index
    with col_periode:
        debut, fin = selecteur_periode_trimestres(
            publies.min().date(), publies.max().date(), cle="pib_offre", defaut="5 ans"
        )
    date_debut, date_fin = pd.Timestamp(debut), pd.Timestamp(fin)
    date_ref = contributions.loc[date_debut:date_fin].dropna().index.max()

    # ------------------------------------------------------- contributions
    titre_section("Contributions sectorielles à la croissance réelle")
    fenetre = contributions.loc[date_debut:date_fin].dropna()
    colonnes_offre = list(fenetre.columns)
    fenetre = fenetre.assign(Croissance_PIB=r["coherence_offre"][mode]["Croissance_PIB"].loc[fenetre.index])
    graphique_puis_tableau(
        tracer_contributions_offre(fenetre, colonnes_offre, libelles, agregats["total_croissance"], mode),
        cle="pib_contrib_offre_" + mode,
        nom_fichier="pib_contributions_offre_" + mode,
        format_date=format_trimestre,
    )

    tolerance = r["tolerance"]
    coherence_periode = r["coherence_offre"][mode].loc[date_debut:date_fin].dropna()
    pire = coherence_periode["Ecart"].abs().max() if not coherence_periode.empty else None
    if pire is not None and pire > tolerance:
        note_technique(
            "Note technique — sur la période affichée, l'écart maximal entre la somme des "
            "contributions sectorielles et la croissance publiée du PIB réel atteint %.2f pt, "
            "au-delà de la tolérance de %.2f pt. Écart attendu en volumes chaînés : le chaînage "
            "n'est pas additif et l'ONS arrondit ses taux à 0,1 pt. La barre « %s » le rend "
            "visible pour que chaque trimestre reboucle exactement sur la croissance publiée."
            % (pire, tolerance, agregats["ecart_chainage"])
        )
    note_technique(
        "Méthode : "
        + (
            "contributions en structure nominale t−k × croissance en volume (SCN 2008, volumes chaînés)"
            if methode["methode"] == "chainage"
            else "variation des volumes à prix constants rapportée au PIB réel t−k"
        )
        + ". Détection automatique — "
        + methode["raison"]
    )

    # ------------------------------------------------------ structure 100 %
    titre_section("Structure du PIB nominal")
    parts = r["parts"].loc[date_debut:date_fin].dropna()
    graphique_puis_tableau(
        tracer_parts_sectorielles(parts, libelles),
        cle="pib_parts",
        nom_fichier="pib_parts_sectorielles",
        format_date=format_trimestre,
    )

    # ---------------------------------------------- croissance par branche
    titre_section("Croissance réelle par branche · " + format_trimestre(date_ref))
    noms = dict(libelles, PIB=agregats["PIB"])
    tableau = pd.DataFrame(
        {
            "Branche": [noms.get(c, c) for c in r["croissance_branches"]["qoq"].columns],
            "QoQ (%)": r["croissance_branches"]["qoq"].loc[date_ref].values,
            "YoY (%)": r["croissance_branches"]["yoy"].loc[date_ref].values,
        }
    ).round(2)

    def _couleur(valeur):
        if pd.isna(valeur):
            return ""
        return "color: " + (POSITIF if valeur >= 0 else NEGATIF)

    st.dataframe(
        tableau.style.map(_couleur, subset=["QoQ (%)", "YoY (%)"]).format(
            {"QoQ (%)": "{:+.2f}", "YoY (%)": "{:+.2f}"}, na_rep="—"
        ),
        width="stretch",
        hide_index=True,
    )
    st.download_button(
        "Exporter en CSV",
        data=tableau.to_csv(index=False).encode("utf-8-sig"),
        file_name="pib_croissance_branches_%s.csv" % format_trimestre(date_ref).replace(" ", "_"),
        mime="text/csv",
        key="csv_pib_branches",
    )
    note_technique("Cliquez sur un en-tête de colonne pour trier. QoQ : t/t−1, YoY : t/t−4, en volume.")

    pied_de_page()
