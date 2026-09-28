"""
Graphiques PIB — uniquement du tracé Plotly, aucune formule : chaque
fonction reçoit des DataFrames déjà calculés par backend.pib.calculator.

Mêmes conventions que backend/inflation/visualizer.py : zéro dépendance
Streamlit, couleurs de la charte (config/branding.py), titre toujours
renseigné, fond transparent. L'habillage sombre de l'écran est appliqué
ensuite par app/components/theme.appliquer_theme_graphique() ; l'export PNG
(export_png=True, pour le rapport) repasse la figure en encre sur papier.
"""

import copy
import math
import os

import pandas as pd
import plotly.graph_objects as go

from config.branding import (
    PALETTE_SERIES,
    COLOR_GOLD,
    COLOR_TEXTE,
    COLOR_ENCRE,
    COLOR_ENCRE_ATTENUEE,
    FONT_FAMILY_TEXTE,
    FONT_FAMILY_TITRE,
)

# Couleurs sobres des pas de waterfall : les teintes sémantiques, adoucies.
_HAUSSE = "rgba(63, 191, 127, 0.78)"
_BAISSE = "rgba(226, 99, 91, 0.78)"
_ECART = "rgba(159, 179, 194, 0.55)"

SUFFIXE_MODE = {"yoy": "glissement annuel (T/T−4)", "qoq": "glissement trimestriel (T/T−1)"}


def libelle_trimestre(date) -> str:
    """'T1 2024' plutôt que la date de fin de trimestre."""
    date = pd.Timestamp(date)
    return f"T{(date.month - 1) // 3 + 1} {date.year}"


def _axe_trimestres(fig: go.Figure, index: pd.DatetimeIndex, max_etiquettes: int = 12):
    """Graduations en trimestres, espacées pour rester lisibles sur 1366 px."""
    if len(index) == 0:
        return
    pas = max(1, math.ceil(len(index) / max_etiquettes))
    graduations = list(index[::-1][::pas])[::-1]
    fig.update_xaxes(tickmode="array", tickvals=graduations, ticktext=[libelle_trimestre(d) for d in graduations])


def _habiller(
    fig: go.Figure, titre: str, titre_y: str = None, suffixe_y: str = None, barmode: str = None, hauteur: int = 440
) -> go.Figure:
    """
    Fond transparent, légende horizontale, polices de la charte.

    Pas de titre Plotly gravé dans la figure : chaque graphique est déjà
    précédé d'un `titre_section()` à l'écran, et d'une légende de figure
    dans le rapport (`_figure()` côté ReportLab) — un titre Plotly en plus
    se superposait à la légende horizontale au-dessus du tracé (aucune
    réservation de hauteur automatique entre les deux). `titre` est
    conservé en paramètre pour les appelants existants mais n'est plus
    rendu ; il retourne dans `fig.layout.meta` pour un usage éventuel
    (alt-text, export…).
    """
    fig.update_layout(
        meta=dict(titre=titre),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY_TEXTE),
        hovermode="x unified",
        legend=dict(title="", orientation="h", y=1.02, x=0.5, xanchor="center", yanchor="bottom"),
        margin=dict(t=60),
        height=hauteur,
    )
    if barmode:
        fig.update_layout(barmode=barmode)
    if titre_y or suffixe_y:
        fig.update_yaxes(title_text=titre_y, ticksuffix=suffixe_y)
    return fig


def _exporter(fig: go.Figure, nom_fichier: str) -> str:
    """
    PNG pour le rapport imprimé : copie de la figure repassée en encre sur
    fond blanc (la figure affichée à l'écran n'est pas modifiée).
    """
    from config.settings import GRAPHES_DIR

    papier = go.Figure(copy.deepcopy(fig.to_dict()))
    papier.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family=FONT_FAMILY_TEXTE, color=COLOR_ENCRE, size=13),
        legend=dict(font=dict(color=COLOR_ENCRE_ATTENUEE)),
        margin=dict(l=60, r=30, t=65, b=50),
    )
    papier.update_yaxes(gridcolor="rgba(16,32,47,0.10)", zerolinecolor="rgba(16,32,47,0.35)")
    for trace in papier.data:
        if trace.type == "scatter" and trace.line.color == COLOR_TEXTE:
            trace.line.color = COLOR_ENCRE
            trace.marker.color = COLOR_ENCRE
    os.makedirs(GRAPHES_DIR, exist_ok=True)
    chemin = os.path.join(str(GRAPHES_DIR), nom_fichier)
    papier.write_image(chemin, width=1200, height=620, scale=2)
    return chemin


# ===========================================================================
# Page 1 — Vue macroéconomique
# ===========================================================================


