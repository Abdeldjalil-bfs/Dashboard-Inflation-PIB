"""
ons_cnt.py : Extraction des Comptes Nationaux Trimestriels (CNT) de l'ONS.

Fonctions principales (utilisables depuis Streamlit ou en script) :
    traiter(annee, trimestre)            -> Resultat (tidy, contrôles, Excel en mémoire)
    comparer_avec_base(conn, tidy)       -> écarts (révisions) vs. millésimes déjà en base
    injecter_en_base(conn, tidy)         -> écrit dans SQLite (idempotent par rapport)

Intégré au projet sans modification fonctionnelle de l'extraction (regex,
lecture des tableaux, format tidy, contrôles). Changements d'intégration,
détaillés dans docs/AUDIT_INGESTION_CNT.md :
  - chemin de base, URL, délai et vérification SSL lus dans config/settings.py ;
  - avertissements urllib3 coupés seulement si la vérification SSL l'est ;
  - erreurs réseau converties en ONSInjoignable, extraction vide en
    ExtractionVide (sous-classe de RuntimeError, comme avant) ;
  - to_excel(..., sheet_name=...) : le passage positionnel échoue sous pandas 3 ;
  - injection réellement atomique : to_sql validait sa propre transaction,
    remplacé par executemany dans le bloc `with conn:` ;
  - fonctions d'appui à la page (historique des imports, détection d'un
    nouveau rapport, trimestre par défaut).
"""

from __future__ import annotations

import io
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pdfplumber
import requests
import urllib3

from config.settings import (
    CNT_DB_PATH,
    ONS_CNT_URL_TEMPLATE,
    ONS_CNT_VERIFY_SSL,
    ONS_CNT_TIMEOUT,
)

URL_TEMPLATE = ONS_CNT_URL_TEMPLATE
VERIFY_SSL = ONS_CNT_VERIFY_SSL

if not VERIFY_SSL:
    # Uniquement si la vérification est désactivée : sinon ces avertissements
    # sont utiles et ne doivent pas être masqués pour tout le processus.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ENTETES_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
}

# ------------------------------------------------------------------
# Regex (inchangées)
# ------------------------------------------------------------------
YEAR_LINE_RE = re.compile(r"^(?:20\d{2}\s*)+$")
TOKEN_RE = re.compile(r"T[1-4]|année")
NUM_RE = re.compile(r"-?\d[\d\s]*,\d+")
PAGE_NUM_RE = re.compile(r"^\d+$")

VALUE_TITLE_AGG_RE = re.compile(r"Produit Intérieur Brut trimestriel par grands secteurs")
VALUE_TITLE_DETAILED_RE = re.compile(r"^Produit Intérieur Brut trimestriel aux prix courants")
GROWTH_TITLE_DETAILED_RE = re.compile(r"^Taux de croissance des valeurs ajoutées aux prix de l'année précédente cha")
GROWTH_TITLE_AGG_RE = re.compile(r"Taux de croissance des valeurs ajoutées par grands secteurs.*chaînés")
EQUILIBRE_VALUE_RE = re.compile(r"^Equilibre Ressources-Emplois")
EQUILIBRE_GROWTH_RE = re.compile(r"^Taux de croissance aux prix de l'année précédente cha")

# Les 4 blocs : ordre des regex = ordre de priorité à la fusion (comme avant)
BLOCS = {
    "Valeurs": {
        "titres": [VALUE_TITLE_AGG_RE, VALUE_TITLE_DETAILED_RE],
        "unite": "Millions DA",
        "description": "PIB et valeurs ajoutées par secteur/branche, prix courants",
    },
    "Croissance": {
        "titres": [GROWTH_TITLE_DETAILED_RE, GROWTH_TITLE_AGG_RE],
        "unite": "%",
        "description": "Croissance des valeurs ajoutées, prix de l'année précédente chaînés (t/t-4)",
    },
    "Emplois_valeurs": {
        "titres": [EQUILIBRE_VALUE_RE],
        "unite": "Millions DA",
        "description": "Équilibre Ressources-Emplois, prix courants",
    },
    "Emplois_croissance": {
        "titres": [EQUILIBRE_GROWTH_RE],
        "unite": "%",
        "description": "Équilibre Ressources-Emplois, croissance prix chaînés (t/t-4)",
    },
}


