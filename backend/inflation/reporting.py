"""
Rapport PDF mensuel d'inflation.

Module autonome, testable sans Streamlit. Il enchaîne trois responsabilités
nettement séparées :

  1. moteur de rédaction  — règles déterministes, aucun appel à un modèle de
     langage ; tous les gabarits viennent de config/narrative_rules.json ;
  2. extraction des données — un seul point de contact avec
     backend.inflation.calculator, la fonction construire_contexte_rapport() ;
  3. assemblage du document — les PNG produits par les fonctions tracer_* de
     backend.inflation.visualizer (export_png=True), un document neutre
     (couverture, sections, blocs) et l'interface unique rendre_document(),
     seule à connaître le moteur PDF (ReportLab, 100 % Python : aucune
     bibliothèque système requise, donc aucun problème GTK sous Windows).

Architecture éditoriale (couverture, puis 7 sections) :
    1. Synthèse du mois (national, MoM/YoY/moyenne annuelle, causes)
    2. Inflation globale — glissement annuel (3 masses, agricoles frais en
       détail, sous-jacentes 1 & 2, réglementés, FCI)
    3. Inflation en moyenne annuelle — même logique que la section 2
    4. Inflation en glissement mensuel — même logique que la section 2
    5. Groupes de dépenses (Grand Alger, National — inchangé)
    6. Catégories économiques (inchangé)
    7. Annexe méthodologique

Tous les graphiques d'évolution ne couvrent que les 12 derniers mois
(fenêtre glissante), quel que soit l'historique disponible ; seule la
synthèse chiffrée (statistiques de régime, moyennes comparées) s'appuie
sur tout l'historique.
"""

import hashlib
import json
import os
from datetime import datetime

from config.settings import (
    FICHIER_DONNEES_CALCULS,
    NARRATIVE_RULES_PATH,
    WEIGHTS_PATH,
    GRAPHES_DIR,
    FEUILLE_GRAND_ALGER,
    FEUILLE_NATIONAL,
    FEUILLE_CATEGORIES,
    FEUILLE_CORE,
    FEUILLE_NON_CORE,
    LOGO_OR_PATH,
    FEUILLE_NATIONAL_CORE2,
    FEUILLE_NATIONAL_REGLEMENTES,
    FEUILLE_NATIONAL_FCI,
)
from config.branding import (
    COLOR_NAVY_DARKEST,
    COLOR_NAVY_DEEP,
    COLOR_GOLD,
    COLOR_GOLD_DARK,
    COLOR_CYAN,
    COLOR_PAPIER,
    COLOR_PAPIER_ALT,
    COLOR_ENCRE,
    COLOR_ENCRE_ATTENUEE,
    COLOR_POSITIF,
    COLOR_NEGATIF,
    FONT_FAMILY_TITRE,
    FONT_FAMILY_TEXTE,
    FONT_GOOGLE_IMPORT,
    INSTITUTION,
)
from backend.inflation import calculator as calc
from backend.inflation import visualizer as viz

# ---------------------------------------------------------------------------
# Règles de rédaction : chargées une seule fois
# ---------------------------------------------------------------------------

with open(NARRATIVE_RULES_PATH, "r", encoding="utf-8") as _flux:
    REGLES = json.load(_flux)

GABARITS = REGLES["gabarits"]
QUALIFICATIFS = REGLES["qualificatifs"]
STRUCTURE_INFLATION = REGLES["rapport_inflation"]

_MOIS_FR = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


def libelle_mois(date):
    """'juillet 2025'."""
    import pandas as pd

    date = pd.to_datetime(date)
    return _MOIS_FR[date.month] + " " + str(date.year)


