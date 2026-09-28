"""
Tests du module de rapport.

Le moteur de rédaction est testé en isolation complète (aucune lecture de
fichier Excel) ; les fonctions de calcul et l'assemblage sont testés contre le
fichier de travail réel, et sautés s'il est absent.
"""

import os

import pytest

from config.settings import FICHIER_DONNEES_CALCULS
from backend.inflation import reporting as R
from backend.inflation import calculator as calc

DONNEES_PRESENTES = os.path.exists(str(FICHIER_DONNEES_CALCULS))
besoin_donnees = pytest.mark.skipif(not DONNEES_PRESENTES, reason="fichier de calculs absent")


# ---------------------------------------------------------------------------
# Moteur de rédaction — déterministe, sans données
# ---------------------------------------------------------------------------

SEUILS = {"seuil_modere": 0.2, "seuil_marque": 0.6}


@pytest.mark.parametrize(
    "delta, attendu",
    [
        (1.5, "acceleration_marquee"),
        (0.6, "acceleration_marquee"),
        (0.3, "acceleration_moderee"),
        (0.2, "acceleration_moderee"),
        (0.05, "stable"),
        (0.0, "stable"),
        (-0.1, "stable"),
        (-0.3, "deceleration_moderee"),
        (-0.9, "deceleration_marquee"),
    ],
)
def test_qualificatif_variation(delta, attendu):
    assert R.qualificatif_variation(delta, SEUILS) == R.QUALIFICATIFS[attendu]


def test_qualificatif_variation_sans_valeur():
    assert R.qualificatif_variation(None, SEUILS) == R.QUALIFICATIFS["stable"]


def test_texte_ipc_global_contient_les_chiffres():
    texte = R.texte_ipc_global(5.20, 4.80, 3.50, "yoy", mois_libelle="mars 2025")
    assert "mars 2025" in texte
    assert "5.20" in texte
    assert "4.80" in texte
    assert "glissement annuel" in texte
    # 5,20 % dépasse le seuil d'alerte de 4 % : la phrase doit être présente
    assert "seuil" in texte


def test_texte_ipc_global_moyenne_ytd():
    texte = R.texte_ipc_global(
        3.0, 2.9, 3.0, "yoy", mois_libelle="mars 2025", moyenne_ytd=2.75, nb_mois_ytd=3, annee=2025
    )
    assert "2.75" in texte and "2025" in texte


@pytest.mark.parametrize(
    "core, core_prec, nc, nc_prec, fragment",
    [
        # core ↑ et non-core ↑ -> tension généralisée
        (4.0, 3.5, 9.0, 7.0, "généralisée"),
        # core stable et non-core ↑ -> choc sur la composante volatile
        (4.0, 3.98, 9.0, 7.0, "choc d'offre"),
        # core ↑ et non-core ↓ -> diffusion au sous-jacent
        (4.0, 3.5, 5.0, 7.0, "diffusion"),
        # core ↓ -> décélération
        (3.0, 3.9, 5.0, 7.0, "repli"),
    ],
)
def test_texte_core_noncore_matrice(core, core_prec, nc, nc_prec, fragment):
    """Les quatre cas de la matrice éditoriale sont bien discriminés."""
    texte = R.texte_core_noncore(core, core_prec, nc, nc_prec)
    assert fragment in texte


def test_texte_core_noncore_signale_ecart_important():
    texte = R.texte_core_noncore(2.0, 2.0, 12.0, 11.0)
    assert "écart" in texte.lower()


def test_texte_contributions_positifs_et_negatifs():
    positifs = [
        {"nom": "Alimentation", "contribution": 1.2, "part": 60.0},
        {"nom": "Transports", "contribution": 0.4, "part": 20.0},
    ]
    negatifs = [{"nom": "Habillement", "contribution": -0.3, "part": 15.0}]
    texte = R.texte_contributions(positifs, negatifs, 1.3, "yoy")
    assert "Alimentation" in texte and "Transports" in texte
    assert "Habillement" in texte
    assert " et " in texte  # énumération correcte
    assert "freine" in texte


def test_texte_contributions_sans_negatif():
    positifs = [{"nom": "Alimentation", "contribution": 1.2, "part": 100.0}]
    texte = R.texte_contributions(positifs, [], 1.2, "mom")
    assert "Aucun poste" in texte


def test_texte_par_groupe_signale_un_choc_hors_du_trio_de_tete():
    contributions = [
        {"nom": "A", "contribution": 1.0, "part": 50.0},
        {"nom": "B", "contribution": 0.5, "part": 25.0},
        {"nom": "C", "contribution": 0.3, "part": 15.0},
        {"nom": "D", "contribution": 0.05, "part": 2.0},
    ]
    texte = R.texte_par_groupe_categorie("test", contributions, seuil_choc=3.0, variations={"D": 7.5})
    assert "A" in texte
    assert "D" in texte and "7.50" in texte


def test_note_technique_absente_si_coherent():
    assert R.note_technique_coherence(True, 0.01) is None


def test_note_technique_presente_si_ecart():
    note = R.note_technique_coherence(False, 0.42)
    assert note is not None and "0.42" in note


