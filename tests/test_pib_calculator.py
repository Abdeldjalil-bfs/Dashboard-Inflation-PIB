"""
Tests du module PIB : formules sur données factices, cohérence des
contributions, détection de méthode, journal de saisie, et contrôle sur
les fichiers ONS réels quand ils sont présents.
"""

import os

import numpy as np
import pandas as pd
import pytest

from backend.pib import calculator as C
from backend.pib import lecture_ons as L
from backend.pib import data_entry as D
from backend.common.statistiques import (
    statistiques_serie,
    moyenne_depuis_debut_annee,
    classer_contributeurs,
)

SECTEURS = ["Hydrocarbures", "Agriculture", "Industrie_hors_hydrocarbures", "BTPH", "Services"]
TOUS = SECTEURS + ["Impots_nets_produits"]
DATES = pd.date_range("2023-03-31", periods=8, freq="QE")


def _df_offre():
    """Prix constants : VA réelle = VA nominale / déflateur."""
    base = {
        "Hydrocarbures": 500.0,
        "Agriculture": 200.0,
        "Industrie_hors_hydrocarbures": 300.0,
        "BTPH": 150.0,
        "Services": 600.0,
    }
    data = {}
    for s in SECTEURS:
        data[f"{s}_nominal"] = [base[s] * (1 + 0.01 * i) for i in range(8)]
        data[f"{s}_deflateur"] = [100.0 * (1 + 0.005 * i) for i in range(8)]
    data["Impots_nets_produits_nominal"] = [100.0 + 2 * i for i in range(8)]
    data["Impots_nets_produits_deflateur"] = [100.0] * 8
    return pd.DataFrame(data, index=DATES)


def _df_offre_chainee():
    """
    Volumes chaînés synthétiques : chaque secteur a sa croissance réelle et
    son prix ; le PIB réel publié est construit par la méthode 2 (moyenne
    des croissances pondérée par les parts nominales en t−4).
    """
    rng = np.random.default_rng(0)
    n = 12
    dates = pd.date_range("2020-03-31", periods=n, freq="QE")
    data = {}
    for s in TOUS:
        volume = 100 * np.cumprod(1 + rng.normal(0.01, 0.02, n))
        prix = 100 * np.cumprod(1 + rng.normal(0.02, 0.01, n))
        data[f"{s}_reel"] = volume
        data[f"{s}_nominal"] = volume * prix / 100
    df = pd.DataFrame(data, index=dates)
    nominal = df[[f"{s}_nominal" for s in TOUS]].sum(axis=1)
    croissance = sum(
        df[f"{s}_nominal"].shift(4) / nominal.shift(4) * (df[f"{s}_reel"] / df[f"{s}_reel"].shift(4) - 1) for s in TOUS
    )
    pib_reel = [nominal.iloc[i] for i in range(4)]
    for i in range(4, n):
        pib_reel.append(pib_reel[i - 4] * (1 + croissance.iloc[i]))
    df["PIB_reel"] = pib_reel
    df["PIB_nominal"] = nominal
    return df


def _df_demande():
    rng = np.random.default_rng(1)
    n = 10
    dates = pd.date_range("2020-03-31", periods=n, freq="QE")
    data = {}
    for cle, base in [
        ("Consommation_menages", 500),
        ("Consommation_administrations", 200),
        ("FBCF", 300),
        ("Variation_stocks", 20),
        ("Exportations", 250),
        ("Importations", 270),
    ]:
        reel = base * np.cumprod(1 + rng.normal(0.01, 0.03, n))
        data[f"{cle}_reel"] = reel
        data[f"{cle}_nominal"] = reel * 1.05
    df = pd.DataFrame(data, index=dates)
    for suffixe in ("reel", "nominal"):
        df[f"PIB_{suffixe}"] = (
            df[f"Consommation_menages_{suffixe}"]
            + df[f"Consommation_administrations_{suffixe}"]
            + df[f"FBCF_{suffixe}"]
            + df[f"Variation_stocks_{suffixe}"]
            + df[f"Exportations_{suffixe}"]
            - df[f"Importations_{suffixe}"]
        )
    return df


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------


def test_charger_offre_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        C.charger_offre(str(tmp_path / "inexistant.xlsx"))


def test_charger_demande_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        C.charger_demande(str(tmp_path / "inexistant.xlsx"))