def _nombre(valeur):
    """'7.85%' ou '+0.23' -> float. Les extracteurs renvoient des chaînes."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return float(str(valeur).replace("%", "").replace(" ", "").replace(",", "."))


# ===========================================================================
# 1. MOTEUR DE RÉDACTION
# ===========================================================================


def qualificatif_variation(delta_pts, seuils):
    """
    Qualifie une variation d'un mois sur l'autre, en points.

        delta >=  seuil_marque   -> accélère nettement
        delta >=  seuil_modere   -> accélère légèrement
        |delta| <  seuil_modere  -> reste globalement stable
        delta <= -seuil_modere   -> ralentit légèrement
        delta <= -seuil_marque   -> décélère nettement

    `seuils` est un dict {"seuil_modere", "seuil_marque"} issu de
    config/narrative_rules.json : aucun seuil n'est codé en dur ici.
    """
    if delta_pts is None:
        return QUALIFICATIFS["stable"]

    modere = seuils["seuil_modere"]
    marque = seuils["seuil_marque"]

    if delta_pts >= marque:
        return QUALIFICATIFS["acceleration_marquee"]
    if delta_pts >= modere:
        return QUALIFICATIFS["acceleration_moderee"]
    if delta_pts <= -marque:
        return QUALIFICATIFS["deceleration_marquee"]
    if delta_pts <= -modere:
        return QUALIFICATIFS["deceleration_moderee"]
    return QUALIFICATIFS["stable"]


def texte_ipc_global(
    valeur_actuelle,
    valeur_precedente,
    moyenne_longue_periode,
    mode,
    mois_libelle="",
    moyenne_ytd=None,
    nb_mois_ytd=None,
    annee=None,
):
    """
    Paragraphe d'ouverture sur l'indice global : niveau, sens du mouvement,
    position par rapport à la moyenne de longue période, moyenne de l'année.
    """
    gab = GABARITS["ipc_global"]
    seuils = REGLES["seuils_variation"]["ipc_global"]
    delta = valeur_actuelle - valeur_precedente

    phrases = [
        gab["phrase_principale"]
        .format(
            mois_libelle=mois_libelle,
            mode_libelle=GABARITS["mode_libelle"][mode],
            valeur=valeur_actuelle,
            valeur_precedente=valeur_precedente,
            qualificatif=qualificatif_variation(delta, seuils),
            delta=delta,
        )
        .strip()
    ]

    if moyenne_longue_periode is not None:
        ecart = valeur_actuelle - moyenne_longue_periode
        if abs(ecart) < 0.25:
            phrases.append(gab["comparaison_moyenne_proche"].format(moyenne=moyenne_longue_periode))
        elif ecart > 0:
            phrases.append(gab["comparaison_moyenne_haute"].format(moyenne=moyenne_longue_periode, ecart=ecart))
        else:
            phrases.append(gab["comparaison_moyenne_basse"].format(moyenne=moyenne_longue_periode, ecart=ecart))

    seuil_eleve = REGLES["seuil_alerte_niveau"]["yoy_eleve"]
    if mode == "yoy" and valeur_actuelle > seuil_eleve:
        phrases.append(gab["alerte_niveau_eleve"].format(seuil=seuil_eleve))

    if moyenne_ytd is not None and nb_mois_ytd and annee:
        phrases.append(gab["moyenne_ytd"].format(nb_mois=nb_mois_ytd, annee=annee, moyenne_ytd=moyenne_ytd))

    return " ".join(phrases)


def texte_core_noncore(core_actuel, core_precedent, noncore_actuel, noncore_precedent, seuils=None):
    """
    Matrice éditoriale à quatre cas, croisant le sens de variation du core et
    celui du non-core. C'est le bloc le plus important du rapport : il tranche
    entre un choc d'offre passager et une diffusion durable aux prix
    sous-jacents.

        core ↑  et non-core ↑  -> tension généralisée
        core ~  et non-core ↑  -> choc sur la composante volatile
        core ↑  et non-core ↓  -> diffusion à l'inflation sous-jacente
        core ↓                 -> décélération

    Le cas « core stable » est traité avec le cas « choc volatil » : ce qui
    compte éditorialement est que la hausse ne se diffuse pas au sous-jacent.
    """
    gab = GABARITS["core_noncore"]
    seuils = seuils or REGLES["seuils_variation"]
    seuils_core = seuils["core"]
    seuils_noncore = seuils["non_core"]

    delta_core = core_actuel - core_precedent
    delta_noncore = noncore_actuel - noncore_precedent

    qual_core = qualificatif_variation(delta_core, seuils_core)
    qual_noncore = qualificatif_variation(delta_noncore, seuils_noncore)

    core_monte = delta_core >= seuils_core["seuil_modere"]
    core_baisse = delta_core <= -seuils_core["seuil_modere"]
    noncore_monte = delta_noncore >= seuils_noncore["seuil_modere"]

    valeurs = dict(
        core=core_actuel,
        delta_core=delta_core,
        noncore=noncore_actuel,
        delta_noncore=delta_noncore,
        qualificatif_core=qual_core,
        qualificatif_noncore=qual_noncore,
    )

    if core_baisse:
        cle = "cas_deceleration"
    elif core_monte and noncore_monte:
        cle = "cas_tension_generalisee"
    elif core_monte and not noncore_monte:
        cle = "cas_diffusion_sous_jacente"
    else:
        cle = "cas_choc_volatil"

    phrases = [gab[cle].format(**valeurs)]

    ecart = abs(noncore_actuel - core_actuel)
    if ecart >= 2.0:
        phrases.append(gab["ecart_core_noncore"].format(ecart=ecart))

    return " ".join(phrases)


def _enumerer(fragments):
    """'a, b et c' — séparateurs pris dans les gabarits."""
    gab = GABARITS["contributions"]
    if not fragments:
        return ""
    if len(fragments) == 1:
        return fragments[0]
    return gab["separateur"].join(fragments[:-1]) + gab["separateur_final"] + fragments[-1]


def texte_contributions(top_positifs, top_negatifs, inflation_totale, mode):
    """
    Phrase de décomposition : qui pousse l'indice, qui le retient, et dans
    quelle proportion. Consomme directement la sortie de
    calculator.identifier_top_contributeurs().
    """
    gab = GABARITS["contributions"]

    fragments = []
    for poste in top_positifs:
        fragments.append(
            gab["element_positif"].format(
                nom=poste["nom"],
                contribution=poste["contribution"],
                part=poste["part"] if poste["part"] is not None else 0,
            )
        )

    if fragments:
        phrases = [
            gab["phrase_principale"].format(
                inflation_totale=inflation_totale,
                mode_libelle=GABARITS["mode_libelle"][mode],
                detail_positifs=_enumerer(fragments),
            )
        ]
    else:
        # Aucun poste positif ce mois-ci (mouvement entièrement négatif) :
        # la phrase "les principaux moteurs sont ." serait vide de sens.
        phrases = [
            gab["aucun_positif"].format(
                inflation_totale=inflation_totale,
                mode_libelle=GABARITS["mode_libelle"][mode],
            )
        ]

    if top_negatifs:
        fragments_neg = [
            gab["element_negatif"].format(nom=p["nom"], contribution=abs(p["contribution"])) for p in top_negatifs
        ]
        phrases.append(
            gab["phrase_negatifs"].format(
                detail_negatifs=_enumerer(fragments_neg),
                verbe="freinent" if len(fragments_neg) > 1 else "freine",
            )
        )
    else:
        phrases.append(gab["aucun_negatif"])

    return " ".join(phrases)


def texte_par_groupe_categorie(nom_feuille, contributions, seuil_choc=None, variations=None):
    """
    Commente le classement des contributions d'un panier, et signale
    nommément tout poste dont la variation mensuelle dépasse `seuil_choc`,
    même s'il ne figure pas parmi les premiers contributeurs.

    `contributions` : liste de dicts {"nom", "contribution", "part"}.
    `variations`    : dict {nom: variation mensuelle en %}, facultatif.
    """
    gab = GABARITS["par_groupe"]
    if seuil_choc is None:
        seuil_choc = REGLES["seuil_choc_groupe"]["valeur"]

    if not contributions:
        return ""

    classes = sorted(contributions, key=lambda p: -abs(p["contribution"]))
    premier = classes[0]
    suivants = [gab["suivant"].format(nom=p["nom"], contribution=p["contribution"]) for p in classes[1:3]]

    phrases = [
        gab["ouverture"].format(
            premier=premier["nom"],
            contribution_premiere=premier["contribution"],
            suivants=_enumerer(suivants) if suivants else "aucun autre poste notable",
        )
    ]

    if variations:
        tete = {p["nom"] for p in classes[:3]}
        for nom, variation in variations.items():
            if nom in tete or variation is None:
                continue
            if abs(variation) >= seuil_choc:
                phrases.append(gab["choc_isole"].format(nom=nom, variation=variation))
                break  # un seul choc signalé, pour ne pas noyer le propos

    return " ".join(p for p in phrases if p)


def note_technique_coherence(coherent, ecart):
    """Note discrète si la somme des contributions s'écarte de l'inflation."""
    if coherent:
        return None
    tolerance = REGLES["tolerance_coherence_contributions"]["valeur"]
    return GABARITS["note_technique"]["ecart_coherence"].format(ecart=abs(ecart), tolerance=tolerance)


def note_detail_partiel_agricole_frais(n_disponibles, n_total):
    """
    Signale, si besoin, que le détail par produit des agricoles frais ne
    repose que sur une partie du panier ce mois-ci (voir
    etendre_historique_depuis_complementaire : 4 des 8 sous-produits n'ont
    pas de source récente dans le fichier complémentaire).
    """
    if n_disponibles >= n_total:
        return None
    return GABARITS["note_technique"]["detail_partiel_agricole_frais"].format(
        n_disponibles=n_disponibles, n_total=n_total
    )


def texte_sous_jacentes(core1, core2, mode):
    """
    Sous-jacente 1 (hors agricoles frais = Core) contre sous-jacente 2 (hors
    réglementés ET hors agricoles frais), avec commentaire sur l'écart :
    un écart qui se creuse signale que les produits réglementés tirent le
    sous-jacent dans un sens distinct du reste du panier.
    """
    gab = GABARITS["sous_jacentes"]
    seuil = REGLES["seuil_ecart_sous_jacentes"]["valeur"]
    ecart = abs(core1 - core2)

    phrases = [
        gab["phrase_principale"].format(
            core1=core1,
            core2=core2,
            mode_libelle=GABARITS["mode_libelle"][mode],
        )
    ]
    phrases.append((gab["ecart_marque"] if ecart >= seuil else gab["ecart_stable"]).format(ecart=ecart))
    return " ".join(phrases)


def texte_reglementes(valeur, mode):
    """Taux agrégé des produits réglementés — jamais de détail par produit."""
    return GABARITS["reglementes"]["phrase"].format(valeur=valeur, mode_libelle=GABARITS["mode_libelle"][mode])


def texte_fci(valeur, mode):
    """Mention contextuelle unique du taux des produits à fort contenu d'import."""
    return GABARITS["fci"]["phrase"].format(valeur=valeur, mode_libelle=GABARITS["mode_libelle"][mode])


def texte_focus_alimentaire(taux_frais, taux_industriel, mode):
    """
    Au sein des biens alimentaires : lequel des agricoles frais ou des
    alimentaires industriels porte le mouvement du mois.
    """
    gab = GABARITS["focus_alimentaire"]
    seuil = REGLES["seuil_focus_alimentaire"]["valeur"]
    mode_libelle = GABARITS["mode_libelle"][mode]

    if abs(taux_frais - taux_industriel) < seuil:
        cle = "phrase_equivalent"
    elif abs(taux_frais) > abs(taux_industriel):
        cle = "phrase_frais_domine"
    else:
        cle = "phrase_industriel_domine"

    return gab[cle].format(frais=taux_frais, industriel=taux_industriel, mode_libelle=mode_libelle)


# ===========================================================================
# 2. EXTRACTION DES DONNÉES
# ===========================================================================

# Panier -> (feuille, libellé affiché dans le rapport)
PANIERS = [
    ("grand_alger", FEUILLE_GRAND_ALGER, "Grand Alger"),
    ("national", FEUILLE_NATIONAL, "National"),
    ("categories", FEUILLE_CATEGORIES, "Catégories"),
    ("core", FEUILLE_CORE, "Core (sous-jacente 1)"),
    ("non_core", FEUILLE_NON_CORE, "Non-core (agricoles frais)"),
    # Séries nationales complémentaires : pas de sous-produits ni de poids
    # détaillé (voir README) — mesures seulement, aucune contribution.
    ("core2", FEUILLE_NATIONAL_CORE2, "Sous-jacente 2"),
    ("reglementes", FEUILLE_NATIONAL_REGLEMENTES, "Réglementés"),
    ("fci", FEUILLE_NATIONAL_FCI, "Fort contenu d'import"),
]