class CNTIntrouvable(Exception):
    """Le rapport demandé n'est pas (encore) publié sur ons.dz."""


class ONSInjoignable(Exception):
    """ons.dz ne répond pas : réseau coupé, délai dépassé ou certificat refusé."""


class ExtractionVide(RuntimeError):
    """Le PDF a été téléchargé mais aucun tableau n'a pu en être extrait."""


# ------------------------------------------------------------------
# 1) Téléchargement en mémoire
# ------------------------------------------------------------------
def url_cnt(annee: int, trimestre: int) -> str:
    return URL_TEMPLATE.format(trimestre=trimestre, annee=annee)


def telecharger_pdf(annee: int, trimestre: int) -> bytes:
    url = url_cnt(annee, trimestre)
    try:
        r = requests.get(url, headers=_ENTETES_HTTP, timeout=ONS_CNT_TIMEOUT, verify=VERIFY_SSL)
    except requests.exceptions.SSLError as err:
        raise ONSInjoignable(f"Certificat de {url} refusé (vérification SSL active) : {err}") from err
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as err:
        raise ONSInjoignable(f"ons.dz injoignable ({url}) : {err}") from err
    if r.status_code == 404 or not r.content.startswith(b"%PDF"):
        raise CNTIntrouvable(
            f"Rapport CNT T{trimestre} {annee} introuvable sur ons.dz ({url}). Il n'est probablement pas encore publié."
        )
    r.raise_for_status()
    return r.content


def rapport_publie(annee: int, trimestre: int) -> bool:
    """
    Test léger (requête HEAD) de la présence du rapport sur ons.dz. Lève
    ONSInjoignable si le site ne répond pas : « pas publié » et « pas
    joignable » ne doivent pas se confondre.
    """
    url = url_cnt(annee, trimestre)
    try:
        r = requests.head(url, headers=_ENTETES_HTTP, timeout=30, verify=VERIFY_SSL, allow_redirects=True)
    except requests.exceptions.RequestException as err:
        raise ONSInjoignable(f"ons.dz injoignable ({url}) : {err}") from err
    type_contenu = r.headers.get("Content-Type", "")
    return r.status_code == 200 and "pdf" in type_contenu.lower()


# ------------------------------------------------------------------
# 2) Extraction (logique d'origine, sortie « long » avec colonne Valeur)
# ------------------------------------------------------------------
def clean_num(s: str) -> float:
    return float(s.replace("\xa0", " ").replace(" ", "").replace(",", "."))


def normalize_label(label: str) -> str:
    fixed = {
        "produit intérieur brut": "Produit Intérieur Brut",
        "produit intérieur brut hh": "Produit Intérieur Brut HH",
    }
    return fixed.get(label.lower(), label)


def extract_full_table(title_idx: int, lines: list[str], max_window: int = 80) -> pd.DataFrame:
    window_end = min(title_idx + max_window, len(lines))

    year_line_idx = None
    for i in range(title_idx + 1, min(title_idx + 6, len(lines))):
        if YEAR_LINE_RE.match(lines[i].strip()):
            year_line_idx = i
            break
    if year_line_idx is None:
        return pd.DataFrame()
    years = [int(y) for y in re.findall(r"20\d{2}", lines[year_line_idx])]

    header_idx = None
    for i in range(year_line_idx + 1, min(year_line_idx + 4, len(lines))):
        if "T1" in lines[i]:
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()
    tokens = TOKEN_RE.findall(lines[header_idx])

    col_map, yi = [], 0
    for t in tokens:
        col_map.append((years[yi] if yi < len(years) else None, t))
        if t == "année":
            yi += 1

    records = []
    for i in range(header_idx + 1, window_end):
        raw = lines[i].strip()
        if not raw or PAGE_NUM_RE.match(raw):
            break
        nums = NUM_RE.findall(raw)
        if not nums:
            break
        label = normalize_label(raw[: raw.find(nums[0])].strip())
        if not label:
            break
        for (year, quarter), val in zip(col_map, [clean_num(n) for n in nums]):
            records.append({"Année": year, "Trimestre": quarter, "Secteur": label, "Valeur": val})
    return pd.DataFrame(records)