# ---------------------------------------------------------------------------
# A — Croissance
# ---------------------------------------------------------------------------


def test_glissement_qoq_et_yoy():
    serie = pd.Series([100.0, 102.0, 104.0, 106.0, 110.0], index=DATES[:5])
    qoq = C.calculer_glissement(serie, mode="qoq")
    yoy = C.calculer_glissement(serie, mode="yoy")
    assert qoq.iloc[1] == pytest.approx(2.0)
    assert pd.isna(yoy.iloc[3])
    assert yoy.iloc[4] == pytest.approx(10.0)


def test_glissement_mode_invalide():
    with pytest.raises(ValueError):
        C.calculer_glissement(pd.Series([1.0, 2.0]), mode="mensuel")


def test_taux_croissance_dataframe():
    df = pd.DataFrame({"a": [100.0, 110.0], "b": [50.0, 45.0]}, index=DATES[:2])
    g = C.calculer_taux_croissance(df, "qoq")
    assert g["a"].iloc[1] == pytest.approx(10.0)
    assert g["b"].iloc[1] == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# PIB nominal / réel
# ---------------------------------------------------------------------------


def test_pib_nominal_offre():
    pib = C.calculer_pib_nominal_offre(_df_offre())
    assert pib.iloc[0] == pytest.approx(500 + 200 + 300 + 150 + 600 + 100)


def test_pib_nominal_offre_colonne_manquante():
    with pytest.raises(ValueError):
        C.calculer_pib_nominal_offre(_df_offre().drop(columns=["Services_nominal"]))


def test_pib_nominal_demande_applique_les_signes():
    df = _df_demande()
    pib = C.calculer_pib_nominal_demande(df)
    assert (pib - df["PIB_nominal"]).abs().max() < 1e-9


def test_va_reelle_deflation():
    va = C.calculer_va_reelle(_df_offre())
    assert va["Hydrocarbures"].iloc[0] == pytest.approx(500.0)
    assert va["Hydrocarbures"].iloc[1] == pytest.approx(505.0 / 100.5 * 100)


def test_pib_reel_prefere_le_total_publie():
    df = _df_offre_chainee()
    assert (C.calculer_pib_reel(df) - df["PIB_reel"]).abs().max() == 0


def test_pib_reel_somme_a_prix_constants():
    df = _df_offre()
    assert (C.calculer_pib_reel(df) - C.calculer_va_reelle(df).sum(axis=1)).abs().max() < 1e-9


def test_split_hydrocarbures_additivite_nominale():
    split = C.calculer_split_hydrocarbures(_df_offre())
    assert (split["PIB_HH_nominal"] + split["PIB_H_nominal"] - split["PIB_nominal_total"]).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# B — Déflateur
# ---------------------------------------------------------------------------


def test_deflateur_et_inflation_implicite():
    nominal = pd.Series([100.0, 110.0, 120.0, 130.0, 132.0], index=DATES[:5])
    reel = pd.Series([100.0, 100.0, 100.0, 100.0, 110.0], index=DATES[:5])
    defl = C.calculer_deflateur(nominal, reel)
    assert defl.iloc[1] == pytest.approx(110.0)
    infl = C.calculer_inflation_implicite(defl, "yoy")
    assert infl.iloc[4] == pytest.approx((120.0 / 100.0 - 1) * 100)


# ---------------------------------------------------------------------------
# C — Contributions offre
# ---------------------------------------------------------------------------


def test_methode1_exacte_a_prix_constants():
    df = _df_offre()
    contrib = C.calculer_contributions_offre(df, methode="prix_constants")
    croissance = C.calculer_glissement(C.calculer_pib_reel(df), "yoy")
    ecart = (contrib.sum(axis=1) - croissance).iloc[4:]
    assert ecart.abs().max() < 1e-9


def test_methode1_formule():
    df = _df_offre()
    contrib = C.calculer_contributions_offre(df, methode="prix_constants")
    va = C.calculer_va_reelle(df)
    pib = va.sum(axis=1)
    attendu = (va["BTPH"].iloc[5] - va["BTPH"].iloc[1]) / pib.iloc[1] * 100
    assert contrib["BTPH"].iloc[5] == pytest.approx(attendu)


