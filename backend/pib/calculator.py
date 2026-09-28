"""
Calculs PIB — comptes nationaux trimestriels (normes ONS / SCN 2008).

Architecture parallèle à backend/inflation/calculator.py : zéro dépendance
Streamlit, aucune formule dans les pages. Toutes les fonctions renvoient des
objets pandas indexés par trimestre ; pipeline_pib() rassemble l'ensemble et
l'écrit dans un fichier miroir (data/processed/Fichier_PIB_et_calculs.xlsx),
sans jamais modifier les fichiers sources.

Fréquence trimestrielle : glissement annuel = t/t−4, trimestriel = t/t−1.

Méthode des contributions — détectée, pas supposée (voir
backend.pib.lecture_ons.detecter_nature_volumes) :
  - 'prix_constants' (méthode 1, pratique historique ONS) :
        C_i = (VA_réelle_i,t − VA_réelle_i,t−k) / PIB_réel_t−k × 100
  - 'chainage' (méthode 2, SCN 2008, volumes chaînés non additifs) :
        C_i = (VA_nominale_i,t−k / PIB_nominal_t−k) × g_réel_i × 100
Les fichiers ONS actuels portent des volumes chaînés : méthode 2.
"""

import json
import os

import pandas as pd

from backend.common.statistiques import (
    statistiques_serie,
    moyenne_depuis_debut_annee,
    classer_contributeurs,
)

MODES = {"qoq": 1, "yoy": 4}


def _config_pib() -> dict:
    from config.settings import PIB_CONFIG_PATH

    with open(PIB_CONFIG_PATH, "r", encoding="utf-8") as flux:
        return json.load(flux)


def _secteurs() -> list:
    return [s["cle"] for s in _config_pib()["secteurs_offre"]]


def _decalage(mode: str) -> int:
    if mode not in MODES:
        raise ValueError("mode doit valoir 'qoq' ou 'yoy'")
    return MODES[mode]


def libelles_offre() -> dict:
    """{clé canonique: libellé affiché} pour les secteurs et les impôts nets."""
    config = _config_pib()
    libelles = {s["cle"]: s["libelle"] for s in config["secteurs_offre"]}
    libelles[config["impots_nets_produits"]["cle"]] = config["impots_nets_produits"]["libelle"]
    libelles["Ecart_chainage"] = config["libelles_agregats"]["ecart_chainage"]
    return libelles


def libelles_demande() -> dict:
    """{clé canonique: libellé affiché} pour les postes et contributions de la demande."""
    config = _config_pib()
    libelles = {p["cle"]: p["libelle"] for p in config["postes_demande"]}
    libelles.update({c["cle"]: c["libelle"] for c in config["contributions_demande"]})
    return libelles


# ===========================================================================
# Chargement
# ===========================================================================


def charger_offre(fichier: str = None, journal=None) -> pd.DataFrame:
    """
    Fichier Offre ONS (PIB_TR_S.xlsx par défaut) au schéma canonique
    '<secteur>_nominal' / '<secteur>_reel' + 'PIB_nominal' / 'PIB_reel',
    journal des saisies appliqué — voir backend.pib.lecture_ons.
    """
    from config.settings import FICHIER_PIB_OFFRE
    from backend.pib.lecture_ons import lire_offre_ons

    fichier = fichier or str(FICHIER_PIB_OFFRE)
    if not os.path.exists(fichier):
        raise FileNotFoundError(
            "Fichier Offre PIB introuvable : %s. Déposez le fichier reçu dans "
            "data/raw/pib/ (voir config/pib_config.json pour le format attendu)." % fichier
        )
    return lire_offre_ons(fichier, journal=journal)