def _collect(lines: list[str], title_re: re.Pattern) -> pd.DataFrame:
    idxs = [i for i, l in enumerate(lines) if title_re.search(l.strip())]
    if not idxs:
        return pd.DataFrame()
    df = pd.concat([extract_full_table(i, lines) for i in idxs], ignore_index=True)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["Année", "Trimestre", "Secteur"], keep="last")


def combine_long(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    dfs = [d for d in dfs if not d.empty]
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True).drop_duplicates(subset=["Année", "Trimestre", "Secteur"], keep="first")


def extraire_blocs(pdf_bytes: bytes) -> dict[str, pd.DataFrame]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    lines = text.split("\n")
    return {bloc: combine_long([_collect(lines, rx) for rx in cfg["titres"]]) for bloc, cfg in BLOCS.items()}


# ------------------------------------------------------------------
# 3) Format TIDY (une ligne = une observation)
# ------------------------------------------------------------------
TIDY_COLS = ["rapport", "bloc", "poste", "annee", "trimestre", "periode", "periodicite", "valeur", "unite"]


def build_tidy(blocs: dict[str, pd.DataFrame], annee: int, trimestre: int) -> pd.DataFrame:
    rapport = f"{annee}T{trimestre}"  # tri lexicographique = tri chronologique
    frames = []
    for bloc, df in blocs.items():
        if df.empty:
            continue
        d = pd.DataFrame(
            {
                "rapport": rapport,
                "bloc": bloc,
                "poste": df["Secteur"],
                "annee": df["Année"].astype(int),
                "trimestre": df["Trimestre"].replace({"année": "A"}),
                "valeur": df["Valeur"],
                "unite": BLOCS[bloc]["unite"],
            }
        )
        d["periodicite"] = np.where(d["trimestre"] == "A", "Annuel", "Trimestriel")
        d["periode"] = d["annee"].astype(str) + "-" + d["trimestre"]
        frames.append(d[TIDY_COLS])
    if not frames:
        return pd.DataFrame(columns=TIDY_COLS)
    return pd.concat(frames, ignore_index=True)