def test_methode2_reboucle_sur_volumes_chaines():
    df = _df_offre_chainee()
    contrib = C.calculer_contributions_offre(df, methode="chainage")
    croissance = C.calculer_glissement(df["PIB_reel"], "yoy")
    coherence = C.controle_coherence(contrib, croissance, tolerance=0.1)
    assert coherence["Dans_tolerance"].dropna().all()
    assert coherence["Dans_tolerance"].iloc[:4].isna().all()


def test_methode1_sur_volumes_chaines_sort_de_la_tolerance():
    """Démontre pourquoi la détection compte : méthode 1 sur données chaînées."""
    df = _df_offre_chainee()
    contrib = C.calculer_contributions_offre(df, methode="prix_constants")
    croissance = C.calculer_glissement(df["PIB_reel"], "yoy")
    assert not C.controle_coherence(contrib, croissance)["Dans_tolerance"].dropna().all()


def test_ecart_chainage_fait_reboucler():
    df = _df_offre()
    contrib = C.calculer_contributions_offre(df, methode="prix_constants")
    croissance = C.calculer_glissement(C.calculer_pib_reel(df), "yoy") + 0.3
    complet = C.completer_ecart_chainage(contrib, croissance)
    assert (complet.sum(axis=1) - croissance).iloc[4:].abs().max() < 1e-9
    assert complet["Ecart_chainage"].iloc[4] == pytest.approx(0.3)


def test_verifier_additivite_historique():
    df = _df_offre()
    coherent = C.verifier_additivite_contributions(C.calculer_contributions_croissance(df), C.calculer_pib_reel(df))
    assert coherent.iloc[4:].all()


def test_croissance_hh_chainage_ponderee():
    df = _df_offre_chainee()
    g = C.calculer_croissance_agregats(df, "chainage", "yoy")
    autres = [s for s in TOUS if s != "Hydrocarbures"]
    w = {s: df[f"{s}_nominal"].iloc[4] for s in autres}
    attendu = sum(
        df[f"{s}_nominal"].iloc[4] * (df[f"{s}_reel"].iloc[8] / df[f"{s}_reel"].iloc[4] - 1) * 100 for s in autres
    ) / sum(w.values())
    assert g["HH_reel"].iloc[8] == pytest.approx(attendu)


def test_parts_sectorielles_somment_a_100():
    parts = C.calculer_parts_sectorielles(_df_offre())
    assert (parts.sum(axis=1) - 100).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# D / E — Demande
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("methode", ["prix_constants", "chainage"])
@pytest.mark.parametrize("mode", ["yoy", "qoq"])
def test_demande_reboucle_avec_residuel(methode, mode):
    contrib = C.calculer_contributions_demande(_df_demande(), methode, mode)
    somme = contrib[
        ["Consommation_menages", "Consommation_administrations", "FBCF", "Exportations_nettes", "Residuel"]
    ].sum(axis=1, min_count=5)
    assert (somme - contrib["Croissance_PIB"]).dropna().abs().max() < 1e-9


def test_demande_importations_signe_negatif():
    df = _df_demande()
    contrib = C.calculer_contributions_demande(df, "prix_constants", "yoy")
    attendu = -(df["Importations_reel"].iloc[6] - df["Importations_reel"].iloc[2]) / df["PIB_reel"].iloc[2] * 100
    assert contrib["Importations"].iloc[6] == pytest.approx(attendu)
    assert contrib["Exportations_nettes"].iloc[6] == pytest.approx(
        contrib["Exportations"].iloc[6] + contrib["Importations"].iloc[6]
    )


def test_demande_residuel_nul_a_prix_constants_sans_stocks():
    df = _df_demande()
    df["Variation_stocks_reel"] = 0.0
    df["Variation_stocks_nominal"] = 0.0
    for s in ("reel", "nominal"):
        df[f"PIB_{s}"] = (
            df[f"Consommation_menages_{s}"]
            + df[f"Consommation_administrations_{s}"]
            + df[f"FBCF_{s}"]
            + df[f"Exportations_{s}"]
            - df[f"Importations_{s}"]
        )
    contrib = C.calculer_contributions_demande(df, "prix_constants", "yoy")
    assert contrib["Residuel"].dropna().abs().max() < 1e-9


