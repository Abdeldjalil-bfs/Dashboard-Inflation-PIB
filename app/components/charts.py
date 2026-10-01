"""
Bloc graphique standard du tableau de bord.

Chaque graphique est précédé d'un panneau rétractable, fermé par défaut, qui
affiche les valeurs de la série sous forme de tableau (dates les plus récentes
en tête) avec un bouton d'export CSV.
"""

import io
import warnings

import pandas as pd
import streamlit as st

from app.components.theme import appliquer_theme_graphique
from app.components.periode import format_mois

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def tableau_vers_excel_tidy(tableau: pd.DataFrame, nom_valeur: str = "valeur") -> bytes:
    """
    Même tableau que l'export CSV, reformaté en tidy data (une ligne par
    observation : date, série, valeur) plutôt qu'une colonne par série —
    directement réutilisable pour une analyse statistique ou un outil de BI,
    sans étape de reformatage préalable.
    """
    nom_index = tableau.index.name or "Date"
    long = tableau.rename_axis(nom_index).reset_index().melt(id_vars=nom_index, var_name="serie", value_name=nom_valeur)
    long = long.dropna(subset=[nom_valeur])
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        long.to_excel(writer, index=False, sheet_name="donnees")
    return tampon.getvalue()


def figure_vers_tableau(fig, format_date=None):
    """
    Reconstruit un tableau à partir des séries tracées : une colonne par
    série, indexé par date, les plus récentes en tête. Un axe catégoriel
    (secteurs d'un waterfall…) garde l'ordre du graphique.

    `format_date` met en forme les dates (format_mois par défaut ;
    format_trimestre pour le module PIB).
    """
    format_date = format_date or format_mois
    if fig is None or not fig.data:
        return pd.DataFrame()

    colonnes = {}
    for trace in fig.data:
        nom = getattr(trace, "name", None) or "série"
        x = getattr(trace, "x", None)
        y = getattr(trace, "y", None)
        if x is None or y is None:
            continue
        serie = pd.Series(list(y), index=pd.Index(list(x), name="Date"))
        base, suffixe = nom, 2
        while nom in colonnes:
            nom = base + " (" + str(suffixe) + ")"
            suffixe += 1
        colonnes[nom] = serie

    if not colonnes:
        return pd.DataFrame()

    df = pd.DataFrame(colonnes)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dates = pd.to_datetime(df.index)
    except (TypeError, ValueError):
        df.index.name = ""
        return df.round(2)
    df.index = dates
    df = df.sort_index(ascending=False)
    df.index = [format_date(d) for d in df.index]
    df.index.name = "Date"
    return df.round(2)


def graphique_avec_tableau(
    fig, cle, libelle_tableau="Afficher les valeurs", nom_fichier="donnees", hauteur=None, titre=None
):
    """
    Affiche le panneau rétractable de données PUIS le graphique habillé selon
    la charte. `cle` doit être unique dans la page.
    """
    if fig is None:
        st.info("Graphique indisponible : données manquantes.")
        return None

    tableau = figure_vers_tableau(fig)

    with st.expander(libelle_tableau, expanded=False):
        if tableau.empty:
            st.caption("Aucune valeur à afficher.")
        else:
            st.dataframe(tableau, width="stretch", height=280)
            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                st.download_button(
                    "Exporter en CSV",
                    data=tableau.to_csv(index=True).encode("utf-8-sig"),
                    file_name=nom_fichier + ".csv",
                    mime="text/csv",
                    key="csv_" + cle,
                )
            with col_xlsx:
                st.download_button(
                    "Exporter en Excel (.xlsx)",
                    data=tableau_vers_excel_tidy(tableau),
                    file_name=nom_fichier + ".xlsx",
                    mime=MIME_XLSX,
                    key="xlsx_" + cle,
                )

    fig = appliquer_theme_graphique(fig, hauteur=hauteur, titre=titre)
    st.plotly_chart(fig, width="stretch", key="graph_" + cle)
    return fig


def graphique_puis_tableau(
    fig,
    cle,
    nom_fichier="donnees",
    hauteur=None,
    titre=None,
    libelle_tableau="Valeurs de la série",
    format_date=None,
    tableau=None,
):
    """
    Le graphique occupe toute la largeur, le tableau de ses valeurs vient
    juste en dessous.

    Empilé plutôt que côte à côte : à côté, le graphique perdait 40 % de sa
    largeur et le tableau restait trop étroit pour être lu confortablement.

    `tableau` remplace le tableau déduit des traces quand la page dispose
    d'une présentation plus lisible des mêmes valeurs.
    """
    if fig is None:
        st.info("Graphique indisponible : données manquantes.")
        return None

    if tableau is None:
        tableau = figure_vers_tableau(fig, format_date)

    figure = appliquer_theme_graphique(fig, hauteur=hauteur, titre=titre)
    st.plotly_chart(figure, width="stretch", key="graph_" + cle)

    with st.expander(libelle_tableau, expanded=False):
        if tableau.empty:
            st.caption("Aucune valeur à afficher.")
        else:
            st.dataframe(tableau, width="stretch", height=300)
            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                st.download_button(
                    "Exporter en CSV",
                    data=tableau.to_csv(index=True).encode("utf-8-sig"),
                    file_name=nom_fichier + ".csv",
                    mime="text/csv",
                    key="csv_" + cle,
                )
            with col_xlsx:
                st.download_button(
                    "Exporter en Excel (.xlsx)",
                    data=tableau_vers_excel_tidy(tableau),
                    file_name=nom_fichier + ".xlsx",
                    mime=MIME_XLSX,
                    key="xlsx_" + cle,
                )
    return figure


# Ancien nom conservé : la disposition côte à côte a été abandonnée au profit
# de l'empilement, plus lisible.
graphique_et_tableau_cote_a_cote = graphique_puis_tableau
