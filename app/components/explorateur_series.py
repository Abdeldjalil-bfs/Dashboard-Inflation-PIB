"""
Explorateur de séries, commun aux pages Séries des modules Inflation et PIB :
graphique (lignes, barres, empilements, base 100), synthèse chiffrée sur la
période et tableau exportable. Mise en page uniquement : les données
arrivent déjà chargées.
"""

import plotly.graph_objects as go
import streamlit as st

from app.components.theme import (
    titre_section,
    appliquer_theme_graphique,
    PALETTE_SERIES,
    COULEUR_AGREGAT,
    TEXTE_ATTENUE,
    NAVY_DEEP,
)


def modes_representation(type_mesure):
    """Représentations pertinentes : pas d'empilement sur des niveaux."""
    if type_mesure == "niveau":
        return ["Lignes", "Base 100"]
    if type_mesure == "contribution":
        return ["Barres empilées", "Lignes", "Aires empilées"]
    return ["Lignes", "Barres"]


def base_100(df):
    """Réindexe chaque série sur 100 à sa première valeur connue."""
    resultat = df.copy()
    for colonne in resultat.columns:
        serie = resultat[colonne].dropna()
        if not serie.empty and serie.iloc[0] != 0:
            resultat[colonne] = resultat[colonne] / serie.iloc[0] * 100.0
    return resultat


def statistiques(df):
    """Dernière valeur, variation sur la période, minimum, maximum, moyenne."""
    import pandas as pd

    lignes = []
    for colonne in df.columns:
        serie = df[colonne].dropna()
        if serie.empty:
            continue
        lignes.append(
            {
                "Série": colonne,
                "Dernière": round(serie.iloc[-1], 2),
                "Variation": round(serie.iloc[-1] - serie.iloc[0], 2),
                "Minimum": round(serie.min(), 2),
                "Maximum": round(serie.max(), 2),
                "Moyenne": round(serie.mean(), 2),
            }
        )
    return pd.DataFrame(lignes)


def afficher_series(donnees, mode, unite, titre, titre_axe, format_date, periode_txt, nom_csv, cle, agregat=None):
    """
    `donnees` : DataFrame indexé par date, une colonne par série (libellés
    affichés). `agregat` : (nom, Series) superposée en trait épais, ou None.
    """
    affichees = base_100(donnees) if mode == "Base 100" else donnees
    unite_affichee = "" if mode == "Base 100" else unite
    empile = mode in ("Barres empilées", "Aires empilées")

    titre_section("Graphique")
    figure = go.Figure()
    for rang, colonne in enumerate(affichees.columns):
        couleur = PALETTE_SERIES[rang % len(PALETTE_SERIES)]
        infobulle = "%{y:.2f} " + unite_affichee + "<extra>" + colonne + "</extra>"
        if mode in ("Barres empilées", "Barres"):
            figure.add_trace(
                go.Bar(
                    x=affichees.index,
                    y=affichees[colonne],
                    name=colonne,
                    marker=dict(color=couleur, line=dict(color=NAVY_DEEP, width=1)),
                    hovertemplate=infobulle,
                )
            )
        elif mode == "Aires empilées":
            figure.add_trace(
                go.Scatter(
                    x=affichees.index,
                    y=affichees[colonne],
                    name=colonne,
                    mode="lines",
                    stackgroup="pile",
                    line=dict(color=couleur, width=1.2),
                    hovertemplate=infobulle,
                )
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=affichees.index,
                    y=affichees[colonne],
                    name=colonne,
                    mode="lines",
                    line=dict(color=couleur, width=2),
                    hovertemplate=infobulle,
                )
            )
    if agregat is not None and not agregat[1].empty:
        nom, serie = agregat
        figure.add_trace(
            go.Scatter(
                x=serie.index,
                y=serie,
                name=nom,
                mode="lines",
                line=dict(color=COULEUR_AGREGAT, width=2.6),
                hovertemplate="%{y:.2f}<extra>" + nom + "</extra>",
            )
        )
    figure.update_layout(
        barmode="relative" if empile else "group",
        xaxis_title=None,
        hovermode="x unified",
        yaxis_title=titre_axe + (" (" + unite_affichee + ")" if unite_affichee else ""),
    )
    titre_complet = titre + (" — base 100" if mode == "Base 100" else "")
    st.plotly_chart(
        appliquer_theme_graphique(figure, hauteur=520, titre=titre_complet), width="stretch", key="graph_" + cle
    )

    titre_section("Synthèse sur la période")
    stats = statistiques(affichees)
    if not stats.empty:
        st.dataframe(
            stats,
            width="stretch",
            hide_index=True,
            column_config={
                "Série": st.column_config.TextColumn("Série", width="large"),
                "Dernière": st.column_config.NumberColumn("Dernière", format="%.2f"),
                "Variation": st.column_config.NumberColumn("Variation", format="%+.2f"),
                "Minimum": st.column_config.NumberColumn("Minimum", format="%.2f"),
                "Maximum": st.column_config.NumberColumn("Maximum", format="%.2f"),
                "Moyenne": st.column_config.NumberColumn("Moyenne", format="%.2f"),
            },
        )
        st.markdown(
            "<div style='font-size:0.7rem;color:" + TEXTE_ATTENUE + ";'>Variation = dernière valeur "
            "moins première valeur de la période (" + periode_txt + ").</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Afficher les valeurs de la série", expanded=False):
        tableau = affichees.sort_index(ascending=False).round(2)
        tableau.index = [format_date(d) for d in tableau.index]
        tableau.index.name = "Date"
        st.dataframe(tableau, width="stretch", height=320)
        st.download_button(
            "Exporter en CSV",
            data=tableau.to_csv(index=True).encode("utf-8-sig"),
            file_name=nom_csv + ".csv",
            mime="text/csv",
            key="csv_" + cle,
        )