def test_ratios_demande():
    df = _df_demande()
    ratios = C.calculer_ratios_demande(df)
    assert ratios["Taux_investissement"].iloc[0] == pytest.approx(
        df["FBCF_nominal"].iloc[0] / df["PIB_nominal"].iloc[0] * 100
    )
    assert ratios["Taux_ouverture"].iloc[0] == pytest.approx(
        (df["Exportations_nominal"].iloc[0] + df["Importations_nominal"].iloc[0]) / df["PIB_nominal"].iloc[0] * 100
    )


# ---------------------------------------------------------------------------
# F — Statistiques
# ---------------------------------------------------------------------------


def test_statistiques_et_moyenne_depuis_t1():
    serie = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=pd.date_range("2023-03-31", periods=6, freq="QE"))
    stats = statistiques_serie(serie)
    assert stats["moyenne"] == pytest.approx(3.5)
    ytd = moyenne_depuis_debut_annee(serie, "2024-06-30")
    assert ytd["actuelle"] == pytest.approx(5.5)
    assert ytd["precedente"] == pytest.approx(1.5)
    assert ytd["nb_periodes"] == 2


def test_classer_contributeurs():
    positifs, negatifs = classer_contributeurs({"a": 1.0, "b": 3.0, "c": -2.0, "d": float("nan")}, n=2)
    assert [p["nom"] for p in positifs] == ["b", "a"]
    assert negatifs[0]["nom"] == "c"
    assert positifs[0]["part"] == pytest.approx(50.0)


def test_extraire_variation():
    serie = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 105.0, 107.0], index=pd.date_range("2023-03-31", periods=6, freq="QE")
    )
    valeur, delta = C.extraire_variation(serie, serie.index[-1], "yoy")
    assert valeur == pytest.approx(round((107 / 101 - 1) * 100, 2))
    assert delta == pytest.approx(round((107 / 101 - 1) * 100 - 5.0, 2), abs=0.011)


# ---------------------------------------------------------------------------
# Journal de saisie (les classeurs ONS ne sont jamais réécrits)
# ---------------------------------------------------------------------------


def test_journal_applique_insertion_modification_suppression(tmp_path):
    journal = tmp_path / "journal.xlsx"
    df = pd.DataFrame({"Construction": [1.0, 2.0]}, index=DATES[:2])
    D.enregistrer_saisie("offre", "PIB_N", "Construction", DATES[1], "modification", 5.0, journal=journal)
    D.enregistrer_saisie("offre", "PIB_N", "Construction", DATES[2], "insertion", 7.0, journal=journal)
    D.enregistrer_saisie("offre", "PIB_N", "Construction", DATES[0], "suppression", journal=journal)
    D.enregistrer_saisie("demande", "PIB_N", "FBCF", DATES[0], "insertion", 9.0, journal=journal)
    corrige = L.appliquer_journal(df, "offre", "PIB_N", journal)
    assert pd.isna(corrige.loc[DATES[0], "Construction"])
    assert corrige.loc[DATES[1], "Construction"] == 5.0
    assert corrige.loc[DATES[2], "Construction"] == 7.0
    assert len(D.historique_saisies(journal)) == 4


def test_journal_refuse_colonne_inconnue(tmp_path):
    with pytest.raises(ValueError):
        D.enregistrer_saisie(
            "offre", "PIB_N", "Colonne fantôme", DATES[0], "insertion", 1.0, journal=tmp_path / "j.xlsx"
        )
    with pytest.raises(ValueError):
        D.enregistrer_saisie("offre", "PIB_N", "Construction", DATES[0], "insertion", None, journal=tmp_path / "j.xlsx")


def test_anomalie_trimestrielle_detecte_une_faute_de_frappe():
    dates = pd.date_range("2015-03-31", periods=40, freq="QE")
    valeurs = [100 * (1.01**i) * (1.05 if d.month == 12 else 1.0) for i, d in enumerate(dates)]
    df = pd.DataFrame({"Construction": valeurs}, index=dates)
    cible = dates[-1] + pd.DateOffset(months=3)
    normal = D.evaluer_saisie(df, "Construction", cible, 100 * 1.01**40, "Offre")
    faute = D.evaluer_saisie(df, "Construction", cible, valeurs[-1] * 10, "Offre")
    assert normal["severite"] == "ok"
    assert faute["severite"] == "marque"


# ---------------------------------------------------------------------------
# Données ONS réelles (sautés si absentes)
# ---------------------------------------------------------------------------


