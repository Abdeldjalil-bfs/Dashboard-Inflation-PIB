"""
Détection d'anomalies à la saisie des valeurs brutes.

Module de lecture et de statistique pur : aucune dépendance à Streamlit,
aucune écriture. Il répond à une seule question — « cette valeur est-elle
plausible au regard de l'historique de cette série ? » — et laisse
l'appelant décider quoi en faire.

Deux angles complémentaires, car ils n'attrapent pas les mêmes erreurs :

  * le NIVEAU    : la valeur elle-même, comparée aux niveaux récents.
                   Attrape les fautes de frappe (facteur 10, virgule
                   oubliée, chiffre doublé).
  * la VARIATION : le glissement mensuel qu'implique la valeur, comparé
                   aux glissements observés — de préférence sur le même
                   mois calendaire. Attrape les ruptures de dynamique, sans
                   crier au loup sur une hausse saisonnière habituelle.

L'écart est mesuré par un z-score MODIFIÉ (médiane et MAD) et non par un
z-score classique : sur des séries de prix, quelques valeurs extrêmes déjà
présentes dans l'historique gonflent l'écart-type et anesthésient la
détection.
"""

import json

import numpy as np
import pandas as pd

from config.settings import ANOMALY_RULES_PATH
from backend.common.excel_io import lire_feuille_wide

with open(ANOMALY_RULES_PATH, "r", encoding="utf-8") as _flux:
    REGLES = json.load(_flux)

MESSAGES = REGLES["messages"]

# Constante de cohérence du z-score modifié : 0.6745 est le quantile 0,75 de
# la loi normale centrée réduite. Elle aligne l'échelle du MAD sur celle de
# l'écart-type, afin que les seuils se lisent bien « en écarts-types ».
_COHERENCE_MAD = 0.6745

# Score attribué quand l'historique n'a aucune dispersion : assez grand
# pour franchir le palier « marqué », assez fini pour rester affichable.
_Z_DISPERSION_NULLE = 99.0


def seuils_par_defaut() -> dict:
    """Seuils de sévérité, tels que définis dans config/anomaly_rules.json."""
    return {
        "modere": REGLES["z_score_modere"],
        "marque": REGLES["z_score_marque"],
    }


def zscore_modifie(historique: pd.Series, valeur: float) -> float:
    """
    Écart robuste entre `valeur` et l'historique, en écarts-types.

    Renvoie 0.0 quand l'historique est trop court pour conclure : mieux vaut
    ne rien signaler que signaler au hasard.
    """
    serie = pd.Series(historique).dropna().astype(float)
    if serie.size < 3 or valeur is None or pd.isna(valeur):
        return 0.0

    mediane = float(serie.median())
    mad = float((serie - mediane).abs().median())

    if mad > 0:
        return float(_COHERENCE_MAD * (float(valeur) - mediane) / mad)

    # MAD nul : série quasi constante (plus de la moitié des points
    # identiques). Le z-score modifié diviserait par zéro ; on retombe sur
    # l'écart-type classique.
    ecart_type = float(serie.std(ddof=1)) if serie.size > 1 else 0.0
    if ecart_type > 0:
        return float((float(valeur) - float(serie.mean())) / ecart_type)

    # Dispersion strictement nulle : la série ne bouge jamais. Renvoyer 0
    # désarmerait la détection au moment où elle est la plus fondée — toute
    # valeur réellement différente est ici, par construction, inhabituelle.
    # La tolérance relative évite qu'un simple arrondi flottant (une hausse
    # saisonnière reproduite à 1e-14 près) ne déclenche l'alerte maximale.
    ecart = float(valeur) - mediane
    tolerance = max(1e-9, abs(mediane) * 1e-6)
    if abs(ecart) <= tolerance:
        return 0.0
    return float(np.sign(ecart) * _Z_DISPERSION_NULLE)


