"""
Tests de la détection d'anomalies à la saisie.

Cas synthétiques uniquement : aucune lecture du classeur réel, pour que le
comportement soit vérifiable indépendamment des données de production.
"""

import numpy as np
import pandas as pd
import pytest

from backend.inflation import anomaly_detection as ad


def _mois(debut, nb):
    """Index mensuel de `nb` points à partir de `debut`."""
    return pd.date_range(debut, periods=nb, freq="MS")


def serie_stable(nb=48, depart=100.0, pas=0.4):
    """Série qui progresse régulièrement, sans saisonnalité."""
    index = _mois("2020-01-01", nb)
    valeurs = [depart + pas * rang for rang in range(nb)]
    return pd.Series(valeurs, index=index)


def serie_saisonniere(nb_annees=6, mois_choc=4, ampleur=8.0):
    """
    Série avec une flambée reproduite chaque année sur le même mois.

    Motif typique du mois de Ramadan : une hausse forte mais attendue, qui
    ne doit pas être prise pour une anomalie.
    """
    index = _mois("2018-01-01", nb_annees * 12)
    valeurs, courant = [], 100.0
    for date in index:
        courant *= (1 + ampleur / 100.0) if date.month == mois_choc else 1.003
        valeurs.append(courant)
    return pd.Series(valeurs, index=index)


# ---------------------------------------------------------------------------
# z-score modifié
# ---------------------------------------------------------------------------


def test_zscore_nul_au_centre_de_la_distribution():
    serie = pd.Series([10, 11, 12, 13, 14], index=_mois("2023-01-01", 5))
    assert ad.zscore_modifie(serie, 12) == pytest.approx(0.0, abs=1e-9)


def test_zscore_croit_avec_l_ecart():
    serie = pd.Series([10, 11, 12, 13, 14], index=_mois("2023-01-01", 5))
    assert abs(ad.zscore_modifie(serie, 20)) > abs(ad.zscore_modifie(serie, 15))


def test_zscore_sans_division_par_zero_sur_serie_constante():
    """MAD nul : la fonction doit retomber sur l'écart-type, pas exploser."""
    serie = pd.Series([50.0] * 10, index=_mois("2023-01-01", 10))
    valeur = ad.zscore_modifie(serie, 500.0)
    assert np.isfinite(valeur)


def test_zscore_prudent_sur_historique_trop_court():
    serie = pd.Series([10.0, 11.0], index=_mois("2023-01-01", 2))
    assert ad.zscore_modifie(serie, 900.0) == 0.0


# ---------------------------------------------------------------------------
# Niveau : les fautes de frappe
# ---------------------------------------------------------------------------


def test_valeur_coherente_est_acceptee():
    serie = serie_stable()
    attendue = float(serie.iloc[-1]) + 0.4
    verdict = ad.evaluer_valeur(serie, attendue, pd.Timestamp("2024-01-01"), "Pain_Cereales", "Grand_Alger")
    assert verdict["severite"] == "ok"
    assert verdict["message"] is None


def test_facteur_dix_declenche_une_alerte_marquee():
    """Virgule oubliée : 1 200 au lieu de 120."""
    serie = serie_stable()
    fautive = float(serie.iloc[-1]) * 10
    verdict = ad.evaluer_valeur(serie, fautive, pd.Timestamp("2024-01-01"), "Pain_Cereales", "Grand_Alger")
    assert verdict["severite"] == "marque"
    assert "Pain_Cereales" in verdict["message"]
    assert "Grand_Alger" in verdict["message"]


def test_evaluer_niveau_isole_le_z_du_niveau():
    serie = serie_stable()
    resultat = ad.evaluer_niveau(serie, float(serie.iloc[-1]) * 10)
    assert resultat["base"] == "niveau"
    assert abs(resultat["z"]) > ad.seuils_par_defaut()["marque"]


# ---------------------------------------------------------------------------
# Variation : la saisonnalité
# ---------------------------------------------------------------------------


def test_hausse_saisonniere_connue_n_est_pas_une_anomalie():
    """
    Une flambée de 8 % reproduite fidèlement chaque année sur le même mois
    ne doit pas être signalée : la comparaison se fait mois contre mois.
    """
    serie = serie_saisonniere(nb_annees=6, mois_choc=4, ampleur=8.0)
    # On coupe juste avant un mois d'avril et on propose la hausse habituelle
    historique = serie[serie.index < "2023-04-01"]
    attendue = float(historique.iloc[-1]) * 1.08

    resultat = ad.evaluer_variation(historique, attendue, pd.Timestamp("2023-04-01"))
    assert resultat["desaisonnalise"], "la comparaison doit être mois contre mois"
    assert resultat["severite"] == "ok"


