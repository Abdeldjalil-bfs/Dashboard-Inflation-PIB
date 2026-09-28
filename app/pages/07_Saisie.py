"""
Saisie des données brutes — commune aux modules Inflation et PIB.

Le module affiché est celui d'où l'on vient (mémorisé par la navigation) :
volet PIB dans app/components/saisie_pib.py, volet Inflation ci-dessous.

Un mois, cinq paniers, une règle : dans un panier, on remplit tout ou rien.
Chaque panier est validé séparément ; les anomalies sont signalées avant
écriture, et un écart important exige une confirmation explicite.

Le recalcul des indicateurs n'a lieu qu'à la demande, en fin de page : il
réécrit l'intégralité du fichier de travail.
"""

import pandas as pd
import streamlit as st

from backend.inflation import data_entry as saisie
from backend.inflation.anomaly_detection import evaluer_tableau
from config.settings import FICHIER_DONNEES
from config.textes import MODULE_PIB, MODULE_INFLATION
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    TEXTE_ATTENUE,
)
from app.components.journal import journaliser, signaler
from app.components.auth import est_admin, exiger_admin
from app.components.layout import demarrer_page, libelle_page, aller_a
from app.components.periode import format_mois

MODULE = MODULE_PIB if st.session_state.get("module_actif") == MODULE_PIB else MODULE_INFLATION
contenu = demarrer_page("saisie", MODULE)

# Saisie réservée au profil admin : les autres profils voient le message.
if not est_admin():
    with contenu:
        entete_page(libelle_page("saisie"), "")
        separateur_dore()
        exiger_admin()
        pied_de_page()
    st.stop()

if MODULE == MODULE_PIB:
    from app.components.saisie_pib import afficher_saisie_pib

    with contenu:
        entete_page(
            libelle_page("saisie"),
            "Insertion, modification ou suppression d'une valeur trimestrielle, contrôlée avant enregistrement.",
        )
        separateur_dore()
        afficher_saisie_pib()
        pied_de_page()
    st.stop()

FICHIER = str(FICHIER_DONNEES)


@st.cache_data(show_spinner=False)
def _paniers():
    return saisie.paniers_disponibles(FICHIER), saisie.paniers_manquants(FICHIER)


@st.cache_data(show_spinner=False)
def _dates():
    return saisie.proposer_dates_insertion(FICHIER, nb_mois=6)


@st.cache_data(show_spinner=False)
def _structure(panier):
    return saisie.structure_panier(panier)


@st.cache_data(show_spinner=False)
def _derniers(panier, nb=3):
    return saisie.derniers_mois(FICHIER, panier, nb)


def _vider_caches():
    """Après écriture, l'historique affiché doit refléter le fichier."""
    _paniers.clear()
    _dates.clear()
    _derniers.clear()