def fenetre_recente(historique: pd.Series, n_mois: int = None) -> pd.Series:
    """Les `n_mois` derniers points de la série, dans l'ordre chronologique."""
    if n_mois is None:
        n_mois = REGLES["fenetre_glissante_mois"]
    serie = pd.Series(historique).dropna().sort_index()
    return serie.iloc[-int(n_mois) :] if serie.size > n_mois else serie


def historique_meme_mois(historique: pd.Series, mois_cible: int) -> pd.Series:
    """
    Valeurs de l'historique tombant sur le même mois calendaire.

    C'est ce sous-ensemble qui permet de ne pas prendre une flambée
    saisonnière récurrente pour une anomalie.
    """
    serie = pd.Series(historique).dropna().sort_index()
    if serie.empty or not isinstance(serie.index, pd.DatetimeIndex):
        return pd.Series(dtype=float)
    return serie[serie.index.month == int(mois_cible)]


def classer_severite(z_abs: float, seuils: dict = None) -> str:
    """'ok', 'modere' ou 'marque', selon les deux paliers configurés."""
    seuils = seuils or seuils_par_defaut()
    if z_abs is None or pd.isna(z_abs):
        return "ok"
    if abs(z_abs) >= seuils["marque"]:
        return "marque"
    if abs(z_abs) >= seuils["modere"]:
        return "modere"
    return "ok"


def evaluer_niveau(historique: pd.Series, nouvelle_valeur: float, seuils: dict = None, n_fenetre: int = None) -> dict:
    """
    Compare la valeur au NIVEAU attendu, tendance déduite.

    Comparer brutalement la nouvelle valeur à la médiane de la fenêtre ne
    marche pas sur une série de prix : elle monte, donc le dernier point est
    par construction au sommet de la fenêtre, et toute saisie normale serait
    signalée. On ajuste donc une droite sur la fenêtre, on prolonge d'un mois,
    et on mesure l'écart à cette attente — rapporté à la dispersion des écarts
    déjà observés.

    C'est le filet qui attrape les fautes de frappe grossières : un indice de
    1 200 là où la tendance annonçait 120.
    """
    seuils = seuils or seuils_par_defaut()
    recent = fenetre_recente(historique, n_fenetre)

    if recent.size < 6:
        # Trop court pour ajuster une tendance : comparaison brute.
        z = zscore_modifie(recent, nouvelle_valeur)
        return {
            "z": z,
            "severite": classer_severite(z, seuils),
            "base": "niveau",
            "nb_points": int(recent.size),
            "attendu": None,
        }

    y = recent.astype(float).to_numpy()
    x = np.arange(y.size, dtype=float)
    pente, ordonnee = np.polyfit(x, y, 1)

    residus = pd.Series(y - (pente * x + ordonnee))
    attendu = float(pente * y.size + ordonnee)
    ecart = float(nouvelle_valeur) - attendu
    z = zscore_modifie(residus, ecart)

    # Plancher de significativité : un écart minuscule ne déclenche rien,
    # même si la série est si régulière qu'il pèse des dizaines de sigmas.
    plancher = REGLES["ecart_minimal_niveau_pct"] / 100.0 * abs(attendu)
    if abs(ecart) < plancher:
        z = 0.0

    return {
        "z": z,
        "severite": classer_severite(z, seuils),
        "base": "niveau",
        "nb_points": int(recent.size),
        "attendu": round(attendu, 2),
    }


