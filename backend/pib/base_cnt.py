"""
Lecture de la base CNT (vue cnt_pib_derniere) pour le tableau de bord.

Seul point de lecture de la base côté analyse : les pages et l'accueil ne
font jamais de SQL. Chaque observation affichée est la dernière version
publiée (dernier millésime), le « millésime 0 » (classeurs ONS) servant de
socle historique — voir docs/AUDIT_GLOBAL.md.
"""

import sqlite3

import pandas as pd

from backend.pib import ons_cnt

# Libellé du PIB total, identique dans les classeurs ONS et les PDF CNT
# (normalize_label d'ons_cnt).
POSTE_PIB = "Produit Intérieur Brut"

# Millésime 0 : les classeurs ONS (PIB_TR_S / PIB_TR_D) chargés en base comme
# le plus ancien des rapports. « 0000T0 » précède tout rapport « AAAATn » dans
# l'ordre lexicographique : un rapport CNT ingéré prend donc toujours la main
# sur les trimestres qu'il couvre (vue cnt_pib_derniere).
RAPPORT_SOCLE = "0000T0"
LIBELLE_SOCLE = "Socle ONS (classeurs)"

BLOCS_OFFRE = ("Valeurs", "Croissance")
BLOCS_DEMANDE = ("Emplois_valeurs", "Emplois_croissance")


def libelle_rapport(rapport: str) -> str:
    """'2025T2' -> 'T2 2025' ; le millésime 0 a son libellé propre."""
    if rapport == RAPPORT_SOCLE:
        return LIBELLE_SOCLE
    annee, trimestre = str(rapport).split("T")
    return "T%s %s" % (trimestre, annee)