def _mesures_panier(fichier, feuille, date_reference):
    """
    Mesures d'un panier à la date donnée, MoM et YoY : valeur du mois,
    valeur du MOIS PRÉCÉDENT et écart entre les deux.

    Lues directement dans la série : extraire_inflation_yoy() renvoie un écart
    au même mois de l'an dernier, ce qui faisait écrire « après X % le mois
    précédent » avec une valeur vieille d'un an.
    """
    import pandas as pd

    resultat = {}
    try:
        df = pd.read_excel(fichier, sheet_name=feuille, index_col=0, parse_dates=True)
    except Exception as err:
        df, erreur = None, str(err)
    date_ref = pd.Timestamp(date_reference)
    for mode, colonne in (("mom", "Inflation (%, mom)"), ("yoy", "Inflation (%, yoy)")):
        mesure = {"valeur": None, "delta": None, "precedente": None}
        if df is None or colonne not in df.columns:
            mesure["erreur"] = erreur if df is None else "colonne absente : " + colonne
        else:
            serie = df[colonne].dropna()
            mois = serie.index.to_period("M")
            courant = serie[mois == date_ref.to_period("M")]
            precedent = serie[mois == (date_ref.to_period("M") - 1)]
            if not courant.empty:
                valeur = round(float(courant.iloc[0]), 3)
                mesure["valeur"] = valeur
                if not precedent.empty:
                    mesure["precedente"] = round(float(precedent.iloc[0]), 3)
                    mesure["delta"] = round(valeur - mesure["precedente"], 3)
        try:
            mesure["statistiques"] = calc.calculer_statistiques_historiques(
                fichier, feuille, colonne, periode_reference="post_2015"
            )
        except Exception:
            mesure["statistiques"] = None
        resultat[mode] = mesure
    return resultat


def construire_contexte_rapport(date_reference: str) -> dict:
    """
    Seul point de contact entre ce module et calculator.py.

    Rassemble, pour les cinq paniers et à la date demandée, les niveaux
    d'inflation, les statistiques de régime, la moyenne de l'année en cours,
    les principaux contributeurs et le contrôle de cohérence. Renvoie un
    dictionnaire unique, consommé ensuite par la rédaction et par le gabarit.
    """
    import pandas as pd

    fichier = str(FICHIER_DONNEES_CALCULS)
    date_reference = str(date_reference)
    horodatage = pd.to_datetime(date_reference)
    annee = int(horodatage.year)
    nb_mois_ytd = int(horodatage.month)

    tolerance = REGLES["tolerance_coherence_contributions"]["valeur"]

    paniers = {}
    for cle, feuille, libelle in PANIERS:
        entree = {"feuille": feuille, "libelle": libelle}
        entree["mesures"] = _mesures_panier(fichier, feuille, date_reference)

        try:
            entree["moyenne_ytd"] = calc.calculer_moyenne_ytd(fichier, feuille, "Inflation (%, yoy)", annee)
        except Exception:
            entree["moyenne_ytd"] = None

        # Le focus "agricoles frais" veut le classement complet (8 postes) ;
        # les autres paniers se contentent du podium habituel.
        n_top = 8 if cle == "non_core" else 3

        contributions = {}
        coherence = {}
        for mode in ("mom", "yoy"):
            try:
                positifs, negatifs = calc.identifier_top_contributeurs(
                    fichier, feuille, date_reference, mode=mode, n=n_top
                )
                contributions[mode] = {"positifs": positifs, "negatifs": negatifs}
            except Exception:
                contributions[mode] = None
            try:
                coherent, ecart = calc.verifier_coherence_contributions(
                    fichier, feuille, date_reference, mode, tolerance=tolerance
                )
                coherence[mode] = {"coherent": coherent, "ecart": ecart}
            except Exception:
                coherence[mode] = None

        entree["contributions"] = contributions
        entree["coherence"] = coherence
        paniers[cle] = entree

    # --- Produits alimentaires industriels : composante de 'core', jamais
    # exposée seule ailleurs que par ce taux (voir texte_focus_alimentaire).
    alimentaires_industriels = {}
    for mode in ("mom", "yoy"):
        try:
            alimentaires_industriels[mode] = calc.taux_variation_colonne(
                fichier, FEUILLE_CORE, "Produits_alimentaires_industriels", date_reference, mode=mode
            )
        except Exception:
            alimentaires_industriels[mode] = None

    # --- Moyennes YTD comparables (janvier -> mois courant, cette année et
    # l'an dernier) pour la section 3 (moyenne annuelle).
    moyennes_comparees = {}
    for cle in ("national", "core", "core2", "reglementes"):
        feuille = paniers[cle]["feuille"]
        try:
            moyennes_comparees[cle] = calc.calculer_moyenne_ytd_comparee(
                fichier, feuille, "Inflation (%, yoy)", date_reference
            )
        except Exception:
            moyennes_comparees[cle] = (None, None)

    # --- Complétude du détail agricoles frais : certains postes n'ont plus
    # de source récente (voir calc.AGRICOLE_FRAIS_SANS_SOURCE). La date de
    # début de la lacune est lue dans les données, jamais écrite en dur.
    lacune = {"debut": None, "n_sans_source": 0}
    try:
        df_frais = pd.read_excel(fichier, sheet_name=FEUILLE_NON_CORE).set_index("date")
        fins = [df_frais[c].last_valid_index() for c in calc.AGRICOLE_FRAIS_SANS_SOURCE if c in df_frais.columns]
        date_max_frais = df_frais.index.max()
        fins = [f for f in fins if f is not None and f < date_max_frais]
        if fins:
            lacune = {"debut": pd.Timestamp(min(fins)) + pd.DateOffset(months=1), "n_sans_source": len(fins)}
    except Exception:
        pass
    contrib_non_core_yoy = paniers["non_core"]["contributions"].get("yoy")
    n_disponibles = (
        len(contrib_non_core_yoy["positifs"]) + len(contrib_non_core_yoy["negatifs"]) if contrib_non_core_yoy else 0
    )
    try:
        n_total_agricole_frais = len(calc._poids_bruts(FEUILLE_NON_CORE))
    except Exception:
        n_total_agricole_frais = 8

    return {
        "date_reference": date_reference,
        "mois_libelle": libelle_mois(date_reference),
        "annee": annee,
        "nb_mois_ytd": nb_mois_ytd,
        "paniers": paniers,
        "alimentaires_industriels": alimentaires_industriels,
        "moyennes_comparees": moyennes_comparees,
        "agricole_frais_completude": {
            "n_disponibles": n_disponibles,
            "n_total": n_total_agricole_frais,
        },
        "date_derniere_donnee": calc.get_max_date(fichier, FEUILLE_GRAND_ALGER),
        "lacune_agricole_frais": lacune,
    }


# ===========================================================================
# 3. GRAPHIQUES
# ===========================================================================

# Nom logique -> (fonction de tracé, nom du PNG déposé dans GRAPHES_DIR).
# Les fonctions tracer_* écrivent sous un nom fixe : on se contente de le
# retrouver, aucun tracé n'est refait ici.
#
# Convention transversale du rapport : toutes ces figures n'affichent que
# les 12 derniers mois (fenêtre glissante), quel que soit l'historique
# disponible — voir generer_graphiques_rapport().
GRAPHIQUES_RAPPORT = [
    ("decomposition_yoy", None, "rapport_decomposition_yoy.png", "decomposition_yoy"),
    ("decomposition_moyenne_annuelle", None, "rapport_decomposition_moyenne_annuelle.png", "decomposition_moyenne"),
    ("decomposition_mom", None, "rapport_decomposition_mom.png", "decomposition_mom"),
    ("groupes_grand_alger_yoy", viz.tracer_inflation_grand_alger_yoy, "inflation_grand_alger_yoy.png", "simple"),
    (
        "contrib_grand_alger_yoy",
        viz.tracer_inflation_contributions_grand_alger_yoy,
        "inflation_contributions_grand_alger_yoy.png",
        "simple",
    ),
    ("groupes_national_yoy", viz.tracer_inflation_national_yoy, "inflation_national_yoy.png", "simple"),
    (
        "contrib_national_yoy",
        viz.tracer_inflation_contributions_national_yoy,
        "inflation_contributions_national_yoy.png",
        "simple",
    ),
    ("categories_yoy", viz.tracer_inflation_categories_yoy, "inflation_catégories_yoy.png", "simple"),
    (
        "contrib_categories_yoy",
        viz.tracer_inflation_contributions_categories_yoy,
        "inflation_contributions_catégories_yoy.png",
        "simple",
    ),
]