def evaluer_variation(
    historique: pd.Series, nouvelle_valeur: float, date_cible, seuils: dict = None, n_fenetre: int = None
) -> dict:
    """
    Compare le glissement mensuel qu'implique la valeur aux glissements
    déjà observés.

    Quand l'historique compte assez d'années pour le mois visé, la
    comparaison se fait mois calendaire contre mois calendaire : une hausse
    de 8 % en mars n'est une anomalie que si les mois de mars précédents ne
    montaient pas de 8 %.
    """
    seuils = seuils or seuils_par_defaut()
    vide = {"z": 0.0, "severite": "ok", "base": "variation", "variation": None, "desaisonnalise": False, "nb_points": 0}

    serie = pd.Series(historique).dropna().sort_index()
    if serie.size < 2 or nouvelle_valeur is None or pd.isna(nouvelle_valeur):
        return vide

    dernier = float(serie.iloc[-1])
    if dernier == 0:
        return vide
    variation = (float(nouvelle_valeur) - dernier) / dernier * 100.0

    variations = serie.pct_change().dropna() * 100.0
    if variations.empty:
        return vide

    mois_cible = pd.Timestamp(date_cible).month
    memes_mois = historique_meme_mois(variations, mois_cible)
    minimum = REGLES["min_annees_comparaison_saisonniere"]

    if memes_mois.size >= minimum:
        reference, desaisonnalise = memes_mois, True
    else:
        reference, desaisonnalise = fenetre_recente(variations, n_fenetre), False

    z = zscore_modifie(reference, variation)

    # Même plancher, exprimé en points de pourcentage de glissement : on ne
    # signale pas un mouvement que personne ne jugerait notable.
    mediane_reference = float(pd.Series(reference).dropna().median()) if len(reference) else 0.0
    if abs(variation - mediane_reference) < REGLES["ecart_minimal_variation_pp"]:
        z = 0.0

    return {
        "z": z,
        "severite": classer_severite(z, seuils),
        "base": "variation",
        "variation": round(variation, 2),
        "desaisonnalise": desaisonnalise,
        "nb_points": int(reference.size),
    }


def evaluer_valeur(
    historique: pd.Series,
    nouvelle_valeur: float,
    date_cible,
    colonne: str,
    panier: str,
    seuils: dict = None,
    n_fenetre: int = None,
) -> dict:
    """
    Verdict pour une valeur : la sévérité la plus forte des deux angles
    l'emporte, et le message correspondant est formaté.

    `n_fenetre` : nombre de points de la fenêtre récente (par défaut celui
    des séries mensuelles). Pour une série trimestrielle, la comparaison
    « même mois calendaire » vaut comparaison au même trimestre, puisque les
    dates sont des fins de trimestre.
    """
    seuils = seuils or seuils_par_defaut()
    niveau = evaluer_niveau(historique, nouvelle_valeur, seuils, n_fenetre)
    variation = evaluer_variation(historique, nouvelle_valeur, date_cible, seuils, n_fenetre)

    ordre = {"ok": 0, "modere": 1, "marque": 2}
    dominant = niveau if ordre[niveau["severite"]] >= ordre[variation["severite"]] else variation
    severite = dominant["severite"]

    message = None
    if severite in MESSAGES:
        message = MESSAGES[severite].format(colonne=colonne, panier=panier, z=abs(dominant["z"]))

    return {
        "colonne": colonne,
        "z_niveau": round(niveau["z"], 2),
        "z_variation": round(variation["z"], 2),
        "variation_mom": variation.get("variation"),
        "desaisonnalise": variation.get("desaisonnalise", False),
        "severite": severite,
        "message": message,
    }


def evaluer_tableau(nom_fichier: str, panier: str, date_cible, valeurs: dict) -> dict:
    """
    Évalue toutes les valeurs saisies pour un panier.

    Retourne {colonne: verdict}. Les colonnes absentes de la feuille sont
    ignorées silencieusement : c'est data_entry qui contrôle la structure.
    """
    df = lire_feuille_wide(str(nom_fichier), panier)
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    resultats = {}
    for colonne, valeur in valeurs.items():
        if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
            continue
        if colonne not in df.columns:
            continue
        resultats[colonne] = evaluer_valeur(df[colonne], float(valeur), date_cible, colonne, panier)
    return resultats


def anomalies_par_severite(resultats: dict) -> dict:
    """Regroupe les verdicts : {'modere': [...], 'marque': [...]}"""
    groupes = {"modere": [], "marque": []}
    for verdict in resultats.values():
        if verdict["severite"] in groupes:
            groupes[verdict["severite"]].append(verdict)
    return groupes