def _tidy(df_niveaux: pd.DataFrame, cles: list, bloc_valeurs: str, bloc_croissance: str) -> pd.DataFrame:
    """Nominal (millions DA) et croissance réelle t/t−4 (%) au format tidy de cnt_pib."""
    lignes = []
    for cle in cles:
        poste = POSTE_PIB if cle == "PIB" else cle
        nominal = df_niveaux[cle + "_nominal"]
        reel = df_niveaux[cle + "_reel"]
        croissance = (reel / reel.shift(4) - 1) * 100
        for bloc, serie, unite in ((bloc_valeurs, nominal, "Millions DA"), (bloc_croissance, croissance, "%")):
            for date, valeur in serie.dropna().items():
                trimestre = "T%d" % ((date.month - 1) // 3 + 1)
                lignes.append(
                    {
                        "rapport": RAPPORT_SOCLE,
                        "bloc": bloc,
                        "poste": poste,
                        "annee": date.year,
                        "trimestre": trimestre,
                        "periode": "%d-%s" % (date.year, trimestre),
                        "periodicite": "Trimestriel",
                        "valeur": float(valeur),
                        "unite": unite,
                    }
                )
    return pd.DataFrame(lignes, columns=ons_cnt.TIDY_COLS)


def construire_socle(fichier_offre=None, fichier_demande=None, journal=None) -> pd.DataFrame:
    """
    Millésime 0 au format tidy, depuis les classeurs ONS (journal des saisies
    appliqué). La croissance t/t−4 est tirée des volumes du classeur : la
    re-chaîner redonne exactement ces volumes (test de non-régression).
    """
    from backend.pib.calculator import charger_offre, charger_demande, _config_pib

    config = _config_pib()
    offre = charger_offre(fichier_offre, journal=journal)
    demande = charger_demande(fichier_demande, journal=journal)
    cles_offre = [s["cle"] for s in config["secteurs_offre"]] + [config["impots_nets_produits"]["cle"], "PIB"]
    cles_demande = [p["cle"] for p in config["postes_demande"]] + ["PIB"]
    return pd.concat(
        [_tidy(offre, cles_offre, *BLOCS_OFFRE), _tidy(demande, cles_demande, *BLOCS_DEMANDE)], ignore_index=True
    )


def reconstruire_socle(conn: sqlite3.Connection = None, **sources) -> int:
    """(Ré)injecte le millésime 0 (atomique, idempotent). Renvoie le nombre de lignes."""
    fermer = conn is None
    conn = conn or ons_cnt.ouvrir_base()
    try:
        return ons_cnt.injecter_en_base(conn, construire_socle(**sources))
    finally:
        if fermer:
            conn.close()


def assurer_socle(conn: sqlite3.Connection) -> bool:
    """Injecte le millésime 0 s'il manque (premier lancement). True s'il a été créé."""
    present = conn.execute("SELECT 1 FROM cnt_imports WHERE rapport = ?", (RAPPORT_SOCLE,)).fetchone()
    if present:
        return False
    reconstruire_socle(conn)
    return True


def _correspondance() -> dict:
    """Libellé CNT -> clé canonique (pib_config.json), identité pour les clés elles-mêmes."""
    from backend.pib.calculator import _config_pib

    config = _config_pib()
    table = dict(config.get("correspondance_cnt", {}))
    table[POSTE_PIB] = "PIB"
    return table


def _chainer(nominal: pd.Series, croissance: pd.Series) -> pd.Series:
    """
    Volume chaîné reconstruit à partir des taux t/t−4 : l'année de référence
    (les quatre premiers trimestres connus) vaut le nominal, puis
    V(t) = V(t−4) × (1 + g(t)/100) — la construction de PIB_R par l'ONS.
    """
    index = nominal.dropna().index.union(croissance.dropna().index).sort_values()
    volume = pd.Series(index=index, dtype=float)
    for rang, date in enumerate(index):
        if rang < 4:
            volume[date] = nominal.get(date, float("nan"))
            continue
        precedente = date - pd.DateOffset(years=1)
        g = croissance.get(date)
        if precedente in volume.index and pd.notna(volume[precedente]) and g is not None and pd.notna(g):
            volume[date] = volume[precedente] * (1 + g / 100)
    return volume


def charger_depuis_base(conn: sqlite3.Connection = None) -> tuple:
    """
    (offre, demande) au schéma canonique de backend.pib.lecture_ons, lus
    dans cnt_pib_derniere : nominal tel quel, volumes reconstruits par
    chaînage des taux t/t−4. Les postes CNT non reconnus par la table de
    correspondance sont ignorés par l'analyse (visibles dans la page Séries).
    """
    from backend.pib.calculator import _config_pib

    fermer = conn is None
    conn = conn or ons_cnt.ouvrir_base()
    try:
        assurer_socle(conn)
        df = lire_derniere(conn)
    finally:
        if fermer:
            conn.close()
    table = _correspondance()
    df = df.assign(cle=df["poste"].map(lambda p: table.get(p, p)))
    config = _config_pib()
    cles_offre = [s["cle"] for s in config["secteurs_offre"]] + [config["impots_nets_produits"]["cle"], "PIB"]
    cles_demande = [p["cle"] for p in config["postes_demande"]] + ["PIB"]

    def cadre(cles, bloc_valeurs, bloc_croissance):
        colonnes = {}
        for cle in cles:
            nominal = serie(df.assign(poste=df["cle"]), bloc_valeurs, cle)
            croissance = serie(df.assign(poste=df["cle"]), bloc_croissance, cle)
            colonnes[cle + "_nominal"] = nominal
            colonnes[cle + "_reel"] = _chainer(nominal, croissance)
        return pd.DataFrame(colonnes).sort_index()

    return cadre(cles_offre, *BLOCS_OFFRE), cadre(cles_demande, *BLOCS_DEMANDE)


def lire_derniere(conn: sqlite3.Connection = None, bloc: str = None) -> pd.DataFrame:
    """Observations trimestrielles de cnt_pib_derniere (tout ou un bloc)."""
    fermer = conn is None
    conn = conn or ons_cnt.ouvrir_base()
    try:
        requete = "SELECT * FROM cnt_pib_derniere WHERE periodicite = 'Trimestriel'"
        params = ()
        if bloc:
            requete += " AND bloc = ?"
            params = (bloc,)
        return pd.read_sql_query(requete, conn, params=params)
    finally:
        if fermer:
            conn.close()


def date_trimestre(annee, trimestre) -> pd.Timestamp:
    """Premier jour du dernier mois du trimestre (convention des classeurs ONS)."""
    return pd.Timestamp(year=int(annee), month=3 * int(str(trimestre)[-1]), day=1)


def serie(df: pd.DataFrame, bloc: str, poste: str) -> pd.Series:
    """Série d'un poste d'un bloc, indexée par trimestre."""
    sel = df[(df["bloc"] == bloc) & (df["poste"] == poste)]
    if sel.empty:
        return pd.Series(dtype=float)
    index = [date_trimestre(a, t) for a, t in zip(sel["annee"], sel["trimestre"])]
    return pd.Series(sel["valeur"].to_numpy(dtype=float), index=index).sort_index()


def derniere_croissance_pib(conn: sqlite3.Connection = None):
    """
    Dernier taux de croissance réel (t/t−4, %) du PIB en base, son écart au
    trimestre précédent et la date. None si la base est vide.
    """
    croissance = serie(lire_derniere(conn, "Croissance"), "Croissance", POSTE_PIB).dropna()
    if croissance.empty:
        return None
    date = croissance.index.max()
    valeur = float(croissance.iloc[-1])
    delta = float(croissance.iloc[-1] - croissance.iloc[-2]) if len(croissance) > 1 else None
    return {"valeur": valeur, "delta": delta, "date": date}


def controle_postes(tidy: pd.DataFrame) -> dict:
    """
    Contrôle qualité complémentaire de l'ingestion : postes extraits du PDF
    que la table de correspondance (pib_config.json) ne sait pas rattacher
    aux clés d'analyse. AVERTISSEMENT : ils sont stockés (page Séries) mais
    n'entrent pas dans les calculs ; rien n'est rattaché au hasard.
    """
    from backend.pib.calculator import _config_pib

    config = _config_pib()
    connus = (
        set(_correspondance())
        | {s["cle"] for s in config["secteurs_offre"]}
        | {p["cle"] for p in config["postes_demande"]}
        | {config["impots_nets_produits"]["cle"]}
    )
    inconnus = sorted(set(tidy["poste"]) - connus)
    if not inconnus:
        return {"Niveau": "OK", "Contrôle": "Postes reconnus pour l'analyse", "Détail": "tous les postes"}
    exemples = ", ".join(inconnus[:4]) + (" …" if len(inconnus) > 4 else "")
    return {
        "Niveau": "AVERTISSEMENT",
        "Contrôle": "Postes reconnus pour l'analyse",
        "Détail": "%d poste(s) hors table de correspondance : %s" % (len(inconnus), exemples),
    }


def prochain_rapport_attendu(conn: sqlite3.Connection):
    """
    (année, trimestre) du prochain rapport CNT à rechercher : celui qui suit
    le dernier rapport ingéré, ou, sans rapport ingéré, le trimestre qui suit
    le dernier PIB connu du socle. None si la base est vide.
    """
    ligne = conn.execute("SELECT MAX(rapport) FROM cnt_imports WHERE rapport <> ?", (RAPPORT_SOCLE,)).fetchone()
    if ligne and ligne[0]:
        annee, trimestre = ligne[0].split("T")
        return ons_cnt.trimestre_suivant(int(annee), int(trimestre))
    croissance = serie(lire_derniere(conn), "Emplois_croissance", POSTE_PIB).dropna()
    if croissance.empty:
        croissance = serie(lire_derniere(conn), "Croissance", POSTE_PIB).dropna()
    if croissance.empty:
        return None
    date = croissance.index.max()
    return ons_cnt.trimestre_suivant(date.year, (date.month - 1) // 3 + 1)