with contenu:
    entete_page(
        libelle_page("saisie"),
        "Renseignez les indices bruts du mois, panier par panier. Les valeurs "
        "sont contrôlées avant enregistrement ; les indicateurs sont recalculés "
        "à la demande.",
    )
    separateur_dore()

    try:
        disponibles, manquants = _paniers()
        dates = _dates()
    except Exception as err:
        signaler("07_Saisie", err, "Fichier source illisible.", "error")
        pied_de_page()
        st.stop()

    if not dates:
        st.warning("Aucun mois à proposer : le fichier source semble vide.")
        pied_de_page()
        st.stop()

    # ------------------------------------------------------------ mois visé
    titre_section("Mois de référence")

    col_date, col_info = st.columns([2.2, 5.8], vertical_alignment="center")
    with col_date:
        index = st.selectbox(
            "Mois à saisir",
            options=range(len(dates)),
            format_func=lambda i: format_mois(dates[i].to_timestamp()),
            index=0,
            key="saisie_mois",
        )
    date_cible = dates[index].to_timestamp()

    with col_info:
        st.markdown(
            "<div style='font-size:0.78rem;color:" + TEXTE_ATTENUE + ";'>"
            "Le premier mois proposé suit le dernier mois couvert par "
            "l'ensemble des paniers.</div>",
            unsafe_allow_html=True,
        )

    if manquants:
        st.info(
            "Panier(s) absent(s) du fichier source, donc non saisissable(s) ici : "
            + ", ".join(manquants)
            + ". La feuille « core » notamment n'existe que dans le fichier de "
            "calculs, où elle est reconstituée."
        )

    # ------------------------------------------------------------- paniers
    titre_section("Paniers")

    for panier in disponibles:
        elements = _structure(panier)
        deja = saisie.date_deja_presente(FICHIER, panier, date_cible)
        etiquette = panier + ("  •  mois déjà renseigné" if deja else "")

        with st.expander(etiquette, expanded=False):
            # --- repère : les derniers mois connus ---
            try:
                repere = _derniers(panier, 3)
                if not repere.empty:
                    affiche = repere.copy()
                    affiche.index = [format_mois(d) for d in affiche.index]
                    affiche.index.name = "Mois"
                    st.caption("Trois derniers mois connus")
                    st.dataframe(affiche.round(2), width="stretch")
            except Exception as err:
                signaler("07_Saisie", err, "Historique indisponible.", "caption")

            # --- saisie ---
            st.caption("Valeurs du mois à saisir")
            ligne = pd.DataFrame([{element: None for element in elements}])
            edite = st.data_editor(
                ligne,
                key="editeur_" + panier,
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                column_config={
                    element: st.column_config.NumberColumn(element, format="%.2f", step=0.01) for element in elements
                },
            )
            valeurs = {c: edite.iloc[0][c] for c in elements}

            if deja:
                st.warning(
                    "Ce mois est déjà renseigné pour ce panier. L'enregistrement écrasera les valeurs existantes."
                )

            # --- validation ---
            if st.button("Valider ce panier", key="valider_" + panier):
                etat = saisie.valider_completude(valeurs)

                if etat == "partiel":
                    st.error("Remplissez soit toutes les cases de ce panier, soit aucune.")
                    st.session_state.pop("alertes_" + panier, None)

                elif etat == "vide":
                    st.info("Panier laissé vide, ignoré.")
                    st.session_state.pop("alertes_" + panier, None)

                else:
                    try:
                        verdicts = evaluer_tableau(FICHIER, panier, date_cible, valeurs)
                    except Exception as err:
                        verdicts = {}
                        signaler("07_Saisie", err, "Contrôle d'anomalies indisponible.", "caption")

                    graves = [v for v in verdicts.values() if v["severite"] == "marque"]
                    moderes = [v for v in verdicts.values() if v["severite"] == "modere"]

                    if graves:
                        # Écart important : on conserve l'état pour exiger une
                        # confirmation explicite au rerun suivant.
                        st.session_state["alertes_" + panier] = {
                            "valeurs": valeurs,
                            "graves": [v["message"] for v in graves],
                            "moderes": [v["message"] for v in moderes],
                        }
                    else:
                        for verdict in moderes:
                            st.warning(verdict["message"])
                        try:
                            saisie.inserer_ligne_panier(FICHIER, panier, date_cible, valeurs, ecraser=deja)
                            _vider_caches()
                            journaliser("saisie", "inflation : insertion %s, %s" % (panier, format_mois(date_cible)))
                            st.success("Valeurs enregistrées pour « %s » — %s." % (panier, format_mois(date_cible)))
                        except Exception as err:
                            signaler("07_Saisie", err, "Échec de l'enregistrement.", "error")
                        st.session_state.pop("alertes_" + panier, None)

            # --- confirmation d'un écart important ---
            alertes = st.session_state.get("alertes_" + panier)
            if alertes:
                for message in alertes["moderes"]:
                    st.warning(message)
                for message in alertes["graves"]:
                    st.error(message)

                confirme = st.checkbox(
                    "Je confirme ces valeurs malgré l'alerte",
                    key="confirme_" + panier,
                )
                if confirme and st.button("Enregistrer quand même", key="forcer_" + panier):
                    try:
                        saisie.inserer_ligne_panier(FICHIER, panier, date_cible, alertes["valeurs"], ecraser=deja)
                        _vider_caches()
                        journaliser(
                            "saisie",
                            "inflation : insertion confirmée malgré alerte %s, %s" % (panier, format_mois(date_cible)),
                        )
                        st.success("Valeurs enregistrées pour « %s » — %s." % (panier, format_mois(date_cible)))
                    except Exception as err:
                        signaler("07_Saisie", err, "Échec de l'enregistrement.", "error")
                    st.session_state.pop("alertes_" + panier, None)

    # ------------------------------------------------------- modification
    separateur_dore()
    titre_section("Modifier une valeur")

    st.markdown(
        "<div style='font-size:0.8rem;color:" + TEXTE_ATTENUE + ";margin-bottom:.8rem;'>"
        "Corrigez une valeur déjà enregistrée, élément par élément. La même "
        "détection d'anomalies qu'à la saisie s'applique ; une alerte ne bloque "
        "pas l'enregistrement si vous la confirmez.</div>",
        unsafe_allow_html=True,
    )

    col_panier, col_element, col_mois = st.columns(3)

    with col_panier:
        panier_modif = st.selectbox("Feuille", options=disponibles, key="modif_panier")

    elements_modif = _structure(panier_modif)
    with col_element:
        colonne_modif = st.selectbox("Élément", options=elements_modif, key="modif_colonne_" + panier_modif)

    try:
        dates_modif = saisie.dates_disponibles(FICHIER, panier_modif)
    except Exception as err:
        dates_modif = []
        signaler("saisie", err, "Historique illisible pour « %s »." % panier_modif)

    with col_mois:
        if dates_modif:
            index_modif = st.selectbox(
                "Mois",
                options=range(len(dates_modif)),
                format_func=lambda i: format_mois(dates_modif[i]),
                key="modif_mois_" + panier_modif,
            )
            date_modif = dates_modif[index_modif]
        else:
            date_modif = None
            st.info("Aucun mois renseigné pour ce panier.")

    if date_modif is not None:
        valeur_actuelle = saisie.lire_valeur(FICHIER, panier_modif, colonne_modif, date_modif)

        col_actuelle, col_nouvelle = st.columns([2, 3], vertical_alignment="bottom")
        with col_actuelle:
            st.markdown(
                "<div style='font-size:0.66rem;font-weight:600;letter-spacing:0.13em;"
                "text-transform:uppercase;color:" + TEXTE_ATTENUE + ";margin-bottom:0.3rem;'>"
                "Valeur actuelle</div>"
                "<div style='font-size:1.5rem;font-weight:700;'>"
                + ("%.2f" % valeur_actuelle if valeur_actuelle is not None else "—")
                + "</div>",
                unsafe_allow_html=True,
            )
        with col_nouvelle:
            nouvelle_valeur = st.number_input(
                "Nouvelle valeur",
                value=float(valeur_actuelle) if valeur_actuelle is not None else 0.0,
                step=0.01,
                format="%.2f",
                key="modif_valeur_" + panier_modif,
            )

        cle_etat = "modif_pending"

        if st.button("Vérifier la valeur", key="modif_verifier"):
            verdict = None
            try:
                verdicts = evaluer_tableau(FICHIER, panier_modif, date_modif, {colonne_modif: nouvelle_valeur})
                verdict = verdicts.get(colonne_modif)
            except Exception as err:
                signaler("07_Saisie", err, "Contrôle d'anomalies indisponible.", "caption")

            st.session_state[cle_etat] = {
                "panier": panier_modif,
                "colonne": colonne_modif,
                "date": date_modif,
                "ancienne": valeur_actuelle,
                "nouvelle": nouvelle_valeur,
                "verdict": verdict,
            }

        pending = st.session_state.get(cle_etat)
        correspond = (
            pending is not None
            and pending["panier"] == panier_modif
            and pending["colonne"] == colonne_modif
            and pending["date"] == date_modif
        )

        if correspond:
            st.markdown(
                "<div style='font-size:0.83rem;margin:0.7rem 0;'>"
                + panier_modif
                + " · "
                + colonne_modif
                + " · "
                + format_mois(date_modif)
                + " : <strong>"
                + ("%.2f" % pending["ancienne"] if pending["ancienne"] is not None else "—")
                + "</strong> → <strong>"
                + ("%.2f" % pending["nouvelle"])
                + "</strong></div>",
                unsafe_allow_html=True,
            )

            verdict = pending["verdict"]
            severite = verdict["severite"] if verdict else "ok"

            if verdict and verdict["message"]:
                if severite == "marque":
                    st.error(verdict["message"])
                else:
                    st.warning(verdict["message"])

            peut_confirmer = True
            if severite == "marque":
                peut_confirmer = st.checkbox("Je confirme cette valeur malgré l'alerte", key="modif_confirme_checkbox")

            if st.button("Confirmer la modification", key="modif_confirmer", disabled=not peut_confirmer):
                try:
                    saisie.modifier_valeur(FICHIER, panier_modif, colonne_modif, date_modif, nouvelle_valeur)
                    _vider_caches()
                    journaliser(
                        "saisie",
                        "inflation : modification %s / %s, %s" % (panier_modif, colonne_modif, format_mois(date_modif)),
                    )
                    st.success(
                        "Valeur modifiée pour « %s » — %s, %s." % (colonne_modif, panier_modif, format_mois(date_modif))
                    )
                    st.session_state.pop(cle_etat, None)
                except Exception as err:
                    signaler("07_Saisie", err, "Échec de la modification.", "error")

    # ---------------------------------------------------------- recalcul
    separateur_dore()
    titre_section("Mise à jour des indicateurs")

    st.markdown(
        "<div style='font-size:0.8rem;color:" + TEXTE_ATTENUE + ";margin-bottom:.6rem;'>"
        "Le recalcul reprend l'ensemble des indices, inflations et contributions "
        "à partir des valeurs brutes. À lancer une fois la saisie du mois terminée.</div>",
        unsafe_allow_html=True,
    )

    col_calc, col_retour, _reste = st.columns([2.2, 2.2, 3.6])

    with col_calc:
        if st.button("Recalculer les indicateurs", key="btn_recalcul"):
            with st.spinner("Recalcul en cours…"):
                try:
                    saisie.recalculer_apres_insertion(FICHIER)
                    journaliser("saisie", "inflation : recalcul des indicateurs")
                    st.cache_data.clear()
                    st.session_state["recalcul_ok"] = True
                except Exception as err:
                    st.session_state["recalcul_ok"] = False
                    signaler("07_Saisie", err, "Échec du recalcul.", "error")

    if st.session_state.get("recalcul_ok"):
        st.success("Indicateurs recalculés. Le tableau de bord est à jour.")

    with col_retour:
        if st.button("Voir le tableau de bord", key="btn_dashboard"):
            aller_a("inflation_vue")

    pied_de_page()