def generer_graphiques_rapport(date_fin: str) -> dict:
    """
    Appelle les fonctions tracer_* avec export_png=True et renvoie
    {nom_graphique: chemin_png}. Ne contient aucune logique de tracé.

    Fenêtre fixe de 12 mois se terminant à `date_fin` pour TOUTES les
    figures — convention transversale du rapport (seule la synthèse
    chiffrée s'appuie sur tout l'historique, pour les seuils et moyennes).

    Les graphiques qui échouent sont simplement absents du dictionnaire : le
    gabarit saute la vignette correspondante plutôt que d'interrompre le
    rapport.
    """
    import pandas as pd

    fichier = str(FICHIER_DONNEES_CALCULS)
    os.makedirs(GRAPHES_DIR, exist_ok=True)
    chemins = {}

    fin_dt = pd.to_datetime(date_fin)
    debut_dt = fin_dt - pd.DateOffset(months=11)
    date_debut = debut_dt.strftime("%Y-%m")

    for nom, fonction, fichier_png, signature in GRAPHIQUES_RAPPORT:
        try:
            if signature == "decomposition_yoy":
                viz.tracer_decomposition_yoy_rapport(
                    fichier,
                    FEUILLE_NATIONAL,
                    FEUILLE_NON_CORE,
                    FEUILLE_CORE,
                    FEUILLE_NATIONAL_REGLEMENTES,
                    FEUILLE_NATIONAL_CORE2,
                    date_fin,
                    export_png=True,
                )
            elif signature == "decomposition_moyenne":
                viz.tracer_decomposition_moyenne_annuelle_rapport(
                    fichier, FEUILLE_NATIONAL, FEUILLE_CORE, FEUILLE_NATIONAL_CORE2, date_fin, export_png=True
                )
            elif signature == "decomposition_mom":
                viz.tracer_decomposition_mom_rapport(
                    fichier,
                    FEUILLE_NON_CORE,
                    FEUILLE_CORE,
                    FEUILLE_CATEGORIES,
                    FEUILLE_NATIONAL,
                    date_fin,
                    export_png=True,
                )
            elif signature == "dashboard":
                fonction(
                    nom_fichier=fichier,
                    feuille_categories=FEUILLE_CATEGORIES,
                    feuille_core=FEUILLE_CORE,
                    feuille_non_core=FEUILLE_NON_CORE,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    export_png=True,
                )
            elif signature == "categories":
                fonction(
                    nom_fichier=fichier,
                    feuille_categories=FEUILLE_CATEGORIES,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    export_png=True,
                )
            else:
                fonction(fichier, date_debut, date_fin, export_png=True)
        except Exception:
            continue

        chemin = os.path.join(str(GRAPHES_DIR), fichier_png)
        if os.path.exists(chemin):
            chemins[nom] = chemin

    return chemins


# ===========================================================================
# 4. ANNEXE MÉTHODOLOGIQUE (statique)
# ===========================================================================


def contenu_annexe_methodologique(contexte: dict = None) -> dict:
    """Annexe du rapport mensuel : textes de narrative_rules.json, jetons remplis
    à partir des données (aucune date écrite en dur)."""
    annexe = STRUCTURE_INFLATION["annexe"]
    contexte = contexte or {}
    lacune = contexte.get("lacune_agricole_frais") or {}
    if lacune.get("debut"):
        limite = annexe["limite_granularite"].format(
            n_sans_source=lacune["n_sans_source"], debut_lacune=libelle_mois(lacune["debut"])
        )
    else:
        limite = annexe["limite_granularite_complete"]
    debut_regime = REGLES.get("periode_reference_statistiques", {}).get("post_2015", "")
    return {
        "glossaire": [tuple(x) for x in annexe["glossaire"]],
        "perimetres": [tuple(x) for x in annexe["perimetres"]],
        "limite_granularite": limite,
        "avertissement": annexe["avertissement"].format(
            debut_regime=libelle_mois(debut_regime) if debut_regime else ""
        ),
    }


# ===========================================================================
# 5. ASSEMBLAGE DU DOCUMENT
# ===========================================================================


def _empreinte_ponderations() -> str:
    """Hash court du fichier de pondérations, pour la traçabilité."""
    try:
        with open(WEIGHTS_PATH, "rb") as flux:
            return hashlib.md5(flux.read()).hexdigest()[:10]
    except OSError:
        return "indisponible"


def _constantes_charte() -> dict:
    """Charte transmise au gabarit : une seule source, config/branding.py."""
    return {
        "navy": COLOR_NAVY_DARKEST,
        "navy_deep": COLOR_NAVY_DEEP,
        "or": COLOR_GOLD,
        "or_fonce": COLOR_GOLD_DARK,
        "cyan": COLOR_CYAN,
        "papier": COLOR_PAPIER,
        "papier_alt": COLOR_PAPIER_ALT,
        "encre": COLOR_ENCRE,
        "encre_attenuee": COLOR_ENCRE_ATTENUEE,
        "positif": COLOR_POSITIF,
        "negatif": COLOR_NEGATIF,
        "police_titre": FONT_FAMILY_TITRE,
        "police_texte": FONT_FAMILY_TEXTE,
        "import_polices": FONT_GOOGLE_IMPORT,
        "institution": INSTITUTION,
    }


