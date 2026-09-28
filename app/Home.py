"""
Page d'accueil : choix du module.

Deux cartes construites de la même façon : nom du module, dernier
indicateur clé et sa variation, période de la donnée (toujours lue dans les
données), une phrase descriptive. Aucune navigation secondaire à ce niveau.
"""

import streamlit as st

from backend.inflation.calculator import derniere_inflation
from backend.pib.base_cnt import derniere_croissance_pib
from config.settings import FICHIER_DONNEES_CALCULS, FEUILLE_NATIONAL
from config.textes import ACCUEIL, MODULE_INFLATION, MODULE_PIB
from app.components.auth import require_auth
from app.components.theme import (
    configurer_page,
    appliquer_theme,
    entete_page,
    separateur_dore,
    pied_de_page,
    POSITIF,
    NEGATIF,
    TEXTE_ATTENUE,
)
from app.components.layout import bandeau, aller_a
from app.components.periode import format_mois, format_trimestre

configurer_page("Accueil")
require_auth()
appliquer_theme()

bandeau()
entete_page(ACCUEIL["titre"], ACCUEIL["sous_titre"])
separateur_dore()


@st.cache_data(show_spinner=False)
def _apercu_inflation():
    """Dernière inflation annuelle nationale, écart au mois précédent, ou None."""
    res = derniere_inflation(str(FICHIER_DONNEES_CALCULS), FEUILLE_NATIONAL)
    if res is None:
        return None
    valeur, delta, date = res
    return valeur, delta, format_mois(date)


@st.cache_data(show_spinner=False)
def _apercu_pib():
    """Dernière croissance réelle (t/t−4) lue dans cnt_pib_derniere, ou None."""
    res = derniere_croissance_pib()
    if res is None:
        return None
    return res["valeur"], res["delta"], format_trimestre(res["date"])


def _carte(titre, lecture, indicateur, phrase, vide, hausse_favorable, points=()):
    """
    Carte de module ; `lecture` = (valeur %, variation pp, période) ou None.
    Couleur selon la lecture économique : une hausse de l'inflation est
    défavorable (rouge), une hausse de la croissance favorable (vert).
    """
    if lecture is None:
        corps = (
            "<div class='ba-choice-value' style='opacity:0.45;'>—</div>"
            "<div style='font-size:0.83rem;color:" + TEXTE_ATTENUE + ";margin-top:0.3rem;'>" + vide + "</div>"
        )
    else:
        valeur, delta, periode = lecture
        variation = ""
        if delta is not None:
            couleur = POSITIF if (delta >= 0) == hausse_favorable else NEGATIF
            variation = (
                "<span style='color:"
                + couleur
                + ";font-weight:600;'>"
                + ("▲ " if delta >= 0 else "▼ ")
                + ("%.2f" % abs(delta)).replace(".", ",")
                + " pp</span> &nbsp;"
            )
        corps = (
            "<div class='ba-choice-value'>" + ("%.1f %%" % valeur).replace(".", ",") + "</div>"
            "<div style='font-size:0.83rem;margin-top:0.3rem;'>"
            + variation
            + "<span style='color:"
            + TEXTE_ATTENUE
            + ";'>"
            + indicateur
            + " — "
            + periode
            + "</span></div>"
        )
    tags = "".join("<span class='ba-choice-tag'>" + p + "</span>" for p in points)
    st.markdown(
        "<div class='ba-choice'>"
        "<div class='ba-choice-eyebrow'>" + ACCUEIL["eyebrow"] + "</div>"
        "<div class='ba-choice-title'>"
        + titre
        + "</div>"
        + corps
        + "<div class='ba-choice-desc'>"
        + phrase
        + "</div>"
        + ("<div class='ba-choice-tags'>" + tags + "</div>" if tags else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def _lire(fonction):
    try:
        return fonction()
    except Exception:
        return None


col_gauche, col_droite = st.columns(2, gap="large")

with col_gauche:
    _carte(
        ACCUEIL["inflation_titre"],
        _lire(_apercu_inflation),
        ACCUEIL["inflation_indicateur"],
        ACCUEIL["inflation_phrase"],
        ACCUEIL["vide_inflation"],
        hausse_favorable=False,
        points=ACCUEIL["inflation_points"],
    )
    if st.button(ACCUEIL["bouton"], key="acces_inflation", help=MODULE_INFLATION):
        aller_a("inflation_vue")

with col_droite:
    _carte(
        ACCUEIL["pib_titre"],
        _lire(_apercu_pib),
        ACCUEIL["pib_indicateur"],
        ACCUEIL["pib_phrase"],
        ACCUEIL["vide_pib"],
        hausse_favorable=True,
        points=ACCUEIL["pib_points"],
    )
    if st.button(ACCUEIL["bouton"], key="acces_pib", help=MODULE_PIB):
        aller_a("pib_vue")

pied_de_page()