def test_meme_hausse_hors_du_mois_habituel_est_signalee():
    """La même hausse de 8 %, mais un mois où elle n'a jamais lieu."""
    serie = serie_saisonniere(nb_annees=6, mois_choc=4, ampleur=8.0)
    historique = serie[serie.index < "2023-09-01"]
    valeur = float(historique.iloc[-1]) * 1.08

    resultat = ad.evaluer_variation(historique, valeur, pd.Timestamp("2023-09-01"))
    assert resultat["severite"] in ("modere", "marque")


def test_bascule_sur_historique_complet_si_trop_peu_d_annees():
    """Moins de 4 occurrences du mois : pas de comparaison saisonnière."""
    serie = serie_saisonniere(nb_annees=2, mois_choc=4, ampleur=8.0)
    historique = serie[serie.index < "2019-04-01"]
    resultat = ad.evaluer_variation(historique, float(historique.iloc[-1]) * 1.02, pd.Timestamp("2019-04-01"))
    assert resultat["desaisonnalise"] is False


def test_historique_meme_mois_filtre_bien():
    serie = serie_stable(nb=48)
    avrils = ad.historique_meme_mois(serie, 4)
    assert not avrils.empty
    assert set(avrils.index.month) == {4}


# ---------------------------------------------------------------------------
# Sévérité et agrégation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "z, attendu",
    [
        (0.0, "ok"),
        (2.0, "ok"),
        (2.5, "modere"),
        (3.9, "modere"),
        (4.0, "marque"),
        (9.0, "marque"),
        (-4.5, "marque"),
    ],
)
def test_classer_severite(z, attendu):
    assert ad.classer_severite(z) == attendu


def test_la_severite_la_plus_forte_l_emporte():
    """Niveau anormal mais variation banale : l'alerte doit sortir."""
    serie = serie_stable()
    verdict = ad.evaluer_valeur(serie, float(serie.iloc[-1]) * 10, pd.Timestamp("2024-01-01"), "X", "Grand_Alger")
    assert verdict["severite"] == "marque"
    assert abs(verdict["z_niveau"]) >= abs(verdict["z_variation"]) or verdict["severite"] == "marque"


def test_fenetre_recente_limite_le_nombre_de_points():
    serie = serie_stable(nb=60)
    assert ad.fenetre_recente(serie, 36).size == 36
    assert ad.fenetre_recente(serie, 200).size == 60


def test_anomalies_par_severite_regroupe():
    resultats = {
        "a": {"severite": "ok", "message": None},
        "b": {"severite": "modere", "message": "m"},
        "c": {"severite": "marque", "message": "M"},
    }
    groupes = ad.anomalies_par_severite(resultats)
    assert len(groupes["modere"]) == 1 and len(groupes["marque"]) == 1


def test_les_messages_viennent_du_fichier_de_regles():
    assert set(ad.MESSAGES) >= {"modere", "marque"}
    assert "{colonne}" in ad.MESSAGES["modere"]


# ---------------------------------------------------------------------------
# Planchers de significativité pratique
# ---------------------------------------------------------------------------


def serie_tres_reguliere(nb=48, valeur=180.0, pas=0.01):
    """Série presque immobile — typiquement un indice de loyers."""
    index = _mois("2020-01-01", nb)
    return pd.Series([valeur + pas * r for r in range(nb)], index=index)


def test_petit_ecart_non_signale_sur_serie_tres_reguliere():
    """
    Sur une série quasi immobile, un mouvement de 0,4 % pèse des dizaines
    d'écarts-types robustes. Sans plancher, la saisie crierait au loup à
    chaque mois normal.
    """
    serie = serie_tres_reguliere()
    valeur = float(serie.iloc[-1]) * 1.004
    verdict = ad.evaluer_valeur(serie, valeur, pd.Timestamp("2024-01-01"), "Logements_Charges", "Grand_Alger")
    assert verdict["severite"] == "ok"


def test_gros_ecart_toujours_signale_sur_serie_tres_reguliere():
    """Le plancher ne doit pas anesthésier la détection des vraies erreurs."""
    serie = serie_tres_reguliere()
    verdict = ad.evaluer_valeur(
        serie, float(serie.iloc[-1]) * 10, pd.Timestamp("2024-01-01"), "Logements_Charges", "Grand_Alger"
    )
    assert verdict["severite"] == "marque"


def test_niveau_tient_compte_de_la_tendance():
    """
    Une série qui monte régulièrement place son dernier point au sommet de
    la fenêtre : sans détendance, toute saisie normale serait signalée.
    """
    serie = serie_stable(nb=48, pas=0.8)
    attendue = float(serie.iloc[-1]) + 0.8
    assert ad.evaluer_niveau(serie, attendue)["severite"] == "ok"


def test_les_planchers_sont_configures():
    assert "ecart_minimal_variation_pp" in ad.REGLES
    assert "ecart_minimal_niveau_pct" in ad.REGLES