def charger_demande(fichier: str = None, journal=None) -> pd.DataFrame:
    """Fichier Demande ONS (PIB_TR_D.xlsx par défaut) au schéma canonique."""
    from config.settings import FICHIER_PIB_DEMANDE
    from backend.pib.lecture_ons import lire_demande_ons

    fichier = fichier or str(FICHIER_PIB_DEMANDE)
    if not os.path.exists(fichier):
        raise FileNotFoundError(
            "Fichier Demande PIB introuvable : %s. Déposez le fichier reçu "
            "dans data/raw/pib/ (voir config/pib_config.json)." % fichier
        )
    return lire_demande_ons(fichier, journal=journal)


# ===========================================================================
# A — Taux de croissance
# ===========================================================================


def calculer_glissement(serie: pd.Series, mode: str = "yoy") -> pd.Series:
    """
    Glissement en % :
      mode='qoq' -> g(t) = (Y_t / Y_t−1 − 1) × 100
      mode='yoy' -> g(t) = (Y_t / Y_t−4 − 1) × 100
    """
    k = _decalage(mode)
    resultat = (serie / serie.shift(k) - 1) * 100
    return resultat.rename((serie.name or "serie") + "_" + mode)


def calculer_taux_croissance(df: pd.DataFrame, mode: str = "yoy") -> pd.DataFrame:
    """Glissement de chaque colonne de `df` (mêmes noms de colonnes)."""
    k = _decalage(mode)
    return (df / df.shift(k) - 1) * 100


# ===========================================================================
# PIB nominal et réel
# ===========================================================================


def calculer_pib_nominal_offre(df_offre: pd.DataFrame) -> pd.Series:
    """PIB_N = somme des VA nominales par secteur + impôts nets sur les produits."""
    cle_impots = _config_pib()["impots_nets_produits"]["cle"]
    colonnes = [f"{s}_nominal" for s in _secteurs()] + [f"{cle_impots}_nominal"]
    manquantes = [c for c in colonnes if c not in df_offre.columns]
    if manquantes:
        raise ValueError("Colonnes manquantes dans le fichier Offre : %s" % manquantes)
    return df_offre[colonnes].sum(axis=1, min_count=len(colonnes)).rename("PIB_nominal_offre")


def calculer_pib_nominal_demande(df_demande: pd.DataFrame) -> pd.Series:
    """PIB_N,dem = C + G + FBCF + ΔS + X − M (signes issus de pib_config.json)."""
    postes = _config_pib()["postes_demande"]

    def _col(cle):
        return f"{cle}_nominal" if f"{cle}_nominal" in df_demande.columns else cle

    manquantes = [p["cle"] for p in postes if _col(p["cle"]) not in df_demande.columns]
    if manquantes:
        raise ValueError("Colonnes manquantes dans le fichier Demande : %s" % manquantes)
    total = sum(df_demande[_col(p["cle"])] * p["signe"] for p in postes)
    return total.rename("PIB_nominal_demande")


def calculer_va_reelle(df_offre: pd.DataFrame) -> pd.DataFrame:
    """
    VA réelle par secteur, plus les impôts nets sur les produits.

    '<secteur>_reel' fourni (cas ONS) : utilisé tel quel. À défaut,
    '<secteur>_nominal' / '<secteur>_deflateur' : VA_réelle = VA_nominale /
    Déflateur × 100.
    """
    cle_impots = _config_pib()["impots_nets_produits"]["cle"]
    resultat = pd.DataFrame(index=df_offre.index)
    for s in _secteurs() + [cle_impots]:
        reel_col = f"{s}_reel"
        if reel_col in df_offre.columns:
            resultat[s] = df_offre[reel_col]
            continue
        nominal_col, defl_col = f"{s}_nominal", f"{s}_deflateur"
        if nominal_col not in df_offre.columns or defl_col not in df_offre.columns:
            raise ValueError(
                "Colonnes manquantes pour le secteur '%s' (attendu : '%s', ou le "
                "couple '%s'/'%s')" % (s, reel_col, nominal_col, defl_col)
            )
        resultat[s] = df_offre[nominal_col] / df_offre[defl_col] * 100
    return resultat