def _rediger(contexte: dict) -> dict:
    """
    Applique le moteur de rédaction au contexte. Produit le texte des 7
    sections du rapport (synthèse, glissement annuel, moyenne annuelle,
    glissement mensuel, groupes, catégories — l'annexe est statique).
    """
    paniers = contexte["paniers"]
    textes = {}

    def _mesure(cle, mode):
        return paniers[cle]["mesures"][mode]

    def _texte_moyenne_comparee(cle, libelle):
        actuelle, precedente = contexte["moyennes_comparees"].get(cle, (None, None))
        if actuelle is None or precedente is None:
            return GABARITS["moyenne_comparee"]["indisponible"].format(libelle=libelle)
        delta = actuelle - precedente
        qual = qualificatif_variation(delta, REGLES["seuils_variation"]["ipc_global"])
        return GABARITS["moyenne_comparee"]["phrase"].format(
            libelle=libelle, actuelle=actuelle, precedente=precedente, qual=qual
        )

    # ===================== SECTION 1 — SYNTHÈSE DU MOIS =====================
    national_mom = _mesure("national", "mom")
    national_yoy = _mesure("national", "yoy")
    stats_yoy = national_yoy.get("statistiques") or {}

    textes["synthese_mom"] = (
        texte_ipc_global(
            national_mom["valeur"], national_mom["precedente"], None, "mom", mois_libelle=contexte["mois_libelle"]
        )
        if national_mom["valeur"] is not None
        else "Indice global indisponible pour ce mois (glissement mensuel)."
    )

    if national_yoy["valeur"] is not None:
        textes["synthese_yoy"] = texte_ipc_global(
            national_yoy["valeur"],
            national_yoy["precedente"],
            stats_yoy.get("moyenne"),
            "yoy",
            mois_libelle=contexte["mois_libelle"],
        )
    else:
        textes["synthese_yoy"] = "Indice global indisponible pour ce mois (glissement annuel)."

    contrib_national_yoy = paniers["national"]["contributions"].get("yoy")
    if contrib_national_yoy and national_yoy["valeur"] is not None:
        textes["synthese_causes"] = texte_contributions(
            contrib_national_yoy["positifs"][:2], contrib_national_yoy["negatifs"][:1], national_yoy["valeur"], "yoy"
        )
    else:
        textes["synthese_causes"] = ""

    textes["synthese_moyenne_annuelle"] = _texte_moyenne_comparee(
        "national", "Moyenne annuelle (indice global national)"
    )

    # ============== SECTION 2 — INFLATION GLOBALE, GLISSEMENT ANNUEL ========
    core_yoy = _mesure("core", "yoy")
    core2_yoy = _mesure("core2", "yoy")
    reglementes_yoy = _mesure("reglementes", "yoy")
    fci_yoy = _mesure("fci", "yoy")
    non_core_yoy = _mesure("non_core", "yoy")
    industriel_yoy = contexte["alimentaires_industriels"].get("yoy")

    contrib_categories_yoy = paniers["categories"]["contributions"].get("yoy")
    categories_yoy = _mesure("categories", "yoy")
    textes["decomposition_3masses_yoy"] = (
        texte_contributions(
            contrib_categories_yoy["positifs"], contrib_categories_yoy["negatifs"], categories_yoy["valeur"], "yoy"
        )
        if contrib_categories_yoy and categories_yoy["valeur"] is not None
        else "Décomposition par catégorie indisponible."
    )

    textes["focus_alimentaire_yoy"] = (
        texte_focus_alimentaire(non_core_yoy["valeur"], industriel_yoy, "yoy")
        if non_core_yoy["valeur"] is not None and industriel_yoy is not None
        else ""
    )

    contrib_non_core_yoy = paniers["non_core"]["contributions"].get("yoy")
    textes["focus_agricole_frais_yoy"] = (
        texte_contributions(
            contrib_non_core_yoy["positifs"], contrib_non_core_yoy["negatifs"], non_core_yoy["valeur"], "yoy"
        )
        if contrib_non_core_yoy and non_core_yoy["valeur"] is not None
        else "Détail des agricoles frais indisponible."
    )
    textes["note_agricole_frais_completude"] = note_detail_partiel_agricole_frais(
        contexte["agricole_frais_completude"]["n_disponibles"],
        contexte["agricole_frais_completude"]["n_total"],
    )

    textes["focus_sous_jacentes_yoy"] = (
        texte_sous_jacentes(core_yoy["valeur"], core2_yoy["valeur"], "yoy")
        if core_yoy["valeur"] is not None and core2_yoy["valeur"] is not None
        else "Comparaison des sous-jacentes indisponible."
    )
    textes["focus_reglementes_yoy"] = (
        texte_reglementes(reglementes_yoy["valeur"], "yoy")
        if reglementes_yoy["valeur"] is not None
        else "Indice des produits réglementés indisponible."
    )
    textes["mention_fci_yoy"] = texte_fci(fci_yoy["valeur"], "yoy") if fci_yoy["valeur"] is not None else ""

    # ===================== SECTION 3 — MOYENNE ANNUELLE =====================
    textes["moyenne_annuelle_national"] = _texte_moyenne_comparee("national", "Indice global national")
    textes["moyenne_annuelle_sous_jacente_1"] = _texte_moyenne_comparee("core", "Sous-jacente 1")
    textes["moyenne_annuelle_sous_jacente_2"] = _texte_moyenne_comparee("core2", "Sous-jacente 2")
    textes["moyenne_annuelle_reglementes"] = _texte_moyenne_comparee("reglementes", "Réglementés")
    # Cause de la moyenne : reprend le classement du dernier mois disponible
    # (pas de moteur de contribution sur moyenne glissante — limite documentée en annexe).
    textes["moyenne_annuelle_cause"] = textes["decomposition_3masses_yoy"]
    textes["moyenne_annuelle_agricole_frais"] = textes["focus_agricole_frais_yoy"]

    # ================ SECTION 4 — INFLATION, GLISSEMENT MENSUEL ==============
    core_mom = _mesure("core", "mom")
    core2_mom = _mesure("core2", "mom")
    reglementes_mom = _mesure("reglementes", "mom")
    non_core_mom = _mesure("non_core", "mom")

    contrib_national_mom = paniers["national"]["contributions"].get("mom")
    textes["mom_causes"] = (
        texte_contributions(
            contrib_national_mom["positifs"][:2], contrib_national_mom["negatifs"][:1], national_mom["valeur"], "mom"
        )
        if contrib_national_mom and national_mom["valeur"] is not None
        else ""
    )

    contrib_non_core_mom = paniers["non_core"]["contributions"].get("mom")
    textes["focus_agricole_frais_mom"] = (
        texte_contributions(
            contrib_non_core_mom["positifs"], contrib_non_core_mom["negatifs"], non_core_mom["valeur"], "mom"
        )
        if contrib_non_core_mom and non_core_mom["valeur"] is not None
        else "Détail des agricoles frais indisponible."
    )
    textes["focus_sous_jacentes_mom"] = (
        texte_sous_jacentes(core_mom["valeur"], core2_mom["valeur"], "mom")
        if core_mom["valeur"] is not None and core2_mom["valeur"] is not None
        else "Comparaison des sous-jacentes indisponible."
    )
    textes["focus_reglementes_mom"] = (
        texte_reglementes(reglementes_mom["valeur"], "mom")
        if reglementes_mom["valeur"] is not None
        else "Indice des produits réglementés indisponible."
    )

    # ============== SECTIONS 5-6 — GROUPES / CATÉGORIES (inchangé) ==========
    for cle in ("grand_alger", "national", "categories"):
        panier = paniers[cle]
        contrib = panier["contributions"].get("yoy")
        mesure = panier["mesures"]["yoy"]

        if contrib and mesure["valeur"] is not None:
            textes["contributions_" + cle] = texte_contributions(
                contrib["positifs"], contrib["negatifs"], mesure["valeur"], "yoy"
            )
            tous = contrib["positifs"] + contrib["negatifs"]
            textes["groupes_" + cle] = texte_par_groupe_categorie(panier["feuille"], tous)
        else:
            textes["contributions_" + cle] = "Contributions indisponibles."
            textes["groupes_" + cle] = ""

        coherence = panier["coherence"].get("yoy")
        if coherence:
            note = note_technique_coherence(coherence["coherent"], coherence["ecart"])
            if note:
                textes["note_" + cle] = note

    return textes


# ===========================================================================
# 5. ASSEMBLAGE — interface unique de rendu
# ===========================================================================


def rendre_document(document: dict, chemin_sortie: str) -> str:
    """
    Seule interface de rendu PDF du projet. Le document est neutre
    (voir backend/common/moteur_pdf.py) ; changer de moteur ne touche qu'au
    module moteur_pdf. Renvoie le chemin écrit.
    """
    from backend.common import moteur_pdf
    from config.settings import ASSETS_DIR

    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)
    moteur_pdf.rendre(
        document,
        chemin_sortie,
        _constantes_charte(),
        ASSETS_DIR / "fonts",
        logo=str(LOGO_OR_PATH) if LOGO_OR_PATH.exists() else None,
    )
    return chemin_sortie


def _fmt_pct(valeur, signe=False):
    if valeur is None:
        return "—"
    return virgule_decimale(("%+.2f %%" if signe else "%.2f %%") % valeur)


def _indicateur_inflation(libelle, mesure):
    """(libellé, valeur, delta, classe) : une HAUSSE de l'inflation est défavorable."""
    if not mesure or mesure.get("valeur") is None:
        return (libelle, "—", None, None)
    delta = mesure.get("delta")
    texte_delta = None
    classe = None
    if delta is not None:
        texte_delta = virgule_decimale(("▲ " if delta >= 0 else "▼ ") + "%.2f pt" % abs(delta))
        classe = "defavorable" if delta >= 0 else "favorable"
    return (libelle, _fmt_pct(mesure["valeur"]), texte_delta, classe)


def _contributeurs(contrib):
    if not contrib:
        return []
    gabarit = STRUCTURE_INFLATION["contributeur"]
    lignes = []
    for poste in contrib.get("positifs", []) + contrib.get("negatifs", []):
        lignes.append(
            (
                poste["nom"],
                virgule_decimale(
                    gabarit.format(
                        signe="+" if poste["contribution"] >= 0 else "",
                        contribution=poste["contribution"],
                        part=poste["part"] or 0,
                    )
                ),
            )
        )
    return lignes