def tracer_croissance_hydro_hh(
    croissance: pd.DataFrame, libelles: dict, mode: str = "yoy", export_png: bool = False
) -> go.Figure:
    """
    Barres : croissance réelle des hydrocarbures et du hors hydrocarbures ;
    courbe : croissance du PIB total. `croissance` : sortie de
    calculer_croissance_agregats() (colonnes H_reel, HH_reel, PIB_reel).
    """
    x = croissance.index
    fig = go.Figure()
    for colonne, cle, couleur in (("H_reel", "H", PALETTE_SERIES[7]), ("HH_reel", "HH", PALETTE_SERIES[0])):
        nom = libelles[cle]
        fig.add_trace(
            go.Bar(
                x=x,
                y=croissance[colonne],
                name=nom,
                marker_color=couleur,
                customdata=[libelle_trimestre(d) for d in x],
                hovertemplate=nom + " : %{y:.2f} %<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=croissance["PIB_reel"],
            name=libelles["PIB"],
            mode="lines+markers",
            line=dict(color=COLOR_TEXTE, width=2.4),
            marker=dict(size=5),
            hovertemplate=libelles["PIB"] + " : %{y:.2f} %<extra></extra>",
        )
    )
    _habiller(
        fig,
        "Croissance réelle — hydrocarbures, hors hydrocarbures et PIB total — " + SUFFIXE_MODE[mode],
        "Croissance (%)",
        " %",
        barmode="group",
    )
    _axe_trimestres(fig, x)
    if export_png:
        _exporter(fig, f"pib_croissance_hydro_hh_{mode}.png")
    return fig


def tracer_nominal_vs_reel(
    croissance: pd.DataFrame, date, libelles: dict, mode: str = "yoy", export_png: bool = False
) -> go.Figure:
    """
    Histogramme groupé au trimestre `date` : pour chaque agrégat (hors
    hydrocarbures, hydrocarbures, total), croissance nominale à gauche et
    réelle à droite. L'écart entre les deux barres est l'inflation implicite.
    """
    ligne = croissance.loc[pd.Timestamp(date)]
    agregats = [("HH", "HH"), ("H", "H"), ("PIB", "PIB")]
    x = [libelles[cle] for cle, _ in agregats]
    fig = go.Figure()
    for suffixe, nom, couleur in (("nominal", "Nominal", PALETTE_SERIES[7]), ("reel", "Réel", PALETTE_SERIES[0])):
        valeurs = [ligne[f"{prefixe}_{suffixe}"] for _, prefixe in agregats]
        fig.add_trace(
            go.Bar(
                x=x,
                y=valeurs,
                name=nom,
                marker_color=couleur,
                text=[f"{v:.1f} %" if pd.notna(v) else "" for v in valeurs],
                textposition="outside",
                hovertemplate="%{x} — " + nom + " : %{y:.2f} %<extra></extra>",
            )
        )
    _habiller(
        fig,
        "Croissance nominale et réelle par agrégat — " + libelle_trimestre(date) + ", " + SUFFIXE_MODE[mode],
        "Croissance (%)",
        " %",
        barmode="group",
        hauteur=400,
    )
    fig.update_layout(hovermode="closest")
    if export_png:
        _exporter(fig, f"pib_nominal_vs_reel_{mode}.png")
    return fig


# ===========================================================================
# Page 2 — Optique offre
# ===========================================================================


def tracer_waterfall_offre(
    contributions: pd.DataFrame, date, libelles: dict, libelle_total: str, mode: str = "yoy", export_png: bool = False
) -> go.Figure:
    """
    Waterfall des contributions sectorielles au trimestre `date`, total
    final égal à la croissance du PIB réel. `contributions` : sortie de
    completer_ecart_chainage() — la barre « Écart de chaînage » n'apparaît
    que si elle est non nulle.
    """
    ligne = contributions.loc[pd.Timestamp(date)].dropna()
    colonnes = [c for c in contributions.columns if c in ligne.index]
    if "Ecart_chainage" in colonnes and abs(ligne["Ecart_chainage"]) < 0.005:
        colonnes.remove("Ecart_chainage")

    noms = [libelles.get(c, c) for c in colonnes] + [libelle_total]
    valeurs = [float(ligne[c]) for c in colonnes]
    total = float(ligne[[c for c in contributions.columns if c in ligne.index]].sum())

    fig = go.Figure(
        go.Waterfall(
            x=noms,
            y=valeurs + [total],
            measure=["relative"] * len(valeurs) + ["total"],
            text=[f"{v:+.2f}" for v in valeurs] + [f"{total:.2f} %"],
            textposition="outside",
            increasing=dict(marker=dict(color=_HAUSSE)),
            decreasing=dict(marker=dict(color=_BAISSE)),
            totals=dict(marker=dict(color=COLOR_GOLD)),
            connector=dict(line=dict(color="rgba(159,179,194,0.35)", width=1)),
            hovertemplate="%{x} : %{y:+.2f} pt<extra></extra>",
            name="Contribution",
        )
    )
    _habiller(
        fig,
        "Contributions sectorielles à la croissance du PIB réel — "
        + libelle_trimestre(date)
        + ", "
        + SUFFIXE_MODE[mode],
        "Points de pourcentage",
        " pt",
        hauteur=460,
    )
    fig.update_layout(hovermode="closest", showlegend=False)
    if export_png:
        _exporter(fig, f"pib_waterfall_offre_{mode}.png")
    return fig