# ------------------------------------------------------------------
# 4) Contrôles qualité
# ------------------------------------------------------------------
def controler(tidy: pd.DataFrame, annee: int, trimestre: int) -> pd.DataFrame:
    res = []

    def add(niveau, controle, detail):
        res.append({"Niveau": niveau, "Contrôle": controle, "Détail": detail})

    # a) blocs présents
    for bloc in BLOCS:
        n = (tidy["bloc"] == bloc).sum()
        add(
            "OK" if n else "ERREUR",
            f"Tableau « {bloc} » trouvé",
            f"{n} observations, {tidy.loc[tidy.bloc == bloc, 'poste'].nunique()} postes"
            if n
            else "Aucune donnée extraite",
        )
    if tidy.empty:
        return pd.DataFrame(res)

    # b) doublons / valeurs manquantes
    cles = ["bloc", "poste", "annee", "trimestre"]
    nd = tidy.duplicated(cles).sum()
    add("OK" if nd == 0 else "ERREUR", "Aucun doublon", f"{nd} doublon(s)")
    nn = tidy["valeur"].isna().sum()
    add("OK" if nn == 0 else "ERREUR", "Aucune valeur manquante", f"{nn} manquante(s)")

    # c) dernière période = rapport demandé, et trimestres sans trou
    q = tidy[tidy.periodicite == "Trimestriel"][["annee", "trimestre"]].drop_duplicates()
    if q.empty:
        add("ERREUR", "Dernier trimestre = rapport demandé", "aucune donnée trimestrielle extraite")
    else:
        q["k"] = q["annee"] * 10 + q["trimestre"].str[1].astype(int)
        derniere = int(q["k"].max())
        attendu = annee * 10 + trimestre
        add(
            "OK" if derniere == attendu else "ERREUR",
            "Dernier trimestre = rapport demandé",
            f"dernier trimestre extrait : T{derniere % 10} {derniere // 10}",
        )
        debut = int(q["k"].min())
        tous = {
            a * 10 + t
            for a in range(debut // 10, derniere // 10 + 1)
            for t in range(1, 5)
            if debut <= a * 10 + t <= derniere
        }
        manquants = sorted(tous - set(q["k"]))
        add(
            "OK" if not manquants else "ERREUR",
            "Série trimestrielle continue",
            "aucun trou" if not manquants else f"manquants : {manquants}",
        )

    # d) somme des 4 trimestres = valeur annuelle (blocs en valeurs, années complètes)
    for bloc in ("Valeurs", "Emplois_valeurs"):
        t = tidy[tidy.bloc == bloc]
        if t.empty:
            continue
        qs = (
            t[t.periodicite == "Trimestriel"]
            .groupby(["poste", "annee"])["valeur"]
            .agg(somme="sum", n="size")
            .reset_index()
        )
        an = t[t.periodicite == "Annuel"][["poste", "annee", "valeur"]]
        m = qs[qs.n == 4].merge(an, on=["poste", "annee"])
        tol = np.maximum(0.5, 0.001 * m["valeur"].abs())
        bad = m[(m["somme"] - m["valeur"]).abs() > tol]
        add(
            "OK" if bad.empty else "AVERTISSEMENT",
            f"Σ trimestres = année ({bloc})",
            f"{len(m)} séries testées"
            if bad.empty
            else f"{len(bad)} écart(s), ex. : {bad.iloc[0]['poste']} {bad.iloc[0]['annee']}",
        )

    # e) valeurs aberrantes en croissance
    g = tidy[tidy.bloc.isin(["Croissance", "Emplois_croissance"]) & (tidy.valeur.abs() > 100)]
    add(
        "OK" if g.empty else "AVERTISSEMENT",
        "Croissances plausibles (|x| ≤ 100 %)",
        "RAS" if g.empty else f"{len(g)} valeur(s) > 100 % (peut être légitime pour de petits postes)",
    )
    return pd.DataFrame(res)


# ------------------------------------------------------------------
# 5) Excel téléchargeable
# ------------------------------------------------------------------
def nom_fichier(annee: int, trimestre: int) -> str:
    """Ex. ONS_CNT_2025T2_PIB.xlsx (année d'abord => tri alphabétique = tri chronologique)."""
    return f"ONS_CNT_{annee}T{trimestre}_PIB.xlsx"


def _wide(df_long: pd.DataFrame) -> pd.DataFrame:
    order = list(dict.fromkeys(df_long["Secteur"]))
    w = df_long.pivot_table(index=["Année", "Trimestre"], columns="Secteur", values="Valeur", aggfunc="first")[
        order
    ].reset_index()
    w["_t"] = w["Trimestre"].apply(lambda t: 5 if t == "année" else int(t[1]))
    return w.sort_values(["Année", "_t"]).drop(columns="_t").reset_index(drop=True)


def feuilles_larges(blocs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Les 8 feuilles d'origine (trimestriel / annuel pour chacun des 4 blocs)."""
    out = {}
    for bloc, df in blocs.items():
        if df.empty:
            continue
        w = _wide(df)
        out[f"{bloc}_trimestriel"] = w[w["Trimestre"] != "année"].reset_index(drop=True)
        out[f"{bloc}_annuel"] = w[w["Trimestre"] == "année"].drop(columns="Trimestre").reset_index(drop=True)
    return out


def construire_excel(tidy: pd.DataFrame, blocs: dict[str, pd.DataFrame], annee: int, trimestre: int) -> bytes:
    readme = pd.DataFrame(
        {
            "Rubrique": ["Source", "Rapport", "URL", "Extrait le", "Feuille « Tidy »", "Autres feuilles", "Unités"],
            "Valeur": [
                "Office National des Statistiques (ONS), Comptes Nationaux Trimestriels",
                f"T{trimestre} {annee}",
                url_cnt(annee, trimestre),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Format long : 1 ligne = 1 observation (rapport, bloc, poste, année, trimestre, valeur, unité)",
                "Vues larges (1 colonne par poste), trimestrielles et annuelles, par bloc",
                "Millions DA (valeurs) ; % variation t/t-4 (croissance)",
            ],
        }
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="Lisez-moi", index=False)
        tidy.to_excel(xw, sheet_name="Tidy", index=False)
        for nom, df in feuilles_larges(blocs).items():
            df.to_excel(xw, sheet_name=nom[:31], index=False)
        for ws in xw.book.worksheets:  # en-tête figé + largeurs
            ws.freeze_panes = "A2"
            for col in ws.columns:
                largeur = max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, largeur + 2), 60)
    return buf.getvalue()


