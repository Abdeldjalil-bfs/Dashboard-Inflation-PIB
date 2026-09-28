"""
Sécurité : authentification par fichier Excel en clair (`data/users.xlsx`,
colonnes `username`/`password`, sans distinction de profil), accès aux pages
de saisie, journalisation.
"""

import os

import pandas as pd
import pytest


@pytest.fixture
def fichier(tmp_path):
    chemin = tmp_path / "users.xlsx"
    pd.DataFrame({"username": ["alice", "bob"], "password": ["secret1", "secret2"]}).to_excel(chemin, index=False)
    return chemin


def test_fichier_utilisateurs_format_attendu(fichier):
    df = pd.read_excel(fichier)
    assert list(df.columns) == ["username", "password"]
    assert df.loc[df["username"] == "alice", "password"].iloc[0] == "secret1"


def test_fichier_utilisateurs_hors_depot():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gitignore = open(os.path.join(racine, ".gitignore"), encoding="utf-8").read()
    assert "data/users.xlsx" in gitignore


def test_journal_ecrit(tmp_path, monkeypatch):
    import logging
    from backend.common import journal

    monkeypatch.setattr("config.settings.FICHIER_JOURNAL", tmp_path / "j.log")
    logging.getLogger("dashboard").handlers.clear()
    journal.evenement("connexion", "test", "alice")
    for h in logging.getLogger("dashboard").handlers:
        h.flush()
    assert "[connexion] test (utilisateur : alice)" in (tmp_path / "j.log").read_text(encoding="utf-8")
    logging.getLogger("dashboard").handlers.clear()


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _page(nom):
    from streamlit.testing.v1 import AppTest

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(racine, "app", "pages", nom), default_timeout=120)
    at.session_state["authenticated"] = True
    at.session_state["username"] = "test"
    return at.run()


def test_saisie_ouverte_a_tout_compte_authentifie():
    """Plus de distinction de profil : app.components.auth.est_admin() renvoie
    toujours True, tout compte connecté voit le bouton de recalcul."""
    at = _page("07_Saisie.py")
    assert not at.exception
    assert [b for b in at.button if b.key == "btn_recalcul"]