def _fichiers_reels():
    from config.settings import FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE

    return os.path.exists(FICHIER_PIB_OFFRE) and os.path.exists(FICHIER_PIB_DEMANDE)


@pytest.mark.skipif(not _fichiers_reels(), reason="fichiers ONS absents")
def test_donnees_reelles_pipeline(tmp_path):
    r = C.pipeline_pib(journal=tmp_path / "vide.xlsx", chemin_calculs=str(tmp_path / "calc.xlsx"), source="classeurs")
    assert r["methode"]["methode"] == "chainage"
    assert os.path.exists(tmp_path / "calc.xlsx")
    # Nominal : la somme des secteurs égale le PIB publié.
    offre = r["offre"]
    assert (C.calculer_pib_nominal_offre(offre) - offre["PIB_nominal"]).abs().max() < 1.0
    # Demande : reboucle exactement grâce au résiduel.
    d = r["contributions_demande"]["yoy"]
    somme = d[["Consommation_menages", "Consommation_administrations", "FBCF", "Exportations_nettes", "Residuel"]].sum(
        axis=1
    )
    assert (somme - d["Croissance_PIB"]).dropna().abs().max() < 1e-9
    # Offre : la méthode 2 reste proche de la croissance publiée (arrondi ONS).
    ecart = r["coherence_offre"]["yoy"]["Ecart"].dropna().abs()
    assert ecart.mean() < 0.5
    # Waterfall : avec l'écart de chaînage, le total reboucle exactement.
    w = r["contributions_offre"]["yoy"].dropna()
    croissance = C.calculer_glissement(offre["PIB_reel"], "yoy").loc[w.index]
    assert (w.sum(axis=1) - croissance).abs().max() < 1e-9


@pytest.mark.skipif(not _fichiers_reels(), reason="fichiers ONS absents")
def test_sources_non_modifiees(tmp_path):
    from config.settings import FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE

    avant = [os.path.getmtime(f) for f in (FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE)]
    C.pipeline_pib(journal=tmp_path / "vide.xlsx", chemin_calculs=str(tmp_path / "calc.xlsx"), source="classeurs")
    assert [os.path.getmtime(f) for f in (FICHIER_PIB_OFFRE, FICHIER_PIB_DEMANDE)] == avant


@pytest.mark.skipif(not _fichiers_reels(), reason="fichiers ONS absents")
def test_base_millesime0_reproduit_les_classeurs(tmp_path):
    """Les pages lisent cnt_pib_derniere : avec le seul socle en base, tous les
    résultats doivent être identiques à ceux calculés sur les classeurs."""
    from backend.pib import ons_cnt

    conn = ons_cnt.ouvrir_base(tmp_path / "t.db")
    base = C.pipeline_pib(source="base", conn=conn, ecrire=False)
    classeurs = C.pipeline_pib(source="classeurs", ecrire=False)
    for cle in ("croissance", "contributions_offre", "contributions_demande"):
        for mode in ("yoy", "qoq"):
            a, b = base[cle][mode], classeurs[cle][mode]
            commun = a.index.intersection(b.index)
            assert (a.loc[commun] - b.loc[commun]).abs().max().max() < 1e-8, (cle, mode)
    assert (base["ratios"] - classeurs["ratios"]).abs().max().max() < 1e-10


@pytest.mark.skipif(not _fichiers_reels(), reason="fichiers ONS absents")
def test_rapport_cnt_prend_la_main_sur_le_socle(tmp_path):
    """Un rapport CNT ingéré remplace le socle sur les trimestres qu'il couvre."""
    import pandas as pd
    from backend.pib import ons_cnt, base_cnt

    conn = ons_cnt.ouvrir_base(tmp_path / "t.db")
    base_cnt.assurer_socle(conn)
    tidy = pd.DataFrame(
        [
            {
                "rapport": "2025T2",
                "bloc": "Croissance",
                "poste": base_cnt.POSTE_PIB,
                "annee": 2025,
                "trimestre": "T2",
                "periode": "2025-T2",
                "periodicite": "Trimestriel",
                "valeur": 9.9,
                "unite": "%",
            }
        ]
    )
    ons_cnt.injecter_en_base(conn, tidy)
    r = C.pipeline_pib(source="base", conn=conn, ecrire=False)
    assert r["croissance"]["yoy"]["PIB_reel"].loc["2025-06-01"] == pytest.approx(9.9)