# ------------------------------------------------------------------
# 6) Pipeline complet
# ------------------------------------------------------------------
@dataclass
class Resultat:
    annee: int
    trimestre: int
    url: str
    tidy: pd.DataFrame
    blocs: dict
    controles: pd.DataFrame
    excel: bytes
    nom_fichier: str

    @property
    def rapport(self) -> str:
        return f"{self.annee}T{self.trimestre}"

    @property
    def valide(self) -> bool:
        return not (self.controles["Niveau"] == "ERREUR").any()


def traiter_pdf(pdf: bytes, annee: int, trimestre: int) -> Resultat:
    """Extraction, contrôles et Excel à partir d'un PDF déjà en mémoire."""
    blocs = extraire_blocs(pdf)
    tidy = build_tidy(blocs, annee, trimestre)
    if tidy.empty:
        raise ExtractionVide("Aucun tableau n'a pu être extrait de ce PDF (mise en page modifiée ?).")
    ctrl = controler(tidy, annee, trimestre)
    return Resultat(
        annee,
        trimestre,
        url_cnt(annee, trimestre),
        tidy,
        blocs,
        ctrl,
        construire_excel(tidy, blocs, annee, trimestre),
        nom_fichier(annee, trimestre),
    )


def traiter(annee: int, trimestre: int) -> Resultat:
    return traiter_pdf(telecharger_pdf(annee, trimestre), annee, trimestre)


# ------------------------------------------------------------------
# 7) Base de données (SQLite) : millésimes conservés
# ------------------------------------------------------------------
DDL = """
CREATE TABLE IF NOT EXISTS cnt_pib (
    rapport TEXT, bloc TEXT, poste TEXT, annee INTEGER, trimestre TEXT,
    periode TEXT, periodicite TEXT, valeur REAL, unite TEXT,
    PRIMARY KEY (rapport, bloc, poste, annee, trimestre));
CREATE TABLE IF NOT EXISTS cnt_imports (
    rapport TEXT PRIMARY KEY, importe_le TEXT, nb_lignes INTEGER);
CREATE VIEW IF NOT EXISTS cnt_pib_derniere AS
    SELECT p.* FROM cnt_pib p JOIN (
        SELECT bloc, poste, annee, trimestre, MAX(rapport) AS r FROM cnt_pib
        GROUP BY bloc, poste, annee, trimestre) m
    ON p.bloc = m.bloc AND p.poste = m.poste AND p.annee = m.annee
       AND p.trimestre = m.trimestre AND p.rapport = m.r;
"""


def ouvrir_base(chemin=None) -> sqlite3.Connection:
    chemin = str(chemin or CNT_DB_PATH)
    conn = sqlite3.connect(chemin)
    conn.executescript(DDL)
    return conn


def comparer_avec_base(conn: sqlite3.Connection, tidy: pd.DataFrame) -> dict:
    """Compare le nouveau rapport au dernier millésime antérieur déjà en base."""
    rapport = tidy["rapport"].iloc[0]
    prev = pd.read_sql_query(
        """SELECT p.bloc, p.poste, p.annee, p.trimestre, p.valeur AS ancienne, p.rapport AS rapport_prec
           FROM cnt_pib p JOIN (
             SELECT bloc, poste, annee, trimestre, MAX(rapport) AS r FROM cnt_pib
             WHERE rapport < ? GROUP BY bloc, poste, annee, trimestre) m
           ON p.bloc=m.bloc AND p.poste=m.poste AND p.annee=m.annee
              AND p.trimestre=m.trimestre AND p.rapport=m.r""",
        conn,
        params=(rapport,),
    )
    deja = pd.read_sql_query("SELECT 1 FROM cnt_imports WHERE rapport = ?", conn, params=(rapport,))
    cles = ["bloc", "poste", "annee", "trimestre"]
    m = tidy.merge(prev, on=cles, how="left")
    nouvelles = m[m["ancienne"].isna()]
    revisees = m[m["ancienne"].notna() & ((m["valeur"] - m["ancienne"]).abs() > 1e-9)].copy()
    revisees["ecart"] = revisees["valeur"] - revisees["ancienne"]
    return {
        "deja_importe": not deja.empty,
        "nb_nouvelles": len(nouvelles),
        "nb_revisees": len(revisees),
        "revisees": revisees[["bloc", "poste", "periode", "rapport_prec", "ancienne", "valeur", "ecart"]].sort_values(
            "ecart", key=abs, ascending=False
        ),
    }