def calculer_pib_reel(df_offre: pd.DataFrame) -> pd.Series:
    """
    PIB réel. Le total publié ('PIB_reel', cas ONS) prime : en volumes
    chaînés, la somme des branches NE reconstitue PAS le PIB réel (écart
    moyen de 6 % sur les fichiers ONS). À défaut (prix constants,
    données de test), somme des VA réelles et des impôts nets réels.
    """
    if "PIB_reel" in df_offre.columns:
        return df_offre["PIB_reel"].rename("PIB_reel")
    return calculer_va_reelle(df_offre).sum(axis=1, min_count=1).rename("PIB_reel")


def calculer_split_hydrocarbures(df_offre: pd.DataFrame) -> pd.DataFrame:
    """
    Niveaux Hydrocarbures / Hors hydrocarbures / Total, nominal et réel.

    PIB_HH_reel = PIB réel − Hydrocarbures réel n'a de sens qu'à prix
    constants : en volumes chaînés, utiliser les TAUX de croissance de
    calculer_croissance_agregats() plutôt que ce niveau.
    """
    secteur_hydro = _config_pib()["secteur_hydrocarbures"]
    pib_nominal = calculer_pib_nominal_offre(df_offre)
    pib_reel = calculer_pib_reel(df_offre)
    h_nominal = df_offre[f"{secteur_hydro}_nominal"]
    h_reel = calculer_va_reelle(df_offre)[secteur_hydro]
    return pd.DataFrame(
        {
            "PIB_nominal_total": pib_nominal,
            "PIB_H_nominal": h_nominal,
            "PIB_HH_nominal": pib_nominal - h_nominal,
            "PIB_reel_total": pib_reel,
            "PIB_H_reel": h_reel,
            "PIB_HH_reel": pib_reel - h_reel,
        }
    )


def calculer_divergence_statistique(pib_offre: pd.Series, pib_demande: pd.Series) -> pd.Series:
    """Divergence_t = PIB_Offre,t − PIB_Demande,t (nominal)."""
    return (pib_offre - pib_demande).rename("Divergence_statistique")


# ===========================================================================
# B — Déflateur implicite
# ===========================================================================


def calculer_deflateur(pib_nominal: pd.Series, pib_reel: pd.Series) -> pd.Series:
    """Déflateur(t) = PIB_nominal(t) / PIB_réel(t) × 100."""
    return (pib_nominal / pib_reel * 100).rename("Deflateur")


def calculer_inflation_implicite(deflateur: pd.Series, mode: str = "yoy") -> pd.Series:
    """Δ Déflateur(t/t−4) = (Déflateur_t / Déflateur_t−4 − 1) × 100 (ou t−1)."""
    return calculer_glissement(deflateur, mode).rename("Inflation_implicite_" + mode)


# ===========================================================================
# Croissance des agrégats Total / Hydrocarbures / Hors hydrocarbures
# ===========================================================================


def _croissance_ponderee(df_offre, cles, mode):
    """
    Croissance réelle d'un agrégat de secteurs en volumes chaînés : moyenne
    des croissances de chaque secteur pondérée par sa VA nominale en t−k
    (même logique que la méthode 2 des contributions).
    """
    k = _decalage(mode)
    poids = pd.concat([df_offre[f"{c}_nominal"].shift(k) for c in cles], axis=1)
    croissances = pd.concat([calculer_glissement(df_offre[f"{c}_reel"], mode) for c in cles], axis=1)
    poids.columns = croissances.columns = cles
    return (poids * croissances).sum(axis=1, min_count=len(cles)) / poids.sum(axis=1, min_count=len(cles))