def document_inflation(contexte, textes, graphiques):
    """Document neutre du rapport mensuel (7 sections), sans aucun rendu."""
    st_ = STRUCTURE_INFLATION
    sec, blocs, ind, leg = st_["sections"], st_["blocs"], st_["indicateurs"], st_["legendes"]
    paniers = contexte["paniers"]

    def m(cle, mode):
        return paniers[cle]["mesures"][mode]

    def fig(cle):
        return ("figure", graphiques.get(cle), leg[cle])

    def section(cle, liste, **jetons):
        titre, chapeau = sec[cle]
        return {"titre": titre, "chapeau": chapeau.format(**jetons) if chapeau else "", "blocs": liste}

    annexe = contenu_annexe_methodologique(contexte)
    cv = st_["couverture_chiffres"]
    return {
        "titre_document": st_["titre_document"],
        "couverture": {
            "titre": st_["couverture_titre"],
            "periode": contexte["mois_libelle"].capitalize(),
            "chiffres": [_indicateur_inflation(lib, m(cle, "yoy")) for lib, cle in cv],
            "pied": st_["couverture_pied"].format(derniere_donnee=libelle_mois(contexte["date_derniere_donnee"])),
        },
        "sections": [
            section(
                "synthese",
                [
                    (
                        "indicateurs",
                        [
                            _indicateur_inflation(ind["national_mom"], m("national", "mom")),
                            _indicateur_inflation(ind["national_yoy"], m("national", "yoy")),
                            _indicateur_inflation(ind["core"], m("core", "yoy")),
                            _indicateur_inflation(ind["core2"], m("core2", "yoy")),
                        ],
                    ),
                    ("titre_bloc", blocs["glissement_mensuel"]),
                    ("paragraphe", textes.get("synthese_mom")),
                    ("titre_bloc", blocs["glissement_annuel"]),
                    ("paragraphe", textes.get("synthese_yoy")),
                    ("paragraphe", textes.get("synthese_causes")),
                    ("titre_bloc", blocs["moyenne_annuelle"]),
                    ("paragraphe", textes.get("synthese_moyenne_annuelle")),
                ],
                mois=contexte["mois_libelle"],
            ),
            section(
                "yoy",
                [
                    fig("decomposition_yoy"),
                    ("indicateurs", [_indicateur_inflation(ind["global_national"], m("national", "yoy"))]),
                    ("titre_bloc", blocs["trois_masses"]),
                    ("paragraphe", textes.get("decomposition_3masses_yoy")),
                    ("titre_bloc", blocs["focus_alimentaire"]),
                    ("paragraphe", textes.get("focus_alimentaire_yoy")),
                    ("titre_bloc", blocs["focus_agricole_frais"]),
                    ("paragraphe", textes.get("focus_agricole_frais_yoy")),
                    ("tableau", _contributeurs(paniers["non_core"]["contributions"].get("yoy"))),
                    ("note", textes.get("note_agricole_frais_completude")),
                    ("titre_bloc", blocs["focus_sous_jacentes"]),
                    (
                        "indicateurs",
                        [
                            _indicateur_inflation(ind["core_long"], m("core", "yoy")),
                            _indicateur_inflation(ind["core2_long"], m("core2", "yoy")),
                        ],
                    ),
                    ("paragraphe", textes.get("focus_sous_jacentes_yoy")),
                    ("titre_bloc", blocs["focus_reglementes"]),
                    ("paragraphe", textes.get("focus_reglementes_yoy")),
                    ("note", textes.get("mention_fci_yoy")),
                ],
            ),
            section(
                "moyenne",
                [
                    fig("decomposition_moyenne_annuelle"),
                    ("paragraphe", textes.get("moyenne_annuelle_national")),
                    ("titre_bloc", blocs["cause_principale"]),
                    ("paragraphe", textes.get("moyenne_annuelle_cause")),
                    ("note", st_["note_cause_moyenne"]),
                    ("titre_bloc", blocs["focus_agricole_frais"]),
                    ("paragraphe", textes.get("moyenne_annuelle_agricole_frais")),
                    ("titre_bloc", blocs["focus_sous_jacentes"]),
                    ("paragraphe", textes.get("moyenne_annuelle_sous_jacente_1")),
                    ("paragraphe", textes.get("moyenne_annuelle_sous_jacente_2")),
                    ("titre_bloc", blocs["focus_reglementes"]),
                    ("paragraphe", textes.get("moyenne_annuelle_reglementes")),
                ],
            ),
            section(
                "mom",
                [
                    fig("decomposition_mom"),
                    ("indicateurs", [_indicateur_inflation(ind["global_national"], m("national", "mom"))]),
                    ("titre_bloc", blocs["cause_principale"]),
                    ("paragraphe", textes.get("mom_causes")),
                    ("titre_bloc", blocs["focus_agricole_frais"]),
                    ("paragraphe", textes.get("focus_agricole_frais_mom")),
                    ("tableau", _contributeurs(paniers["non_core"]["contributions"].get("mom"))),
                    ("titre_bloc", blocs["focus_sous_jacentes"]),
                    ("paragraphe", textes.get("focus_sous_jacentes_mom")),
                    ("titre_bloc", blocs["focus_reglementes"]),
                    ("paragraphe", textes.get("focus_reglementes_mom")),
                ],
            ),
            section(
                "groupes",
                [
                    ("titre_bloc", blocs["grand_alger"]),
                    fig("groupes_grand_alger_yoy"),
                    ("paragraphe", textes.get("contributions_grand_alger")),
                    ("paragraphe", textes.get("groupes_grand_alger")),
                    fig("contrib_grand_alger_yoy"),
                    (
                        "indicateurs",
                        [
                            _indicateur_inflation(ind["grand_alger_yoy"], m("grand_alger", "yoy")),
                            _indicateur_inflation(ind["grand_alger_mom"], m("grand_alger", "mom")),
                        ],
                    ),
                    ("note", textes.get("note_grand_alger")),
                    ("saut_de_page",),
                    ("titre_bloc", blocs["national"]),
                    fig("groupes_national_yoy"),
                    ("paragraphe", textes.get("contributions_national")),
                    ("paragraphe", textes.get("groupes_national")),
                    fig("contrib_national_yoy"),
                    (
                        "indicateurs",
                        [
                            _indicateur_inflation(ind["national_annuel"], m("national", "yoy")),
                            _indicateur_inflation(ind["national_mensuel"], m("national", "mom")),
                        ],
                    ),
                    ("note", textes.get("note_national")),
                ],
            ),
            section(
                "categories",
                [
                    fig("categories_yoy"),
                    ("paragraphe", textes.get("contributions_categories")),
                    ("paragraphe", textes.get("groupes_categories")),
                    fig("contrib_categories_yoy"),
                    (
                        "indicateurs",
                        [
                            _indicateur_inflation(ind["categories_yoy"], m("categories", "yoy")),
                            _indicateur_inflation(ind["categories_mom"], m("categories", "mom")),
                        ],
                    ),
                    ("note", textes.get("note_categories")),
                ],
            ),
            section(
                "annexe",
                [
                    ("titre_bloc", blocs["glossaire"]),
                    ("tableau", annexe["glossaire"]),
                    ("titre_bloc", blocs["perimetres"]),
                    ("tableau", annexe["perimetres"]),
                    ("titre_bloc", blocs["limite"]),
                    ("paragraphe", annexe["limite_granularite"]),
                    ("avertissement", annexe["avertissement"]),
                ],
            ),
        ],
        "tracabilite": [
            (st_["tracabilite"]["genere_le"], datetime.now().strftime("%d/%m/%Y à %H:%M")),
            (st_["tracabilite"]["derniere_donnee"], libelle_mois(contexte["date_derniere_donnee"])),
            (st_["tracabilite"]["empreinte"], _empreinte_ponderations()),
        ],
    }


def generer_rapport_pdf(date_reference: str, chemin_sortie: str) -> str:
    """
    Rapport mensuel : contexte de données -> rédaction -> graphiques (12
    derniers mois, voir generer_graphiques_rapport) -> document -> PDF.
    Un graphique dont l'export échoue est remplacé par un message ; le
    rapport est toujours produit.
    """
    contexte = construire_contexte_rapport(date_reference)
    textes = {cle: virgule_decimale(t) if isinstance(t, str) else t for cle, t in _rediger(contexte).items()}
    graphiques = generer_graphiques_rapport(date_reference)
    return rendre_document(document_inflation(contexte, textes, graphiques), chemin_sortie)


# ===========================================================================
# 6. SECTION PIB — rapport trimestriel
# ===========================================================================
#
# Même chaîne que le rapport d'inflation : contexte (seul point de contact
# avec backend.pib.calculator) -> rédaction par règles déterministes
# (config/narrative_rules.json, bloc "pib") -> PNG exportés par les
# fonctions tracer_* de backend.pib.visualizer -> gabarit rapport_pib.html,
# feuille de style commune.

REGLES_PIB = REGLES["pib"]
GABARITS_PIB = REGLES_PIB["gabarits"]


