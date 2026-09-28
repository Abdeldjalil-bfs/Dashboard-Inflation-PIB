"""
Sélecteur de période, compact.

Une barre de raccourcis (1 an, 5 ans, 10 ans, personnalisée) et, au besoin,
deux listes mois/année. Aucune notion de jour n'est exposée : les séries
sont mensuelles, afficher un jour serait une fausse précision.

La liste de raccourcis n'est qu'un catalogue : `selecteur_periode` ne garde
que ceux plus courts que l'historique réellement disponible (elle relit
`date_min`/`date_max` à chaque appel), donc plus de mois arrivent dans le
fichier de calculs, plus de raccourcis apparaissent d'eux-mêmes. La borne de
fin de la période personnalisée, elle, ne dépasse jamais `date_max`.
"""

import pandas as pd
import streamlit as st

RACCOURCIS = [("1 an", 12), ("5 ans", 60), ("10 ans", 120)]
PERSONNALISEE = "Personnalisée"

_MOIS_FR = {
    1: "janv.",
    2: "févr.",
    3: "mars",
    4: "avr.",
    5: "mai",
    6: "juin",
    7: "juil.",
    8: "août",
    9: "sept.",
    10: "oct.",
    11: "nov.",
    12: "déc.",
}


def format_mois(date):
    """'juil. 2025' — indépendant de la locale du système."""
    date = pd.Timestamp(date)
    return _MOIS_FR[date.month] + " " + str(date.year)


def _profondeur(libelle):
    for nom, mois in RACCOURCIS:
        if nom == libelle:
            return mois
    return None


def selecteur_periode(date_min, date_max, cle, defaut="5 ans"):
    """Affiche le sélecteur et renvoie (début, fin) en dates Python."""
    date_min = pd.Timestamp(date_min)
    date_max = pd.Timestamp(date_max)
    total_mois = (date_max.year - date_min.year) * 12 + (date_max.month - date_min.month)

    # On n'offre que les raccourcis plus courts que l'historique disponible.
    options = [nom for nom, mois in RACCOURCIS if mois is None or mois <= total_mois]
    options.append(PERSONNALISEE)
    if defaut not in options:
        defaut = PERSONNALISEE

    # Pas de colonnes internes : appelé depuis une colonne de la page, un
    # découpage supplémentaire étranglait le contrôle segmenté, qui partait
    # alors sur trois rangées. Il occupe donc toute la largeur reçue, et le
    # résumé se place en dessous.
    choix = (
        st.segmented_control(
            "Période",
            options=options,
            default=defaut,
            key="periode_choix_" + cle,
        )
        or defaut
    )

    debut, fin = date_min, date_max

    if choix == PERSONNALISEE:
        mois_dispo = pd.period_range(date_min, date_max, freq="M")
        libelles = [format_mois(p.to_timestamp()) for p in mois_dispo]

        col_d, col_f = st.columns(2)
        with col_d:
            i_debut = st.selectbox(
                "Début",
                options=range(len(libelles)),
                format_func=lambda i: libelles[i],
                index=0,
                key="periode_debut_" + cle,
            )
        with col_f:
            i_fin = st.selectbox(
                "Fin",
                options=range(len(libelles)),
                format_func=lambda i: libelles[i],
                index=len(libelles) - 1,
                key="periode_fin_" + cle,
            )
        if i_fin < i_debut:
            i_debut, i_fin = i_fin, i_debut
        debut = mois_dispo[i_debut].to_timestamp(how="start")
        fin = mois_dispo[i_fin].to_timestamp(how="end").normalize()
    else:
        mois = _profondeur(choix)
        if mois is not None:
            debut = max(date_min, date_max - pd.DateOffset(months=mois - 1))

    nb_mois = (fin.year - debut.year) * 12 + (fin.month - debut.month) + 1
    st.markdown(
        "<div class='ba-periode-resume'>"
        + format_mois(debut)
        + " <span class='ba-periode-fleche'>&rarr;</span> "
        + format_mois(fin)
        + "<span class='ba-periode-compte'>"
        + str(nb_mois)
        + " mois</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    return debut.date(), fin.date()


# ---------------------------------------------------------------------------
# Variante trimestrielle (module PIB) — même logique, unité de "profondeur"
# en trimestres plutôt qu'en mois (RACCOURCIS_TRIMESTRE : 1/5/10 ans = 4/20/40
# trimestres), et le sélecteur "Personnalisée" liste des trimestres (T1 2024)
# plutôt que des mois.
# ---------------------------------------------------------------------------

RACCOURCIS_TRIMESTRE = [("1 an", 4), ("5 ans", 20), ("10 ans", 40)]


def format_trimestre(date):
    """'T3 2024' — indépendant de la locale du système."""
    date = pd.Timestamp(date)
    return "T" + str((date.month - 1) // 3 + 1) + " " + str(date.year)


def _profondeur_trimestre(libelle):
    for nom, trimestres in RACCOURCIS_TRIMESTRE:
        if nom == libelle:
            return trimestres
    return None


def selecteur_periode_trimestres(date_min, date_max, cle, defaut="5 ans"):
    """Variante trimestrielle de selecteur_periode() — voir sa docstring."""
    date_min = pd.Timestamp(date_min)
    date_max = pd.Timestamp(date_max)
    total_trimestres = len(pd.period_range(date_min, date_max, freq="Q"))

    options = [nom for nom, tr in RACCOURCIS_TRIMESTRE if tr is None or tr <= total_trimestres]
    options.append(PERSONNALISEE)
    if defaut not in options:
        defaut = PERSONNALISEE

    choix = (
        st.segmented_control(
            "Période",
            options=options,
            default=defaut,
            key="periode_choix_" + cle,
        )
        or defaut
    )

    debut, fin = date_min, date_max
    trimestres_dispo = pd.period_range(date_min, date_max, freq="Q")

    if choix == PERSONNALISEE:
        libelles = [format_trimestre(p.to_timestamp()) for p in trimestres_dispo]

        col_d, col_f = st.columns(2)
        with col_d:
            i_debut = st.selectbox(
                "Début",
                options=range(len(libelles)),
                format_func=lambda i: libelles[i],
                index=0,
                key="periode_debut_" + cle,
            )
        with col_f:
            i_fin = st.selectbox(
                "Fin",
                options=range(len(libelles)),
                format_func=lambda i: libelles[i],
                index=len(libelles) - 1,
                key="periode_fin_" + cle,
            )
        if i_fin < i_debut:
            i_debut, i_fin = i_fin, i_debut
        debut = trimestres_dispo[i_debut].to_timestamp(how="start")
        fin = trimestres_dispo[i_fin].to_timestamp(how="end").normalize()
    else:
        nb_trimestres = _profondeur_trimestre(choix)
        if nb_trimestres is not None:
            debut = max(date_min, date_max - pd.DateOffset(months=3 * (nb_trimestres - 1)))

    nb = len(pd.period_range(debut, fin, freq="Q"))
    st.markdown(
        "<div class='ba-periode-resume'>"
        + format_trimestre(debut)
        + " <span class='ba-periode-fleche'>&rarr;</span> "
        + format_trimestre(fin)
        + "<span class='ba-periode-compte'>"
        + str(nb)
        + " trimestres</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    return debut.date(), fin.date()