def calculer_croissance_agregats(df_offre: pd.DataFrame, methode: str, mode: str = "yoy") -> pd.DataFrame:
    """
    Croissance réelle et nominale du PIB total, des hydrocarbures et du hors
    hydrocarbures. Colonnes : PIB_reel, H_reel, HH_reel, PIB_nominal,
    H_nominal, HH_nominal.

    HH réel : à prix constants, glissement de (PIB réel − hydrocarbures) ;
    en volumes chaînés, moyenne pondérée des croissances des autres
    secteurs et des impôts nets (la soustraction n'y a pas de sens).
    """
    config = _config_pib()
    hydro = config["secteur_hydrocarbures"]
    autres = [s for s in _secteurs() if s != hydro] + [config["impots_nets_produits"]["cle"]]
    split = calculer_split_hydrocarbures(df_offre)

    if methode == "chainage":
        hh_reel = _croissance_ponderee(df_offre, autres, mode)
    else:
        hh_reel = calculer_glissement(split["PIB_HH_reel"], mode)

    return pd.DataFrame(
        {
            "PIB_reel": calculer_glissement(split["PIB_reel_total"], mode),
            "H_reel": calculer_glissement(split["PIB_H_reel"], mode),
            "HH_reel": hh_reel,
            "PIB_nominal": calculer_glissement(split["PIB_nominal_total"], mode),
            "H_nominal": calculer_glissement(split["PIB_H_nominal"], mode),
            "HH_nominal": calculer_glissement(split["PIB_HH_nominal"], mode),
        }
    )


# ===========================================================================
# C — Contributions, optique offre
# ===========================================================================


def _contribution(reel, nominal, pib_reel, pib_nominal, methode, k):
    """Contribution d'une composante à la croissance du PIB réel, en points."""
    if methode == "chainage":
        return (nominal.shift(k) / pib_nominal.shift(k)) * (reel / reel.shift(k) - 1) * 100
    return (reel - reel.shift(k)) / pib_reel.shift(k) * 100


def calculer_contributions_offre(df_offre: pd.DataFrame, methode: str = "chainage", mode: str = "yoy") -> pd.DataFrame:
    """
    Contribution de chaque secteur et des impôts nets à la croissance du PIB
    réel, en points de pourcentage (méthode 1 ou 2, voir en-tête du module).
    """
    if methode not in ("prix_constants", "chainage"):
        raise ValueError("methode doit valoir 'prix_constants' ou 'chainage'")
    k = _decalage(mode)
    va_reelle = calculer_va_reelle(df_offre)
    pib_reel = calculer_pib_reel(df_offre)
    pib_nominal = calculer_pib_nominal_offre(df_offre)

    contributions = pd.DataFrame(index=df_offre.index)
    for cle in va_reelle.columns:
        nominal = df_offre[f"{cle}_nominal"] if f"{cle}_nominal" in df_offre.columns else None
        if methode == "chainage" and nominal is None:
            raise ValueError("Méthode 2 : VA nominale manquante pour '%s'" % cle)
        contributions[cle] = _contribution(va_reelle[cle], nominal, pib_reel, pib_nominal, methode, k)
    return contributions


def calculer_contributions_croissance(
    df_offre: pd.DataFrame, methode: str = "prix_constants", mode: str = "yoy"
) -> pd.DataFrame:
    """Nom historique, conservé : contributions sectorielles (méthode 1 par défaut)."""
    return calculer_contributions_offre(df_offre, methode=methode, mode=mode)


def controle_coherence(contributions: pd.DataFrame, croissance: pd.Series, tolerance: float = 0.1) -> pd.DataFrame:
    """
    Somme des contributions vs croissance du PIB réel, trimestre par
    trimestre. Colonnes : Somme_contributions, Croissance_PIB, Ecart (signé,
    somme − croissance), Dans_tolerance (NaN si non calculable : historique
    trop court ou trimestre non publié, ce n'est pas une incohérence).
    """
    somme = contributions.sum(axis=1, min_count=contributions.shape[1])
    ecart = somme - croissance
    dans_tolerance = (ecart.abs() <= tolerance).where(ecart.notna())
    return pd.DataFrame(
        {
            "Somme_contributions": somme,
            "Croissance_PIB": croissance,
            "Ecart": ecart,
            "Dans_tolerance": dans_tolerance,
        }
    )