def _lignes_sql(tidy: pd.DataFrame) -> list[tuple]:
    """Lignes du tidy en types Python natifs (sqlite3 ne lie pas les numpy.int64)."""
    propre = tidy[TIDY_COLS].astype(object).where(tidy[TIDY_COLS].notna(), None)
    return [
        tuple(v.item() if hasattr(v, "item") else v for v in ligne)
        for ligne in propre.itertuples(index=False, name=None)
    ]


def injecter_en_base(conn: sqlite3.Connection, tidy: pd.DataFrame) -> int:
    """
    Idempotent : remplace le millésime s'il existe. DELETE, INSERT et mise à
    jour de cnt_imports dans UNE transaction : `to_sql` validait la sienne,
    si bien qu'une panne après l'insertion laissait l'ancien millésime
    supprimé et cnt_imports non mis à jour. executemany dans `with conn:`
    garantit tout ou rien.
    """
    rapport = tidy["rapport"].iloc[0]
    colonnes = ", ".join(TIDY_COLS)
    marques = ", ".join("?" for _ in TIDY_COLS)
    with conn:
        conn.execute("DELETE FROM cnt_pib WHERE rapport = ?", (rapport,))
        conn.executemany(f"INSERT INTO cnt_pib ({colonnes}) VALUES ({marques})", _lignes_sql(tidy))
        conn.execute(
            "INSERT OR REPLACE INTO cnt_imports VALUES (?, ?, ?)",
            (rapport, datetime.now().isoformat(timespec="seconds"), len(tidy)),
        )
    return len(tidy)


# ------------------------------------------------------------------
# 8) Appui à la page d'ingestion
# ------------------------------------------------------------------
def historique_imports(conn: sqlite3.Connection) -> pd.DataFrame:
    """Rapports déjà en base, du plus récent au plus ancien."""
    return pd.read_sql_query("SELECT rapport, importe_le, nb_lignes FROM cnt_imports ORDER BY rapport DESC", conn)


def date_import(conn: sqlite3.Connection, annee: int, trimestre: int):
    """Date de dernière importation du rapport, ou None."""
    ligne = conn.execute("SELECT importe_le FROM cnt_imports WHERE rapport = ?", (f"{annee}T{trimestre}",)).fetchone()
    return ligne[0] if ligne else None


def trimestre_suivant(annee: int, trimestre: int) -> tuple[int, int]:
    return (annee + 1, 1) if trimestre == 4 else (annee, trimestre + 1)


def dernier_importe(conn: sqlite3.Connection):
    """(année, trimestre) du rapport le plus récent en base, ou None."""
    ligne = conn.execute("SELECT MAX(rapport) FROM cnt_imports").fetchone()
    if not ligne or not ligne[0]:
        return None
    annee, trimestre = ligne[0].split("T")
    return int(annee), int(trimestre)


def _trimestre_precedent(annee: int, trimestre: int) -> tuple[int, int]:
    return (annee - 1, 4) if trimestre == 1 else (annee, trimestre - 1)


def trimestre_par_defaut(aujourd_hui: date = None, delai_jours: int = 120) -> tuple[int, int]:
    """
    Dernier trimestre plausiblement publié : le dernier trimestre ACHEVÉ à
    la date `aujourd_hui − delai_jours` (délai de publication des CNT).
    """
    reference = (aujourd_hui or date.today()) - timedelta(days=delai_jours)
    return _trimestre_precedent(reference.year, (reference.month - 1) // 3 + 1)
