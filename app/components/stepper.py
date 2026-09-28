"""
Indicateur d'étapes horizontal, sobre, aux couleurs de la charte :
étape faite en or atténué, étape active en or plein, étapes à venir en gris.
Aucune dépendance autre que Streamlit et le thème.
"""

import streamlit as st

from app.components.theme import GOLD, TEXTE, TEXTE_ATTENUE, POSITIF, NEGATIF

_BADGES = {
    "OK": ("OK", POSITIF, "rgba(63, 191, 127, 0.13)"),
    "AVERTISSEMENT": ("Avertissement", GOLD, "rgba(188, 158, 110, 0.16)"),
    "ERREUR": ("Erreur", NEGATIF, "rgba(226, 99, 91, 0.14)"),
}


def stepper(etapes, active, faites=()):
    """
    `etapes` : libellés dans l'ordre ; `active` : index (0-based) de l'étape
    en cours, ou None si tout est terminé ; `faites` : index déjà franchis.
    """
    blocs = []
    for i, libelle in enumerate(etapes):
        if i == active:
            couleur, fond, bord, poids = GOLD, "rgba(188,158,110,0.14)", GOLD, "700"
        elif i in faites:
            couleur, fond, bord, poids = TEXTE, "transparent", "rgba(188,158,110,0.55)", "500"
        else:
            couleur, fond, bord, poids = TEXTE_ATTENUE, "transparent", "rgba(159,179,194,0.25)", "400"
        pastille = "&#10003;" if (i in faites and i != active) else str(i + 1)
        blocs.append(
            "<div style='flex:1;display:flex;align-items:center;gap:0.55rem;min-width:0;'>"
            "<div style='flex:0 0 1.75rem;height:1.75rem;border-radius:50%;display:flex;"
            "align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;"
            "border:1.5px solid " + bord + ";background:" + fond + ";color:" + couleur + ";'>" + pastille + "</div>"
            "<div style='font-size:0.8rem;font-weight:"
            + poids
            + ";color:"
            + couleur
            + ";white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>"
            + libelle
            + "</div>"
            + (
                "<div style='flex:1;height:1px;background:rgba(159,179,194,0.22);margin:0 0.4rem;'></div>"
                if i < len(etapes) - 1
                else ""
            )
            + "</div>"
        )
    st.markdown(
        "<div style='display:flex;gap:0.4rem;align-items:center;padding:0.8rem 1rem;"
        "margin:0.4rem 0 1.2rem 0;border:1px solid rgba(188,158,110,0.22);border-radius:12px;"
        "background:rgba(255,255,255,0.025);'>" + "".join(blocs) + "</div>",
        unsafe_allow_html=True,
    )


def badge(niveau):
    """Badge de statut sobre (OK / Avertissement / Erreur)."""
    texte, couleur, fond = _BADGES.get(niveau, (niveau, TEXTE_ATTENUE, "transparent"))
    return (
        "<span style='display:inline-block;padding:0.12rem 0.55rem;border-radius:999px;"
        "font-size:0.72rem;font-weight:600;letter-spacing:0.02em;color:"
        + couleur
        + ";background:"
        + fond
        + ";border:1px solid "
        + couleur
        + "55;'>"
        + texte
        + "</span>"
    )
