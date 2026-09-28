"""
Qualité des textes de l'interface : aucune date écrite en dur (elles doivent
venir des données ou de la date du jour), aucun texte provisoire, aucun
émoji dans les titres d'onglet.
"""

import ast
import glob
import json
import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANNEE = re.compile(r"\b(19|20)\d{2}\b")
# Noms propres contenant un millésime : norme comptable et espace de noms SVG.
EXCEPTIONS = re.compile(r"SCN 2008|w3\.org/2000")
PROVISOIRE = re.compile(r"bientôt disponible|en cours de développement|en préparation|TODO|lorem ipsum", re.IGNORECASE)
EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿]")


def _litteraux(chemin):
    """Chaînes littérales d'un module, hors docstrings et hors commentaires."""
    arbre = ast.parse(open(chemin, encoding="utf-8").read())
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    return [
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def _textes_interface():
    fichiers = glob.glob(os.path.join(RACINE, "app", "**", "*.py"), recursive=True)
    fichiers.append(os.path.join(RACINE, "config", "textes.py"))
    for chemin in fichiers:
        for texte in _litteraux(chemin):
            yield os.path.relpath(chemin, RACINE), texte
    for nom in ("narrative_rules.json", "pib_config.json", "anomaly_rules.json"):

        def parcourir(valeur):
            if isinstance(valeur, str):
                yield valeur
            elif isinstance(valeur, dict):
                for cle, v in valeur.items():
                    if not cle.startswith("periode_reference"):
                        yield from parcourir(v)
            elif isinstance(valeur, list):
                for v in valeur:
                    yield from parcourir(v)

        donnees = json.load(open(os.path.join(RACINE, "config", nom), encoding="utf-8"))
        for texte in parcourir(donnees):
            yield "config/" + nom, texte


def test_aucune_date_en_dur_dans_les_textes():
    fautes = [
        (f, t)
        for f, t in _textes_interface()
        if ANNEE.search(EXCEPTIONS.sub("", t)) and not t.startswith(("http", "%"))
    ]
    # Paramètres de période de référence (post_2015) exclus : ce sont des
    # réglages de calcul, pas des textes affichés.
    fautes = [(f, t) for f, t in fautes if not re.fullmatch(r"\d{4}-\d{2}", t)]
    assert not fautes, fautes


def test_aucun_texte_provisoire():
    fautes = [(f, t) for f, t in _textes_interface() if PROVISOIRE.search(t)]
    assert not fautes, fautes


def test_pas_d_emoji_dans_les_titres_d_onglet():
    from config.textes import LIBELLES_PAGES, MODULE_INFLATION, MODULE_PIB

    for libelle in list(LIBELLES_PAGES.values()) + [MODULE_INFLATION, MODULE_PIB]:
        assert not EMOJI.search(libelle), libelle
