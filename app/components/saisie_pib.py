"""
Volet PIB de la page de saisie : insertion, modification ou suppression
d'une valeur trimestrielle, avec la même détection d'anomalies que
l'inflation (adaptée au trimestre). Mise en page uniquement : la logique
vit dans backend.pib.data_entry, qui consigne chaque saisie dans un journal
sans jamais réécrire les classeurs ONS.
"""

import pandas as pd
import streamlit as st

from backend.pib import data_entry as saisie
from backend.pib.base_cnt import reconstruire_socle
from app.components.journal import journaliser, signaler
from app.components.theme import titre_section, separateur_dore, TEXTE_ATTENUE
from app.components.periode import format_trimestre

_ACTIONS = {"insertion": "Insérer", "modification": "Modifier", "suppression": "Supprimer"}


def _texte(message):
    st.markdown(
        "<div style='font-size:0.8rem;color:" + TEXTE_ATTENUE + ";margin-bottom:.8rem;'>" + message + "</div>",
        unsafe_allow_html=True,
    )


def afficher_saisie_pib():
    _texte(
        "Les fichiers ONS sont pilotés par formules : ils ne sont jamais réécrits. "
        "Chaque saisie est consignée dans un journal, puis le socle historique de la "
        "base est reconstruit et les indicateurs sont recalculés aussitôt. Une valeur saisie n'est pas "
        "propagée par les formules ONS : corrigez séparément prix courants et volumes."
    )

    fichiers = saisie.fichiers_disponibles()
    if not fichiers:
        st.warning("Aucun fichier PIB dans data/raw/pib/.")
        return

    # --------------------------------------------------- filtres alignés
    titre_section("Valeur visée")
    c1, c2, c3, c4 = st.columns([2, 2, 3.4, 1.8], vertical_alignment="top")
    with c1:
        fichier = st.selectbox("Fichier", options=list(fichiers), format_func=fichiers.get, key="pib_saisie_fichier")
    feuilles = saisie.feuilles_disponibles()
    with c2:
        feuille = st.selectbox("Onglet", options=list(feuilles), format_func=feuilles.get, key="pib_saisie_feuille")
    with c3:
        colonne = st.selectbox(
            "Série", options=saisie.colonnes_saisissables(fichier), key="pib_saisie_colonne_" + fichier
        )
    with c4:
        action = st.selectbox("Action", options=list(_ACTIONS), format_func=_ACTIONS.get, key="pib_saisie_action")

    try:
        df = saisie.lire_feuille(fichier, feuille)
    except Exception as err:
        signaler("saisie_pib", err, "Lecture impossible.", "error")
        return

    if action == "insertion":
        trimestres = saisie.proposer_trimestres_insertion(df, colonne)
    else:
        trimestres = saisie.trimestres_disponibles(df, colonne)
    if not trimestres:
        st.info("Aucun trimestre disponible pour cette action.")
        return

    c5, c6, c7 = st.columns([2, 2, 5.2], vertical_alignment="bottom")
    with c5:
        i = st.selectbox(
            "Trimestre",
            options=range(len(trimestres)),
            format_func=lambda k: format_trimestre(trimestres[k]),
            key="pib_saisie_trimestre_" + action,
        )
    date = pd.Timestamp(trimestres[i])
    actuelle = saisie.lire_valeur(df, colonne, date)
    with c6:
        st.markdown(
            "<div style='font-size:0.66rem;font-weight:600;letter-spacing:0.13em;"
            "text-transform:uppercase;color:" + TEXTE_ATTENUE + ";margin-bottom:0.3rem;'>"
            "Valeur actuelle</div><div style='font-size:1.4rem;font-weight:700;'>"
            + ("%.1f" % actuelle if actuelle is not None else "—")
            + "</div>",
            unsafe_allow_html=True,
        )
    nouvelle = None
    # Point de départ du champ : la valeur actuelle, ou à défaut la dernière
    # valeur connue de la série (une insertion part rarement de zéro).
    connues = saisie.trimestres_disponibles(df, colonne)
    depart = actuelle if actuelle is not None else (saisie.lire_valeur(df, colonne, connues[0]) if connues else 0.0)
    with c7:
        if action != "suppression":
            nouvelle = st.number_input(
                "Nouvelle valeur (millions DA)", value=float(depart), step=100.0, format="%.1f", key="pib_saisie_valeur"
            )

    # ------------------------------------------------- contrôle et saisie
    cle = (fichier, feuille, colonne, str(date), action, nouvelle)
    if st.button("Vérifier", key="pib_saisie_verifier"):
        verdict = None
        if nouvelle is not None:
            try:
                verdict = saisie.evaluer_saisie(df, colonne, date, nouvelle, fichiers[fichier] + " · " + feuille)
            except Exception as err:
                signaler("saisie_pib", err, "Contrôle d'anomalies indisponible.", "caption")
        st.session_state["pib_saisie_attente"] = {"cle": cle, "verdict": verdict}

    attente = st.session_state.get("pib_saisie_attente")
    if attente and attente["cle"] == cle:
        verdict = attente["verdict"]
        severite = verdict["severite"] if verdict else "ok"
        if verdict and verdict["message"]:
            (st.error if severite == "marque" else st.warning)(verdict["message"])
        elif action != "suppression":
            st.success("Aucune anomalie détectée pour %s." % format_trimestre(date))

        peut = True
        if severite == "marque" or action == "suppression":
            peut = st.checkbox("Je confirme cette " + action, key="pib_saisie_confirme")
        if st.button("Enregistrer", key="pib_saisie_enregistrer", disabled=not peut):
            try:
                saisie.enregistrer_saisie(
                    fichier, feuille, colonne, date, action, nouvelle, utilisateur=st.session_state.get("username", "")
                )
                # Les pages lisent la base : le socle (millésime 0) est
                # reconstruit depuis les classeurs + journal, en une transaction.
                reconstruire_socle()
                journaliser("saisie", "%s %s %s %s %s" % (action, fichier, feuille, colonne, format_trimestre(date)))
                st.cache_data.clear()
                st.session_state.pop("pib_saisie_attente", None)
                st.success(
                    "Saisie enregistrée (%s, %s, %s) ; indicateurs recalculés à l'affichage."
                    % (_ACTIONS[action].lower(), colonne, format_trimestre(date))
                )
            except Exception as err:
                signaler("saisie", err, "L'enregistrement a échoué ; aucune donnée n'a été modifiée.")

    # -------------------------------------------------------------- journal
    separateur_dore()
    titre_section("Journal des saisies PIB")
    journal = saisie.historique_saisies()
    if journal.empty:
        _texte("Aucune saisie enregistrée.")
        return
    affiche = journal.copy()
    affiche["date"] = [format_trimestre(d) if pd.notna(d) else "" for d in affiche["date"]]
    st.dataframe(affiche, width="stretch", hide_index=True, height=260)
    st.download_button(
        "Exporter en CSV",
        data=affiche.to_csv(index=False).encode("utf-8-sig"),
        file_name="journal_saisies_pib.csv",
        mime="text/csv",
        key="csv_journal_pib",
    )
