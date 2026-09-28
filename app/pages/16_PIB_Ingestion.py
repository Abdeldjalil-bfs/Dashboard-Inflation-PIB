"""
PIB — Ingestion de données.

Parcours en cinq étapes pour importer un rapport des Comptes Nationaux
Trimestriels (CNT) publié par l'ONS : sélection, extraction, contrôles
qualité, comparaison avec la base, validation et injection. Rien n'est écrit
en base sans validation explicite.

Mise en page uniquement : toute la logique vit dans backend/pib/ons_cnt.py.
Le résultat de l'extraction est conservé dans st.session_state, car chaque
clic relance le script.
"""

from datetime import date

import pandas as pd
import streamlit as st

from backend.pib import ons_cnt as cnt
from backend.pib import base_cnt
from app.components.theme import (
    entete_page,
    separateur_dore,
    titre_section,
    pied_de_page,
    TEXTE_ATTENUE,
    TEXTE,
)
from app.components.auth import est_admin
from app.components.journal import journaliser, journaliser_erreur
from app.components.layout import demarrer_page, libelle_page, aller_a
from app.components.stepper import stepper, badge

contenu = demarrer_page("pib_ingestion")

ETAPES = ["Sélection", "Extraction", "Contrôles qualité", "Comparaison", "Validation"]

# Explication, en langage simple, de chaque contrôle (clé = début du libellé).
EXPLICATIONS = {
    "Tableau": (
        "Vérifie que chacun des quatre tableaux attendus a bien été lu dans le PDF.",
        "Si un tableau manque, la mise en page du rapport a peut-être changé : ne pas injecter, "
        "signaler le rapport à l'équipe technique.",
    ),
    "Aucun doublon": (
        "Vérifie qu'une même observation (poste, période) n'apparaît qu'une fois.",
        "Un doublon indique une lecture ambiguë du PDF : ne pas injecter.",
    ),
    "Aucune valeur manquante": (
        "Vérifie que chaque case lue contient bien un nombre.",
        "Une valeur manquante signale une cellule mal lue : ne pas injecter.",
    ),
    "Dernier trimestre": (
        "Vérifie que le rapport s'arrête bien au trimestre demandé.",
        "Un écart signifie souvent qu'un autre rapport a été ouvert : vérifier l'année et le trimestre.",
    ),
    "Série trimestrielle": (
        "Vérifie qu'aucun trimestre ne manque entre le début et la fin du rapport.",
        "Un trou empêche le calcul des glissements : ne pas injecter.",
    ),
    "Σ trimestres": (
        "Vérifie que la somme des quatre trimestres égale la valeur annuelle publiée.",
        "Un petit écart peut venir des arrondis de l'ONS : l'injection reste possible, mais regardez le poste cité.",
    ),
    "Postes reconnus": (
        "Vérifie que chaque poste du PDF est rattaché à une rubrique d'analyse "
        "(table de correspondance de config/pib_config.json).",
        "Les postes non reconnus sont conservés en base et visibles dans la page Séries, "
        "mais n'entrent pas dans les calculs : faites compléter la table de correspondance.",
    ),
    "Croissances plausibles": (
        "Signale les taux de croissance supérieurs à 100 % en valeur absolue.",
        "Peut être légitime pour un petit poste (stocks, par exemple) : "
        "vérifiez dans le PDF, puis injectez si la valeur est confirmée.",
    ),
}


def _aide(texte):
    st.markdown(
        "<div style='font-size:0.8rem;color:" + TEXTE_ATTENUE + ";margin:-0.3rem 0 0.9rem 0;"
        "line-height:1.55;'>" + texte + "</div>",
        unsafe_allow_html=True,
    )


def _etat_vide(texte):
    st.markdown(
        "<div class='ba-card' style='text-align:center;padding:1.4rem;'>"
        "<div style='font-size:0.85rem;color:" + TEXTE_ATTENUE + ";'>" + texte + "</div></div>",
        unsafe_allow_html=True,
    )


