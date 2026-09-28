"""
Accès des pages PIB aux résultats de calcul.

Aucune formule ici : un simple cache Streamlit autour de
backend.pib.calculator.pipeline_pib(), qui lit les sources, calcule et
écrit le fichier miroir. Le cache est vidé après chaque saisie PIB.
"""

import streamlit as st

from backend.pib.calculator import pipeline_pib, libelles_offre, libelles_demande, _config_pib
from config.textes import MESSAGES
from app.components.theme import TEXTE_ATTENUE, pied_de_page
from app.components.journal import signaler


@st.cache_data(show_spinner="Calcul des indicateurs PIB…")
def resultats_pib():
    return pipeline_pib()


@st.cache_data(show_spinner=False)
def libelles_pib():
    """(libellés offre, libellés demande, libellés des agrégats)."""
    return libelles_offre(), libelles_demande(), _config_pib()["libelles_agregats"]


@st.cache_data(show_spinner=False)
def unite_affichage():
    """(diviseur depuis l'unité source, libellé court de l'unité affichée)."""
    config = _config_pib()
    return float(config["diviseur_affichage"]), config["unite_affichage"]


def charger_ou_arreter():
    """Résultats PIB, ou message explicite et arrêt de la page."""
    try:
        return resultats_pib()
    except FileNotFoundError as err:
        signaler("pib", err, MESSAGES["base_vide"], "info")
    except Exception as err:
        signaler("donnees_pib", err, "Données PIB indisponibles.", "error")
    pied_de_page()
    st.stop()


def note_technique(texte):
    """Note discrète sous un graphique, qui ne bloque pas l'affichage.
    Séparateur décimal français (3,90 %)."""
    from backend.inflation.reporting import virgule_decimale

    texte = virgule_decimale(texte)
    st.markdown(
        "<div style='font-size:0.74rem;color:" + TEXTE_ATTENUE + ";margin:-0.2rem 0 0.8rem 0;"
        "border-left:2px solid rgba(188,158,110,0.45);padding-left:0.6rem;'>" + texte + "</div>",
        unsafe_allow_html=True,
    )
