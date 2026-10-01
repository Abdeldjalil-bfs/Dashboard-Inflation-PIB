"""
PIB — Optique demande et emplois (PIB_TR_D.xlsx).

Contributions de la consommation des ménages, de la consommation publique,
de l'investissement et des exportations nettes à la croissance réelle, plus
la ligne résiduelle « variations de stocks et écart statistique » ; taux
d'investissement et d'ouverture commerciale. Mise en page et filtres
uniquement.
"""

import pandas as pd
import streamlit as st

from backend.pib.calculator import valeur_et_delta, _config_pib
from backend.pib.visualizer import tracer_contributions_demande, tracer_parts_demande, tracer_ratios
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
from app.components.donnees_pib import charger_ou_arreter, libelles_pib, note_technique

contenu = demarrer_page("pib_demande")

with contenu:
    entete_page(
        libelle_page("pib_demande"),
        "Contributions des emplois finals à la croissance réelle, taux d'investissement et d'ouverture commerciale.",
    )
    separateur_dore()

    r = charger_ou_arreter()
    _lib_offre, libelles, agregats = libelles_pib()
    colonnes = [c["cle"] for c in _config_pib()["contributions_demande"]]

    # ------------------------------------------------------------- filtres
    titre_section("Filtres")
    col_gliss, col_periode = st.columns([2, 7.4], vertical_alignment="top")
    with col_gliss:
        glissement = st.selectbox(
            "Type de glissement",
            options=["Glissement annuel (T/T−4)", "Glissement trimestriel (T/T−1)"],
            key="pib_demande_glissement",
        )
    mode = "yoy" if glissement.startswith("Glissement annuel") else "qoq"

    contributions = r["contributions_demande"][mode]
    publies = contributions.dropna().index
    with col_periode:
        debut, fin = selecteur_periode_trimestres(
            publies.min().date(), publies.max().date(), cle="pib_demande", defaut="5 ans"
        )
    date_debut, date_fin = pd.Timestamp(debut), pd.Timestamp(fin)
    fenetre = contributions.loc[date_debut:date_fin].dropna()
    date_ref = fenetre.index.max()

    # -------------------------------------------------------- contributions
    titre_section("Contributions à la croissance réelle")
    graphique_puis_tableau(
        tracer_contributions_demande(fenetre, colonnes, libelles, agregats["total_croissance"], mode),
        cle="pib_contrib_demande_" + mode,
        nom_fichier="pib_contributions_demande_" + mode,
        format_date=format_trimestre,
    )
    derniere = fenetre.loc[date_ref]
    note_technique(
        "La ligne « %s » est calculée en résiduel (croissance du PIB moins la somme des "
        "autres contributions) : la variation de stocks en volume publiée par l'ONS "
        "n'est pas exploitable, et c'est ce solde qui fait reboucler les barres sur la "
        "croissance. %s : %+.2f pt sur %.2f %%."
        % (libelles["Residuel"], format_trimestre(date_ref), derniere["Residuel"], derniere["Croissance_PIB"])
    )

    # ------------------------------------------- contributions (X et M distinguées)
    titre_section("Contributions à la croissance réelle — exportations et importations distinguées")
    colonnes_detail = ["Consommation_menages", "Consommation_administrations", "FBCF", "Exportations", "Importations", "Residuel"]
    graphique_puis_tableau(
        tracer_contributions_demande(fenetre, colonnes_detail, libelles, agregats["total_croissance"], mode),
        cle="pib_contrib_demande_detail_" + mode,
        nom_fichier="pib_contributions_demande_detail_" + mode,
        format_date=format_trimestre,
    )
    note_technique(
        "Mêmes contributions que le graphique précédent, mais les exportations et les "
        "importations apparaissent séparément plutôt que nettées en « exportations nettes »."
    )

    # ------------------------------------------------------ structure nominale
    titre_section("Structure nominale de la demande")
    parts_demande = r["parts_demande"].loc[date_debut:date_fin].dropna()
    graphique_puis_tableau(
        tracer_parts_demande(parts_demande, libelles),
        cle="pib_parts_demande",
        nom_fichier="pib_parts_demande",
        format_date=format_trimestre,
    )
    note_technique(
        "Part de chaque poste dans le PIB nominal ; les importations apparaissent en "
        "négatif puisqu'elles se soustraient du PIB (même principe que la structure du "
        "PIB nominal par secteur, page Offre, mais la variation de stocks — inexploitable "
        "— n'y figure pas : la somme des colonnes peut s'écarter légèrement de 100 %)."
    )

    # --------------------------------------------------------------- ratios
    titre_section("Ratios · " + format_trimestre(date_ref))
    ratios = r["ratios"].loc[date_debut:date_fin].dropna()
    date_ratio = ratios.index.max()
    k1, k2 = st.columns(2, gap="medium")
    for colonne, cle_ratio, cle_lib in (
        (k1, "Taux_investissement", "taux_investissement"),
        (k2, "Taux_ouverture", "taux_ouverture"),
    ):
        valeur, _ = valeur_et_delta(ratios[cle_ratio], date_ratio)
        # Ratios très saisonniers : la variation se lit sur un an.
        un_an_avant = ratios[cle_ratio].shift(4).get(date_ratio)
        delta = valeur - un_an_avant if valeur is not None and pd.notna(un_an_avant) else None
        with colonne:
            st.markdown(
                carte_kpi(
                    agregats[cle_lib],
                    valeur,
                    delta,
                    unite=" %",
                    unite_delta="pt",
                    favorable_si_hausse=None,
                    decimales=1,
                    note="vs même trimestre de l'an dernier · " + format_trimestre(date_ratio),
                ),
                unsafe_allow_html=True,
            )

    graphique_puis_tableau(
        tracer_ratios(ratios, agregats),
        cle="pib_ratios",
        nom_fichier="pib_ratios_demande",
        format_date=format_trimestre,
    )

    pied_de_page()