def verifier_additivite_contributions(
    contributions: pd.DataFrame, pib_reel_total: pd.Series, tolerance: float = 0.1
) -> pd.Series:
    """Booléen par trimestre (NaN si non calculable) — voir controle_coherence()."""
    croissance = calculer_glissement(pib_reel_total, mode="yoy")
    return controle_coherence(contributions, croissance, tolerance)["Dans_tolerance"]


def completer_ecart_chainage(contributions: pd.DataFrame, croissance: pd.Series) -> pd.DataFrame:
    """
    Ajoute la colonne 'Ecart_chainage' = croissance − somme des
    contributions, pour qu'un waterfall reboucle exactement sur la
    croissance publiée. Nulle à prix constants, structurelle en volumes
    chaînés (non-additivité et arrondi des taux ONS à 0,1 pt).
    """
    resultat = contributions.copy()
    resultat["Ecart_chainage"] = croissance - contributions.sum(axis=1, min_count=contributions.shape[1])
    return resultat


def calculer_parts_sectorielles(df_offre: pd.DataFrame) -> pd.DataFrame:
    """Part (%) de chaque secteur et des impôts nets dans le PIB nominal."""
    cle_impots = _config_pib()["impots_nets_produits"]["cle"]
    pib_nominal = calculer_pib_nominal_offre(df_offre)
    return pd.DataFrame({cle: df_offre[f"{cle}_nominal"] / pib_nominal * 100 for cle in _secteurs() + [cle_impots]})


def calculer_croissance_par_branche(df_offre: pd.DataFrame) -> dict:
    """{'qoq': DataFrame, 'yoy': DataFrame} de croissance réelle par branche."""
    va_reelle = calculer_va_reelle(df_offre)
    va_reelle["PIB"] = calculer_pib_reel(df_offre)
    return {mode: calculer_taux_croissance(va_reelle, mode) for mode in MODES}


# ===========================================================================
# D — Contributions, optique demande
# ===========================================================================


def calculer_contributions_demande(
    df_demande: pd.DataFrame, methode: str = "chainage", mode: str = "yoy"
) -> pd.DataFrame:
    """
    Contributions à la croissance du PIB réel, optique demande.

    Composantes positives (C, G, FBCF, X) : même formule que l'offre.
    Importations : signe négatif, Contribution_M = −(ΔM_réel) / PIB_réel_t−k.
    Exportations nettes = contribution X + contribution M.
    Résiduel « variations de stocks et écart statistique » = croissance du
    PIB − (C + G + FBCF + X nettes) : la somme reboucle par construction.
    La variation de stocks en volume n'est pas utilisée (série ONS
    inexploitable, et un taux de croissance n'a pas de sens pour une série
    qui change de signe).

    Colonnes : un par poste de postes_demande hors stocks, puis
    Exportations_nettes, Residuel, Croissance_PIB.
    """
    if methode not in ("prix_constants", "chainage"):
        raise ValueError("methode doit valoir 'prix_constants' ou 'chainage'")
    k = _decalage(mode)
    postes = [p for p in _config_pib()["postes_demande"] if p["cle"] != "Variation_stocks"]
    pib_reel = df_demande["PIB_reel"]
    pib_nominal = df_demande["PIB_nominal"]

    resultat = pd.DataFrame(index=df_demande.index)
    for poste in postes:
        cle = poste["cle"]
        resultat[cle] = poste["signe"] * _contribution(
            df_demande[f"{cle}_reel"], df_demande[f"{cle}_nominal"], pib_reel, pib_nominal, methode, k
        )

    resultat["Exportations_nettes"] = resultat["Exportations"] + resultat["Importations"]
    croissance = calculer_glissement(pib_reel, mode)
    resultat["Residuel"] = croissance - resultat[
        ["Consommation_menages", "Consommation_administrations", "FBCF", "Exportations_nettes"]
    ].sum(axis=1, min_count=4)
    resultat["Croissance_PIB"] = croissance
    return resultat


# ===========================================================================
# E — Ratios
# ===========================================================================