def test_annexe_est_statique():
    """L'annexe ne doit dépendre d'aucune donnée : deux appels identiques."""
    assert R.contenu_annexe_methodologique() == R.contenu_annexe_methodologique()
    annexe = R.contenu_annexe_methodologique()
    assert {"glossaire", "perimetres", "avertissement"} <= set(annexe)
    assert any(terme == "pp" for terme, _ in annexe["glossaire"])


def test_aucun_texte_narratif_code_en_dur():
    """Les gabarits viennent tous du fichier de règles."""
    assert "gabarits" in R.REGLES
    for bloc in ("ipc_global", "core_noncore", "contributions", "par_groupe"):
        assert bloc in R.GABARITS


# ---------------------------------------------------------------------------
# Fonctions de calcul ajoutées pour le rapport
# ---------------------------------------------------------------------------


@besoin_donnees
def test_statistiques_historiques():
    stats = calc.calculer_statistiques_historiques(None, "Grand_Alger", "Inflation (%, yoy)")
    assert set(stats) == {"moyenne", "ecart_type", "min", "max", "nb_observations"}
    assert stats["nb_observations"] > 0
    assert stats["min"] <= stats["moyenne"] <= stats["max"]


@besoin_donnees
def test_statistiques_post_2015_restreint_la_fenetre():
    tout = calc.calculer_statistiques_historiques(None, "Grand_Alger", "Inflation (%, yoy)")
    recent = calc.calculer_statistiques_historiques(
        None, "Grand_Alger", "Inflation (%, yoy)", periode_reference="post_2015"
    )
    assert recent["nb_observations"] < tout["nb_observations"]


@besoin_donnees
def test_moyenne_ytd():
    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    moyenne = calc.calculer_moyenne_ytd(None, "Grand_Alger", "Inflation (%, yoy)", date_max.year)
    assert moyenne is not None


@besoin_donnees
def test_moyenne_ytd_annee_absente():
    assert calc.calculer_moyenne_ytd(None, "Grand_Alger", "Inflation (%, yoy)", 1980) is None


@besoin_donnees
def test_top_contributeurs():
    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    positifs, negatifs = calc.identifier_top_contributeurs(None, "Grand_Alger", date_max, mode="yoy", n=3)
    assert len(positifs) <= 3 and len(negatifs) <= 3
    for fiche in positifs + negatifs:
        assert {"nom", "contribution", "part"} == set(fiche)
        # La part est une fraction de la masse : toujours bornée
        assert fiche["part"] is None or 0 <= fiche["part"] <= 100
    # Tri par valeur absolue décroissante
    valeurs = [abs(p["contribution"]) for p in positifs]
    assert valeurs == sorted(valeurs, reverse=True)


@besoin_donnees
def test_top_contributeurs_mode_invalide():
    with pytest.raises(ValueError):
        calc.identifier_top_contributeurs(None, "Grand_Alger", "2025-07-01", mode="trimestre")


@besoin_donnees
def test_coherence_des_contributions():
    """La somme des contributions doit reconstituer l'inflation du panier."""
    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    for mode in ("mom", "yoy"):
        coherent, ecart = calc.verifier_coherence_contributions(None, "Grand_Alger", date_max, mode)
        assert coherent, "écart de %.3f pp en %s" % (ecart, mode)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@besoin_donnees
def test_construire_contexte_rapport():
    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    contexte = R.construire_contexte_rapport(date_max.strftime("%Y-%m-%d"))

    assert set(contexte["paniers"]) == {
        "grand_alger",
        "national",
        "categories",
        "core",
        "non_core",
        "core2",
        "reglementes",
        "fci",
    }
    for panier in contexte["paniers"].values():
        assert "mom" in panier["mesures"] and "yoy" in panier["mesures"]

    national = contexte["paniers"]["national"]["mesures"]["yoy"]
    # precedente est reconstituée : valeur - delta
    assert abs((national["precedente"] + national["delta"]) - national["valeur"]) < 0.01


@besoin_donnees
def test_redaction_complete():
    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    contexte = R.construire_contexte_rapport(date_max.strftime("%Y-%m-%d"))
    textes = R._rediger(contexte)
    for cle in ("synthese_yoy", "focus_sous_jacentes_yoy", "contributions_national"):
        assert textes[cle] and len(textes[cle]) > 40


@besoin_donnees
def test_generation_du_document(tmp_path):
    """
    Le document est produit : PDF si WeasyPrint ou un navigateur est
    disponible, HTML en dernier recours.

    Le contrôle de contenu diffère selon le format : dans un PDF le texte est
    compressé, on vérifie donc la signature et la pagination plutôt que des
    chaînes lisibles.
    """
    import re

    date_max = calc.get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger")
    sortie = str(tmp_path / "rapport.pdf")
    try:
        chemin = R.generer_rapport_pdf(date_max.strftime("%Y-%m-%d"), sortie)
    except R.RenduPdfIndisponible as err:
        chemin = err.chemin_html

    assert os.path.exists(chemin) and os.path.getsize(chemin) > 5000
    contenu = open(chemin, "rb").read()

    if chemin.endswith(".pdf"):
        assert contenu.startswith(b"%PDF-")
        # Couverture, synthèse, trois sections et annexe : au moins 5 pages.
        assert len(re.findall(rb"/Type\s*/Page[^s]", contenu)) >= 5
    else:
        assert b"Synth" in contenu  # la synthèse exécutive est bien présente
