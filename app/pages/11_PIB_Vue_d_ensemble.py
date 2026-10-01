"""
PIB — Vue macroéconomique globale et synthèse.

Quatre cartes KPI (PIB nominal, croissance réelle totale, croissance hors
hydrocarbures, croissance hydrocarbures), croissance réelle hydrocarbures /
hors hydrocarbures / PIB total, contributions hydrocarbures / hors
hydrocarbures à la croissance, puis croissance nominale vs réelle par
agrégat. Mise en page et filtres uniquement : tous les calculs viennent de
backend.pib.calculator (via app.components.donnees_pib).
"""

import pandas as pd
import streamlit as st

from backend.pib.calculator import valeur_et_delta
from backend.pib.visualizer import (
    tracer_croissance_hydro_hh,
    tracer_contributions_hydro_hh,
    tracer_nominal_vs_reel,
)
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
)
from app.components.layout import demarrer_page, libelle_page
from app.components.kpi_card import carte_kpi
from app.components.charts import graphique_puis_tableau
from app.components.periode import selecteur_periode_trimestres, format_trimestre
from app.components.donnees_pib import (
    charger_ou_arreter,
    libelles_pib,
    note_technique,
    unite_affichage,
)

contenu = demarrer_page("pib_vue")

with contenu:
    entete_page(
        libelle_page("pib_vue"),
        "Niveau du PIB, croissance réelle totale et hors hydrocarbures, déflateur implicite.",
    )
    separateur_dore()

    r = charger_ou_arreter()
    lib_offre, _lib_demande, agregats = libelles_pib()

    # ------------------------------------------------------------- filtres
    titre_section("Filtres")
    col_gliss, col_periode = st.columns([2, 7.4], vertical_alignment="top")
    with col_gliss:
        glissement = st.selectbox(
            "Type de glissement",
            options=["Glissement annuel (T/T−4)", "Glissement trimestriel (T/T−1)"],
            key="pib_glissement",
        )
    mode = "yoy" if glissement.startswith("Glissement annuel") else "qoq"

    croissance = r["croissance"][mode]
    publies = croissance["PIB_reel"].dropna().index
    with col_periode:
        debut, fin = selecteur_periode_trimestres(
            publies.min().date(), publies.max().date(), cle="pib_vue", defaut="5 ans"
        )
    date_debut, date_fin = pd.Timestamp(debut), pd.Timestamp(fin)
    fenetre = croissance.loc[date_debut:date_fin]

    # Les indicateurs suivent la fin de la période choisie : dernier
    # trimestre de la fenêtre où les quatre sont publiés (le détail
    # sectoriel en volume paraît après le PIB total).
    complets = fenetre[["PIB_reel", "HH_reel"]].dropna().index
    date_ref = complets.max() if len(complets) else fenetre["PIB_reel"].dropna().index.max()

    # -------------------------------------------------------- indicateurs
    titre_section("Indicateurs clés · " + format_trimestre(date_ref))
    niveaux = r["niveaux"]
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    k = 4 if mode == "yoy" else 1
    note = "vs même trimestre de l'an dernier" if mode == "yoy" else "vs trimestre précédent"

    diviseur, unite = unite_affichage()
    pib_niveau = niveaux["PIB_nominal"] / diviseur
    valeur_pib = pib_niveau.get(date_ref)
    precedent = pib_niveau.shift(k).get(date_ref)
    variation_pib = (valeur_pib / precedent - 1) * 100 if valeur_pib is not None and pd.notna(precedent) else None
    with k1:
        st.markdown(
            carte_kpi(
                "PIB total (nominal, " + unite + ")",
                valeur_pib,
                variation_pib,
                unite="",
                unite_delta="%",
                favorable_si_hausse=True,
                decimales=0,
                note=note,
            ),
            unsafe_allow_html=True,
        )

    suffixe = "YoY" if mode == "yoy" else "QoQ"
    for colonne, libelle, cle in (
        (k2, "Croissance réelle", "PIB_reel"),
        (k3, "Croissance hors hydrocarbures", "HH_reel"),
        (k4, "Croissance hydrocarbures", "H_reel"),
    ):
        valeur, delta = valeur_et_delta(croissance[cle], date_ref)
        with colonne:
            st.markdown(
                carte_kpi(
                    libelle + " (" + suffixe + ")",
                    valeur,
                    delta,
                    favorable_si_hausse=True,
                    note="écart au trimestre précédent",
                ),
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------- graphique 1
    titre_section("Croissance réelle par agrégat")
    graphique_puis_tableau(
        tracer_croissance_hydro_hh(fenetre, agregats, mode),
        cle="pib_hydro_hh_" + mode,
        nom_fichier="pib_croissance_hydro_hh_" + mode,
        format_date=format_trimestre,
    )
    manquants = fenetre.loc[fenetre["PIB_reel"].notna() & fenetre["HH_reel"].isna()].index
    if len(manquants):
        note_technique(
            "Le détail sectoriel en volume n'est publié que jusqu'au "
            + format_trimestre(date_ref)
            + " : au-delà, seule la courbe du PIB total "
            "(publiée dans le fichier Demande) est disponible, et les indicateurs "
            "s'arrêtent au dernier trimestre complet."
        )

    # --------------------------------------------------------- graphique 1bis
    titre_section("Contributions hydrocarbures / hors hydrocarbures")
    contributions = r["contributions_offre"][mode].assign(
        Croissance_PIB=r["coherence_offre"][mode]["Croissance_PIB"]
    )
    graphique_puis_tableau(
        tracer_contributions_hydro_hh(
            contributions.loc[date_debut:date_fin].dropna(),
            "Hydrocarbures",
            dict(lib_offre, HH=agregats["HH"]),
            agregats["total_croissance"],
            mode,
        ),
        cle="pib_contrib_hydro_hh_" + mode,
        nom_fichier="pib_contributions_hydro_hh_" + mode,
        format_date=format_trimestre,
    )

    # --------------------------------------------------------- graphique 2
    titre_section("Nominal et réel")
    date_detail = fenetre.dropna().index.max()
    if pd.isna(date_detail):
        st.info("Aucun trimestre complet dans la période choisie.")
    else:
        graphique_puis_tableau(
            tracer_nominal_vs_reel(croissance, date_detail, agregats, mode),
            cle="pib_nominal_reel_" + mode,
            nom_fichier="pib_nominal_vs_reel_" + mode,
        )
        note_technique(
            "Écart entre la barre nominale et la barre réelle : variation des prix "
            "(inflation implicite de l'agrégat). Comparaison faite en taux de "
            "croissance : les volumes ONS étant chaînés, un niveau réel hors "
            "hydrocarbures n'est pas défini."
        )

    pied_de_page()
