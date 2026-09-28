"""
Ingestion CNT : parcours complet sur PDF factice, idempotence, atomicité,
révisions entre millésimes, erreurs réseau. Aucun accès réseau réel.
"""

import io
import os
import sqlite3
import sys

import pandas as pd
import pytest
import requests

pytest.importorskip("pdfplumber")
pytest.importorskip("reportlab")

sys.path.insert(0, os.path.dirname(__file__))
from cnt_pdf_factice import pdf_cnt  # noqa: E402

from backend.pib import ons_cnt as O  # noqa: E402


@pytest.fixture
def base(tmp_path):
    conn = O.ouvrir_base(tmp_path / "test.db")
    yield conn
    conn.close()


def _resultat(annee=2025, trimestre=2, revision=0.0, **kw):
    return O.traiter_pdf(pdf_cnt(annee, trimestre, revision, **kw), annee, trimestre)


# ---------------------------------------------------------------------------
# Extraction, contrôles, Excel
# ---------------------------------------------------------------------------


def test_parcours_extraction_controles_excel():
    r = _resultat()
    assert r.rapport == "2025T2" and r.valide
    assert set(r.tidy["bloc"]) == set(O.BLOCS)
    assert list(r.tidy.columns) == O.TIDY_COLS
    assert r.nom_fichier == "ONS_CNT_2025T2_PIB.xlsx"
    feuilles = pd.ExcelFile(io.BytesIO(r.excel)).sheet_names
    assert feuilles[:2] == ["Lisez-moi", "Tidy"]
    assert "Valeurs_trimestriel" in feuilles and "Emplois_croissance_annuel" in feuilles


def test_bloc_manquant_est_une_erreur():
    r = _resultat(blocs=["Valeurs", "Croissance", "Emplois_valeurs"])
    assert not r.valide
    erreurs = r.controles[r.controles["Niveau"] == "ERREUR"]["Contrôle"].tolist()
    assert "Tableau « Emplois_croissance » trouvé" in erreurs


def test_mauvais_trimestre_est_une_erreur():
    r = O.traiter_pdf(pdf_cnt(2025, 2), 2025, 3)
    assert not r.valide


def test_extraction_vide():
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    c = canvas.Canvas(tampon)
    c.drawString(50, 700, "Document sans tableau")
    c.showPage()
    c.save()
    with pytest.raises(O.ExtractionVide):
        O.traiter_pdf(tampon.getvalue(), 2025, 2)


# ---------------------------------------------------------------------------
# Base : injection, idempotence, atomicité, révisions
# ---------------------------------------------------------------------------


def test_injection_et_reinjection_idempotente(base):
    r = _resultat()
    assert O.injecter_en_base(base, r.tidy) == len(r.tidy)
    assert O.injecter_en_base(base, r.tidy) == len(r.tidy)
    assert base.execute("SELECT COUNT(*) FROM cnt_pib").fetchone()[0] == len(r.tidy)
    assert O.historique_imports(base)["rapport"].tolist() == ["2025T2"]
    assert O.comparer_avec_base(base, r.tidy)["deja_importe"]


def test_atomicite_panne_apres_insertion(base):
    """Panne sur cnt_imports, APRÈS l'insertion : tout doit être annulé."""
    ancien = _resultat()
    O.injecter_en_base(base, ancien.tidy)
    avant = pd.read_sql_query("SELECT * FROM cnt_pib ORDER BY bloc, poste, annee, trimestre", base)
    base.execute("CREATE TRIGGER panne BEFORE INSERT ON cnt_imports BEGIN SELECT RAISE(ABORT, 'panne simulée'); END")
    nouveau = ancien.tidy.assign(valeur=ancien.tidy["valeur"] + 1)
    with pytest.raises(sqlite3.DatabaseError):
        O.injecter_en_base(base, nouveau)
    apres = pd.read_sql_query("SELECT * FROM cnt_pib ORDER BY bloc, poste, annee, trimestre", base)
    pd.testing.assert_frame_equal(avant, apres)


def test_atomicite_panne_pendant_insertion(base):
    """Doublon de clé au milieu de l'insertion : l'ancien millésime survit."""
    ancien = _resultat()
    O.injecter_en_base(base, ancien.tidy)
    casse = pd.concat([ancien.tidy, ancien.tidy.iloc[[0]]], ignore_index=True)
    with pytest.raises(sqlite3.IntegrityError):
        O.injecter_en_base(base, casse)
    assert base.execute("SELECT COUNT(*) FROM cnt_pib").fetchone()[0] == len(ancien.tidy)