def calculer_ratios_demande(df_demande: pd.DataFrame) -> pd.DataFrame:
    """
    Taux d'investissement = FBCF / PIB × 100 ; taux d'ouverture commerciale
    = (X + M) / PIB × 100. En valeurs nominales : les volumes chaînés ne se
    divisent pas entre eux.
    """
    pib = df_demande["PIB_nominal"]
    return pd.DataFrame(
        {
            "Taux_investissement": df_demande["FBCF_nominal"] / pib * 100,
            "Taux_ouverture": (df_demande["Exportations_nominal"] + df_demande["Importations_nominal"]) / pib * 100,
        }
    )


# ===========================================================================
# F — Statistiques d'appui au rapport
# ===========================================================================


def statistiques_croissance(serie: pd.Series, date_reference) -> dict:
    """Moyenne et écart-type historiques, moyenne depuis T1 de l'année en cours."""
    return {
        "historique": statistiques_serie(serie, date_fin=date_reference),
        "depuis_t1": moyenne_depuis_debut_annee(serie.loc[: pd.Timestamp(date_reference)], date_reference),
    }


def top_contributeurs(
    contributions: pd.DataFrame, date, libelles: dict = None, n: int = 3, exclure=("Croissance_PIB", "Ecart_chainage")
):
    """Plus forts contributeurs positifs et négatifs au trimestre `date`."""
    ligne = contributions.loc[pd.Timestamp(date)]
    libelles = libelles or {}
    valeurs = [(libelles.get(c, c), ligne[c]) for c in contributions.columns if c not in exclure]
    return classer_contributeurs(valeurs, n=n)


def extraire_variation(serie: pd.Series, date_ref, mode: str = "yoy"):
    """
    Glissement de `serie` au trimestre `date_ref` (le plus proche) et son
    évolution face au trimestre précédent — même contrat que
    extraire_inflation_mom/yoy côté Inflation. (valeur, delta), None si non
    calculable.
    """
    return valeur_et_delta(calculer_glissement(serie, mode=mode), date_ref)


def valeur_et_delta(serie: pd.Series, date_ref):
    """Valeur de `serie` au trimestre le plus proche de `date_ref` et écart au
    trimestre précédent. (valeur, delta), chacun None si non calculable."""
    serie = serie.sort_index()
    if serie.empty:
        return None, None
    pos = serie.index.get_indexer([pd.Timestamp(date_ref)], method="nearest")[0]
    valeur = serie.iloc[pos]
    precedent = serie.iloc[pos - 1] if pos > 0 else float("nan")
    valeur = round(float(valeur), 2) if pd.notna(valeur) else None
    delta = round(float(serie.iloc[pos] - precedent), 2) if pd.notna(serie.iloc[pos]) and pd.notna(precedent) else None
    return valeur, delta


# ===========================================================================
# Pipeline et fichier miroir
# ===========================================================================


