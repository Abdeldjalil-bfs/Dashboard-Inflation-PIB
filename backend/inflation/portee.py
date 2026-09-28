"""
Résolution de la portée géographique : UN seul endroit décide, pour
« Grand Alger » ou « National », quelles feuilles, séries, fonctions de
tracé et titres utiliser. Les pages ne choisissent plus rien elles-mêmes :
c'est ce qui laissait passer des séries Grand Alger en portée National.

Rappel des données (voir docs/AUDIT_GLOBAL.md) : la décomposition core /
non-core (feuilles `categories`, `core`, `Produits_agricoles_frais`) décrit
le panier Grand Alger. Au niveau national, les séries disponibles sont
l'indice global, les huit groupes, la sous-jacente 2, les produits
réglementés et le fort contenu d'import.
"""

from config.settings import (
    FICHIER_DONNEES_CALCULS,
    FEUILLE_GRAND_ALGER,
    FEUILLE_NATIONAL,
    FEUILLE_CORE,
    FEUILLE_NON_CORE,
    FEUILLE_CATEGORIES,
    FEUILLE_NATIONAL_CORE2,
    FEUILLE_NATIONAL_REGLEMENTES,
    FEUILLE_NATIONAL_FCI,
)

PORTEES = ("Grand Alger", "National")
NOTE_NATIONAL = (
    "La décomposition core / non-core n'est publiée que pour le panier "
    "Grand Alger : en portée National, les contributions sont celles des "
    "huit groupes du panier national."
)


def _suffixe(mode):
    return " — glissement annuel" if mode == "yoy" else " — glissement mensuel"


def scope_vue_ensemble(portee: str, mode: str) -> dict:
    """
    Tout ce dont la vue d'ensemble a besoin pour une portée et un mode.
    Les fonctions de tracé sont renvoyées prêtes à appeler avec
    (date_debut, date_fin) : aucune feuille n'est choisie dans la page.
    """
    from backend.inflation import visualizer as viz

    if portee not in PORTEES:
        raise ValueError("Portée inconnue : %s" % portee)
    fichier = str(FICHIER_DONNEES_CALCULS)
    annuel = mode == "yoy"

    if portee == "Grand Alger":
        tracer_evol = viz.tracer_inflation_dashboard_yoy if annuel else viz.tracer_inflation_dashboard_mom
        tracer_contrib = (
            viz.tracer_contributions_core_noncore_yoy if annuel else viz.tracer_contributions_core_noncore_mom
        )
        return {
            "cle": "grand_alger_" + mode,
            "portee": portee,
            "feuille_globale": FEUILLE_GRAND_ALGER,
            "kpi": [
                ("Indice global · Grand Alger", FEUILLE_GRAND_ALGER),
                ("Core · Grand Alger", FEUILLE_CORE),
                ("Non-core · Grand Alger", FEUILLE_NON_CORE),
            ],
            "tracer_evolution": lambda d, f: tracer_evol(
                nom_fichier=fichier,
                feuille_categories=FEUILLE_GRAND_ALGER,
                feuille_core=FEUILLE_CORE,
                feuille_non_core=FEUILLE_NON_CORE,
                date_debut=d,
                date_fin=f,
                export_png=False,
            ),
            "titre_evolution": "Inflation de l'indice global, du core et du non-core · Grand Alger" + _suffixe(mode),
            "tracer_contributions": lambda d, f: tracer_contrib(
                nom_fichier=fichier, feuille_categories=FEUILLE_CATEGORIES, date_debut=d, date_fin=f, export_png=False
            ),
            "titre_contributions": "Contribution du core et du non-core · Grand Alger" + _suffixe(mode),
            "note": None,
        }

    tracer_evol = viz.tracer_indices_complementaires_yoy if annuel else viz.tracer_indices_complementaires_mom
    tracer_contrib = (
        viz.tracer_inflation_contributions_national_yoy if annuel else viz.tracer_inflation_contributions_national_mom
    )
    return {
        "cle": "national_" + mode,
        "portee": portee,
        "feuille_globale": FEUILLE_NATIONAL,
        "kpi": [
            ("Indice global · National", FEUILLE_NATIONAL),
            ("Sous-jacente 2 · National", FEUILLE_NATIONAL_CORE2),
            ("Produits réglementés · National", FEUILLE_NATIONAL_REGLEMENTES),
        ],
        "tracer_evolution": lambda d, f: tracer_evol(
            nom_fichier=fichier,
            feuille_national=FEUILLE_NATIONAL,
            feuille_reglementes=FEUILLE_NATIONAL_REGLEMENTES,
            feuille_fci=FEUILLE_NATIONAL_FCI,
            feuille_core2=FEUILLE_NATIONAL_CORE2,
            date_debut=d,
            date_fin=f,
            export_png=False,
        ),
        "titre_evolution": "Inflation nationale : indice global, sous-jacente 2, réglementés, "
        "fort contenu d'import" + _suffixe(mode),
        "tracer_contributions": lambda d, f: tracer_contrib(fichier, d, f, export_png=False),
        "titre_contributions": "Contribution des huit groupes à l'indice national" + _suffixe(mode),
        "note": NOTE_NATIONAL,
    }