def test_revisions_entre_deux_rapports(base):
    t1 = _resultat(2025, 1)
    O.injecter_en_base(base, t1.tidy)
    t2 = _resultat(2025, 2, revision=250.0)  # T4 2024 révisé de +250
    comp = O.comparer_avec_base(base, t2.tidy)
    assert not comp["deja_importe"]
    rev = comp["revisees"]
    valeurs = rev[rev["bloc"].isin(["Valeurs", "Emplois_valeurs"]) & (rev["periode"] == "2024-T4")]
    assert len(valeurs) == 8 and (valeurs["ecart"].round(1) == 250.0).all()
    assert (rev["rapport_prec"] == "2025T1").all()
    assert comp["nb_nouvelles"] > 0  # T2 2025 n'existait pas dans T1 2025
    # Tri par écart absolu décroissant
    assert rev["ecart"].abs().is_monotonic_decreasing
    # La vue fournit le dernier millésime
    O.injecter_en_base(base, t2.tidy)
    derniere = pd.read_sql_query(
        "SELECT rapport, valeur FROM cnt_pib_derniere WHERE bloc='Valeurs' "
        "AND poste='Agriculture' AND periode='2024-T4'",
        base,
    )
    assert derniere["rapport"].tolist() == ["2025T2"]


# ---------------------------------------------------------------------------
# Réseau (simulé)
# ---------------------------------------------------------------------------


class _Reponse:
    def __init__(self, status, contenu=b"", entetes=None):
        self.status_code, self.content, self.headers = status, contenu, entetes or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_rapport_inexistant(monkeypatch):
    monkeypatch.setattr(O.requests, "get", lambda *a, **k: _Reponse(404, b"<html>"))
    with pytest.raises(O.CNTIntrouvable):
        O.traiter(2031, 1)


def test_page_html_au_lieu_du_pdf(monkeypatch):
    monkeypatch.setattr(O.requests, "get", lambda *a, **k: _Reponse(200, b"<html>introuvable"))
    with pytest.raises(O.CNTIntrouvable):
        O.traiter(2031, 1)


@pytest.mark.parametrize(
    "erreur",
    [
        requests.exceptions.ConnectionError("hors ligne"),
        requests.exceptions.Timeout("délai"),
        requests.exceptions.SSLError("certificat"),
    ],
)
def test_sans_reseau(monkeypatch, erreur):
    def _leve(*a, **k):
        raise erreur

    monkeypatch.setattr(O.requests, "get", _leve)
    monkeypatch.setattr(O.requests, "head", _leve)
    with pytest.raises(O.ONSInjoignable):
        O.traiter(2025, 2)
    with pytest.raises(O.ONSInjoignable):
        O.rapport_publie(2025, 3)


def test_traiter_avec_pdf_telecharge(monkeypatch):
    monkeypatch.setattr(O.requests, "get", lambda *a, **k: _Reponse(200, pdf_cnt()))
    assert O.traiter(2025, 2).valide


def test_detection_nouveau_rapport(monkeypatch, base):
    O.injecter_en_base(base, _resultat(2025, 2).tidy)
    assert O.dernier_importe(base) == (2025, 2)
    assert O.trimestre_suivant(2025, 4) == (2026, 1)
    monkeypatch.setattr(
        O.requests,
        "head",
        lambda url, **k: (
            _Reponse(200, entetes={"Content-Type": "application/pdf"}) if "CNT3T2025" in url else _Reponse(404)
        ),
    )
    assert O.rapport_publie(*O.trimestre_suivant(*O.dernier_importe(base)))
    assert not O.rapport_publie(2025, 4)


def test_trimestre_par_defaut():
    from datetime import date

    assert O.trimestre_par_defaut(date(2026, 9, 28)) == (2026, 1)
    assert O.trimestre_par_defaut(date(2026, 1, 10)) == (2025, 2)


# ---------------------------------------------------------------------------
# Test réel (ons.dz) : exécuté seulement si ONS_CNT_TEST_RESEAU=1
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("ONS_CNT_TEST_RESEAU") != "1", reason="test réseau réel : définir ONS_CNT_TEST_RESEAU=1"
)
def test_reel_cnt_2025_t2():
    r = O.traiter(2025, 2)
    print(r.controles.to_string())
    assert set(r.tidy["bloc"]) == set(O.BLOCS)
    assert r.valide