def libelle_trimestre_long(date):
    """'deuxième trimestre 2025'."""
    import pandas as pd

    date = pd.Timestamp(date)
    rangs = {1: "premier", 2: "deuxième", 3: "troisième", 4: "quatrième"}
    return rangs[(date.month - 1) // 3 + 1] + " trimestre " + str(date.year)


def qualificatif_niveau_croissance(valeur):
    """Lecture du niveau de croissance réelle : contraction, faible, modérée, soutenue."""
    seuils = REGLES_PIB["seuils_niveau_croissance"]
    niveaux = REGLES_PIB["niveaux"]
    if valeur < 0:
        return niveaux["contraction"]
    if valeur < seuils["faible"]:
        return niveaux["faible"]
    if valeur < seuils["soutenue"]:
        return niveaux["moderee"]
    return niveaux["soutenue"]


def _enumerer_pib(fragments):
    if len(fragments) <= 1:
        return "".join(fragments)
    return GABARITS_PIB["separateur"].join(fragments[:-1]) + GABARITS_PIB["separateur_final"] + fragments[-1]


def texte_synthese_pib(valeur, valeur_precedente, trimestre):
    """Phrase d'ouverture : niveau de croissance et accélération / ralentissement."""
    if valeur is None:
        return ""
    delta = valeur - valeur_precedente if valeur_precedente is not None else 0.0
    precedente = valeur_precedente if valeur_precedente is not None else valeur
    if valeur < 0:
        return GABARITS_PIB["synthese_baisse"].format(
            trimestre=trimestre, valeur_abs=abs(valeur), valeur_precedente=precedente, delta=delta
        )
    return GABARITS_PIB["synthese_hausse"].format(
        trimestre=trimestre,
        valeur=valeur,
        valeur_precedente=precedente,
        delta=delta,
        niveau=qualificatif_niveau_croissance(valeur),
        qualificatif=qualificatif_variation(delta, REGLES_PIB["seuils_variation_croissance"]),
    )


def texte_comparaison_moyenne_pib(valeur, statistiques, debut_historique):
    moyenne, ecart_type = statistiques.get("moyenne"), statistiques.get("ecart_type")
    if valeur is None or moyenne is None or ecart_type is None:
        return ""
    seuil = REGLES_PIB["seuils_variation_croissance"]["seuil_modere"]
    if valeur - moyenne > seuil:
        position = GABARITS_PIB["position_au_dessus"]
    elif valeur - moyenne < -seuil:
        position = GABARITS_PIB["position_en_dessous"]
    else:
        position = GABARITS_PIB["position_proche"]
    return GABARITS_PIB["comparaison_moyenne"].format(
        debut_historique=debut_historique, moyenne=moyenne, ecart_type=ecart_type, position=position
    )


def texte_hydrocarbures(hh, h, total):
    """Croissance hors hydrocarbures et hydrocarbures, écart commenté au-delà du seuil."""
    if hh is None or h is None:
        return ""
    cle = "hydrocarbures_hausse" if h >= 0 else "hydrocarbures_baisse"
    texte = GABARITS_PIB[cle].format(hh=hh, h=h, h_abs=abs(h))
    if total is not None and abs(hh - total) > REGLES_PIB["seuil_ecart_hors_hydrocarbures"]["valeur"]:
        sens = "sens_hydrocarbures_freinent" if hh > total else "sens_hydrocarbures_soutiennent"
        texte += " " + GABARITS_PIB["ecart_hors_hydrocarbures"].format(ecart=hh - total, sens=GABARITS_PIB[sens])
    return texte


def texte_contributions_pib(positifs, negatifs, optique):
    """Moteurs et freins de la croissance, optique 'offre' ou 'demande'."""
    element = GABARITS_PIB["element"]
    if positifs:
        texte = GABARITS_PIB[optique + "_positifs"].format(
            detail=_enumerer_pib([element.format(**p) for p in positifs])
        )
    else:
        texte = GABARITS_PIB[optique + "_aucun_positif"]
    if negatifs:
        verbe = GABARITS_PIB["verbe_pluriel" if len(negatifs) > 1 else "verbe_singulier"]
        texte += " " + GABARITS_PIB["negatifs"].format(
            detail=_enumerer_pib([element.format(**n) for n in negatifs]), verbe=verbe
        )
    return texte


def construire_contexte_pib(date_reference=None) -> dict:
    """
    Seul point de contact entre le rapport PIB et backend.pib.calculator.
    `date_reference` : trimestre visé (dernier publié si None ou au-delà).
    """
    import pandas as pd
    from backend.pib import calculator as calc_pib

    r = calc_pib.pipeline_pib()
    libelles_o, libelles_d = calc_pib.libelles_offre(), calc_pib.libelles_demande()
    croissance = r["croissance"]["yoy"]
    publies = croissance["HH_reel"].dropna().index
    date = publies.max() if date_reference is None else min(pd.Timestamp(date_reference), publies.max())
    date = publies[publies <= date].max()

    def _valeur(serie, d=date):
        v = serie.get(d) if hasattr(serie, "get") else serie
        return None if v is None or pd.isna(v) else round(float(v), 3)

    precedent = publies[publies < date].max()
    pib = croissance["PIB_reel"]
    stats = calc_pib.statistiques_croissance(pib.loc[:date], date)
    contrib_o = r["contributions_offre"]["yoy"]
    contrib_d = r["contributions_demande"]["yoy"]
    ratios = r["ratios"]
    coherence = r["coherence_offre"]["yoy"].loc[date]
    ratio_date = ratios.index[ratios.index <= date].max()

    return {
        "date": date,
        "trimestre_libelle": libelle_trimestre_long(date),
        "trimestre_court": "T%d %d" % ((date.month - 1) // 3 + 1, date.year),
        "debut_historique": "T%d %d" % ((pib.dropna().index.min().month - 1) // 3 + 1, pib.dropna().index.min().year),
        "croissance": {
            "pib": _valeur(pib),
            "pib_precedent": _valeur(pib, precedent),
            "hh": _valeur(croissance["HH_reel"]),
            "hh_precedent": _valeur(croissance["HH_reel"], precedent),
            "h": _valeur(croissance["H_reel"]),
            "h_precedent": _valeur(croissance["H_reel"], precedent),
            "nominal": _valeur(croissance["PIB_nominal"]),
        },
        "deflateur": {
            "niveau": _valeur(r["deflateur"]["Deflateur"]),
            "inflation": _valeur(r["deflateur"]["Inflation_implicite_yoy"]),
        },
        "statistiques": stats,
        "offre": calc_pib.top_contributeurs(contrib_o, date, libelles_o, n=3),
        "demande": calc_pib.top_contributeurs(
            contrib_d[
                ["Consommation_menages", "Consommation_administrations", "FBCF", "Exportations_nettes", "Residuel"]
            ],
            date,
            libelles_d,
            n=3,
        ),
        "residuel": _valeur(contrib_d["Residuel"]),
        "coherence": {"ecart": _valeur(coherence["Ecart"]), "tolerance": r["tolerance"]},
        "ratios": {
            "investissement": _valeur(ratios["Taux_investissement"], ratio_date),
            "ouverture": _valeur(ratios["Taux_ouverture"], ratio_date),
            "delta_investissement": _valeur(ratios["Taux_investissement"].diff(4), ratio_date),
            "delta_ouverture": _valeur(ratios["Taux_ouverture"].diff(4), ratio_date),
        },
        "methode": r["methode"],
        "resultats": r,
    }


def virgule_decimale(texte: str) -> str:
    """'3.9 %' -> '3,9 %' : séparateur décimal français, sans toucher au reste."""
    import re

    return re.sub(r"(?<=\d)\.(?=\d)", ",", texte)


def _rediger_pib(contexte: dict) -> dict:
    """Textes du rapport PIB, tous issus des gabarits de narrative_rules.json."""
    textes = _rediger_pib_brut(contexte)
    return {cle: virgule_decimale(texte) for cle, texte in textes.items()}


def _rediger_pib_brut(contexte: dict) -> dict:
    c = contexte["croissance"]
    textes = {
        "synthese": texte_synthese_pib(c["pib"], c["pib_precedent"], contexte["trimestre_libelle"]),
        "comparaison": texte_comparaison_moyenne_pib(
            c["pib"], contexte["statistiques"]["historique"], contexte["debut_historique"]
        ),
        "hydrocarbures": texte_hydrocarbures(c["hh"], c["h"], c["pib"]),
        "offre": texte_contributions_pib(*contexte["offre"], optique="offre"),
        "demande": texte_contributions_pib(*contexte["demande"], optique="demande"),
        "methode": GABARITS_PIB["methode_" + contexte["methode"]["methode"]],
    }
    ytd = contexte["statistiques"]["depuis_t1"]
    textes["moyenne_depuis_t1"] = (
        GABARITS_PIB["moyenne_depuis_t1"].format(
            annee=contexte["date"].year,
            annee_precedente=contexte["date"].year - 1,
            moyenne=ytd["actuelle"],
            moyenne_precedente=ytd["precedente"],
        )
        if ytd["actuelle"] is not None and ytd["precedente"] is not None
        else ""
    )
    d = contexte["deflateur"]
    textes["deflateur"] = (
        GABARITS_PIB["deflateur"].format(inflation=d["inflation"], nominal=c["nominal"])
        if d["inflation"] is not None and c["nominal"] is not None
        else ""
    )
    ratios = contexte["ratios"]
    textes["ratios"] = GABARITS_PIB["ratios"].format(**ratios) if None not in ratios.values() else ""
    coherence = contexte["coherence"]
    textes["note_ecart"] = (
        GABARITS_PIB["note_ecart_chainage"].format(**coherence)
        if coherence["ecart"] is not None and abs(coherence["ecart"]) > coherence["tolerance"]
        else ""
    )
    textes["note_residuel"] = (
        GABARITS_PIB["note_residuel"].format(residuel=contexte["residuel"]) if contexte["residuel"] is not None else ""
    )
    return textes


def generer_graphiques_pib(contexte: dict) -> dict:
    """
    PNG du rapport PIB via les fonctions tracer_* (export_png=True), sur les
    N derniers trimestres (narrative_rules.json). Un graphique en échec est
    simplement absent : le gabarit saute la vignette.
    """
    import pandas as pd
    from backend.pib import visualizer as viz_pib
    from backend.pib import calculator as calc_pib

    r = contexte["resultats"]
    date = contexte["date"]
    n = REGLES_PIB["nombre_trimestres_graphiques"]
    debut = date - pd.DateOffset(months=3 * (n - 1))
    agregats = calc_pib._config_pib()["libelles_agregats"]
    colonnes_demande = [c["cle"] for c in calc_pib._config_pib()["contributions_demande"]]

    travaux = {
        "croissance": lambda: viz_pib.tracer_croissance_hydro_hh(
            r["croissance"]["yoy"].loc[debut:date], agregats, "yoy", export_png=True
        ),
        "nominal_reel": lambda: viz_pib.tracer_nominal_vs_reel(
            r["croissance"]["yoy"], date, agregats, "yoy", export_png=True
        ),
        "waterfall": lambda: viz_pib.tracer_waterfall_offre(
            r["contributions_offre"]["yoy"],
            date,
            calc_pib.libelles_offre(),
            agregats["total_croissance"],
            "yoy",
            export_png=True,
        ),
        "parts": lambda: viz_pib.tracer_parts_sectorielles(
            r["parts"].loc[debut:date], calc_pib.libelles_offre(), export_png=True
        ),
        "demande": lambda: viz_pib.tracer_contributions_demande(
            r["contributions_demande"]["yoy"].loc[debut:date],
            colonnes_demande,
            calc_pib.libelles_demande(),
            agregats["total_croissance"],
            "yoy",
            export_png=True,
        ),
        "ratios": lambda: viz_pib.tracer_ratios(r["ratios"].loc[debut:date], agregats, export_png=True),
    }
    fichiers = {
        "croissance": "pib_croissance_hydro_hh_yoy.png",
        "nominal_reel": "pib_nominal_vs_reel_yoy.png",
        "waterfall": "pib_waterfall_offre_yoy.png",
        "parts": "pib_parts_sectorielles.png",
        "demande": "pib_contributions_demande_yoy.png",
        "ratios": "pib_ratios_demande.png",
    }
    chemins = {}
    for nom, tracer in travaux.items():
        chemin = os.path.join(str(GRAPHES_DIR), fichiers[nom])
        if os.path.exists(chemin):
            os.remove(chemin)
        try:
            tracer()
        except Exception:
            continue
        if os.path.exists(chemin):
            chemins[nom] = chemin
    return chemins


def document_pib(contexte, textes, graphiques):
    """Document neutre du rapport trimestriel PIB (4 sections)."""
    st_ = REGLES_PIB["structure"]
    sec, leg, ch = st_["sections"], st_["legendes"], st_["chiffres"]
    c = contexte["croissance"]

    def indicateur(libelle, valeur, precedente, signe=False):
        texte = "—" if valeur is None else virgule_decimale(("%+.1f %%" if signe else "%.1f %%") % valeur)
        delta = classe = None
        if valeur is not None and precedente is not None:
            d = valeur - precedente
            delta = virgule_decimale(("▲ " if d >= 0 else "▼ ") + "%.1f pt" % abs(d))
            classe = "favorable" if d >= 0 else "defavorable"
        return (libelle, texte, delta, classe)

    def fig(cle):
        return ("figure", graphiques.get(cle), leg[cle])

    def section(cle, liste):
        titre, chapeau = sec[cle]
        return {"titre": titre, "chapeau": chapeau.format(trimestre_long=contexte["trimestre_libelle"]), "blocs": liste}

    def contributeurs(paire):
        positifs, negatifs = paire
        return [
            (
                p["nom"],
                virgule_decimale(
                    "%+.2f pt" % p["contribution"]
                    + (" · %.0f %% du mouvement" % p["part"] if p["part"] is not None else "")
                ),
            )
            for p in positifs + negatifs
        ]

    return {
        "titre_document": st_["titre_document"],
        "couverture": {
            "titre": st_["couverture_titre"],
            "periode": contexte["trimestre_libelle"].capitalize(),
            "chiffres": [
                indicateur(ch["pib"], c["pib"], c["pib_precedent"]),
                indicateur(ch["hh"], c["hh"], c["hh_precedent"]),
                indicateur(ch["inflation"], contexte["deflateur"]["inflation"], None, signe=True),
            ],
            "pied": st_["couverture_pied"].format(trimestre=contexte["trimestre_court"]),
        },
        "sections": [
            section(
                "synthese",
                [
                    (
                        "indicateurs",
                        [
                            indicateur(ch["pib"], c["pib"], c["pib_precedent"]),
                            indicateur(ch["hh"], c["hh"], c["hh_precedent"]),
                            indicateur(ch["h"], c["h"], c["h_precedent"]),
                        ],
                    ),
                    ("paragraphe", textes["synthese"]),
                    ("paragraphe", textes["comparaison"]),
                    ("paragraphe", textes["moyenne_depuis_t1"]),
                    ("paragraphe", textes["hydrocarbures"]),
                    ("paragraphe", textes["deflateur"]),
                    fig("croissance"),
                    fig("nominal_reel"),
                ],
            ),
            section(
                "offre",
                [
                    fig("waterfall"),
                    ("paragraphe", textes["offre"]),
                    ("tableau", contributeurs(contexte["offre"])),
                    ("note", textes["note_ecart"]),
                    fig("parts"),
                ],
            ),
            section(
                "demande",
                [
                    fig("demande"),
                    ("paragraphe", textes["demande"]),
                    ("tableau", contributeurs(contexte["demande"])),
                    ("note", textes["note_residuel"]),
                    fig("ratios"),
                    ("paragraphe", textes["ratios"]),
                ],
            ),
            section(
                "annexe",
                [
                    ("titre_bloc", st_["blocs"]["methode"]),
                    ("paragraphe", textes["methode"]),
                    ("titre_bloc", st_["blocs"]["glossaire"]),
                    ("tableau", [tuple(x) for x in st_["glossaire"]]),
                    ("avertissement", st_["avertissement"]),
                ],
            ),
        ],
        "tracabilite": [
            (st_["tracabilite"]["genere_le"], datetime.now().strftime("%d/%m/%Y à %H:%M")),
            (st_["tracabilite"]["derniere_donnee"], contexte["trimestre_court"]),
            (st_["tracabilite"]["methode"], contexte["methode"]["raison"]),
        ],
    }


def generer_rapport_pib_pdf(date_reference, chemin_sortie: str) -> str:
    """Rapport trimestriel PIB : même chaîne et même moteur que le rapport mensuel."""
    contexte = construire_contexte_pib(date_reference)
    textes = _rediger_pib(contexte)
    graphiques = generer_graphiques_pib(contexte)
    return rendre_document(document_pib(contexte, textes, graphiques), chemin_sortie)