def tracer_contributions_offre(
    contributions: pd.DataFrame,
    colonnes: list,
    libelles: dict,
    libelle_total: str,
    mode: str = "yoy",
    export_png: bool = False,
) -> go.Figure:
    """
    Barres empilées des contributions sectorielles (négatives sous zéro) sur
    toute la période sélectionnée, et courbe de la croissance du PIB réel —
    même lecture que tracer_contributions_demande, pour l'optique offre.
    `contributions` : sortie de completer_ecart_chainage() (comprend déjà
    'Ecart_chainage'), une seule barre par trimestre au lieu du waterfall à
    un trimestre.
    """
    x = contributions.index
    fig = go.Figure()
    for i, colonne in enumerate(colonnes):
        nom = libelles.get(colonne, colonne)
        fig.add_trace(
            go.Bar(
                x=x,
                y=contributions[colonne],
                name=nom,
                marker_color=PALETTE_SERIES[i % len(PALETTE_SERIES)],
                hovertemplate=nom + " : %{y:+.2f} pt<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=contributions["Croissance_PIB"],
            name=libelle_total,
            mode="lines+markers",
            line=dict(color=COLOR_TEXTE, width=2.4),
            marker=dict(size=5),
            hovertemplate=libelle_total + " : %{y:.2f} %<extra></extra>",
        )
    )
    _habiller(
        fig,
        "Contributions sectorielles à la croissance du PIB réel — " + SUFFIXE_MODE[mode],
        "Points de pourcentage",
        " pt",
        barmode="relative",
        hauteur=480,
    )
    _axe_trimestres(fig, x)
    if export_png:
        _exporter(fig, f"pib_contributions_offre_{mode}.png")
    return fig


def tracer_parts_sectorielles(parts: pd.DataFrame, libelles: dict, export_png: bool = False) -> go.Figure:
    """Barres empilées à 100 % : part de chaque secteur dans le PIB nominal."""
    x = parts.index
    fig = go.Figure()
    for i, colonne in enumerate(parts.columns):
        nom = libelles.get(colonne, colonne)
        fig.add_trace(
            go.Bar(
                x=x,
                y=parts[colonne],
                name=nom,
                marker_color=PALETTE_SERIES[i % len(PALETTE_SERIES)],
                hovertemplate=nom + " : %{y:.1f} %<extra></extra>",
            )
        )
    _habiller(
        fig, "Structure du PIB nominal par secteur (parts en %)", "Part du PIB (%)", " %", barmode="stack", hauteur=460
    )
    fig.update_yaxes(range=[0, 100])
    _axe_trimestres(fig, x)
    if export_png:
        _exporter(fig, "pib_parts_sectorielles.png")
    return fig


# ===========================================================================
# Page 3 — Optique demande
# ===========================================================================


def tracer_contributions_demande(
    contributions: pd.DataFrame,
    colonnes: list,
    libelles: dict,
    libelle_total: str,
    mode: str = "yoy",
    export_png: bool = False,
) -> go.Figure:
    """
    Barres empilées des contributions (négatives sous zéro) et courbe de la
    croissance du PIB réel, qui passe exactement par la somme des barres
    grâce à la ligne résiduelle.
    """
    x = contributions.index
    fig = go.Figure()
    for i, colonne in enumerate(colonnes):
        nom = libelles.get(colonne, colonne)
        fig.add_trace(
            go.Bar(
                x=x,
                y=contributions[colonne],
                name=nom,
                marker_color=PALETTE_SERIES[i % len(PALETTE_SERIES)],
                hovertemplate=nom + " : %{y:+.2f} pt<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=contributions["Croissance_PIB"],
            name=libelle_total,
            mode="lines+markers",
            line=dict(color=COLOR_TEXTE, width=2.4),
            marker=dict(size=5),
            hovertemplate=libelle_total + " : %{y:.2f} %<extra></extra>",
        )
    )
    _habiller(
        fig,
        "Contributions de la demande à la croissance du PIB réel — " + SUFFIXE_MODE[mode],
        "Points de pourcentage",
        " pt",
        barmode="relative",
        hauteur=480,
    )
    _axe_trimestres(fig, x)
    if export_png:
        _exporter(fig, f"pib_contributions_demande_{mode}.png")
    return fig


def tracer_ratios(ratios: pd.DataFrame, libelles: dict, export_png: bool = False) -> go.Figure:
    """Évolution du taux d'investissement et du taux d'ouverture commerciale."""
    x = ratios.index
    fig = go.Figure()
    for i, (colonne, cle) in enumerate(
        (("Taux_investissement", "taux_investissement"), ("Taux_ouverture", "taux_ouverture"))
    ):
        nom = libelles[cle]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=ratios[colonne],
                name=nom,
                mode="lines+markers",
                line=dict(color=PALETTE_SERIES[i * 7 % len(PALETTE_SERIES)], width=2),
                marker=dict(size=4),
                hovertemplate=nom + " : %{y:.1f} %<extra></extra>",
            )
        )
    _habiller(
        fig, "Taux d'investissement et taux d'ouverture commerciale (% du PIB nominal)", "% du PIB", " %", hauteur=420
    )
    _axe_trimestres(fig, x)
    if export_png:
        _exporter(fig, "pib_ratios_demande.png")
    return fig
