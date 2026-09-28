"""
Tests de fumée des pages Streamlit (streamlit.testing.v1.AppTest) :
chargement sans exception une fois connecté, redirection sans
authentification, titres de graphiques renseignés.
"""

import glob
import os

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sorted(glob.glob(os.path.join(RACINE, "app", "pages", "*.py")))
INTERNES = [p for p in PAGES if not os.path.basename(p).startswith("00_")]


def _app(chemin, connecte=True, **etat):
    at = AppTest.from_file(chemin, default_timeout=120)
    if connecte:
        at.session_state["authenticated"] = True
        at.session_state["username"] = "test"
    for cle, valeur in etat.items():
        at.session_state[cle] = valeur
    return at


@pytest.mark.parametrize(
    "chemin", INTERNES + [os.path.join(RACINE, "app", "Home.py")], ids=lambda p: os.path.basename(p)
)
def test_page_se_charge_sans_exception(chemin):
    at = _app(chemin).run()
    assert not at.exception, [e.message for e in at.exception]
    assert not [e for e in at.error if "Traceback" in str(e.value)]


@pytest.mark.parametrize("chemin", INTERNES, ids=lambda p: os.path.basename(p))
def test_page_exige_authentification(chemin):
    at = _app(chemin, connecte=False).run()
    # require_auth redirige vers la connexion avant tout contenu : aucun
    # graphique ni titre de page n'est rendu.
    assert not at.get("plotly_chart")
    assert not [m for m in at.markdown if "ba-page-title" in str(m.value)]


def test_saisie_suit_le_module_actif():
    at = _app(os.path.join(RACINE, "app", "pages", "07_Saisie.py"), module_actif="PIB").run()
    assert not at.exception
    assert any("Journal des saisies PIB" in str(m.value) for m in at.markdown)


def _titres_graphiques(at):
    import json

    titres = []
    for g in at.get("plotly_chart"):
        spec = json.loads(g.proto.spec)
        titre = spec.get("layout", {}).get("title") or {}
        titres.append(titre.get("text") if isinstance(titre, dict) else titre)
    return titres


def _nb_titres_section(at):
    return sum(1 for m in at.markdown if "ba-section-text" in str(m.value))


@pytest.mark.parametrize("chemin", INTERNES, ids=lambda p: os.path.basename(p))
def test_titres_de_graphiques_renseignes(chemin):
    """
    Chaque graphique doit être identifiable : par son propre titre Plotly,
    ou par le titre de section (`titre_section()`) affiché juste au-dessus à
    l'écran. Cas des pages PIB : leur titre Plotly a été retiré pour ne pas
    chevaucher la légende horizontale (backend/pib/visualizer.py::_habiller).
    """
    at = _app(chemin).run()
    titres = _titres_graphiques(at)
    if not titres:
        return
    if all(t and str(t).strip() not in ("", "undefined", "None") for t in titres):
        return
    assert _nb_titres_section(at) >= len(titres), (chemin, titres)


def test_page_de_connexion(tmp_path, monkeypatch):
    """La page publique se charge et accepte un compte du fichier Excel en clair."""
    import pandas as pd

    fichier = tmp_path / "users.xlsx"
    pd.DataFrame({"username": ["essai"], "password": ["mot-de-passe"]}).to_excel(fichier, index=False)
    monkeypatch.setattr("config.settings.USERS_FILE", fichier)
    at = AppTest.from_file(os.path.join(RACINE, "app", "pages", "00_Connexion.py"), default_timeout=120).run()
    assert not at.exception, [e.message for e in at.exception]
    at.text_input(key="login_username").set_value("essai")
    at.text_input(key="login_password").set_value("mot-de-passe")
    at.button(key="btn_connexion").click().run()
    assert at.session_state["authenticated"] is True
    assert at.session_state["username"] == "essai"