def pipeline_pib(
    fichier_offre: str = None,
    fichier_demande: str = None,
    journal=None,
    chemin_calculs: str = None,
    ecrire: bool = True,
    source: str = "base",
    conn=None,
) -> dict:
    """
    Calcule tous les indicateurs PIB et, si `ecrire`, les écrit dans le
    fichier miroir. Les sources ne sont jamais modifiées.

    source="base" (défaut, tableau de bord) : lecture de la vue
    cnt_pib_derniere — dernier millésime de chaque observation, le socle
    (classeurs ONS, « millésime 0 ») étant injecté au premier lancement.
    source="classeurs" : lecture directe des classeurs ONS (tests, contrôle).
    """
    from config.settings import FICHIER_PIB_OFFRE, FICHIER_PIB_CALCULS
    from backend.pib.lecture_ons import detecter_nature_volumes

    config = _config_pib()
    tolerance = config["tolerance_coherence_pp"]
    fichier_offre = fichier_offre or str(FICHIER_PIB_OFFRE)

    if source == "base":
        from backend.pib.base_cnt import charger_depuis_base

        offre, demande = charger_depuis_base(conn)
    elif source == "classeurs":
        offre = charger_offre(fichier_offre, journal=journal)
        demande = charger_demande(fichier_demande, journal=journal)
    else:
        raise ValueError("source doit valoir 'base' ou 'classeurs'")
    methode = detecter_nature_volumes(fichier_offre, offre)
    m = methode["methode"]

    # Le réel de la demande est publié plus loin que celui de l'offre
    # (valeurs identiques sur la période commune) : il prolonge le total.
    pib_reel = offre["PIB_reel"].combine_first(demande["PIB_reel"])
    pib_nominal = calculer_pib_nominal_offre(offre).combine_first(demande["PIB_nominal"])
    deflateur = calculer_deflateur(pib_nominal, pib_reel)

    resultats = {
        "offre": offre,
        "demande": demande,
        "methode": methode,
        "tolerance": tolerance,
        "niveaux": pd.DataFrame({"PIB_nominal": pib_nominal, "PIB_reel": pib_reel, "Deflateur": deflateur}),
        "deflateur": pd.DataFrame(
            {
                "Deflateur": deflateur,
                "Inflation_implicite_yoy": calculer_inflation_implicite(deflateur, "yoy"),
                "Inflation_implicite_qoq": calculer_inflation_implicite(deflateur, "qoq"),
            }
        ),
        "croissance": {},
        "contributions_offre": {},
        "coherence_offre": {},
        "contributions_demande": {},
        "croissance_branches": calculer_croissance_par_branche(offre),
        "parts": calculer_parts_sectorielles(offre),
        "ratios": calculer_ratios_demande(demande),
    }

    for mode in MODES:
        croissance = calculer_croissance_agregats(offre, m, mode)
        croissance["PIB_reel"] = calculer_glissement(pib_reel, mode)
        resultats["croissance"][mode] = croissance

        contrib = calculer_contributions_offre(offre, m, mode)
        croissance_offre = calculer_glissement(offre["PIB_reel"], mode)
        resultats["coherence_offre"][mode] = controle_coherence(contrib, croissance_offre, tolerance)
        resultats["contributions_offre"][mode] = completer_ecart_chainage(contrib, croissance_offre)
        resultats["contributions_demande"][mode] = calculer_contributions_demande(demande, m, mode)

    if ecrire:
        ecrire_fichier_calculs(resultats, chemin_calculs or str(FICHIER_PIB_CALCULS))
    return resultats


def ecrire_fichier_calculs(resultats: dict, chemin: str) -> str:
    """Fichier miroir des calculs PIB, une feuille par famille d'indicateurs."""
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    feuilles = {
        "offre_sources": resultats["offre"],
        "demande_sources": resultats["demande"],
        "niveaux_deflateur": resultats["niveaux"].join(resultats["deflateur"].drop(columns="Deflateur")),
        "parts_sectorielles": resultats["parts"],
        "ratios_demande": resultats["ratios"],
    }
    for mode in MODES:
        feuilles["croissance_" + mode] = resultats["croissance"][mode]
        feuilles["branches_" + mode] = resultats["croissance_branches"][mode]
        feuilles["contrib_offre_" + mode] = resultats["contributions_offre"][mode]
        feuilles["coherence_offre_" + mode] = resultats["coherence_offre"][mode]
        feuilles["contrib_demande_" + mode] = resultats["contributions_demande"][mode]

    methode = resultats["methode"]
    with pd.ExcelWriter(chemin, engine="openpyxl") as writer:
        pd.DataFrame(
            [(cle, str(valeur)) for cle, valeur in methode.items()]
            + [("tolerance_coherence_pp", resultats["tolerance"])],
            columns=["parametre", "valeur"],
        ).to_excel(writer, sheet_name="methode", index=False)
        for nom, df in feuilles.items():
            df.rename_axis("date").to_excel(writer, sheet_name=nom)
    return chemin