def _explication(controle):
    for debut, texte in EXPLICATIONS.items():
        if controle.startswith(debut):
            return texte
    return ("", "")


def _carte(libelle, valeur, note):
    """Carte d'indicateur sans pastille de variation (comptes, états)."""
    st.markdown(
        "<div class='ba-kpi'><div class='ba-kpi-label'>" + libelle + "</div>"
        "<div class='ba-kpi-value'>" + str(valeur) + "</div>"
        "<div class='ba-kpi-delta-note'>" + note + "</div></div>",
        unsafe_allow_html=True,
    )


def _libelle_rapport(rapport):
    return base_cnt.libelle_rapport(rapport)


def _peut_injecter():
    """Injection réservée au profil admin (backend/auth/users.py)."""
    return est_admin()


with contenu:
    entete_page(
        libelle_page("pib_ingestion"),
        "Importez un rapport des Comptes Nationaux Trimestriels (CNT) publié par l'Office "
        "National des Statistiques sur ons.dz. Les tableaux du PDF sont extraits, contrôlés puis "
        "comparés à la base. Aucune donnée n'est écrite sans votre validation explicite.",
    )
    with st.expander("Glossaire", expanded=False):
        st.markdown(
            "- **Rapport, ou millésime** : une publication CNT donnée, par exemple « T%d %d ». "
            % tuple(reversed(cnt.trimestre_par_defaut()))
            + "Chaque rapport republie aussi les trimestres précédents.\n"
            "- **Révision** : une valeur déjà publiée que l'ONS corrige dans un rapport plus récent. "
            "C'est un comportement normal de la comptabilité nationale.\n"
            "- **Tidy** : format « une ligne = une observation » (rapport, tableau, poste, période, "
            "valeur, unité), utilisé pour la base et la feuille « Tidy » de l'Excel.\n"
            "- **Blocs** : les quatre tableaux lus dans le PDF. *Valeurs* : PIB et valeurs ajoutées à "
            "prix courants. *Croissance* : taux t/t−4 aux prix de l'année précédente chaînés. "
            "*Emplois_valeurs* et *Emplois_croissance* : équilibre ressources-emplois, en valeurs et "
            "en croissance.\n"
            "- **Erreur ou avertissement** : une *erreur* bloque l'injection, car la lecture du PDF "
            "n'est pas fiable. Un *avertissement* informe sans bloquer."
        )
    separateur_dore()

    resultat = st.session_state.get("cnt_resultat")
    injection = st.session_state.get("cnt_injection")
    if resultat is None:
        active, faites = 0, ()
    elif not resultat.valide:
        active, faites = 2, (0, 1)
    elif injection and injection["rapport"] == resultat.rapport:
        active, faites = None, (0, 1, 2, 3, 4)
    else:
        active, faites = 4, (0, 1, 2, 3)
    stepper(ETAPES, active, faites)

    conn = cnt.ouvrir_base()
    try:
        base_cnt.assurer_socle(conn)
        # ======================================================= ÉTAPE 1
        titre_section("1 · Sélection du rapport")
        _aide(
            "Choisissez l'année et le trimestre du rapport. Par défaut : le dernier trimestre "
            "que l'ONS a normalement déjà publié (délai de publication d'environ quatre mois)."
        )

        annee_def, trim_def = st.session_state.get("cnt_preselection") or cnt.trimestre_par_defaut()
        annees = list(range(date.today().year, 2014, -1))
        c1, c2, c3, c4 = st.columns([1.6, 1.6, 2.2, 2.8], vertical_alignment="bottom")
        with c1:
            annee = st.selectbox(
                "Année", annees, index=annees.index(annee_def) if annee_def in annees else 0, key="cnt_annee"
            )
        with c2:
            trimestre = st.selectbox(
                "Trimestre", [1, 2, 3, 4], index=trim_def - 1, format_func=lambda t: "T%d" % t, key="cnt_trimestre"
            )
        with c3:
            extraire = st.button("Extraire le rapport", key="cnt_extraire")
        with c4:
            rechercher = st.button(
                "Rechercher un nouveau rapport", key="cnt_rechercher", type="tertiary", icon=":material/search:"
            )

        importe_le = cnt.date_import(conn, annee, trimestre)
        st.markdown(
            "<div style='font-size:0.78rem;color:" + TEXTE_ATTENUE + ";margin-top:0.4rem;'>"
            "Source : <code>"
            + cnt.url_cnt(annee, trimestre)
            + "</code><br/>"
            + (
                "Déjà importé le " + importe_le.replace("T", " à ")
                if importe_le
                else "Ce rapport n'a encore jamais été importé."
            )
            + "</div>",
            unsafe_allow_html=True,
        )

        if rechercher:
            cible = base_cnt.prochain_rapport_attendu(conn) or cnt.trimestre_par_defaut()
            try:
                with st.spinner("Interrogation d'ons.dz…"):
                    publie = cnt.rapport_publie(*cible)
                st.session_state["cnt_recherche"] = {"cible": cible, "publie": publie}
            except cnt.ONSInjoignable:
                st.session_state["cnt_recherche"] = {"cible": cible, "publie": None}

        recherche = st.session_state.get("cnt_recherche")
        if recherche:
            a, t = recherche["cible"]
            if recherche["publie"] is None:
                st.warning("ons.dz ne répond pas pour le moment. Vérifiez la connexion, puis réessayez.")
            elif recherche["publie"]:
                st.success("Nouveau rapport disponible : T%d %d." % (t, a))
                if st.button("Préparer l'extraction de T%d %d" % (t, a), key="cnt_preremplir"):
                    st.session_state["cnt_preselection"] = (a, t)
                    for cle in ("cnt_annee", "cnt_trimestre", "cnt_recherche"):
                        st.session_state.pop(cle, None)
                    st.rerun()
            else:
                st.info("Pas encore de rapport T%d %d sur ons.dz." % (t, a))

        with st.expander("Vous avez déjà le PDF ? Déposez-le ici", expanded=False):
            _aide(
                "Utile si ons.dz est temporairement injoignable. Le fichier doit être le rapport CNT "
                "correspondant à l'année et au trimestre sélectionnés ci-dessus."
            )
            pdf_local = st.file_uploader("Rapport CNT (PDF)", type=["pdf"], key="cnt_pdf_local")
            extraire_local = st.button("Extraire ce fichier", key="cnt_extraire_local", disabled=pdf_local is None)

        # ======================================================= ÉTAPE 2
        if extraire or extraire_local:
            st.session_state.pop("cnt_resultat", None)
            st.session_state.pop("cnt_injection", None)
            st.session_state.pop("cnt_erreur", None)
            progression = st.progress(0, text="Téléchargement du rapport depuis ons.dz (jusqu'à 2 minutes)…")
            try:
                if extraire_local:
                    pdf = pdf_local.getvalue()
                else:
                    pdf = cnt.telecharger_pdf(annee, trimestre)
                progression.progress(55, text="Lecture des tableaux du PDF…")
                resultat = cnt.traiter_pdf(pdf, annee, trimestre)
                progression.progress(100, text="Extraction terminée.")
                st.session_state["cnt_resultat"] = resultat
                st.session_state["cnt_extraction_n"] = st.session_state.get("cnt_extraction_n", 0) + 1
            except cnt.CNTIntrouvable:
                st.session_state["cnt_erreur"] = (
                    "introuvable",
                    "Ce rapport n'est pas encore publié sur ons.dz. Vérifiez l'année "
                    "et le trimestre, ou réessayez plus tard.",
                )
            except cnt.ONSInjoignable as err:
                journaliser_erreur("ingestion", err)
                st.session_state["cnt_erreur"] = (
                    "reseau",
                    "ons.dz ne répond pas (connexion coupée ou délai dépassé). Aucune donnée "
                    "n'a été écrite. Réessayez dans quelques instants.",
                )
            except cnt.ExtractionVide:
                st.session_state["cnt_erreur"] = (
                    "vide",
                    "La mise en page du PDF a peut-être changé : aucun tableau n'a pu être lu. "
                    "Aucune donnée n'a été écrite.",
                )
            except Exception as err:
                journaliser_erreur("ingestion", err)
                st.session_state["cnt_erreur"] = (
                    "autre",
                    "L'extraction a échoué de façon inattendue. Aucune donnée n'a été écrite.",
                )
            progression.empty()
            st.rerun()

        titre_section("2 · Extraction")
        erreur = st.session_state.get("cnt_erreur")
        resultat = st.session_state.get("cnt_resultat")
        if erreur:
            (st.info if erreur[0] == "introuvable" else st.error)(erreur[1])
            if erreur[0] == "reseau" and st.button("Réessayer", key="cnt_reessayer"):
                st.session_state.pop("cnt_erreur", None)
                st.rerun()
        if resultat is None:
            if not erreur:
                _etat_vide(
                    "Aucun rapport extrait pour l'instant. Sélectionnez une année et un "
                    "trimestre, puis cliquez sur « Extraire le rapport »."
                )
        else:
            tidy = resultat.tidy
            trimestriel = tidy[tidy["periodicite"] == "Trimestriel"]
            cles = trimestriel["annee"] * 10 + trimestriel["trimestre"].str[1].astype(int)
            debut, fin = int(cles.min()), int(cles.max())
            _aide(
                "Rapport <strong style='color:"
                + TEXTE
                + ";'>"
                + _libelle_rapport(resultat.rapport)
                + "</strong> lu. Vous pouvez télécharger l'Excel dès maintenant : il ne modifie pas la base."
            )
            k1, k2 = st.columns([1.2, 3], gap="medium")
            with k1:
                st.markdown(
                    "<div class='ba-kpi'><div class='ba-kpi-label'>Observations extraites</div>"
                    "<div class='ba-kpi-value'>"
                    + format(len(tidy), ",").replace(",", " ")
                    + "</div><div class='ba-kpi-delta-note'>période T%d %d → T%d %d</div></div>"
                    % (debut % 10, debut // 10, fin % 10, fin // 10),
                    unsafe_allow_html=True,
                )
            with k2:
                synthese = (
                    tidy.groupby("bloc")
                    .agg(Observations=("valeur", "size"), Postes=("poste", "nunique"))
                    .reindex(list(cnt.BLOCS))
                    .fillna(0)
                    .astype(int)
                )
                synthese.insert(0, "Contenu", [cnt.BLOCS[b]["description"] for b in synthese.index])
                synthese.index.name = "Bloc"
                st.dataframe(synthese, width="stretch")
            st.download_button(
                "Télécharger l'Excel (" + resultat.nom_fichier + ")",
                data=resultat.excel,
                file_name=resultat.nom_fichier,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cnt_excel",
            )

        # ======================================================= ÉTAPE 3
        titre_section("3 · Contrôles qualité")
        if resultat is None:
            _etat_vide("Les contrôles s'afficheront après l'extraction.")
        else:
            _aide(
                "Chaque ligne vérifie un point de la lecture du PDF. Une <strong>erreur</strong> bloque "
                "l'injection ; un <strong>avertissement</strong> informe sans bloquer."
            )
            ctrl = pd.concat(
                [resultat.controles, pd.DataFrame([base_cnt.controle_postes(resultat.tidy)])], ignore_index=True
            )
            compte = ctrl["Niveau"].value_counts()
            n_ok, n_av, n_err = (int(compte.get(n, 0)) for n in ("OK", "AVERTISSEMENT", "ERREUR"))
            st.markdown(
                "<div style='margin:0 0 0.6rem 0;font-size:0.9rem;'>"
                + badge("OK")
                + " "
                + str(n_ok)
                + " &nbsp;&nbsp;"
                + badge("AVERTISSEMENT")
                + " "
                + str(n_av)
                + " &nbsp;&nbsp;"
                + badge("ERREUR")
                + " "
                + str(n_err)
                + "</div>",
                unsafe_allow_html=True,
            )
            lignes = "".join(
                "<tr><td style='padding:0.45rem 0.6rem;'>" + badge(l["Niveau"]) + "</td>"
                "<td style='padding:0.45rem 0.6rem;color:"
                + TEXTE
                + ";' title=\""
                + _explication(l["Contrôle"])[0].replace('"', "'")
                + "\">"
                + l["Contrôle"]
                + "</td>"
                "<td style='padding:0.45rem 0.6rem;color:" + TEXTE_ATTENUE + ";'>" + str(l["Détail"]) + "</td></tr>"
                for _i, l in ctrl.iterrows()
            )
            st.markdown(
                "<div style='overflow-x:auto;'><table style='width:100%;border-collapse:collapse;"
                "font-size:0.82rem;border:1px solid rgba(188,158,110,0.18);border-radius:10px;'>"
                "<thead><tr style='text-align:left;color:" + TEXTE_ATTENUE + ";font-size:0.7rem;"
                "text-transform:uppercase;letter-spacing:0.1em;'><th style='padding:0.5rem 0.6rem;'>Niveau</th>"
                "<th style='padding:0.5rem 0.6rem;'>Contrôle</th><th style='padding:0.5rem 0.6rem;'>Détail</th>"
                "</tr></thead><tbody>" + lignes + "</tbody></table></div>",
                unsafe_allow_html=True,
            )
            with st.expander("Comprendre les contrôles et que faire en cas d'écart", expanded=n_err > 0):
                vus = set()
                for _i, l in ctrl.iterrows():
                    quoi, faire = _explication(l["Contrôle"])
                    if quoi and quoi not in vus:
                        vus.add(quoi)
                        st.markdown("**" + l["Contrôle"].split(" «")[0] + "** — " + quoi + " *" + faire + "*")

        # ======================================================= ÉTAPE 4
        titre_section("4 · Comparaison avec la base")
        comparaison = None
        if resultat is None:
            _etat_vide("La comparaison avec les rapports déjà importés s'affichera après l'extraction.")
        else:
            comparaison = cnt.comparer_avec_base(conn, resultat.tidy)
            _aide(
                "La base conserve tous les rapports. Les pages d'analyse lisent la dernière version "
                "de chaque chiffre (vue <code>cnt_pib_derniere</code>), si bien qu'un rapport plus ancien "
                "ne peut jamais écraser un plus récent. Une <strong>révision</strong> est une valeur "
                "que l'ONS a corrigée depuis le rapport précédent : c'est normal."
            )
            k1, k2, k3 = st.columns(3, gap="medium")
            with k1:
                _carte(
                    "Rapport déjà importé",
                    "Oui" if comparaison["deja_importe"] else "Non",
                    ("le " + importe_le.replace("T", " à ")) if importe_le else "première importation",
                )
            with k2:
                _carte(
                    "Observations nouvelles",
                    format(comparaison["nb_nouvelles"], ",").replace(",", "\u202f"),
                    "absentes des rapports antérieurs",
                )
            with k3:
                _carte(
                    "Observations révisées",
                    format(comparaison["nb_revisees"], ",").replace(",", "\u202f"),
                    "par rapport au rapport précédent",
                )

            revisions = comparaison["revisees"]
            if revisions.empty:
                _etat_vide(
                    "Aucune révision détectée : les valeurs communes avec les rapports "
                    "précédents sont identiques, ou aucun rapport antérieur n'est en base."
                )
            else:
                tableau = revisions.rename(
                    columns={
                        "bloc": "Bloc",
                        "poste": "Poste",
                        "periode": "Période",
                        "rapport_prec": "Rapport précédent",
                        "ancienne": "Ancienne valeur",
                        "valeur": "Nouvelle valeur",
                        "ecart": "Écart",
                    }
                )
                tableau["Rapport précédent"] = tableau["Rapport précédent"].map(_libelle_rapport)
                st.dataframe(tableau.round(2), width="stretch", hide_index=True, height=300)
                st.download_button(
                    "Exporter les révisions en CSV",
                    data=tableau.to_csv(index=False).encode("utf-8-sig"),
                    file_name="revisions_%s.csv" % resultat.rapport,
                    mime="text/csv",
                    key="cnt_revisions_csv",
                )

        # ======================================================= ÉTAPE 5
        titre_section("5 · Validation et injection")
        if resultat is None:
            _etat_vide("L'injection sera proposée une fois le rapport extrait et contrôlé.")
        else:
            bloque = not resultat.valide
            if bloque:
                st.error(
                    "Injection impossible : au moins un contrôle est en erreur. La lecture du PDF "
                    "n'est pas fiable ; aucune donnée ne sera écrite."
                )
            elif not _peut_injecter():
                st.info(
                    "L'injection est réservée aux profils administrateurs. Vous pouvez télécharger "
                    "l'Excel et transmettre le rapport."
                )
            else:
                if comparaison and comparaison["deja_importe"]:
                    st.warning(
                        "Ce rapport est déjà en base. Le réinjecter remplacera uniquement sa propre "
                        "version (" + _libelle_rapport(resultat.rapport) + ") ; les autres rapports "
                        "restent intacts."
                    )
                _aide(
                    "L'écriture est faite en une seule opération : en cas d'incident, la base reste "
                    "exactement dans son état antérieur."
                )
                # Clé propre à chaque extraction : une confirmation donnée pour un
                # rapport ne doit jamais rester cochée pour le suivant.
                confirme = st.checkbox(
                    "Je confirme l'injection de %d observations du rapport %s."
                    % (len(resultat.tidy), _libelle_rapport(resultat.rapport)),
                    value=False,
                    key="cnt_confirme_%d" % st.session_state.get("cnt_extraction_n", 0),
                )
                if st.button("Injecter en base", key="cnt_injecter", disabled=not confirme):
                    try:
                        n = cnt.injecter_en_base(conn, resultat.tidy)
                        journaliser("ingestion", "rapport CNT %s injecté (%d lignes)" % (resultat.rapport, n))
                        st.cache_data.clear()
                        st.session_state["cnt_injection"] = {"rapport": resultat.rapport, "lignes": n}
                        st.session_state["cnt_extraction_n"] = st.session_state.get("cnt_extraction_n", 0) + 1
                        st.rerun()
                    except Exception as err:
                        journaliser_erreur("ingestion", err)
                        st.error(
                            "L'injection a échoué ; la base n'a pas été modifiée. Réessayez ; si le "
                            "problème persiste, consultez le journal de l'application."
                        )

            injection = st.session_state.get("cnt_injection")
            if injection and injection["rapport"] == resultat.rapport:
                st.success(
                    "%d lignes écrites pour le rapport %s. Les caches des pages PIB ont été vidés."
                    % (injection["lignes"], _libelle_rapport(injection["rapport"]))
                )
                if st.button("Voir la vue d'ensemble du PIB", key="cnt_vers_vue"):
                    aller_a("pib_vue")

        # ================================================ HISTORIQUE
        separateur_dore()
        titre_section("Historique des imports")
        historique = cnt.historique_imports(conn)
        if historique.empty:
            _etat_vide("Aucun rapport n'a encore été importé en base.")
        else:
            historique["rapport"] = historique["rapport"].map(_libelle_rapport)
            historique["importe_le"] = historique["importe_le"].str.replace("T", " à ")
            st.dataframe(
                historique.rename(columns={"rapport": "Rapport", "importe_le": "Importé le", "nb_lignes": "Lignes"}),
                width="stretch",
                hide_index=True,
            )
    finally:
        conn.close()

    pied_de_page()
