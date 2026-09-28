"""
Rapport PDF (moteur ReportLab) : génération complète et ouverture du PDF,
repli propre si l'export des graphiques échoue, absence de texte éditorial
codé en dur dans reporting.py.
"""

import ast
import os

import pytest

from config.settings import FICHIER_DONNEES_CALCULS

pymupdf = pytest.importorskip("pymupdf")
from backend.inflation import reporting as R  # noqa: E402

donnees = pytest.mark.skipif(
    not os.path.exists(FICHIER_DONNEES_CALCULS), reason="fichier de calculs absent (lancer pipeline_global)"
)


def _date_max():
    from backend.inflation.calculator import get_max_date

    return get_max_date(str(FICHIER_DONNEES_CALCULS), "Grand_Alger").strftime("%Y-%m-%d")


@donnees
def test_rapport_inflation_complet(tmp_path):
    chemin = R.generer_rapport_pdf(_date_max(), str(tmp_path / "r.pdf"))
    doc = pymupdf.open(chemin)
    texte = "\n".join(p.get_text() for p in doc)
    assert doc.page_count >= 10
    assert doc[0].get_images(), "logo absent de la couverture"
    assert sum(len(p.get_images()) for p in doc) >= 6, "graphiques absents"
    structure = R.STRUCTURE_INFLATION
    for titre, _chapeau in structure["sections"].values():
        assert titre in texte
    assert "page 2 / %d" % doc.page_count in texte
    assert "%" in texte and "pt" in texte  # KPI


@donnees
def test_rapport_se_genere_meme_si_export_image_echoue(tmp_path, monkeypatch):
    import plotly.graph_objects as go

    def _echec(*_a, **_k):
        raise RuntimeError("export d'image impossible")

    monkeypatch.setattr(go.Figure, "write_image", _echec)
    for f in os.listdir(os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs", "graphes")):
        if f.endswith(".png"):
            os.remove(os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs", "graphes", f))
    chemin = R.generer_rapport_pdf(_date_max(), str(tmp_path / "r.pdf"))
    texte = "\n".join(p.get_text() for p in pymupdf.open(chemin))
    assert "Graphique indisponible" in texte


def test_rapport_pib_complet(tmp_path):
    from config.settings import FICHIER_PIB_OFFRE

    if not os.path.exists(FICHIER_PIB_OFFRE):
        pytest.skip("fichiers PIB absents")
    chemin = R.generer_rapport_pib_pdf(None, str(tmp_path / "p.pdf"))
    doc = pymupdf.open(chemin)
    texte = "\n".join(p.get_text() for p in doc)
    assert doc.page_count >= 5
    for titre, _c in R.REGLES_PIB["structure"]["sections"].values():
        assert titre in texte


def test_aucun_texte_editorial_code_en_dur():
    """Les phrases longues de reporting.py (hors docstrings) doivent venir de narrative_rules.json."""
    source = open(R.__file__, encoding="utf-8").read()
    arbre = ast.parse(source)
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    phrases = [
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in docstrings
        and len(n.value) > 60
        and n.value.count(" ") > 8
    ]
    assert not phrases, phrases
